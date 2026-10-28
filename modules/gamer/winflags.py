"""Windows-Feinheiten für Overlay-Fenster: immer oben halten, nie den Fokus stehlen, Klicks durchlassen.
Auf anderen Systemen sind alle Funktionen wirkungslos (und werfen nie)."""
import os

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x20, 0x80000, 0x80, 0x08000000
HWND_TOPMOST, SWP_FLAGS = -1, 0x0001 | 0x0002 | 0x0010 | 0x0040       # NOMOVE | NOSIZE | NOACTIVATE | SHOWWINDOW


def _hwnd(win):
    import ctypes
    wid = win.winfo_id()
    return ctypes.windll.user32.GetParent(wid) or wid


def prepare(win, click_through: bool) -> None:
    """Kein Eintrag in der Taskleiste, kein Fokus; bei click_through gehen Mausklicks hindurch."""
    if os.name != "nt":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        h = _hwnd(win)
        ex = u.GetWindowLongW(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        ex = (ex | WS_EX_TRANSPARENT) if click_through else (ex & ~WS_EX_TRANSPARENT)
        u.SetWindowLongW(h, GWL_EXSTYLE, ex)
    except Exception:
        pass


def keep_on_top(win) -> None:
    """Holt das Fenster wieder über andere "immer oben"-Fenster (z. B. ein Spiel im randlosen Vollbild)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.SetWindowPos(_hwnd(win), HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
    except Exception:
        pass


def exclude_from_capture(win, on: bool) -> None:
    """Streamer-Modus: Das Fenster erscheint nicht in Bildschirmaufnahmen und Streams (SetWindowDisplayAffinity, Windows 10 Version 2004 oder neuer)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.SetWindowDisplayAffinity(_hwnd(win), 0x11 if on else 0)     # WDA_EXCLUDEFROMCAPTURE | WDA_NONE
    except Exception:
        pass
