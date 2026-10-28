"""Modul "Click tools": Fadenkreuz, Hotkey-Manager, Farb-Trigger, Zeitplaner, Profile pro Programm."""
import threading
import traceback

from core import config, winutil
from core.plugin_api import BasePlugin

from . import appprofiles, hotkeys, mousekeys, pixel, scheduler, spreadcal
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
        self.xh_profiles = self._clean_profiles(d.get("xh_profiles"))
        self.xh_current = ""                 # zuletzt geladenes Profil
        self._xh_auto = ""                   # Profil, das der Programm-Wechsel zuletzt geladen hat
        self.rules = hotkeys.parse_rules(d.get("rules"))
        self.entries = scheduler.parse_entries(d.get("entries"))
        self.schedule_on = bool(d.get("schedule_on", False))
        self.app_rules = appprofiles.parse_rules(d.get("app_rules"))
        self.app_profiles_on = bool(d.get("app_profiles_on", False))
        self.pixel_cfg = d.get("pixel") if isinstance(d.get("pixel"), dict) else {}
        self.mk = mousekeys.MouseKeyTools(d.get("mousekeys"))
        self.spread_cal = {"running": False, "text": "", "ok": None, "cancel": False}
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
        self._register_crosshair_hotkeys()
        self.app.after(2500, self._xh_poll)
        if self.crosshair_on:
            self.app.after(800, self.show_crosshair)
        if self.mk.cfg["antiafk"]["on"]:
            self.mk.start_afk()

    def save(self):
        config.save_json(config.app_dir() / FILE, {
            "crosshair": self.crosshair_cfg.to_dict(), "crosshair_on": self.crosshair_on, "xh_profiles": self.xh_profiles,
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

    # ---------------------------------------------------------------- Fadenkreuz-Profile je Spiel
    MAX_XH_PROFILES = 20

    @staticmethod
    def _clean_profiles(data) -> dict:
        out = {}
        if isinstance(data, dict):
            for name, v in list(data.items())[:Plugin.MAX_XH_PROFILES]:
                if isinstance(v, dict) and isinstance(v.get("cfg"), dict):
                    out[str(name)[:40]] = {"cfg": CrosshairConfig.from_dict(v["cfg"]).to_dict(), "program": str(v.get("program", ""))[:60]}
        return out

    def xh_save_profile(self, name: str, program: str = "") -> str:
        name = (name or "").strip()[:40]
        if not name:
            return "Please enter a name."
        if len(self.xh_profiles) >= self.MAX_XH_PROFILES and name not in self.xh_profiles:
            return "At most 20 crosshair profiles."
        self.xh_profiles[name] = {"cfg": self.crosshair_cfg.to_dict(), "program": (program or "").strip()[:60]}
        self.xh_current = name
        self.save()
        return ""

    def xh_load_profile(self, name: str) -> bool:
        prof = self.xh_profiles.get(name)
        if prof is None:
            return False
        self.xh_current = name
        self.update_crosshair(CrosshairConfig.from_dict(prof["cfg"]))
        return True

    def xh_delete_profile(self, name: str) -> None:
        self.xh_profiles.pop(name, None)
        if self.xh_current == name:
            self.xh_current = ""
        self.save()

    def xh_next_profile(self) -> None:
        names = list(self.xh_profiles)
        if names:
            nxt = names[(names.index(self.xh_current) + 1) % len(names)] if self.xh_current in names else names[0]
            self.xh_load_profile(nxt)
            if self.overlay.active is False and self.crosshair_on:
                self.overlay.show(self.crosshair_cfg)

    def xh_match(self, title_and_proc: str) -> str:
        """Name des ersten Profils, dessen Programm im Fenstertitel/Programmnamen vorkommt ('' = keines)."""
        hay = (title_and_proc or "").lower()
        return next((n for n, p in self.xh_profiles.items() if p["program"] and p["program"].lower() in hay), "")

    def _xh_poll(self):
        """Alle 2 s: gehört das Fenster im Vordergrund zu einem Profil, wird es geladen (nur wenn Profile mit Programm existieren)."""
        try:
            if any(p["program"] for p in self.xh_profiles.values()):
                w = winutil.active_window() or {}
                name = self.xh_match(f"{w.get('title', '')} {w.get('proc', '')}")
                if name and name != self._xh_auto:
                    self._xh_auto = name
                    self.xh_load_profile(name)
                    cb = getattr(self, "on_profile_change", None)
                    if cb:
                        cb()
                elif not name:
                    self._xh_auto = ""
        except Exception:
            traceback.print_exc()
        finally:
            self.app.after(2000, self._xh_poll)

    def _register_crosshair_hotkeys(self):
        from core.hotkey_registry import Entry
        reg = self.app.hotkeys
        reg.register(Entry("crosshair.toggle", "Crosshair: show / hide", "Crosshair", "",
                           action=lambda: self.hide_crosshair() if self.crosshair_on else self.show_crosshair()))
        reg.register(Entry("crosshair.next", "Crosshair: next profile", "Crosshair", "", action=self.xh_next_profile))

    # ---------------------------------------------------------------- Streuung vom Spiel messen
    def calibrate_spread_start(self, color: str = "", tolerance: int = 40) -> str:
        """Misst im Hintergrund, wie weit das Fadenkreuz des Spiels beim Schießen auseinanderrückt. '' oder Fehlermeldung."""
        st = self.spread_cal
        if st["running"]:
            return ""
        try:
            from PIL import ImageGrab  # noqa: F401
            if color.strip():
                spreadcal.parse_hex(color)
        except spreadcal.SpreadError as exc:
            return str(exc)
        except Exception:
            return "Screen capture is not available (Pillow is missing)."
        spreadcal._SCREEN[:] = [self.app.winfo_screenwidth(), self.app.winfo_screenheight()]
        st.update(running=True, text="", ok=None, cancel=False)
        threading.Thread(target=self._spread_run, args=(color.strip(), max(10, min(120, int(tolerance)))), daemon=True).start()
        return ""

    def calibrate_spread_cancel(self):
        self.spread_cal["cancel"] = True

    def _spread_run(self, color, tol):
        import time

        from core.i18n import tr
        st = self.spread_cal
        fire = {"on": False}
        listener = None
        was_active = self.overlay.active
        cfg_before = CrosshairConfig.from_dict(self.crosshair_cfg.to_dict())

        def say(text):
            st["text"] = text

        def notify(title, text):
            try:
                self.app.call_soon(self.app.notifier.notify, "timer", title, text, True)
            except Exception:
                pass

        def check():
            if st["cancel"]:
                raise spreadcal.SpreadError("Calibration cancelled.")

        def grab():
            try:
                return spreadcal.grab_center()
            except Exception:
                raise spreadcal.SpreadError("Screen capture was refused. On macOS allow “Screen Recording” for the app.") from None
        try:
            from pynput import mouse

            def on_click(_x, _y, button, pressed):
                if str(button) == "Button.left":
                    fire["on"] = bool(pressed)
            listener = mouse.Listener(on_click=on_click)
            listener.daemon = True
            listener.start()
            if was_active:
                self.app.call_soon(self.overlay.hide)           # das eigene Fadenkreuz darf die Messung nicht stören
            for i in range(5, 0, -1):
                check()
                say(tr("Starting in {n} s – switch to your game. Your own crosshair is hidden during the measurement.", n=i))
                if i == 5:
                    notify(tr("Crosshair calibration"), tr("Switch to your game now. Do not move the mouse until the next message."))
                time.sleep(1)
            target = spreadcal.parse_hex(color) if color else None
            if target is None:
                found = spreadcal.detect_color(grab())
                if not found:
                    raise spreadcal.SpreadError("The colour of the game's crosshair was not found. Enter it by hand (colour of the lines).")
                target = spreadcal.parse_hex(found)
            idle = []
            for _ in range(8):
                check()
                idle.append(spreadcal.gap_of(grab(), target, tol))
                time.sleep(0.03)
            idle = [g for g in idle if g is not None]
            if len(idle) < 4:
                raise spreadcal.SpreadError("The crosshair of the game was not found in the picture. Check the colour, stand still and keep the game in front.")
            idle_gap = sorted(idle)[len(idle) // 2]
            say(tr("Hold the left mouse button and fire for about 2 seconds."))
            notify(tr("Crosshair calibration"), tr("Hold the left mouse button and fire for about 2 seconds."))
            end = time.monotonic() + 30
            while not fire["on"]:
                check()
                if time.monotonic() > end:
                    raise spreadcal.SpreadError("No shot was detected. Calibration cancelled.")
                time.sleep(0.02)
            t0 = time.perf_counter()
            series, release_t = [], None
            while True:
                now = time.perf_counter() - t0
                if release_t is None and (not fire["on"] or now > 3.0):
                    release_t = now
                if release_t is not None and now > release_t + 1.2:
                    break
                series.append((now, spreadcal.gap_of(grab(), target, tol)))
                time.sleep(0.01)
            res = spreadcal.analyze(idle_gap, series, release_t)
            cfg = CrosshairConfig.from_dict({**cfg_before.to_dict(), **res, "react_on": True, "react": "Spread on fire"})
            self.crosshair_cfg = cfg
            self.save()
            st.update(ok=True, text=tr("Measured: spreads {s} px, opens in {r} ms, closes in {f} ms. The reaction “Spread on fire” is switched on.",
                                       s=res["spread_px"], r=res["spread_rise_ms"], f=res["spread_fall_ms"]))
        except spreadcal.SpreadError as exc:
            st.update(ok=False, text=tr(str(exc)))
        except Exception as exc:
            traceback.print_exc()
            st.update(ok=False, text=f"{type(exc).__name__}: {exc}")
        finally:
            if listener is not None:
                listener.stop()
            st["running"] = False
            if was_active:
                self.app.call_soon(self.overlay.show, self.crosshair_cfg)
            cb = getattr(self, "on_spread_change", None)
            if cb:
                self.app.call_soon(cb)

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
    def start_pixel(self, x, y, color, tolerance, macro, once, on_change=False) -> str:
        self.stop_pixel()
        try:
            if not macro:
                return "Choose a saved macro."
            self.pixel_watcher = pixel.PixelWatcher(
                x, y, color, tolerance, lambda: self.app.call_soon(self._pixel_hit, macro), once=once,
                on_error=lambda e: self.app.call_soon(self._pixel_error, e), on_change=on_change)
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
