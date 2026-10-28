"""Modul "Click tools": Fadenkreuz, Hotkey-Manager, Farb-Trigger, Zeitplaner, Profile pro Programm."""
import threading
import traceback

from core import config, winutil
from core.plugin_api import BasePlugin

from . import appprofiles, hotkeys, mousekeys, pixel, scheduler
from .crosshair import CrosshairConfig, CrosshairOverlay

FILE = "clicktools.json"


class Plugin(BasePlugin):
    id = "clicktools"
    name = "Crosshair"
    icon = "◎"
    version = "1.0.0"
    order = 20
    description = "A crosshair overlay for the middle of your screen."

    # ---------------------------------------------------------------- Zustand
    def on_load(self):
        d = config.load_json(config.app_dir() / FILE, {})
        d = d if isinstance(d, dict) else {}
        self.crosshair_cfg = CrosshairConfig.from_dict(d.get("crosshair"))
        self.crosshair_on = bool(d.get("crosshair_on", False))
        self.rules = hotkeys.parse_rules(d.get("rules"))
        self.entries = scheduler.parse_entries(d.get("entries"))
        self.schedule_on = bool(d.get("schedule_on", False))
        self.app_rules = appprofiles.parse_rules(d.get("app_rules"))
        self.app_profiles_on = bool(d.get("app_profiles_on", False))
        self.pixel_cfg = d.get("pixel") if isinstance(d.get("pixel"), dict) else {}
        self.mk = mousekeys.MouseKeyTools(d.get("mousekeys"))
        self.overlay = CrosshairOverlay(self.app)
        self._hk = None
        self.hotkey_error = ""
        self.pixel_watcher = None
        self.pixel_status = ""
        self.sched = scheduler.Scheduler(lambda: list(self.entries), self.run_macro)
        self.watcher = appprofiles.AppProfileWatcher(lambda: self.app_rules, self._switch_profile, winutil.active_window)
        self.apply_hotkeys()
        if self.schedule_on and self.entries:
            self.sched.start()
        if self.app_profiles_on and self.app_rules:
            self.watcher.start()
        if self.crosshair_on:
            self.app.after(800, self.show_crosshair)
        if self.mk.cfg["antiafk"]["on"]:
            self.mk.start_afk()

    def save(self):
        config.save_json(config.app_dir() / FILE, {
            "crosshair": self.crosshair_cfg.to_dict(), "crosshair_on": self.crosshair_on,
            "rules": [r.to_dict() for r in self.rules], "entries": [e.to_dict() for e in self.entries],
            "schedule_on": self.schedule_on, "app_rules": [r.__dict__ for r in self.app_rules],
            "app_profiles_on": self.app_profiles_on, "pixel": self.pixel_cfg, "mousekeys": self.mk.cfg})

    def on_shutdown(self):
        self.stop_pixel()
        self.sched.stop()
        self.watcher.stop()
        self._stop_hotkeys()
        self.mk.stop_all()
        self.overlay.hide()

    def create_page(self, parent):
        from .page import ClickToolsPage
        return ClickToolsPage(parent, self, mode="crosshair")

    # ---------------------------------------------------------------- Fadenkreuz
    def show_crosshair(self):
        self.crosshair_on = True
        self.overlay.show(self.crosshair_cfg)
        self.save()

    def hide_crosshair(self):
        self.crosshair_on = False
        self.overlay.hide()
        self.save()

    def update_crosshair(self, cfg: CrosshairConfig):
        self.crosshair_cfg = cfg.clamp()
        if self.overlay.active:
            self.overlay.show(self.crosshair_cfg)
        self.save()

    # ---------------------------------------------------------------- Makros starten (für Hotkeys, Trigger, Zeitplaner)
    def run_macro(self, name: str) -> str:
        macros = self.app.plugin_by_id.get("macros")
        if macros is None:
            return "The macro module is not available."
        try:
            text = macros.load(name)
        except (OSError, ValueError):
            return "This macro could not be opened."
        return macros.run(text)

    # ---------------------------------------------------------------- Hotkey-Manager
    def _stop_hotkeys(self):
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass
            self._hk = None

    def apply_hotkeys(self) -> str:
        self._stop_hotkeys()
        self.hotkey_error = ""
        mapping = hotkeys.build_mapping(self.rules, self._do_rule) if self.rules else {}
        for hk, fn in self.mk.mapping().items():       # Werkzeuge "Maus & Tastatur"
            mapping.setdefault(hk, fn)
        if not mapping:
            return ""
        try:
            from core.hotkeys import global_hotkeys
            self._hk = global_hotkeys(mapping)
            self._hk.daemon = True
            self._hk.start()
        except Exception as exc:
            self._hk = None
            self.hotkey_error = f"{type(exc).__name__}: {exc}"
        return self.hotkey_error

    def _do_rule(self, rule: hotkeys.Rule):
        def work():
            try:
                if rule.action == "macro":
                    self.app.call_soon(self.run_macro, rule.value)
                    return
                from pynput import keyboard
                kb = keyboard.Controller()
                if rule.action == "text":
                    kb.type(rule.value)
                else:
                    k = rule.value
                    kb.tap(keyboard.KeyCode.from_char(k) if len(k) == 1 else keyboard.Key[k])
            except Exception:
                traceback.print_exc()
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- Farb-Trigger
    def start_pixel(self, x, y, color, tolerance, macro, once) -> str:
        self.stop_pixel()
        try:
            if not macro:
                return "Choose a saved macro."
            self.pixel_watcher = pixel.PixelWatcher(
                x, y, color, tolerance, lambda: self.app.call_soon(self._pixel_hit, macro), once=once,
                on_error=lambda e: self.app.call_soon(self._pixel_error, e))
            pixel.grab_pixel(int(x), int(y))                       # früh prüfen, ob der Bildschirm gelesen werden darf
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            self.pixel_watcher = None
            return f"{type(exc).__name__}: {exc}"
        self.pixel_status = ""
        self.pixel_watcher.start()
        return ""

    def _pixel_hit(self, macro):
        err = self.run_macro(macro)
        self.pixel_status = err or "Triggered."

    def _pixel_error(self, err):
        self.pixel_status = err
        self.pixel_watcher = None

    def stop_pixel(self):
        if getattr(self, "pixel_watcher", None) is not None:
            self.pixel_watcher.stop()
            self.pixel_watcher = None

    # ---------------------------------------------------------------- Zeitplaner / Programm-Profile
    def set_schedule(self, entries, on: bool):
        self.entries, self.schedule_on = entries, on
        self.sched.stop()
        if on and entries:
            self.sched.start()
        self.save()

    def set_app_rules(self, rules, on: bool):
        self.app_rules, self.app_profiles_on = rules, on
        self.watcher.stop()
        if on and rules:
            self.watcher.start()
        self.save()

    def _switch_profile(self, name: str):
        ac = self.app.plugin_by_id.get("autoclicker")
        if ac is None:
            return
        path = ac.profiles_dir() / f"{name}.json"
        try:
            prof = ac.load_profile_file(path)
        except (OSError, ValueError):
            return
        self.app.call_soon(self._apply_profile, ac, prof)

    @staticmethod
    def _apply_profile(ac, prof):
        if ac.engine.running:                  # nie mitten im Lauf umschalten
            return
        ac.set_profile(prof)
