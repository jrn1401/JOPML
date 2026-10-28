"""Modul "Gamer & Stream": Session-Timer, System-Overlay, Tasten-Overlay, CPS-/Reaktionstest, Screenshot."""
import threading

from core import config
from core.plugin_api import BasePlugin

from core.hotkey_registry import Entry

from . import helpers, overlays
from .overlays import KeysOverlay, StatsOverlay, TextOverlay
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
        self.shot_error = ""
        # ---- Multiplayer-Helfer (1.6.0)
        self.match = helpers.MatchCounter(d.get("match"))
        self.timers = helpers.NamedTimers(d.get("timers"))
        self.notes = helpers.Notes(d.get("notes"))
        self.pings = helpers.PingHistory()
        self.ping_host = str(d.get("ping_host") or "1.1.1.1")[:60]
        self.streamer_mode = bool(d.get("streamer_mode", False))
        overlays.STREAMER["on"] = self.streamer_mode
        self.match_overlay = TextOverlay(self.app, OverlayStyle.from_dict(d.get("match_style"), y=140), self._match_text)
        self.timers_overlay = TextOverlay(self.app, OverlayStyle.from_dict(d.get("timers_style"), y=220, color="#fbbf24"), self._timers_text, 250)
        self.notes_overlay = TextOverlay(self.app, OverlayStyle.from_dict(d.get("notes_style"), y=300, size=12), self._notes_text, 1000)
        self.net_overlay = TextOverlay(self.app, OverlayStyle.from_dict(d.get("net_style"), y=100, size=12), self.pings.text, 1000)
        self._net_run = False
        self._hidden_by_toggle: list = []
        self._timer_job = None
        # Overlays, die beim Beenden an waren, kommen beim nächsten Start von selbst wieder
        keys = self.overlay_map().keys()
        self.overlays_on: set = {k for k in (d.get("overlays_on") if isinstance(d.get("overlays_on"), list) else []) if k in keys}
        # Automatische Erkennung von Sieg / Niederlage (Bildschirm, nur Farben eines Bereichs)
        self.auto = helpers.AutoOutcome(d.get("match_auto"))
        self.auto_status = ""
        self.auto_ok = True
        self.auto_last = ""
        self._auto_run = False
        self._register_hotkeys()
        self._poll()
        self.app.after(2500, self._restore)

    def _restore(self) -> None:
        for k in sorted(self.overlays_on):
            try:
                self.show_overlay(k)
            except Exception as exc:
                print("Overlay restore error:", k, exc)
        if self.auto.on:
            self.start_auto()

    def overlay_map(self) -> dict:
        return {"stats": self.stats_overlay, "keys": self.keys_overlay, "match": self.match_overlay,
                "timers": self.timers_overlay, "notes": self.notes_overlay, "net": self.net_overlay}

    # ---- Texte der Overlays
    def _match_text(self) -> str:
        from core.i18n import tr
        m = self.match
        return "\n".join([tr("Round") + f": {m.rounds}", tr("Wins / Losses") + f": {m.wins} / {m.losses}", tr("K / D") + f": {m.kills} / {m.deaths}  ({m.kd()})"])

    def _timers_text(self) -> str:
        return "\n".join(self.timers.lines())

    def _notes_text(self) -> str:
        n = self.notes
        return (n.current + "\n" if n.current else "") + n.text()

    # ---- Hotkeys
    def _register_hotkeys(self):
        reg = self.app.hotkeys
        add = lambda i, label, default, fn: reg.register(Entry(i, label, "Gaming & Stream", default, action=fn))
        add("gamer.screenshot", "Screenshot of a region", SHOT_HOTKEY, self.screenshot)
        add("gamer.win", "Match: count a win", "", lambda: self.count("wins"))
        add("gamer.loss", "Match: count a loss", "", lambda: self.count("losses"))
        add("gamer.kill", "Match: count a kill", "", lambda: self.count("kills"))
        add("gamer.death", "Match: count a death", "", lambda: self.count("deaths"))
        add("gamer.round", "Match: next round", "", lambda: self.count("rounds"))
        add("gamer.learn_win", "Match: learn the win screen", "", lambda: self.learn("win"))
        add("gamer.learn_loss", "Match: learn the loss screen", "", lambda: self.learn("loss"))
        for i in range(helpers.MAX_TIMERS):
            add(f"gamer.timer.{i + 1}", f"Start timer {i + 1} (restarts it)", "", lambda i=i: self.start_timer(i))
        add("gamer.timers_stop", "Stop all timers", "", self.stop_timers)
        add("gamer.notes_next", "Notes: next map", "", self.next_note)
        add("gamer.overlays_all", "Show / hide all overlays", "", self.toggle_all_overlays)

    def count(self, field: str) -> None:
        self.match.add(field)
        self.save()

    # ---- Automatische Erkennung von Sieg / Niederlage
    def _grab_region(self):
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=self.auto.region).convert("RGB")

    def set_auto_region(self, box) -> None:
        self.auto.region = tuple(int(v) for v in box)
        self.save()

    def learn(self, kind: str) -> str:
        """Merkt sich den aktuellen Inhalt des gewählten Bereichs als Sieg- bzw. Niederlage-Bild. Gibt '' oder eine Meldung zurück."""
        from core.i18n import tr
        self.auto_ok = False
        if self.auto.region is None:
            self.auto_status = tr("Choose a screen area first.")
            return self.auto_status
        try:
            n = self.auto.learn(kind, helpers.signature(self._grab_region()))
        except Exception as exc:
            self.auto_status = tr("Screen could not be read: {e}", e=f"{type(exc).__name__}: {exc}")
            return self.auto_status
        self.auto_ok = True
        self.save()
        self.auto_status = tr("Win screen learned ({n} saved).", n=n) if kind == "win" else tr("Loss screen learned ({n} saved).", n=n)
        return self.auto_status

    def probe(self) -> str:
        """Was erkennt das Programm gerade im gewählten Bereich? (Prüfknopf)"""
        from core.i18n import tr
        if not self.auto.ready():
            return tr("Nothing learned yet.")
        try:
            sig = helpers.signature(self._grab_region())
        except Exception as exc:
            return tr("Screen could not be read: {e}", e=f"{type(exc).__name__}: {exc}")
        w, l = self.auto.scores(sig)
        kind = self.auto.classify(sig)
        what = tr("a win screen") if kind == "wins" else tr("a loss screen") if kind == "losses" else tr("neither")
        return tr("Right now the screen looks like: {what} (difference to win {w}, to loss {l}, must be below {t}).",
                  what=what, w=round(w, 1), l=round(l, 1), t=self.auto.tolerance)

    def set_auto(self, on: bool) -> None:
        self.auto.on = bool(on)
        self.save()
        if on:
            self.start_auto()
        else:
            self._auto_run = False

    def start_auto(self) -> None:
        if self._auto_run:
            return
        self._auto_run = True
        import time

        def loop():
            from core import perf
            while self._auto_run:
                try:
                    if self.auto.on and self.auto.ready():
                        kind = self.auto.feed(helpers.signature(self._grab_region()))
                        if kind:
                            self.app.call_soon(self._auto_counted, kind)
                    time.sleep(1.5 if perf.POTATO else 0.7)
                except Exception as exc:
                    self.auto_status = f"{type(exc).__name__}: {exc}"
                    time.sleep(5)
        threading.Thread(target=loop, daemon=True).start()

    def _auto_counted(self, kind: str) -> None:
        import time
        from core.i18n import tr
        self.count(kind)
        self.auto_last = time.strftime("%H:%M:%S") + "  " + (tr("Win counted automatically") if kind == "wins" else tr("Loss counted automatically"))

    def start_timer(self, i: int) -> None:
        self.timers.start(i)
        if not self.timers_overlay.active:
            self.timers_overlay.show()
        self._tick_timers()

    def stop_timers(self) -> None:
        self.timers.stop_all()

    def _tick_timers(self):
        """Prüft laufende Timer alle 0,5 s, solange welche laufen; am Ende Meldung mit Ton."""
        from core.i18n import tr
        for i in self.timers.due():
            slot = self.timers.slots[i]
            self.app.notifier.notify("timer", tr("{name}: time is up!", name=slot["name"]))
        if self.timers.running:
            if self._timer_job is None:
                self._timer_job = self.app.after(500, self._timer_tick_job)
        elif self.timers_overlay.active and not self.timers.running:
            self.app.after(2500, lambda: None if self.timers.running else self.timers_overlay.hide())

    def _timer_tick_job(self):
        self._timer_job = None
        self._tick_timers()

    def next_note(self) -> None:
        names = list(self.notes.maps)
        if names:
            self.notes.current = names[(names.index(self.notes.current) + 1) % len(names)] if self.notes.current in names else names[0]
            self.save()

    # ---- Alle Overlays mit einer Taste ein/aus
    def toggle_all_overlays(self) -> None:
        shown = [k for k, o in self.overlay_map().items() if o.active]
        crosshair = self.app.plugin_by_id.get("clicktools")
        if shown or (crosshair is not None and crosshair.crosshair_on and not self._hidden_by_toggle):
            self._hidden_by_toggle = list(shown)
            for k in shown:
                self.overlay_map()[k].hide()
            self._net_run = False
            self._hide_cross = bool(crosshair and crosshair.crosshair_on)
            if self._hide_cross:
                crosshair.overlay.hide()
        else:
            for k in self._hidden_by_toggle:
                self.show_overlay(k)
            if getattr(self, "_hide_cross", False) and crosshair is not None:
                crosshair.overlay.show(crosshair.crosshair_cfg)
            self._hidden_by_toggle = []

    def show_overlay(self, key: str):
        o = self.overlay_map()[key]
        res = o.show()
        if key == "net":
            self._start_ping_loop()
        if key not in self.overlays_on:
            self.overlays_on.add(key)
            self.save()
        return res

    def hide_overlay(self, key: str):
        self.overlay_map()[key].hide()
        if key == "net":
            self._net_run = False
        if key in self.overlays_on:
            self.overlays_on.discard(key)
            self.save()

    def _start_ping_loop(self):
        if self._net_run:
            return
        self._net_run = True
        import threading
        import time
        from . import sysinfo

        def loop():
            while self._net_run:
                self.pings.add(sysinfo.ping_ms(helpers.split_host(self.ping_host)))
                time.sleep(2)
        threading.Thread(target=loop, daemon=True).start()

    def set_streamer_mode(self, on: bool) -> None:
        self.streamer_mode = bool(on)
        overlays.STREAMER["on"] = self.streamer_mode
        for o in self.overlay_map().values():
            if o.active:
                o.restyle()
        self.save()

    def save(self):
        config.save_json(config.app_dir() / FILE, {"break_min": self.timer.break_min, "drink_min": self.timer.drink_min,
                                                   "shot_folder": self.shot_folder,
                                                   "stats_style": self.stats_overlay.style.to_dict(),
                                                   "keys_style": self.keys_overlay.style.to_dict(),
                                                   "stats_flags": self.stats_overlay.show_flags,
                                                   "match": self.match.to_dict(), "timers": self.timers.to_list(), "notes": self.notes.to_dict(),
                                                   "match_style": self.match_overlay.style.to_dict(), "timers_style": self.timers_overlay.style.to_dict(),
                                                   "notes_style": self.notes_overlay.style.to_dict(), "net_style": self.net_overlay.style.to_dict(),
                                                   "ping_host": self.ping_host, "streamer_mode": self.streamer_mode,
                                                   "overlays_on": sorted(self.overlays_on), "match_auto": self.auto.to_dict()})

    def on_shutdown(self):
        self._net_run = False
        self._auto_run = False
        for o in self.overlay_map().values():
            o.hide()
        self.save()

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
