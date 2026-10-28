"""Farb-Trigger: beobachtet einen Bildschirmpunkt und startet ein Makro, sobald dort die Zielfarbe erscheint."""
import threading
import time

from core.i18n import tr


def parse_hex(h: str) -> tuple[int, int, int]:
    h = (h or "").strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(tr("Colour must look like #ff8800."))
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        raise ValueError(tr("Colour must look like #ff8800.")) from None


def distance(a, b) -> int:
    """Größter Unterschied eines Farbkanals (0–255)."""
    return max(abs(int(x) - int(y)) for x, y in zip(a[:3], b[:3]))


def matches(pixel, target, tolerance: int) -> bool:
    return distance(pixel, target) <= max(0, min(255, int(tolerance)))


def grab_pixel(x: int, y: int):
    """Farbe eines Bildschirmpunkts (RGB). Wirft eine Exception, wenn der Bildschirm nicht gelesen werden darf."""
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=(int(x), int(y), int(x) + 1, int(y) + 1))
    return img.convert("RGB").getpixel((0, 0))


class PixelWatcher:
    """Prüft alle `interval` Sekunden. on_trigger() wird bei einem Treffer aufgerufen; danach `cooldown` Sekunden Pause
    (oder Stopp, wenn once=True). grab ist austauschbar (Tests)."""

    def __init__(self, x, y, color, tolerance, on_trigger, interval=0.1, cooldown=2.0, once=False, grab=grab_pixel, on_error=None, on_change=False):
        self.x, self.y = int(x), int(y)
        self.on_change = bool(on_change)               # True: auslösen, sobald sich die Farbe überhaupt ändert
        self.target = None if self.on_change else (parse_hex(color) if isinstance(color, str) else tuple(color))
        self.base = None
        self.tolerance, self.on_trigger = int(tolerance), on_trigger
        self.interval = max(0.02, float(interval))
        self.cooldown, self.once, self.grab, self.on_error = float(cooldown), once, grab, on_error
        self._stop = threading.Event()
        self._t = None
        self.hits = 0

    @property
    def running(self) -> bool:
        return self._t is not None and self._t.is_alive()

    def start(self):
        self._stop.clear()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def join(self, timeout=2):
        if self._t:
            self._t.join(timeout)

    def _hit(self, px) -> bool:
        if not self.on_change:
            return matches(px, self.target, self.tolerance)
        if self.base is None:                           # erster Messwert = Ausgangsfarbe
            self.base = px
            return False
        if distance(px, self.base) > max(0, self.tolerance):
            self.base = px
            return True
        return False

    def _run(self):
        while not self._stop.is_set():
            try:
                px = self.grab(self.x, self.y)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"{type(exc).__name__}: {exc}")
                return
            if self._hit(px):
                self.hits += 1
                try:
                    self.on_trigger()
                except Exception:
                    pass
                if self.once:
                    return
                if self._stop.wait(self.cooldown):
                    return
            elif self._stop.wait(self.interval):
                return
