"""Rückstoß-Trainer – die Logik (ohne GUI).

Der Trainer simuliert eine Waffe im eigenen Übungsfeld: Solange die linke Maustaste gedrückt ist, fällt alle paar
Millisekunden ein Schuss, und jeder Schuss reißt das Ziel nach oben/zur Seite. Du gleichst das mit der Maus aus.
Bewertet wird, wie nah die Treffer am Startpunkt bleiben.

Wichtig: Der Trainer liest die Maus nur innerhalb seines eigenen Fensters und erzeugt selbst keine Eingaben.
Er bewegt nie deine Maus und funktioniert nicht in Spielen – du trainierst deine Hand, nicht ein Script.
"""
import math
import random

SHOTS = 30

PATTERNS = {
    "Gerade hoch": "Klassisch: Der Rückstoß zieht stark nach oben und wird nach 10 Schüssen etwas schwächer.",
    "Hoch, dann rechts": "Erst nach oben, ab Schuss 11 zieht es nach rechts.",
    "Zickzack": "Nach oben und abwechselnd nach links und rechts.",
    "Zufall": "Jede Runde ein neues Muster – zum Testen, ob du wirklich reagierst.",
}


# Bestenliste in der Community: je Muster eine Liste (Schlüssel wie auf dem Server). Gezählt wird nur eine volle Runde mit den
# Standardwerten (Stärke 1, 10 Schuss/s, ohne Hilfslinie), damit die Listen vergleichbar bleiben.
BOARD_KINDS = {"Gerade hoch": "recoil_up", "Hoch, dann rechts": "recoil_right", "Zickzack": "recoil_zigzag", "Zufall": "recoil_random"}
STD_STRENGTH, STD_RATE = 1.0, 10


def board_kind(pattern_name: str, shots: int, strength: float, rate: int, guide: bool) -> str:
    """Name der Bestenliste, in die diese Runde zählt - oder '' (Runde unvollständig, geänderte Stärke/Feuerrate oder Hilfslinie an)."""
    if guide or shots < SHOTS or abs(float(strength) - STD_STRENGTH) > 0.01 or int(rate) != STD_RATE:
        return ""
    return BOARD_KINDS.get(pattern_name, "")


def pattern(name: str, seed: int = 0) -> list:
    """Rückstoß je Schuss als (dx, dy) in Pixeln. Negatives dy = nach oben."""
    out = []
    rnd = random.Random(seed)
    for i in range(SHOTS):
        if name == "Gerade hoch":
            out.append((0.0, -8.0 if i < 10 else -4.5))
        elif name == "Hoch, dann rechts":
            out.append((0.0, -8.0) if i < 10 else (5.5, -2.0))
        elif name == "Zickzack":
            out.append((5.0 if (i // 5) % 2 else -5.0, -6.0 if i < 12 else -3.5))
        else:
            out.append((rnd.uniform(-5, 5), rnd.uniform(-9, -3)))
    return out


def scaled(pat: list, strength: float) -> list:
    strength = max(0.3, min(3.0, float(strength)))
    return [(dx * strength, dy * strength) for dx, dy in pat]


def ideal_path(start: tuple, pat: list) -> list:
    """Wo die Maus bei jedem Schuss sein müsste, damit jeder Treffer genau im Ziel landet (zum Anzeigen als Hilfslinie)."""
    x, y = start
    path, rx, ry = [], 0.0, 0.0
    for dx, dy in pat:
        path.append((x - rx, y - ry))      # Rückstoß VOR diesem Schuss (so rechnet Round.shot)
        rx, ry = rx + dx, ry + dy
    return path


class Round:
    """Eine Übungsrunde. Die Oberfläche ruft start(), shot(maus_x, maus_y) im Schuss-Takt und stop() auf."""

    def __init__(self, pat: list):
        self.pat = pat
        self.start_pos = (0.0, 0.0)
        self.recoil = [0.0, 0.0]
        self.hits = []                 # (x, y) der Treffer

    def start(self, x: float, y: float) -> None:
        self.start_pos = (float(x), float(y))
        self.recoil = [0.0, 0.0]
        self.hits = []

    @property
    def done(self) -> bool:
        return len(self.hits) >= len(self.pat)

    def shot(self, mx: float, my: float):
        """Ein Schuss: Treffer = Mausposition + bisher aufgebauter Rückstoß. Danach kommt der Rückstoß dieses Schusses dazu."""
        if self.done:
            return None
        hit = (mx + self.recoil[0], my + self.recoil[1])
        self.hits.append(hit)
        dx, dy = self.pat[len(self.hits) - 1]
        self.recoil[0] += dx
        self.recoil[1] += dy
        return hit

    def aim(self, mx: float, my: float) -> tuple:
        """Wo der nächste Schuss gerade landen würde."""
        return mx + self.recoil[0], my + self.recoil[1]

    def distance(self, hit) -> float:
        return math.hypot(hit[0] - self.start_pos[0], hit[1] - self.start_pos[1])

    def result(self) -> dict:
        if not self.hits:
            return {"shots": 0, "avg": 0.0, "score": 0, "rating": ""}
        avg = sum(self.distance(h) for h in self.hits) / len(self.hits)
        score = rate(avg)
        # ohne Ausgleich: wie weit wären die Treffer gelandet? (zum Vergleich)
        raw, rx, ry = 0.0, 0.0, 0.0
        for dx, dy in self.pat[:len(self.hits)]:
            raw += math.hypot(rx, ry)
            rx, ry = rx + dx, ry + dy
        return {"shots": len(self.hits), "avg": round(avg, 1), "score": score,
                "rating": rating(score), "without": round(raw / len(self.hits), 1)}


def rate(avg_px: float) -> int:
    return max(0, min(100, round(100 - avg_px * 2)))


def rating(score: int) -> str:
    if score >= 90:
        return "Laser! 🎯"
    if score >= 75:
        return "Sehr gut"
    if score >= 55:
        return "Gut – noch etwas gleichmäßiger ziehen"
    if score >= 30:
        return "Geht so – schau dir die Hilfslinie an"
    return "Weiter üben – zieh die Maus gegen den Rückstoß nach unten"


def color_for(dist: float) -> str:
    return "#2e9d5b" if dist < 10 else ("#e5a50a" if dist < 25 else "#e5484d")
