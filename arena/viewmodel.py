"""Waffen in der Hand: jede Waffe hat eigenes Aussehen und eigene Oberfläche (gebürstetes Metall, Polymer, Holzmaserung, Tarnmuster,
Carbon, Gummigriff), plus Handschuhe und Ärmel. Alles wird beim ersten Mal aus Formen berechnet (numpy) - keine Bilddateien.
make() liefert ein RGBA-Bild; png() macht daraus Bytes für tkinter.PhotoImage."""
import math
import struct
import zlib

import numpy as np

DW, DH = 1000.0, 620.0                 # Entwurfsfläche (Einheiten); Mündung links, Schaft rechts
PIVOT = (780.0, 330.0)
TILT = math.radians(11)               # leichte Drehung: Mündung zeigt nach links oben zur Bildmitte
_cache = {}


# ------------------------------------------------------------------ Rauschen
def _hash(ix, iy, seed=0):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF).astype(np.float32) / 65535.0


def _vnoise(x, y, seed=0):
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(x0, y0, seed), _hash(x0 + 1, y0, seed)
    c, d = _hash(x0, y0 + 1, seed), _hash(x0 + 1, y0 + 1, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _rgb(c):
    if isinstance(c, str):
        return np.array([int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)
    return np.array(c, np.float32)


# ------------------------------------------------------------------ Oberflächen (Entwurfskoordinaten -> Farbe 0..1)
def _tex(mat, X, Y):
    kind, col = mat[0], _rgb(mat[1])
    if kind == "steel":                      # gebürstet: lange waagerechte Schlieren
        s = 0.80 + 0.30 * _vnoise(X / 60.0, Y * 1.4, 1) * 0.6 + 0.16 * _hash(np.floor(X / 9), np.floor(Y * 1.2), 2)
        return col * s[..., None]
    if kind == "polymer":                    # feines Korn
        s = 0.86 + 0.2 * _hash(np.floor(X / 2.3), np.floor(Y / 2.3), 3) + 0.08 * _vnoise(X / 40, Y / 40, 4)
        return col * s[..., None]
    if kind == "rubber":                     # Gummigriff mit Noppen
        dots = (((X % 14) - 7) ** 2 + ((Y % 14) - 7) ** 2) < 6.5
        s = np.where(dots, 0.62, 0.95) * (0.9 + 0.12 * _hash(np.floor(X / 3), np.floor(Y / 3), 5))
        return col * s[..., None]
    if kind == "wood":                       # Maserung
        g = np.sin(Y * 0.17 + 7.0 * _vnoise(X / 150.0, Y / 55.0, 6) + X * 0.012)
        t = (0.5 + 0.5 * g)[..., None]
        dark, light = col * 0.78, np.minimum(col * 1.14, 1.0)
        fine = (0.94 + 0.1 * _hash(np.floor(X / 40), np.floor(Y * 2.2), 7))[..., None]
        return (dark * (1 - t) + light * t) * fine
    if kind == "camo":                       # drei Flecken-Farben
        n1, n2 = _vnoise(X / 80.0, Y / 80.0, 8), _vnoise(X / 46.0 + 9, Y / 46.0, 9)
        base = np.broadcast_to(col, X.shape + (3,)).copy()
        base = np.where((n1 > 0.58)[..., None], col * 0.58, base)
        base = np.where((n2 > 0.64)[..., None], np.array([0.20, 0.17, 0.12], np.float32), base)
        return base * (0.9 + 0.14 * _hash(np.floor(X / 3), np.floor(Y / 3), 10))[..., None]
    if kind == "carbon":                     # Gewebe
        cell = (np.floor(X / 7) + np.floor(Y / 7)) % 2
        s = np.where(cell > 0, 0.72, 1.12) * (0.92 + 0.12 * np.sin((X + Y) * 0.9))
        return col * s[..., None]
    if kind == "glove":                      # Stoff mit Nähten
        s = 0.86 + 0.14 * _hash(np.floor(X / 2), np.floor(Y / 2), 11)
        seam = (np.abs(((X * 0.6 + Y) % 46) - 23) < 1.0)
        return col * (s * np.where(seam, 0.7, 1.0))[..., None]
    if kind == "glow":                       # Leuchtfläche (Akzent, Linsen)
        return np.broadcast_to(np.minimum(col * 1.1, 1.0), X.shape + (3,)).copy()
    return np.broadcast_to(col, X.shape + (3,)).copy()


# ------------------------------------------------------------------ Formen (Abstandsfunktionen, negativ = innen)
def _sd_rrect(X, Y, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    qx, qy = np.abs(X - cx) - ((x1 - x0) / 2 - r), np.abs(Y - cy) - ((y1 - y0) / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def _sd_poly(X, Y, pts):
    n = len(pts)
    d = np.full(X.shape, 1e9, np.float32)
    inside = np.zeros(X.shape, bool)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        px, py = X - ax, Y - ay
        h = np.clip((px * ex + py * ey) / (ex * ex + ey * ey), 0, 1)
        d = np.minimum(d, np.hypot(px - ex * h, py - ey * h))
        cond = ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / (by - ay + 1e-9) + ax)
        inside ^= cond
    return np.where(inside, -d, d)


class _Canvas:
    def __init__(self, wp, theta, accent):
        self.wp, self.sc = int(wp), wp / DW
        self.hp = int(round(DH * self.sc))
        self.theta, self.accent = theta, accent
        self.cos, self.sin = math.cos(theta), math.sin(theta)
        py, px = np.mgrid[0:self.hp, 0:self.wp].astype(np.float32)
        sx, sy = (px + 0.5) / self.sc - PIVOT[0], (py + 0.5) / self.sc - PIVOT[1]
        # Bildpunkt -> Entwurfspunkt (Gegendrehung um den Drehpunkt)
        self.X = PIVOT[0] + self.cos * sx + self.sin * sy
        self.Y = PIVOT[1] - self.sin * sx + self.cos * sy
        self.rgb = np.zeros((self.hp, self.wp, 3), np.float32)
        self.a = np.zeros((self.hp, self.wp), np.float32)

    def to_screen(self, x, y):
        dx, dy = x - PIVOT[0], y - PIVOT[1]
        return (PIVOT[0] + self.cos * dx - self.sin * dy) * self.sc, (PIVOT[1] + self.sin * dx + self.cos * dy) * self.sc

    def _slice(self, bounds):
        xs, ys = [], []
        for cx in (bounds[0], bounds[2]):
            for cy in (bounds[1], bounds[3]):
                px, py = self.to_screen(cx, cy)
                xs.append(px)
                ys.append(py)
        m = 4
        x0, x1 = int(max(0, min(xs) - m)), int(min(self.wp, max(xs) + m + 1))
        y0, y1 = int(max(0, min(ys) - m)), int(min(self.hp, max(ys) + m + 1))
        return (slice(y0, y1), slice(x0, x1)) if x1 > x0 and y1 > y0 else None

    def _paint(self, sl, sd, mat, bevel=True, shade=1.0):
        a = np.clip(0.5 - sd * self.sc, 0, 1)
        if not a.any():
            return
        rgb = _tex(mat, self.X[sl], self.Y[sl]) * shade
        if bevel:
            m = a > 0.5
            k = max(1, int(round(3 * self.sc * 1.6)))
            top = m & ~np.roll(m, k, 0)
            bot = m & ~np.roll(m, -k, 0)
            inner = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
            rows = np.where(m.any(1))[0]
            if rows.size:
                t = (np.arange(m.shape[0], dtype=np.float32) - rows[0]) / max(1, rows[-1] - rows[0])
                rgb = rgb * (1.12 - 0.34 * np.clip(t, 0, 1))[:, None, None]
            rgb = rgb * np.where(top, 1.32, 1.0)[..., None] * np.where(bot, 0.72, 1.0)[..., None] * np.where(inner, 0.62, 1.0)[..., None]
        ra, rc = self.a[sl], self.rgb[sl]
        self.rgb[sl] = rc * (1 - a[..., None]) + np.clip(rgb, 0, 1) * a[..., None]
        self.a[sl] = a + ra * (1 - a)

    def rrect(self, x0, y0, x1, y1, r, mat, **kw):
        sl = self._slice((x0, y0, x1, y1))
        if sl is not None:
            self._paint(sl, _sd_rrect(self.X[sl], self.Y[sl], x0, y0, x1, y1, min(r, (x1 - x0) / 2, (y1 - y0) / 2)), mat, **kw)

    def circle(self, cx, cy, r, mat, **kw):
        sl = self._slice((cx - r, cy - r, cx + r, cy + r))
        if sl is not None:
            self._paint(sl, _sd_circle(self.X[sl], self.Y[sl], cx, cy, r), mat, **kw)

    def poly(self, pts, mat, **kw):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        sl = self._slice((min(xs), min(ys), max(xs), max(ys)))
        if sl is not None:
            self._paint(sl, _sd_poly(self.X[sl], self.Y[sl], pts), mat, **kw)

    def cut(self, x0, y0, x1, y1, r):
        """Loch in das bisher Gemalte (Lüftungsschlitze, Abzugsbügel)."""
        sl = self._slice((x0, y0, x1, y1))
        if sl is not None:
            a = np.clip(0.5 - _sd_rrect(self.X[sl], self.Y[sl], x0, y0, x1, y1, min(r, (x1 - x0) / 2, (y1 - y0) / 2)) * self.sc, 0, 1)
            self.a[sl] *= 1 - a


# ------------------------------------------------------------------ Hände
GLOVE, SLEEVE = ("glove", "#2b303b"), ("polymer", "#1a2030")


def _hands(c, gx, gy, sx, sy, accent):
    # Unterstützhand zuerst (liegt hinter der Waffe nicht - sie greift von unten um den Vorderschaft)
    c.poly([(sx - 20, sy + 40), (sx + 90, sy + 40), (sx + 300, 760), (sx + 40, 760)], SLEEVE, bevel=False, shade=0.9)
    c.rrect(sx - 66, sy - 4, sx + 74, sy + 84, 34, GLOVE)
    for i in range(3):
        c.rrect(sx - 50 + i * 36, sy + 62, sx - 20 + i * 36, sy + 92, 14, GLOVE)
    # Schießhand am Griff
    c.poly([(gx - 10, gy + 70), (gx + 110, gy + 40), (1060, 360), (1060, 760), (gx + 40, 760)], SLEEVE, bevel=False, shade=0.95)
    c.rrect(gx - 56, gy - 36, gx + 62, gy + 104, 38, GLOVE)
    c.rrect(gx - 78, gy - 42, gx - 14, gy + 30, 26, GLOVE)           # Daumen
    c.rrect(gx + 30, gy + 30, gx + 62, gy + 112, 14, GLOVE)
    c.rrect(gx + 70, gy + 150, gx + 270, gy + 164, 4, ("glow", accent), bevel=False)   # Akzentstreifen am Ärmel


# ------------------------------------------------------------------ Waffen (Mündung links)
def _pistol(c, ac):
    st, dk, po, gr = ("steel", "#3a4250"), ("steel", "#232933"), ("polymer", "#262b34"), ("rubber", "#1c2027")
    _hands_pistol(c, ac)
    c.rrect(120, 215, 170, 262, 10, dk)
    c.rrect(150, 190, 610, 292, 28, st)
    c.rrect(176, 198, 590, 205, 3, ("glow", ac), bevel=False)
    for i in range(6):
        c.rrect(505 + i * 15, 214, 511 + i * 15, 284, 2, dk, bevel=False)
    c.rrect(162, 170, 192, 196, 5, dk)
    c.rrect(560, 170, 606, 196, 5, dk)
    c.rrect(250, 285, 632, 338, 20, po)
    c.rrect(322, 322, 450, 398, 34, po)
    c.cut(352, 344, 424, 374, 16)
    c.rrect(392, 338, 412, 372, 5, st)
    c.poly([(520, 312), (648, 312), (704, 520), (592, 544)], gr)
    c.rrect(578, 520, 712, 548, 8, dk)
    c.rrect(262, 292, 300, 306, 3, ("glow", ac), bevel=False)


def _hands_pistol(c, ac):
    c.poly([(560, 470), (700, 430), (1060, 520), (1060, 760), (620, 760)], SLEEVE, bevel=False, shade=0.9)
    c.rrect(470, 392, 660, 486, 38, GLOVE)
    c.poly([(720, 440), (840, 400), (1060, 400), (1060, 760), (700, 760)], SLEEVE, bevel=False, shade=0.95)
    c.rrect(600, 340, 740, 500, 44, GLOVE)
    c.rrect(560, 318, 640, 400, 30, GLOVE)


def _smg(c, ac):
    st, dk, po, cb, gr = ("steel", "#3a4250"), ("steel", "#222831"), ("polymer", "#1f242d"), ("carbon", "#262c37"), ("rubber", "#1b1f26")
    _hands(c, 720, 400, 330, 300, ac)
    c.rrect(60, 235, 240, 266, 10, dk)
    c.rrect(36, 224, 90, 278, 8, dk)
    c.rrect(190, 205, 470, 302, 16, cb)
    for i in range(4):
        c.cut(232 + i * 55, 232, 258 + i * 55, 274, 6)
    c.rrect(200, 284, 460, 291, 3, ("glow", ac), bevel=False)
    c.rrect(440, 190, 770, 312, 22, po)
    c.rrect(452, 195, 756, 202, 2, ("glow", ac), bevel=False)
    c.rrect(560, 218, 660, 248, 5, ("steel", "#101318"))
    c.rrect(260, 170, 720, 192, 4, st)
    for x in range(272, 712, 28):
        c.rrect(x, 173, x + 14, 190, 2, dk, bevel=False)
    c.rrect(520, 118, 652, 172, 12, dk)
    c.circle(634, 145, 21, ("glow", ac))
    c.poly([(380, 300), (474, 300), (448, 506), (362, 494)], ("polymer", "#2b313c"))
    c.rrect(366, 480, 456, 510, 8, dk)
    c.poly([(664, 304), (748, 304), (790, 474), (706, 486)], gr)
    c.rrect(560, 300, 660, 352, 24, po)
    c.cut(586, 316, 636, 334, 9)
    c.rrect(740, 215, 960, 246, 9, st)
    c.rrect(940, 184, 992, 332, 14, po)


def _rifle(c, ac):
    st, dk, ol, gr = ("steel", "#353c48"), ("steel", "#1f242c"), ("polymer", "#4a5436"), ("rubber", "#434c32")
    _hands(c, 790, 410, 430, 292, ac)
    c.rrect(30, 232, 100, 268, 6, dk)
    for i in range(3):
        c.cut(44 + i * 16, 238, 50 + i * 16, 262, 2)
    c.rrect(96, 242, 340, 258, 5, st)
    c.rrect(300, 224, 346, 276, 6, dk)
    c.rrect(270, 198, 560, 304, 18, ol)
    for i in range(5):
        c.cut(302 + i * 50, 228, 328 + i * 50, 274, 8)
    c.rrect(520, 178, 770, 292, 14, ("steel", "#2c323c"))
    c.rrect(300, 158, 770, 180, 4, st)
    for x in range(312, 760, 26):
        c.rrect(x, 161, x + 13, 178, 2, dk, bevel=False)
    c.rrect(470, 98, 640, 160, 16, dk)
    c.circle(626, 128, 25, ("glow", ac))
    c.rrect(486, 106, 560, 112, 3, ("glow", ac), bevel=False)
    c.rrect(566, 286, 790, 334, 12, ("polymer", "#22272f"))
    c.poly([(604, 332), (698, 332), (710, 504), (624, 520)], ("steel", "#2a303a"))
    c.poly([(736, 332), (810, 332), (842, 494), (768, 506)], gr)
    c.poly([(766, 214), (994, 198), (994, 322), (904, 334), (766, 300)], ol)
    c.rrect(772, 166, 806, 196, 5, dk)
    c.rrect(790, 214, 990, 222, 3, ("glow", ac), bevel=False)


def _dmr(c, ac):
    st, dk, wd = ("steel", "#2f3641"), ("steel", "#1c2128"), ("wood", "#74512f")
    _hands(c, 806, 400, 520, 300, ac)
    c.rrect(20, 235, 262, 282, 22, dk)
    for i in range(5):
        c.rrect(64 + i * 40, 238, 70 + i * 40, 280, 2, ("steel", "#2c333d"), bevel=False)
    c.rrect(250, 248, 430, 262, 4, st)
    c.rrect(380, 214, 650, 302, 22, wd)
    c.rrect(600, 190, 810, 302, 14, dk)
    c.rrect(430, 120, 770, 170, 24, st)
    c.rrect(408, 104, 486, 186, 20, dk)
    c.circle(446, 145, 29, ("glow", ac))
    c.circle(446, 145, 13, ("steel", "#0b0e12"), bevel=False)
    c.rrect(740, 110, 806, 180, 18, dk)
    c.rrect(588, 94, 632, 124, 8, dk)
    c.rrect(520, 166, 564, 198, 5, dk)
    c.rrect(676, 166, 720, 198, 5, dk)
    c.rrect(640, 300, 714, 404, 10, ("steel", "#2c333d"))
    c.poly([(764, 300), (836, 300), (856, 474), (780, 486)], wd)
    c.poly([(790, 220), (1002, 204), (1002, 330), (932, 346), (790, 312)], wd)
    c.rrect(800, 232, 990, 240, 3, ("glow", ac), bevel=False)


def _lmg(c, ac):
    st, dk, cm, gr = ("steel", "#353c48"), ("steel", "#20252d"), ("camo", "#5a6a44"), ("rubber", "#232830")
    _hands(c, 818, 410, 420, 300, ac)
    c.rrect(25, 224, 96, 276, 8, dk)
    c.rrect(80, 234, 340, 266, 8, st)
    c.rrect(120, 212, 142, 238, 3, dk)
    c.poly([(330, 300), (366, 300), (486, 362), (458, 376)], dk)
    c.rrect(250, 194, 592, 306, 16, cm)
    for i in range(6):
        c.cut(292 + i * 45, 224, 316 + i * 45, 278, 7)
    c.rrect(300, 158, 570, 180, 4, st)
    c.rrect(560, 172, 806, 312, 16, ("steel", "#2c323c"))
    c.rrect(600, 152, 786, 186, 8, st)
    c.rrect(420, 140, 520, 172, 14, dk)
    c.rrect(588, 304, 764, 476, 20, ("camo", "#4d5d3c"))
    for i in range(3):
        c.rrect(610, 326 + i * 46, 742, 332 + i * 46, 2, dk, bevel=False)
    c.poly([(782, 312), (858, 312), (880, 474), (806, 486)], gr)
    c.poly([(794, 216), (1002, 204), (1002, 338), (906, 348), (794, 322)], ("polymer", "#242a33"))
    c.rrect(808, 230, 990, 238, 3, ("glow", ac), bevel=False)


# Waffe: (Zeichenfunktion, Mündung, Visierpunkt) in Entwurfskoordinaten; der Visierpunkt kommt beim Zielen in die Bildmitte
LOOKS = {"pistol": (_pistol, (125, 238), (176, 178)), "smg": (_smg, (38, 251), (634, 145)), "rifle": (_rifle, (30, 250), (626, 128)),
         "dmr": (_dmr, (20, 258), (770, 145)), "lmg": (_lmg, (25, 250), (350, 150))}


def make(look: str, width: int, accent: str = "#4cc9f0", theta: float = TILT):
    """Gibt (RGBA uint8 (h, w, 4), Mündung (x, y), Visierpunkt (x, y)) zurück; Punkte in Bildpunkten."""
    key = (look, int(width), accent, round(theta, 3))
    if key in _cache:
        return _cache[key]
    fn, muz, sight = LOOKS.get(look, LOOKS["rifle"])
    c = _Canvas(width, theta, accent)
    fn(c, accent)
    # weicher Schlagschatten unter der Silhouette
    out = np.zeros((c.hp, c.wp, 4), np.uint8)
    out[..., :3] = np.clip(c.rgb * 255, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(c.a * 255, 0, 255).astype(np.uint8)
    res = (out, c.to_screen(*muz), c.to_screen(*sight))
    _cache[key] = res
    return res


def crop(rgba: np.ndarray, pad: int = 4) -> np.ndarray:
    a = rgba[..., 3] > 8
    ys, xs = np.where(a)
    if not ys.size:
        return rgba
    return rgba[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]


def thumbnail(look: str, width: int = 230, accent: str = "#4cc9f0") -> np.ndarray:
    """Waffe für die Menükarte: ohne Drehung, ohne Hände, auf den Inhalt zugeschnitten."""
    rgba = make(look, width * 2, accent, theta=0.0)[0]
    c = crop(rgba)
    # auf die gewünschte Breite verkleinern (Mittelwert über Blöcke)
    f = max(1, c.shape[1] // width)
    h, w = c.shape[0] // f * f, c.shape[1] // f * f
    c = c[:h, :w].astype(np.float32)
    a = c[..., 3:4] / 255
    prem = c[..., :3] * a
    prem = prem.reshape(h // f, f, w // f, f, 3).mean((1, 3))
    al = a.reshape(h // f, f, w // f, f, 1).mean((1, 3))
    rgb = np.where(al > 0.01, prem / np.maximum(al, 0.01), 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(al * 255, 0, 255)]).astype(np.uint8)


def png(rgba: np.ndarray) -> bytes:
    """RGBA-Bild als PNG-Bytes (nur zlib, keine Bildbibliothek nötig)."""
    h, w = rgba.shape[:2]
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b"")
