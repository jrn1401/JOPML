"""Rückstoß-Trainer: erfundene Übungswaffen, Designs (Skins), Verlauf und Animations-Hilfen (ohne GUI, testbar).

Alle Waffen hier sind ausgedacht und haben nichts mit echten Spielen oder Waffen zu tun: Sie ändern nur Stärke, Feuerrate,
Schusszahl und Form des Übungsmusters im eigenen Übungsfeld. Der Trainer liest die Maus nur in seinem Fenster und sendet nichts an Spiele.
"""
import math
import time

from . import trainer

# id -> Name, Beschreibung, Stärke, Schuss/s, Schüsse, vert (senkrechter Anteil), sway (seitlicher Anteil)
WEAPONS = {
    "standard": {"name": "Standard", "descr": "The reference weapon. Only this one counts for the leaderboards.",
                 "strength": 1.0, "rate": 10, "shots": trainer.SHOTS, "vert": 1.0, "sway": 1.0},
    "pulse": {"name": "Pulse SMG", "descr": "Fast and light: many shots, weak pull.",
              "strength": 0.7, "rate": 15, "shots": 40, "vert": 0.8, "sway": 1.2},
    "driver": {"name": "Heavy Driver", "descr": "Slow and hard: few shots, strong pull upwards.",
               "strength": 1.5, "rate": 6, "shots": 18, "vert": 1.3, "sway": 0.6},
    "burst": {"name": "Burst Rifle", "descr": "Medium speed with a wobbling pull to the side.",
              "strength": 1.1, "rate": 9, "shots": 24, "vert": 0.9, "sway": 1.6},
    "needle": {"name": "Ion Needler", "descr": "Very fast and long: tests endurance.",
               "strength": 0.6, "rate": 15, "shots": 60, "vert": 0.9, "sway": 1.0},
}
DEFAULT_WEAPON = "standard"


def weapon(wid: str) -> dict:
    return WEAPONS.get(wid) or WEAPONS[DEFAULT_WEAPON]


def weapon_names() -> list:
    return [w["name"] for w in WEAPONS.values()]


def weapon_id(name: str) -> str:
    return next((k for k, w in WEAPONS.items() if w["name"] == name), DEFAULT_WEAPON)


def pattern_for(wid: str, pattern_name: str, seed: int = 0) -> list:
    """Muster der Waffe: Schusszahl, senkrechter und seitlicher Anteil. Stärke wird wie bisher mit trainer.scaled angewendet."""
    w = weapon(wid)
    base = trainer.pattern(pattern_name, seed=seed, shots=int(w["shots"]))
    return [(dx * w["sway"], dy * w["vert"]) for dx, dy in base]


# ------------------------------------------------------------------ Designs
SKINS = {
    "Classic": {"bg": "#111418", "grid": "#1f252c", "target": "#4f8cff", "guide": "#6b7280", "text": "#d1d5db",
                "good": "#2e9d5b", "mid": "#e5a50a", "bad": "#e5484d", "aim": "#ffffff"},
    "Neon": {"bg": "#0a0612", "grid": "#1d1233", "target": "#22d3ee", "guide": "#a855f7", "text": "#f0abfc",
             "good": "#34d399", "mid": "#fde047", "bad": "#fb7185", "aim": "#f0abfc"},
    "Paper": {"bg": "#f4f1e8", "grid": "#e0dccd", "target": "#2563eb", "guide": "#9ca3af", "text": "#1f2937",
              "good": "#15803d", "mid": "#b45309", "bad": "#b91c1c", "aim": "#111827"},
    "Mono": {"bg": "#000000", "grid": "#161616", "target": "#ffffff", "guide": "#666666", "text": "#cccccc",
             "good": "#ffffff", "mid": "#aaaaaa", "bad": "#666666", "aim": "#ffffff"},
    "Sunset": {"bg": "#1c1017", "grid": "#2b1a24", "target": "#fb923c", "guide": "#9d6b7c", "text": "#fde68a",
               "good": "#a3e635", "mid": "#fbbf24", "bad": "#f43f5e", "aim": "#fff7ed"},
}
CROSSHAIRS = ["Ring", "Cross", "Dot"]
MARKERS = ["Dot", "Cross", "Ring"]


def skin(name: str) -> dict:
    return SKINS.get(name) or SKINS["Classic"]


def hit_color(sk: dict, dist: float) -> str:
    return sk["good"] if dist < 10 else (sk["mid"] if dist < 25 else sk["bad"])


# ------------------------------------------------------------------ flüssige Anzeige
class ShotClock:
    """Entkoppelt Schusstakt und Bildrate: bei jedem Bild fragt man, wie viele Schüsse inzwischen fällig sind."""

    def __init__(self, rate: float, start: float = 0.0):
        self.interval = 1.0 / max(1.0, float(rate))
        self.start = start
        self.fired = 0

    def due(self, now: float) -> int:
        """Anzahl der Schüsse, die seit dem letzten Aufruf fällig geworden sind (der erste fällt sofort bei start)."""
        total = int(max(0.0, now - self.start) / self.interval + 1e-9) + 1
        n = max(0, total - self.fired)
        self.fired += n
        return n


def ease(cur: tuple, target: tuple, dt: float, speed: float = 22.0) -> tuple:
    """Gleitet cur in Richtung target; unabhängig von der Bildrate (dt in Sekunden). speed ~ 1/Zeitkonstante."""
    k = 1.0 - math.exp(-max(0.0, dt) * speed)
    return (cur[0] + (target[0] - cur[0]) * k, cur[1] + (target[1] - cur[1]) * k)


def fade(age: float, life: float = 0.6) -> float:
    """1.0 frisch -> 0.0 nach `life` Sekunden (für verblassende Spuren)."""
    if life <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - age / life))


def mix(c1: str, c2: str, t: float) -> str:
    """Mischt zwei #RRGGBB-Farben (t=0 -> c1, t=1 -> c2); damit blenden Spuren ohne Alpha-Kanal in den Hintergrund aus."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


# ------------------------------------------------------------------ Rückmeldung und Verlauf
def drift(hits: list, start: tuple) -> tuple:
    """Mittlere Abweichung der Treffer vom Startpunkt (dx, dy). Positives dy = zu tief."""
    if not hits:
        return 0.0, 0.0
    return (sum(h[0] - start[0] for h in hits) / len(hits), sum(h[1] - start[1] for h in hits) / len(hits))


def drift_hint(hits: list, start: tuple, tolerance: float = 4.0) -> str:
    """Kurzer Tipp, in welche Richtung die Treffer im Mittel abgewichen sind (Englisch = Quelltext, wird mit tr() angezeigt)."""
    dx, dy = drift(hits, start)
    parts = []
    if dy > tolerance:
        parts.append("Your hits ended too low: pull a bit less.")
    elif dy < -tolerance:
        parts.append("Your hits ended too high: pull down more.")
    if dx > tolerance:
        parts.append("Your hits drifted to the right: correct more to the left.")
    elif dx < -tolerance:
        parts.append("Your hits drifted to the left: correct more to the right.")
    return " ".join(parts) if parts else "Well centered – no clear drift."


HISTORY_MAX = 50


def add_history(history, entry: dict) -> list:
    """Hängt eine Runde an (neueste zuletzt), höchstens HISTORY_MAX; ungültige Einträge werden verworfen."""
    out = [e for e in (history if isinstance(history, list) else []) if isinstance(e, dict)]
    try:
        out.append({"score": int(entry["score"]), "avg": float(entry["avg"]), "shots": int(entry["shots"]),
                    "weapon": str(entry.get("weapon", DEFAULT_WEAPON))[:20], "pattern": str(entry.get("pattern", ""))[:30],
                    "t": int(entry.get("t", time.time()))})
    except (KeyError, TypeError, ValueError):
        return out[-HISTORY_MAX:]
    return out[-HISTORY_MAX:]


def stats(history) -> dict:
    """Kennzahlen über den Verlauf: Runden, Bestwert, Mittel, Trend (Mittel der letzten 5 minus der 5 davor), Serie ab 75 Punkten."""
    h = [e for e in (history if isinstance(history, list) else []) if isinstance(e, dict) and isinstance(e.get("score"), int)]
    if not h:
        return {"rounds": 0, "best": 0, "average": 0.0, "trend": 0.0, "streak": 0}
    scores = [e["score"] for e in h]
    last, before = scores[-5:], scores[-10:-5]
    trend = (sum(last) / len(last) - sum(before) / len(before)) if before else 0.0
    streak = 0
    for s in reversed(scores):
        if s < 75:
            break
        streak += 1
    return {"rounds": len(scores), "best": max(scores), "average": round(sum(scores) / len(scores), 1),
            "trend": round(trend, 1), "streak": streak}


def sparkline(history, width: int, height: int, pad: int = 4) -> list:
    """Punkte (x, y) der letzten Punktzahlen (0..100) für ein kleines Liniendiagramm."""
    scores = [e["score"] for e in (history if isinstance(history, list) else []) if isinstance(e, dict) and isinstance(e.get("score"), int)][-30:]
    if not scores:
        return []
    step = (width - 2 * pad) / max(1, len(scores) - 1)
    return [(round(pad + i * step, 1), round(height - pad - (s / 100) * (height - 2 * pad), 1)) for i, s in enumerate(scores)]
