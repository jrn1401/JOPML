"""Fenster-Manager: aktives Fenster in Hälften/Viertel schieben, Layouts für mehrere Fenster."""
from dataclasses import dataclass

from core.i18n import tr

KINDS = ["left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right", "center", "maximize"]
DEFAULT_KEYS = {
    "left": "<ctrl>+<alt>+<left>", "right": "<ctrl>+<alt>+<right>", "top": "<ctrl>+<alt>+<up>", "bottom": "<ctrl>+<alt>+<down>",
    "top-left": "<ctrl>+<alt>+u", "top-right": "<ctrl>+<alt>+i", "bottom-left": "<ctrl>+<alt>+j", "bottom-right": "<ctrl>+<alt>+k",
    "center": "<ctrl>+<alt>+c", "maximize": "<ctrl>+<alt>+<enter>",
}


def snap_rect(kind: str, area: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Rechteck (x, y, b, h) für `kind` innerhalb der Arbeitsfläche area = (x, y, b, h)."""
    x, y, w, h = area
    hw, hh = w // 2, h // 2
    table = {
        "left": (x, y, hw, h), "right": (x + hw, y, w - hw, h), "top": (x, y, w, hh), "bottom": (x, y + hh, w, h - hh),
        "top-left": (x, y, hw, hh), "top-right": (x + hw, y, w - hw, hh),
        "bottom-left": (x, y + hh, hw, h - hh), "bottom-right": (x + hw, y + hh, w - hw, h - hh),
        "center": (x + w // 5, y + h // 10, w * 3 // 5, h * 8 // 10), "maximize": (x, y, w, h),
    }
    if kind not in table:
        raise ValueError(tr("Unknown layout position."))
    return table[kind]


@dataclass
class Slot:
    match: str      # Teil des Fenstertitels oder Programmnamens
    kind: str       # eine Position aus KINDS

    def validate(self) -> "Slot":
        self.match = (self.match or "").strip()
        if len(self.match) < 2:
            raise ValueError(tr("Enter at least 2 characters of the window or program name."))
        if self.kind not in KINDS:
            raise ValueError(tr("Unknown layout position."))
        return self


def parse_layouts(data) -> dict[str, list[Slot]]:
    out: dict[str, list[Slot]] = {}
    for name, slots in (list(data.items())[:20] if isinstance(data, dict) else []):
        good = []
        for s in slots if isinstance(slots, list) else []:
            try:
                good.append(Slot(s["match"], s["kind"]).validate())
            except (KeyError, TypeError, ValueError):
                pass
        if good:
            out[str(name)[:40]] = good[:12]
    return out


def apply_layout(slots: list[Slot], windows: list[dict], area, move) -> int:
    """Schiebt für jeden Platz das erste passende, noch freie Fenster. move(win_id, x, y, w, h) -> Fehlertext/''.
    Gibt die Zahl der verschobenen Fenster zurück."""
    used: set = set()
    moved = 0
    for slot in slots:
        for w in windows:
            if w["id"] in used:
                continue
            if slot.match.lower() in f"{w.get('title', '')} {w.get('proc', '')}".lower():
                used.add(w["id"])
                if not move(w["id"], *snap_rect(slot.kind, area)):
                    moved += 1
                break
    return moved
