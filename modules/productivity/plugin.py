"""Modul "Productivity": Zwischenablage-Verlauf, Fenster-Manager, KI-Makro-Assistent."""
import os
import sys
import tkinter as tk

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
            "layouts": {n: [s.__dict__ for s in sl] for n, sl in self.layouts.items()}})

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
            self.app.after(400, self._track_window)

    def work_area(self) -> tuple[int, int, int, int]:
        w, h = self.app.winfo_screenwidth(), self.app.winfo_screenheight()
        if sys.platform == "darwin":
            return 0, 25, w, h - 25 - 70          # Menüleiste oben, Dock unten (grob)
        if sys.platform.startswith("win"):
            return 0, 0, w, h - 40                # Taskleiste (grob)
        return 0, 0, w, h

    def snap(self, kind: str, window_id=None) -> str:
        try:
            x, y, w, h = winmgr.snap_rect(kind, self.work_area())
        except ValueError as exc:
            return str(exc)
        return winutil.move_window(window_id, x, y, w, h)

    def snap_from_button(self, kind: str, say) -> None:
        """Windows: das zuletzt benutzte andere Fenster sofort verschieben. Mac/Linux: kurze Wartezeit zum Umschalten."""
        if self.last_other:
            say(self.snap(kind, self.last_other["id"]) or tr("Done."), True)
        else:
            self.app.after(1200, lambda: say(self.snap(kind) or tr("Done."), True))

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
            self._hk = global_hotkeys({hk: (lambda k=kind: self.app.call_soon(self.snap, k)) for kind, hk in winmgr.DEFAULT_KEYS.items()})
            self._hk.daemon = True
            self._hk.start()
        except Exception as exc:
            self._hk = None
            self.snap_error = f"{type(exc).__name__}: {exc}"
        return self.snap_error

    def run_layout(self, name: str) -> int:
        slots = self.layouts.get(name, [])
        return winmgr.apply_layout(slots, winutil.list_windows(), self.work_area(), winutil.move_window)
