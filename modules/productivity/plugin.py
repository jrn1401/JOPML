"""Modul "Productivity": Zwischenablage-Verlauf, Fenster-Manager, KI-Makro-Assistent."""
import os
import sys
import tkinter as tk

from core import perf
from core import config, winutil
from core.i18n import tr
from core.plugin_api import BasePlugin

from . import winmgr
from .clipboard import ClipHistory

FILE = "productivity.json"


class Plugin(BasePlugin):
    id = "productivity"
    name = "Productivity"
    icon = "⚡"
    version = "1.0.0"
    order = 50
    description = "Clipboard history, window manager (halves and quarters) and the AI macro assistant."

    def on_load(self):
        d = config.load_json(config.app_dir() / FILE, {})
        d = d if isinstance(d, dict) else {}
        self.clip = ClipHistory(d.get("pins"))
        self.clip_on = bool(d.get("clip_on", True))
        self.snap_on = bool(d.get("snap_on", False))
        self.layouts = winmgr.parse_layouts(d.get("layouts"))
        self.start_layout_on = bool(d.get("start_layout_on", False))
        self.start_layout = str(d.get("start_layout", ""))[:40]
        self._hk = None
        self.snap_error = ""
        self.changed = 0          # zählt Änderungen, damit die Seite weiß, wann sie neu zeichnen muss
        self.apply_snap_hotkeys()
        self.app.after(1000, self._poll_clip)
        if self.start_layout_on and self.start_layout in self.layouts:
            self.app.after(4000, lambda: self.run_layout(self.start_layout))      # kurz warten, bis andere Programme geöffnet sind
        self.last_other = None         # zuletzt benutztes Fenster außerhalb dieses Programms (nur Windows)
        if winutil.WIN:
            self.app.after(500, self._track_window)

    def save(self):
        config.save_json(config.app_dir() / FILE, {
            "pins": self.clip.pins, "clip_on": self.clip_on, "snap_on": self.snap_on,
            "start_layout_on": self.start_layout_on, "start_layout": self.start_layout,
            "layouts": {n: [{**s.__dict__, "rect": list(s.rect) if s.rect else None} for s in sl] for n, sl in self.layouts.items()}})

    def on_shutdown(self):
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass
        self.save()

    def create_page(self, parent):
        from .page import ProductivityPage
        return ProductivityPage(parent, self)

    # ---- Zwischenablage
    def _poll_clip(self):
        try:
            if self.clip_on:
                try:
                    text = self.app.clipboard_get()
                except tk.TclError:
                    text = ""
                if text and self.clip.add(text):
                    self.changed += 1
        finally:
            self.app.after(1200, self._poll_clip)

    # ---- Fenster-Manager
    def _track_window(self):
        """Merkt sich das letzte fremde Fenster im Vordergrund, damit ein Knopf im Launcher es sofort verschieben kann."""
        try:
            w = winutil.active_window()
            if w and w.get("pid") != os.getpid():
                self.last_other = w
        except Exception:
            pass
        finally:
            self.app.after(perf.ms(400), self._track_window)

    def monitors(self) -> list[dict]:
        return winutil.monitors()

    def monitor_areas(self) -> dict:
        """{Monitor-Nr: Arbeitsfläche}; 0 = Hauptmonitor. Leer, wenn die Monitore nicht ermittelt werden können (nicht Windows)."""
        mons = self.monitors()
        out = {m["no"]: m["work"] for m in mons}
        prim = next((m for m in mons if m["primary"]), None)
        if prim:
            out[0] = prim["work"]
        return out

    def work_area(self) -> tuple[int, int, int, int]:
        """Arbeitsfläche des Hauptmonitors (ohne Taskleiste)."""
        areas = self.monitor_areas()
        if 0 in areas:
            return areas[0]
        w, h = self.app.winfo_screenwidth(), self.app.winfo_screenheight()
        if sys.platform == "darwin":
            return 0, 25, w, h - 25 - 70          # Menüleiste oben, Dock unten (grob)
        if sys.platform.startswith("win"):
            return 0, 0, w, h - 40                # Taskleiste (grob)
        return 0, 0, w, h

    def _window_area(self, window_id=None) -> tuple:
        """Arbeitsfläche des Monitors, auf dem das Fenster gerade liegt (window_id None = aktives Fenster)."""
        mons = self.monitors()
        if mons:
            hwnd = window_id
            if not hwnd:
                w = winutil.active_window()
                hwnd = w["id"] if w else None
            rect = winutil.window_rect(hwnd) if hwnd else None
            m = winmgr.monitor_of_rect(rect, mons) if rect else None
            if m:
                return m["work"]
        return self.work_area()

    def snap(self, kind: str, window_id=None, monitor: int | None = None) -> str:
        """Fenster in eine Hälfte/ein Viertel schieben. monitor None = auf dem Monitor lassen, auf dem es ist; 0 = Hauptmonitor; 1.. = Nummer."""
        try:
            area = self._window_area(window_id) if monitor is None else (self.monitor_areas().get(monitor) or self.work_area())
            x, y, w, h = winmgr.snap_rect(kind, area)
        except ValueError as exc:
            return str(exc)
        return winutil.move_window(window_id, x, y, w, h)

    def to_next_monitor(self, window_id=None) -> str:
        """Fenster auf den nächsten Monitor (links → rechts, dann wieder von vorn); Größe und Lage bleiben im gleichen Verhältnis."""
        mons = self.monitors()
        if len(mons) < 2:
            return tr("Only one monitor found.")
        hwnd = window_id
        if not hwnd:
            w = winutil.active_window()
            hwnd = w["id"] if w else None
        rect = winutil.window_rect(hwnd) if hwnd else None
        if not rect:
            return tr("No window found.")
        cur = winmgr.monitor_of_rect(rect, mons)
        nxt = winmgr.next_monitor(cur["no"], mons)
        x, y, w, h = winmgr.abs_rect(winmgr.rel_rect(rect, cur["work"]), nxt["work"])
        return winutil.move_window(hwnd, x, y, w, h)

    def capture_layout(self, name: str, windows: list[dict]) -> int:
        """Speichert die gewählten offenen Fenster mit genauer Lage und Monitor als Layout. Gibt die Zahl der Plätze zurück."""
        mons = self.monitors()
        slots = []
        for w in windows[:12]:
            rect = w.get("rect")
            if not rect:
                continue
            proc = (w.get("proc") or "")
            match = proc.rsplit(".", 1)[0] if "." in proc else proc
            if len(match) < 2:
                match = (w.get("title") or "")[:30]
            m = winmgr.monitor_of_rect(rect, mons)
            area = m["work"] if m else self.work_area()
            try:
                slots.append(winmgr.Slot(match, "saved", m["no"] if m else 0, winmgr.rel_rect(rect, area)).validate())
            except ValueError:
                pass
        if slots and name.strip():
            self.layouts[name.strip()[:40]] = slots
            self.save()
        return len(slots)

    def snap_from_button(self, kind: str, say, monitor: int | None = None) -> None:
        """Windows: das zuletzt benutzte andere Fenster sofort verschieben. Mac/Linux: kurze Wartezeit zum Umschalten."""
        if self.last_other:
            say(self.snap(kind, self.last_other["id"], monitor) or tr("Done."), True)
        else:
            self.app.after(1200, lambda: say(self.snap(kind, None, monitor) or tr("Done."), True))

    def next_monitor_from_button(self, say) -> None:
        if self.last_other:
            err = self.to_next_monitor(self.last_other["id"])
            say(err or tr("Done."), not err)
        else:
            self.app.after(1200, lambda: say(self.to_next_monitor() or tr("Done."), True))

    def apply_snap_hotkeys(self) -> str:
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass
            self._hk = None
        self.snap_error = ""
        if not self.snap_on:
            return ""
        try:
            from core.hotkeys import global_hotkeys
            keys = {hk: (lambda k=kind: self.app.call_soon(self.snap, k)) for kind, hk in winmgr.DEFAULT_KEYS.items()}
            keys[winmgr.NEXT_MONITOR_KEY] = lambda: self.app.call_soon(self.to_next_monitor)
            self._hk = global_hotkeys(keys)
            self._hk.daemon = True
            self._hk.start()
        except Exception as exc:
            self._hk = None
            self.snap_error = f"{type(exc).__name__}: {exc}"
        return self.snap_error

    def run_layout(self, name: str) -> int:
        slots = self.layouts.get(name, [])
        return winmgr.apply_layout(slots, winutil.list_windows(), self.work_area(), winutil.move_window, self.monitor_areas())
