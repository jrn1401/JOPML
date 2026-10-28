"""Fenster-Hilfen für Windows, macOS und Linux (aktives Fenster, Fensterliste, Fenster verschieben).
Alles best effort: Fehler ergeben None/[] bzw. einen Fehlertext, nie einen Absturz. Auf macOS braucht das Verschieben die
Berechtigung "Bedienungshilfen", auf Linux die Programme xdotool bzw. wmctrl."""
import shutil
import subprocess
import sys

WIN, MAC = sys.platform.startswith("win"), sys.platform == "darwin"
NO_WINDOW = 0x08000000 if WIN else 0        # CREATE_NO_WINDOW: Unter Windows blitzt sonst bei jedem Hilfsprogramm kurz ein Konsolenfenster auf


def _run(args: list[str], timeout: float = 3.0) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
    if r.returncode:
        raise OSError((r.stderr or r.stdout or "error").strip()[:200])
    return r.stdout.strip()


def _osa(script: str) -> str:
    return _run(["osascript", "-e", script])


def _win_pid(hwnd) -> int:
    import ctypes
    from ctypes import wintypes
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


# ---------------------------------------------------------------- Windows
def _win_proc(hwnd) -> str:
    import ctypes
    from ctypes import wintypes
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.replace("\\", "/").rsplit("/", 1)[-1]
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def _win_title(hwnd) -> str:
    import ctypes
    n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


# ---------------------------------------------------------------- Öffentliche Funktionen
def active_window() -> dict | None:
    """{"id", "title", "proc"} des Fensters im Vordergrund oder None."""
    try:
        if WIN:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            return {"id": int(hwnd), "title": _win_title(hwnd), "proc": _win_proc(hwnd), "pid": _win_pid(hwnd)} if hwnd else None
        if MAC:
            proc = _osa('tell application "System Events" to get name of first application process whose frontmost is true')
            try:
                title = _osa('tell application "System Events" to tell (first application process whose frontmost is true) to get name of front window')
            except OSError:
                title = ""
            return {"id": proc, "title": title, "proc": proc}
        if shutil.which("xdotool"):
            wid = _run(["xdotool", "getactivewindow"])
            return {"id": wid, "title": _run(["xdotool", "getwindowname", wid]), "proc": ""}
    except Exception:
        return None
    return None


def monitors() -> list[dict]:
    """Alle Monitore (nur Windows; sonst []): {"no": 1.., "work": (x, y, b, h) ohne Taskleiste, "full": (x, y, b, h), "primary": bool},
    von links nach rechts nummeriert (bei gleicher Lage von oben nach unten)."""
    if not WIN:
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        found: list[dict] = []
        cb_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

        def cb(hmon, _hdc, _rect, _l):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                m, w = mi.rcMonitor, mi.rcWork
                found.append({"full": (m.left, m.top, m.right - m.left, m.bottom - m.top),
                              "work": (w.left, w.top, w.right - w.left, w.bottom - w.top), "primary": bool(mi.dwFlags & 1)})
            return 1
        ctypes.windll.user32.EnumDisplayMonitors(None, None, cb_t(cb), 0)
        found.sort(key=lambda m: (m["full"][0], m["full"][1]))
        for i, m in enumerate(found, 1):
            m["no"] = i
        return found
    except Exception:
        return []


def window_rect(hwnd):
    """Sichtbarer Rahmen eines Fensters (links, oben, rechts, unten) ohne den unsichtbaren Schattenrand; nur Windows, sonst None."""
    if not WIN or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def _win_usable(hwnd) -> bool:
    """Echtes Programmfenster (nicht unsichtbar verdeckt wie UWP-Hüllen, kein Werkzeugfenster)?"""
    import ctypes
    from ctypes import wintypes
    cloaked = wintypes.DWORD()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
        return False
    style_ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    return not (style_ex & 0x80) or bool(style_ex & 0x40000)          # WS_EX_TOOLWINDOW nur mit WS_EX_APPWINDOW


def list_windows(detail: bool = False) -> list[dict]:
    """Sichtbare Fenster mit Titel. detail=True ergänzt "rect" (links, oben, rechts, unten) und "min" (minimiert) und lässt
    unsichtbare Hüllen und Werkzeugfenster weg (für das Speichern der Fensteranordnung)."""
    out: list[dict] = []
    try:
        if WIN:
            import ctypes
            from ctypes import wintypes
            cb_t = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

            def cb(hwnd, _l):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    t = _win_title(hwnd)
                    if t:
                        item = {"id": int(hwnd), "title": t, "proc": _win_proc(hwnd)}
                        if detail:
                            if not _win_usable(hwnd) or ctypes.windll.user32.IsIconic(hwnd):
                                return True
                            item["rect"] = window_rect(hwnd)
                            item["pid"] = _win_pid(hwnd)
                        out.append(item)
                return True
            ctypes.windll.user32.EnumWindows(cb_t(cb), 0)
        elif MAC:
            names = _osa('tell application "System Events" to get name of every application process whose visible is true')
            out = [{"id": n.strip(), "title": n.strip(), "proc": n.strip()} for n in names.split(",") if n.strip()]
        elif shutil.which("wmctrl"):
            for line in _run(["wmctrl", "-l"]).splitlines():
                parts = line.split(None, 3)
                if len(parts) == 4:
                    out.append({"id": parts[0], "title": parts[3], "proc": ""})
    except Exception:
        return []
    return out


def move_window(win_id, x: int, y: int, w: int, h: int) -> str:
    """Setzt Position und Größe. win_id None = aktives Fenster. Gibt '' oder einen Fehlertext zurück."""
    x, y, w, h = int(x), int(y), max(100, int(w)), max(80, int(h))
    try:
        if WIN:
            import ctypes
            hwnd = win_id or ctypes.windll.user32.GetForegroundWindow()
            u = ctypes.windll.user32
            if u.IsZoomed(hwnd) or u.IsIconic(hwnd):
                u.ShowWindow(hwnd, 9)                                  # SW_RESTORE (hebt Maximieren auf)
            u.SetWindowPos(hwnd, 0, x, y, w, h, 0x0014)                # NOZORDER | NOACTIVATE
            try:                                                       # unsichtbaren Rand (Schatten) von Windows 10/11 ausgleichen
                from ctypes import wintypes
                a, b = wintypes.RECT(), wintypes.RECT()
                u.GetWindowRect(hwnd, ctypes.byref(a))
                if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(b), ctypes.sizeof(b)) == 0:
                    l, t, r, bt = b.left - a.left, b.top - a.top, a.right - b.right, a.bottom - b.bottom
                    if any((l, t, r, bt)):
                        u.SetWindowPos(hwnd, 0, x - l, y - t, w + l + r, h + t + bt, 0x0014)
            except Exception:
                pass
            return ""
        if MAC:
            target = f'process "{win_id}"' if win_id else "(first application process whose frontmost is true)"
            _osa(f'tell application "System Events" to tell {target}\nset position of window 1 to {{{x}, {y}}}\nset size of window 1 to {{{w}, {h}}}\nend tell')
            return ""
        if shutil.which("wmctrl"):
            args = ["wmctrl", "-i", "-r", str(win_id)] if win_id else ["wmctrl", "-r", ":ACTIVE:"]
            _run(args + ["-e", f"0,{x},{y},{w},{h}"])
            return ""
        return "wmctrl is not installed."
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def is_rect_fullscreen(win: tuple, mon: tuple, tol: int = 2) -> bool:
    """Deckt das Fenster (links, oben, rechts, unten) den ganzen Monitor ab? (reine Rechnung, testbar)"""
    return win[0] <= mon[0] + tol and win[1] <= mon[1] + tol and win[2] >= mon[2] - tol and win[3] >= mon[3] - tol


def fullscreen_active() -> bool:
    """True, wenn gerade ein fremdes Programm den ganzen Bildschirm ausfüllt (Spiel, Film, Präsentation). Nur unter Windows; sonst False."""
    if not WIN:
        return False
    try:
        import ctypes
        import os
        from ctypes import wintypes
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if not hwnd or _win_pid(hwnd) == os.getpid():
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if cls.value in _SHELL_CLASSES:
            return False
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        mon = u.MonitorFromWindow(hwnd, 2)                     # MONITOR_DEFAULTTONEAREST
        u.GetMonitorInfoW(mon, ctypes.byref(mi))
        m = mi.rcMonitor
        return is_rect_fullscreen((r.left, r.top, r.right, r.bottom), (m.left, m.top, m.right, m.bottom))
    except Exception:
        return False
