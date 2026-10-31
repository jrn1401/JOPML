"""Rückstoß-Trainer 3D – Logik und Zeichen-Anweisungen (ohne GUI, deshalb testbar).

Ein Übungsraum in echter Perspektive: Du siehst auf eine Zielscheibe an der Rückwand (nah, mittel oder weit weg, fest oder
seitlich laufend). Der Rückstoß der Übungswaffe ist ein frei erfundenes Muster. Nach der Runde kannst du den Raum in 3D drehen und
siehst alle Schüsse als Linien vom Schützen bis zur Wand.

Wie der 2D-Trainer liest er die Maus nur im eigenen Feld und erzeugt selbst keine Eingaben. Er hat nichts mit einem bestimmten Spiel
zu tun und liest oder verändert kein Spiel.
"""
import math

from . import trainer

F = 600.0                      # Brennweite in Pixeln (Bildschirmpunkte je Meter bei 1 m Abstand)
ROOM_W, FLOOR, CEIL = 6.0, -1.6, 3.4
TARGET_R = 0.5                 # Radius der Scheibe in Metern
TARGET_Y = 0.2
SHOTS = trainer.SHOTS

DISTANCES = {"Nah (10 m)": 10.0, "Mittel (25 m)": 25.0, "Weit (50 m)": 50.0}
TARGET_MODES = {"Fest": "Die Scheibe steht still.", "Läuft seitlich": "Die Scheibe pendelt links und rechts – du verfolgst sie."}
STRAFE_AMP, STRAFE_PERIOD = 3.0, 4.0     # Meter, Sekunden


def depth(name: str) -> float:
    return DISTANCES.get(name, 25.0)


def target_x(mode: str, t: float) -> float:
    """Seitliche Position der Scheibe (Meter) zur Zeit t (Sekunden)."""
    if mode == "Läuft seitlich":
        return STRAFE_AMP * math.sin(2 * math.pi * t / STRAFE_PERIOD)
    return 0.0


def to_wall(px: float, py: float, cx: float, cy: float, d: float) -> tuple:
    """Bildschirmpunkt -> Punkt auf der Rückwand in Metern (x nach rechts, y nach oben)."""
    return d * (px - cx) / F, d * (cy - py) / F


def from_wall(x: float, y: float, cx: float, cy: float, d: float) -> tuple:
    return cx + F * x / d, cy - F * y / d


def target_radius_px(d: float) -> float:
    return F * TARGET_R / d


class Round3D:
    """Eine 3D-Runde. Rückstoß-Logik kommt aus trainer.Round (gleiches Muster wie in 2D); hier kommt Raum und Scheibe dazu."""

    def __init__(self, pattern_name: str, dist_name: str, mode: str, strength: float, rate: int, seed: int, cx: float, cy: float,
                 weapon: str = "standard"):
        self.weapon = weapon
        self.pattern_name, self.dist_name, self.mode = pattern_name, dist_name, mode
        self.strength, self.rate = float(strength), int(rate)
        self.d = depth(dist_name)
        self.cx, self.cy = cx, cy
        from . import weapons
        self.core = trainer.Round(trainer.scaled(weapons.pattern_for(weapon, pattern_name, seed), strength))
        self.core.start(cx, cy)
        self.shots = []            # je Schuss: dict(wall=(x, y), tx=Scheibenposition, dist=Meter, hit=bool)

    @property
    def done(self) -> bool:
        return self.core.done

    def time_of(self, i: int) -> float:
        return i / max(1, self.rate)

    def shoot(self, mx: float, my: float):
        i = len(self.shots)
        hit = self.core.shot(mx, my)
        if hit is None:
            return None
        wx, wy = to_wall(hit[0], hit[1], self.cx, self.cy, self.d)
        tx = target_x(self.mode, self.time_of(i))
        dist = math.hypot(wx - tx, wy - TARGET_Y)
        rec = {"wall": (wx, wy), "tx": tx, "dist": dist, "hit": dist <= TARGET_R}
        self.shots.append(rec)
        return rec

    def target_px(self, t: float) -> tuple:
        return from_wall(target_x(self.mode, t), TARGET_Y, self.cx, self.cy, self.d)

    def result(self) -> dict:
        n = len(self.shots)
        if not n:
            return {"shots": 0, "hits": 0, "accuracy": 0, "avg": 0.0, "score": 0, "rating": ""}
        hits = sum(1 for s in self.shots if s["hit"])
        avg = sum(s["dist"] for s in self.shots) / n          # Meter
        score = score_for(avg)
        return {"shots": n, "hits": hits, "accuracy": round(100 * hits / n), "avg": round(avg / TARGET_R, 2),
                "score": score, "rating": trainer.rating(score)}


def score_for(avg_m: float) -> int:
    """0..100: ein Mittel von 0 Radien = 100, ab 4 Scheibenradien Abstand 0."""
    return max(0, min(100, round(100 * (1 - avg_m / (4 * TARGET_R)))))


# ------------------------------------------------------------------ Kamera und Projektion
class Camera:
    """Umlaufkamera um einen Drehpunkt. yaw/pitch in Radiant, dist in Metern."""

    def __init__(self, pivot=(0.0, 0.4, 12.0), yaw=0.7, pitch=0.35, dist=30.0, width=560, height=440):
        self.pivot, self.yaw, self.pitch, self.dist = pivot, yaw, pitch, dist
        self.w, self.h = width, height

    def rotate(self, dyaw: float, dpitch: float) -> None:
        self.yaw += dyaw
        self.pitch = max(-1.2, min(1.4, self.pitch + dpitch))

    def zoom(self, factor: float) -> None:
        self.dist = max(6.0, min(120.0, self.dist * factor))

    def position(self) -> tuple:
        px, py, pz = self.pivot
        cp = math.cos(self.pitch)
        return (px + self.dist * math.sin(self.yaw) * cp, py + self.dist * math.sin(self.pitch), pz - self.dist * math.cos(self.yaw) * cp)

    def project(self, p: tuple):
        """(sx, sy, tiefe) oder None, wenn der Punkt hinter der Kamera liegt."""
        pos = self.position()
        f = _norm(_sub(self.pivot, pos))
        right = _norm(_cross((0.0, 1.0, 0.0), f))
        up = _cross(f, right)
        v = _sub(p, pos)
        z = _dot(v, f)
        if z < 0.2:
            return None
        k = F * (min(self.w, self.h) / 440.0) / z
        return self.w / 2 + k * _dot(v, right), self.h / 2 - k * _dot(v, up), z


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


# ------------------------------------------------------------------ Zeichen-Anweisungen
# Eine Anweisung ist ("line", [(x, y), ...], farbe, breite) | ("oval", (x0, y0, x1, y1), farbe, füllung) | ("text", (x, y), text, farbe).
def _room_edges(d: float) -> list:
    z0, z1 = 0.5, d
    xs, ys = ROOM_W, (FLOOR, CEIL)
    pts = [(-xs, ys[0]), (xs, ys[0]), (xs, ys[1]), (-xs, ys[1])]
    edges = []
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        edges.append(((a[0], a[1], z0), (b[0], b[1], z0)))      # vorderer Rahmen
        edges.append(((a[0], a[1], z1), (b[0], b[1], z1)))      # Rückwand
        edges.append(((a[0], a[1], z0), (a[0], a[1], z1)))      # Kanten nach hinten
    return edges


def _floor_grid(d: float) -> list:
    lines = []
    for x in range(-int(ROOM_W), int(ROOM_W) + 1, 2):
        lines.append(((float(x), FLOOR, 0.5), (float(x), FLOOR, d)))
    z = 5.0
    while z <= d:
        lines.append(((-ROOM_W, FLOOR, z), (ROOM_W, FLOOR, z)))
        z += 5.0 if d <= 25 else 10.0
    return lines


def _circle(cx: float, cy: float, z: float, r: float, n: int = 28) -> list:
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n + 1)]


def orbit_primitives(cam: Camera, rd: Round3D) -> list:
    """3D-Ansicht nach der Runde: Raum, Scheibe, Einschüsse und Linien vom Schützen zur Wand."""
    out = []

    def line(a, b, col, w=1):
        pa, pb = cam.project(a), cam.project(b)
        if pa and pb:
            out.append(("line", [pa[:2], pb[:2]], col, w))

    for a, b in _floor_grid(rd.d):
        line(a, b, "#1f252c")
    for a, b in _room_edges(rd.d):
        line(a, b, "#3b4552")
    shooter = (0.0, 0.0, 0.0)
    for rad, col in ((TARGET_R, "#4f8cff"), (TARGET_R / 2, "#4f8cff"), (TARGET_R * 2, "#2a4f99")):
        pts = [cam.project(p) for p in _circle(0.0, TARGET_Y, rd.d, rad)]
        if all(pts):
            out.append(("line", [p[:2] for p in pts], col, 2 if rad == TARGET_R else 1))
    if rd.mode == "Läuft seitlich":
        line((-STRAFE_AMP, TARGET_Y, rd.d), (STRAFE_AMP, TARGET_Y, rd.d), "#2a4f99")
    for s in rd.shots:
        wx, wy = s["wall"]
        col = trainer.color_for(s["dist"] / TARGET_R * 10)
        line(shooter, (wx, wy, rd.d), "#2c333b")
        p = cam.project((wx, wy, rd.d))
        if p:
            r = max(2.0, 5.0 * 20.0 / max(cam.dist, 10.0))
            out.append(("oval", (p[0] - r, p[1] - r, p[0] + r, p[1] + r), col, col))
    sp = cam.project(shooter)
    if sp:
        out.append(("oval", (sp[0] - 4, sp[1] - 4, sp[0] + 4, sp[1] + 4), "#ffffff", ""))
    out.append(("text", (10, 10), f"3D: ziehen = drehen, Mausrad = zoomen   ·   {rd.pattern_name}, {rd.dist_name}", "#d1d5db"))
    return out


def play_primitives(rd: Round3D, mouse: tuple, t: float, w: float, h: float) -> list:
    """Live-Ansicht aus Schützen-Sicht: Raum in Perspektive, Scheibe (wandert evtl.), Einschüsse, Fadenkreuz."""
    cx, cy = rd.cx, rd.cy
    out = []

    def proj(x, y, z):
        return cx + F * x / z, cy - F * y / z

    for a, b in _floor_grid(rd.d):
        out.append(("line", [proj(*a), proj(*b)], "#1f252c", 1))
    for a, b in _room_edges(rd.d):
        out.append(("line", [proj(*a), proj(*b)], "#3b4552", 1))
    tx = target_x(rd.mode, t)
    for rad, col, wd in ((TARGET_R * 2, "#2a4f99", 1), (TARGET_R, "#4f8cff", 2), (TARGET_R / 2, "#4f8cff", 1)):
        x0, y0 = proj(tx - rad, TARGET_Y + rad, rd.d)
        x1, y1 = proj(tx + rad, TARGET_Y - rad, rd.d)
        out.append(("oval", (x0, y0, x1, y1), col, ""))
    for s in rd.shots:
        sx, sy = proj(s["wall"][0], s["wall"][1], rd.d)
        col = trainer.color_for(s["dist"] / TARGET_R * 10)
        out.append(("oval", (sx - 3, sy - 3, sx + 3, sy + 3), col, col))
    if not rd.done:
        ax, ay = rd.core.aim(*mouse)
        out.append(("oval", (ax - 6, ay - 6, ax + 6, ay + 6), "#ffffff", ""))
    out.append(("text", (10, 10), f"{rd.pattern_name} · {rd.dist_name} · {rd.mode}   Schuss {len(rd.shots)}/{SHOTS}", "#d1d5db"))
    return out
