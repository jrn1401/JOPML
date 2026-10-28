"""Zwischenablage-Verlauf mit Suche und Anheften. Der Verlauf bleibt im Arbeitsspeicher; nur angeheftete Einträge werden gespeichert."""
MAX_ITEMS = 50
MAX_LEN = 5000
MAX_PINS = 30


class ClipHistory:
    def __init__(self, pins=None):
        self.items: list[str] = []                 # neueste zuerst
        self.pins: list[str] = [p for p in (pins or []) if isinstance(p, str)][:MAX_PINS]
        self.paused = False

    def add(self, text: str) -> bool:
        """Gibt True zurück, wenn etwas Neues aufgenommen wurde."""
        if self.paused or not isinstance(text, str):
            return False
        t = text.strip("\x00")
        if not t.strip() or len(t) > MAX_LEN:
            return False
        if self.items and self.items[0] == t:
            return False
        if t in self.items:
            self.items.remove(t)
        self.items.insert(0, t)
        del self.items[MAX_ITEMS:]
        return True

    def pin(self, text: str) -> bool:
        if text in self.pins or len(self.pins) >= MAX_PINS:
            return False
        self.pins.insert(0, text)
        return True

    def unpin(self, text: str):
        if text in self.pins:
            self.pins.remove(text)

    def remove(self, text: str):
        if text in self.items:
            self.items.remove(text)

    def clear(self):
        self.items.clear()

    def search(self, q: str) -> tuple[list[str], list[str]]:
        """(angeheftet, Verlauf) gefiltert nach q (Groß-/Kleinschreibung egal); Angeheftete erscheinen nicht doppelt im Verlauf."""
        ql = (q or "").strip().lower()
        ok = (lambda t: ql in t.lower()) if ql else (lambda t: True)
        return [t for t in self.pins if ok(t)], [t for t in self.items if ok(t) and t not in self.pins]


def preview(text: str, n: int = 90) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[:n - 1] + "…"
