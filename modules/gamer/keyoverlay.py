"""Tasten-Overlay: zeigt WASD, Leertaste, Maustasten und zuletzt gedrückte Tasten live an (z. B. für Streams)."""
import sys
import time

GRID = [["", "w", ""], ["a", "s", "d"]]
EXTRA = ["shift", "ctrl", "space"]


class KeyState:
    def __init__(self, clock=time.monotonic, recent_s: float = 1.2, flash_s: float = 0.25):
        self.clock, self.recent_s, self.flash_s = clock, recent_s, flash_s
        self.down: set[str] = set()
        self.flash: dict[str, float] = {}          # Tasten, bei denen wir nur das Drücken kennen (macOS)
        self.recent: list[tuple[float, str]] = []

    def press(self, name: str):
        self.down.add(name)
        if not name.startswith("mouse"):
            self.recent.append((self.clock(), name))
            del self.recent[:-12]

    def release(self, name: str):
        self.down.discard(name)

    def tap(self, name: str):
        """Nur 'gedrückt' bekannt: kurz aufleuchten lassen."""
        self.flash[name] = self.clock() + self.flash_s
        self.press(name)
        self.down.discard(name)

    def is_down(self, name: str) -> bool:
        return name in self.down or self.flash.get(name, 0) > self.clock()

    def recent_keys(self) -> list[str]:
        now = self.clock()
        return [n for t, n in self.recent if now - t <= self.recent_s]


def pynput_name(key) -> str:
    ch = getattr(key, "char", None)
    if ch:
        return ch.lower()
    n = getattr(key, "name", "") or ""
    for base in ("shift", "ctrl", "alt", "cmd"):
        if n.startswith(base):
            return base
    return n


class KeyListener:
    """Hört auf Tastatur und Maus. Auf macOS gibt es nur 'gedrückt' für Tasten (Quartz), Maus komplett."""

    def __init__(self, state: KeyState):
        self.state = state
        self._ls: list = []
        self.error = ""

    def start(self) -> str:
        try:
            from pynput import mouse
            ml = mouse.Listener(on_click=lambda x, y, b, p: (self.state.press if p else self.state.release)(
                "mouse_" + str(b).split(".")[-1]))
            ml.daemon = True
            ml.start()
            self._ls.append(ml)
            if sys.platform == "darwin":
                from core import mackeys
                tap = mackeys.KeyTap(lambda code, flags: self.state.tap(mackeys.key_name(code) or ""))
                tap.start()
                self._ls.append(tap)
            else:
                from pynput import keyboard
                kl = keyboard.Listener(on_press=lambda k: self.state.press(pynput_name(k)),
                                       on_release=lambda k: self.state.release(pynput_name(k)))
                kl.daemon = True
                kl.start()
                self._ls.append(kl)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.stop()
        return self.error

    def stop(self):
        for l in self._ls:
            try:
                l.stop()
            except Exception:
                pass
        self._ls = []
