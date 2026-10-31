"""Rechnung für die Anzeige über dem 3D-Bild (ohne tkinter, testbar): Projektion von Weltpunkten, Leuchtspuren, Funken, Hitbox-Umrisse,
Waffenposition in der Hand."""
import math

from . import hit


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Cam:
    """Kamera des Spielers für eine Fenstergröße (w, h) in Bildpunkten."""

    def __init__(self, g, w, h):
        self.w, self.h = float(w), float(h)
        self.f = (self.w / 2) / math.tan(g.fov_now / 2)
        self.dx, self.dy = math.cos(g.ang), math.sin(g.ang)
        self.x, self.y, self.eye = g.x, g.y, g.eye
        self.horizon = self.h / 2 - math.tan(g.pitch) * self.f

    def project(self, p):
        """(sx, sy, Tiefe) oder None, wenn der Punkt hinter der Kamera liegt."""
        vx, vy = p[0] - self.x, p[1] - self.y
        fwd = vx * self.dx + vy * self.dy
        if fwd < 0.12:
            return None
        return (self.w / 2 + (-vx * self.dy + vy * self.dx) / fwd * self.f, self.horizon - (p[2] - self.eye) * self.f / fwd, fwd)


def tracer_segment(cam, p, age, muzzle):
    """Leuchtspur vom Mündungsfeuer zum Einschlagpunkt: ((x0, y0), (x1, y1)) oder None. Der helle Kopf läuft vor, der Schweif folgt."""
    e = cam.project(p)
    if e is None or age < 0 or age > 0.16:
        return None
    head = min(1.0, age / 0.05)
    tail = max(0.0, min(1.0, (age - 0.035) / 0.1))
    if tail >= head - 1e-6:
        return None
    mx, my = muzzle
    return ((mx + (e[0] - mx) * tail, my + (e[1] - my) * tail), (mx + (e[0] - mx) * head, my + (e[1] - my) * head))


def spark_lines(cam, p, age, seed):
    """Kurze Strahlen um einen Einschlag: Liste ((x0, y0), (x1, y1)); verschwindet nach 0,4 s."""
    c = cam.project(p)
    if c is None or age > 0.4:
        return []
    k = age / 0.4
    scale = max(0.6, min(3.0, 3.2 / c[2]))
    out = []
    for i in range(7):
        a = (seed * 12.9898 + i * 2.399) % (2 * math.pi)
        r0, r1 = (3 + 9 * k) * scale, (7 + 20 * k) * scale
        out.append(((c[0] + math.cos(a) * r0, c[1] + math.sin(a) * r0), (c[0] + math.cos(a) * r1, c[1] + math.sin(a) * r1)))
    return out


def hitbox_ovals(cam, b, player_xy):
    """Umrisse der Trefferzonen eines Bots/Ziels als ovale Kästen (x0, y0, x1, y1, Zone)."""
    out = []
    if getattr(b, "kind", "bot") == "target":
        c = cam.project((b.x, b.y, b.z))
        if c:
            r = b.r * cam.f / c[2]
            out.append((c[0] - r, c[1] - r, c[0] + r, c[1] + r, "target"))
        return out
    vx, vy = b.x - player_xy[0], b.y - player_xy[1]
    d = math.hypot(vx, vy)
    if d < 1e-6:
        return out
    sx, sy = -vy / d, vx / d

    def oval(cx, cy, zlo, zhi, rr, zone):
        c = cam.project((cx, cy, (zlo + zhi) / 2))
        if not c:
            return
        k = cam.f / c[2]
        out.append((c[0] - rr * k, c[1] - (zhi - (zlo + zhi) / 2 + rr) * k, c[0] + rr * k, c[1] + (zhi - (zlo + zhi) / 2 + rr) * k, zone))

    oval(b.x, b.y, hit.HEAD[0], hit.HEAD[0], hit.HEAD[1], "head")
    oval(b.x, b.y, hit.TORSO[0], hit.TORSO[1], hit.TORSO[2], "body")
    for s in (-1, 1):
        oval(b.x + sx * hit.LEG[3] * s, b.y + sy * hit.LEG[3] * s, hit.LEG[0] + hit.LEG[2], hit.LEG[1], hit.LEG[2], "legs")
    return out


def crosshair_gap(g, w):
    """Abstand der Strich-Enden in der Mitte: wächst mit der Streuung (Bewegung, Schüsse), schrumpft beim Visieren."""
    focal = (w / 2) / math.tan(g.fov_now / 2)
    return 4 + math.tan(math.radians(g.spread_deg())) * focal * 0.6


def vm_place(g, w, h, muzzle, sight, sway=(0.0, 0.0), raise_k=0.0):
    """Wo die Mündung der Waffe auf dem Bildschirm liegt: Hüfte -> Visier (Visierpunkt in der Mitte), dazu Gehwippen, Rückstoß, Nachladen."""
    a = smooth(g.ads)
    hip = (w * 0.56, h * 0.67)
    ads = (w / 2 - (sight[0] - muzzle[0]), h * 0.58 - (sight[1] - muzzle[1]))      # Visier knapp unter dem Fadenkreuz, Waffe waagerecht
    mx, my = hip[0] + (ads[0] - hip[0]) * a, hip[1] + (ads[1] - hip[1]) * a
    moving = min(1.0, g.speed / 2.4)
    bob = math.sin(g.t * 8.5) * moving * (1 - 0.8 * a)
    mx += bob * w * 0.004
    my += abs(bob) * h * 0.009
    kick = max(0.0, 1 - (g.t - g.last_shot) / 0.1)
    mx += kick * w * 0.012
    my += kick * h * 0.02 * (1 - 0.5 * a)
    if g.reload_until:
        prog = 1 - max(0.0, g.reload_until - g.t) / max(g.w["reload"], 0.1)
        dip = math.sin(math.pi * min(1.0, prog))
        my += dip * h * 0.3
        mx += dip * w * 0.05
    my += raise_k * h * 0.35
    return mx + sway[0], my + sway[1]
