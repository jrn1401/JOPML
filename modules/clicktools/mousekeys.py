"""Maus & Tastatur: Mehrfachklick auf einer Taste, Taste halten per Umschalter, Auto-Scroll und Anti-AFK.

Die Logik kennt keine Oberfläche; die Eingabe läuft über ein austauschbares Backend (echt: pynput, im Test: Attrappe)."""
import threading

from core.i18n import tr

from .hotkeys import normalize_hotkey

BUTTONS = ["left", "right", "middle"]
HOLD_TARGETS = ["shift", "ctrl", "w", "a", "s", "d", "space", "mouse_left", "mouse_right"]
DEFAULTS = {
    "multiclick": {"on": False, "hotkey": "<f9>", "button": "left", "count": 3, "delay_ms": 30},
    "holdtoggle": {"on": False, "hotkey": "<f10>", "target": "shift"},
    "autoscroll": {"on": False, "hotkey": "<f11>", "direction": "down", "speed": 5},
    "antiafk": {"on": False, "interval_s": 60, "mode": "mouse"},
}


def _num(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return default


def _hk(v, default):
    try:
        return normalize_hotkey(str(v))
    except ValueError:
        return default


def parse(data) -> dict:
    """Prüft gespeicherte Einstellungen und ersetzt Ungültiges durch Standardwerte."""
    d = data if isinstance(data, dict) else {}
    out = {}
    m = d.get("multiclick") if isinstance(d.get("multiclick"), dict) else {}
    out["multiclick"] = {"on": bool(m.get("on")), "hotkey": _hk(m.get("hotkey"), "<f9>"),
                         "button": m.get("button") if m.get("button") in BUTTONS else "left",
                         "count": _num(m.get("count"), 2, 5, 3), "delay_ms": _num(m.get("delay_ms"), 0, 500, 30)}
    h = d.get("holdtoggle") if isinstance(d.get("holdtoggle"), dict) else {}
    out["holdtoggle"] = {"on": bool(h.get("on")), "hotkey": _hk(h.get("hotkey"), "<f10>"),
                         "target": h.get("target") if h.get("target") in HOLD_TARGETS else "shift"}
    s = d.get("autoscroll") if isinstance(d.get("autoscroll"), dict) else {}
    out["autoscroll"] = {"on": bool(s.get("on")), "hotkey": _hk(s.get("hotkey"), "<f11>"),
                         "direction": s.get("direction") if s.get("direction") in ("up", "down") else "down",
                         "speed": _num(s.get("speed"), 1, 30, 5)}
    a = d.get("antiafk") if isinstance(d.get("antiafk"), dict) else {}
    out["antiafk"] = {"on": bool(a.get("on")), "interval_s": _num(a.get("interval_s"), 10, 600, 60),
                      "mode": a.get("mode") if a.get("mode") in ("mouse", "key") else "mouse"}
    hks = [out[k]["hotkey"] for k in ("multiclick", "holdtoggle", "autoscroll")]
    if len(set(hks)) < 3:                                    # doppelte Tastenkürzel: Standardwerte
        for k in ("multiclick", "holdtoggle", "autoscroll"):
            out[k]["hotkey"] = DEFAULTS[k]["hotkey"]
    return out


class PynputInput:
    def __init__(self):
        from pynput import keyboard, mouse
        self.kb, self.ms = keyboard.Controller(), mouse.Controller()
        self._Key, self._KeyCode, self._Button = keyboard.Key, keyboard.KeyCode, mouse.Button

    def _k(self, name):
        return self._KeyCode.from_char(name) if len(name) == 1 else self._Key[name]

    def click(self, button, count, delay_ms):
        import time
        for i in range(count):
            self.ms.click(getattr(self._Button, button), 1)
            if i < count - 1 and delay_ms:
                time.sleep(delay_ms / 1000)

    def press(self, name):
        if name.startswith("mouse_"):
            self.ms.press(getattr(self._Button, name[6:]))
        else:
            self.kb.press(self._k(name))

    def release(self, name):
        if name.startswith("mouse_"):
            self.ms.release(getattr(self._Button, name[6:]))
        else:
            self.kb.release(self._k(name))

    def scroll(self, n):
        self.ms.scroll(0, n)

    def nudge(self):
        x, y = self.ms.position
        self.ms.position = (x + 1, y)
        self.ms.position = (x, y)

    def tap(self, name):
        self.kb.tap(self._k(name))


class MouseKeyTools:
    def __init__(self, cfg=None, backend=None):
        self.cfg = parse(cfg)
        self._backend = backend
        self.holding = False
        self.scrolling = False
        self.afk_running = False
        self._stop_scroll = threading.Event()
        self._stop_afk = threading.Event()
        self.error = ""

    @property
    def backend(self):
        if self._backend is None:
            self._backend = PynputInput()
        return self._backend

    def mapping(self, call=None) -> dict:
        """Tastenkürzel -> Funktion für die eingeschalteten Werkzeuge. call(fn) führt fn aus (Standard: direkt)."""
        call = call or (lambda f: f())
        m, c = {}, self.cfg
        if c["multiclick"]["on"]:
            m[c["multiclick"]["hotkey"]] = lambda: call(self.multi_click)
        if c["holdtoggle"]["on"]:
            m[c["holdtoggle"]["hotkey"]] = lambda: call(self.toggle_hold)
        if c["autoscroll"]["on"]:
            m[c["autoscroll"]["hotkey"]] = lambda: call(self.toggle_scroll)
        return m

    # ---- Mehrfachklick
    def multi_click(self):
        c = self.cfg["multiclick"]
        threading.Thread(target=self._safe, args=(self.backend.click, c["button"], c["count"], c["delay_ms"]), daemon=True).start()

    # ---- Halten per Umschalter
    def toggle_hold(self) -> bool:
        target = self.cfg["holdtoggle"]["target"]
        try:
            if self.holding:
                self.backend.release(target)
                self.holding = False
            else:
                self.backend.press(target)
                self.holding = True
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        return self.holding

    # ---- Auto-Scroll
    def toggle_scroll(self) -> bool:
        if self.scrolling:
            self._stop_scroll.set()
            self.scrolling = False
            return False
        self._stop_scroll.clear()
        self.scrolling = True
        c = self.cfg["autoscroll"]
        step = 1 if c["direction"] == "up" else -1
        period = 1.0 / c["speed"]

        def loop():
            while not self._stop_scroll.wait(period):
                self._safe(self.backend.scroll, step)
        threading.Thread(target=loop, daemon=True).start()
        return True

    # ---- Anti-AFK
    def start_afk(self) -> None:
        self.stop_afk()
        self._stop_afk.clear()
        self.afk_running = True
        c = self.cfg["antiafk"]

        def loop():
            while not self._stop_afk.wait(c["interval_s"]):
                if c["mode"] == "mouse":
                    self._safe(self.backend.nudge)
                else:
                    self._safe(self.backend.tap, "shift")
        threading.Thread(target=loop, daemon=True).start()

    def stop_afk(self) -> None:
        self._stop_afk.set()
        self.afk_running = False

    def stop_all(self) -> None:
        """Notaus/Beenden: nichts gedrückt oder laufen lassen."""
        self._stop_scroll.set()
        self.scrolling = False
        self.stop_afk()
        if self.holding:
            try:
                self.backend.release(self.cfg["holdtoggle"]["target"])
            except Exception:
                pass
            self.holding = False

    def _safe(self, fn, *args):
        try:
            fn(*args)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
