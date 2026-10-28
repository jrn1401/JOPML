"""Fenster-Manager: aktives Fenster in Hälften/Viertel schieben, Layouts für mehrere Fenster."""
from dataclasses import dataclass

from core.i18n import tr

KINDS = ["left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right", "center", "maximize"]
DEFAULT_KEYS = {
    "left": "<ctrl>+<alt>+<left>", "right": "<ctrl>+<alt>+<right>", "top": "<ctrl>+<alt>+<up>", "bottom": "<ctrl>+<alt>+<down>",
    "top-left": "<ctrl>+<alt>+u", "top-right": "<ctrl>+<alt>+i", "bottom-left": "<ctrl>+<alt>+j", "bottom-right": "<ctrl>+<alt>+k",
    "center": "<ctrl>+<alt>+c", "maximize": "<ctrl>+<alt>+<enter>",
}


NEXT_MONITOR_KEY = "<ctrl>+<alt>+m"          # Fenster auf den nächsten Monitor


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


MAX_MONITOR = 8


@dataclass
class Slot:
    match: str                  # Teil des Fenstertitels oder Programmnamens
    kind: str                   # eine Position aus KINDS oder "saved" (genaue gespeicherte Lage in `rect`)
    monitor: int = 0            # 0 = Hauptmonitor, 1.. = Monitor von links nach rechts
    rect: tuple | None = None   # nur bei "saved": (x, y, b, h) als Bruchteile (0..1) der Arbeitsfläche des Monitors

    def validate(self) -> "Slot":
        self.match = (self.match or "").strip()
        if len(self.match) < 2:
            raise ValueError(tr("Enter at least 2 characters of the window or program name."))
        try:
            self.monitor = int(self.monitor)
        except (TypeError, ValueError):
            raise ValueError(tr("Unknown monitor."))
        if not 0 <= self.monitor <= MAX_MONITOR:
            raise ValueError(tr("Unknown monitor."))
        if self.kind == "saved":
            r = self.rect
            if not (isinstance(r, (list, tuple)) and len(r) == 4 and all(isinstance(v, (int, float)) for v in r)
                    and 0 <= r[0] <= 1 and 0 <= r[1] <= 1 and 0.02 <= r[2] <= 1.5 and 0.02 <= r[3] <= 1.5):
                raise ValueError(tr("Unknown layout position."))
            self.rect = tuple(float(v) for v in r)
        elif self.kind not in KINDS:
            raise ValueError(tr("Unknown layout position."))
        else:
            self.rect = None
        return self

    def label(self) -> str:
        where = tr("saved position") if self.kind == "saved" else self.kind
        return f"{self.match} → {where}" + (f" ({tr('monitor')} {self.monitor})" if self.monitor else "")


def parse_slot(text: str) -> Slot:
    """"chrome:left" oder "chrome:left@2" (Monitor 2) → geprüfter Platz."""
    m, _, rest = text.partition(":")
    kind, _, mon = rest.partition("@")
    return Slot(m, kind.strip().lower(), int(mon) if mon.strip().isdigit() else (0 if not mon.strip() else -1)).validate()


def rel_rect(rect: tuple, area: tuple) -> tuple:
    """Fenster (links, oben, rechts, unten) als Bruchteile (x, y, b, h) der Arbeitsfläche area = (x, y, b, h)."""
    ax, ay, aw, ah = area
    l, t, r, b = rect
    aw, ah = max(1, aw), max(1, ah)
    clamp = lambda v: round(max(0.0, min(1.0, v)), 4)
    return clamp((l - ax) / aw), clamp((t - ay) / ah), round(max(0.02, min(1.5, (r - l) / aw)), 4), round(max(0.02, min(1.5, (b - t) / ah)), 4)


def abs_rect(frac: tuple, area: tuple) -> tuple[int, int, int, int]:
    ax, ay, aw, ah = area
    return round(ax + frac[0] * aw), round(ay + frac[1] * ah), round(frac[2] * aw), round(frac[3] * ah)


def monitor_of_rect(rect: tuple, mons: list[dict]):
    """Monitor (Eintrag aus winutil.monitors()), in dem die Mitte des Fensters liegt; sonst der nächste; ohne Monitore None."""
    if not mons:
        return None
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2

    def dist(m):
        x, y, w, h = m["full"]
        dx = max(x - cx, 0, cx - (x + w))
        dy = max(y - cy, 0, cy - (y + h))
        return dx * dx + dy * dy
    return min(mons, key=dist)


def next_monitor(current_no: int, mons: list[dict]):
    """Der Monitor nach `current_no` (Nummer) in der Reihenfolge links → rechts, am Ende wieder der erste."""
    if not mons:
        return None
    nums = sorted(m["no"] for m in mons)
    nxt = next((n for n in nums if n > current_no), nums[0])
    return next(m for m in mons if m["no"] == nxt)


def slot_rect(slot: Slot, area: tuple, areas: dict | None = None) -> tuple[int, int, int, int]:
    """Zielrechteck für einen Platz: Arbeitsfläche des gewählten Monitors (fehlt er, die des Hauptmonitors) + Position."""
    a = (areas or {}).get(slot.monitor) or area
    return abs_rect(slot.rect, a) if slot.kind == "saved" and slot.rect else snap_rect(slot.kind, a)


def parse_layouts(data) -> dict[str, list[Slot]]:
    out: dict[str, list[Slot]] = {}
    for name, slots in (list(data.items())[:20] if isinstance(data, dict) else []):
        good = []
        for s in slots if isinstance(slots, list) else []:
            try:
                good.append(Slot(s["match"], s["kind"], s.get("monitor", 0), s.get("rect")).validate())
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
        if good:
            out[str(name)[:40]] = good[:12]
    return out


def apply_layout(slots: list[Slot], windows: list[dict], area, move, areas: dict | None = None) -> int:
    """Schiebt für jeden Platz das erste passende, noch freie Fenster. move(win_id, x, y, w, h) -> Fehlertext/''.
    areas = {Monitor-Nr: Arbeitsfläche} (0 = Hauptmonitor); ohne Angabe gilt überall `area`. Gibt die Zahl der verschobenen Fenster zurück."""
    used: set = set()
    moved = 0
    for slot in slots:
        for w in windows:
            if w["id"] in used:
                continue
            if slot.match.lower() in f"{w.get('title', '')} {w.get('proc', '')}".lower():
                used.add(w["id"])
                if not move(w["id"], *slot_rect(slot, area, areas)):
                    moved += 1
                break
    return moved
