"""Modul "Gamer & Stream": Session-Timer, System-Overlay, Tasten-Overlay, CPS-/Reaktionstest, Screenshot."""
import threading

from core import config
from core.plugin_api import BasePlugin

from .overlays import KeysOverlay, StatsOverlay
from .overlaystyle import OverlayStyle
from .screenshot import RegionSelector, save
from .timer import SessionTimer

FILE = "gamer.json"
SHOT_HOTKEY = "<ctrl>+<shift>+<f11>"


class Plugin(BasePlugin):
    id = "gamer"
    name = "Gamer & Stream"
    icon = "🎮"
    version = "1.0.0"
    order = 60
    description = "Session timer, system and key overlay, CPS and reaction test with leaderboard, screenshot tool."

    def on_load(self):
        d = config.load_json(config.app_dir() / FILE, {})
        d = d if isinstance(d, dict) else {}
        self.timer = SessionTimer(int(d.get("break_min", 60)), int(d.get("drink_min", 30)))
        self.reminders: list[str] = []
        self.stats_overlay = StatsOverlay(self.app, OverlayStyle.from_dict(d.get("stats_style")))
        self.keys_overlay = KeysOverlay(self.app, OverlayStyle.from_dict(
            d.get("keys_style"), font="Segoe UI", size=11, color="#22d3ee", y=500))
        flags = d.get("stats_flags")
        if isinstance(flags, dict):
            for k in self.stats_overlay.show_flags:
                self.stats_overlay.show_flags[k] = bool(flags.get(k, True))
        self.shot_folder = d.get("shot_folder") or ""
        self.last_shot = ""
        self._hk = None
        self.shot_error = ""
        try:
            from core.hotkeys import global_hotkeys
            self._hk = global_hotkeys({SHOT_HOTKEY: lambda: self.app.call_soon(self.screenshot)})
            self._hk.daemon = True
            self._hk.start()
        except Exception as exc:
            self.shot_error = f"{type(exc).__name__}: {exc}"
        self._poll()

    def save(self):
        config.save_json(config.app_dir() / FILE, {"break_min": self.timer.break_min, "drink_min": self.timer.drink_min,
                                                   "shot_folder": self.shot_folder,
                                                   "stats_style": self.stats_overlay.style.to_dict(),
                                                   "keys_style": self.keys_overlay.style.to_dict(),
                                                   "stats_flags": self.stats_overlay.show_flags})

    def on_shutdown(self):
        self.stats_overlay.hide()
        self.keys_overlay.hide()
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass

    def create_page(self, parent):
        from .page import GamerPage
        return GamerPage(parent, self)

    # ---- Erinnerungen (läuft immer, auch wenn die Seite zu ist)
    def _poll(self):
        try:
            for kind in self.timer.due():
                self.reminders.append(kind)
                from core.i18n import tr
                self.app.notifier.notify("timer", tr("Time for a break! Stand up and stretch.") if kind == "break" else tr("Drink some water."))
        finally:
            self.app.after(5000, self._poll)

    # ---- Screenshot
    def screenshot(self):
        from pathlib import Path
        folder = Path(self.shot_folder) if self.shot_folder else None

        def done(img):
            try:
                self.last_shot = str(save(img, folder))
            except OSError as exc:
                self.last_shot = f"error: {exc}"
        try:
            RegionSelector(self.app, done).start()
        except Exception as exc:
            self.last_shot = f"error: {type(exc).__name__}: {exc}"
