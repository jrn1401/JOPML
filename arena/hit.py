"""Trefferzonen (Hitboxen) der Bots und Ziele: echte Körper im Raum statt einer flachen Wand.
Kopf = Kugel, Rumpf = Kapsel, Beine = zwei Kapseln. Die Maße sind etwas kleiner als das gezeichnete Bild, damit nur echte Treffer zählen."""
import math

# Maße in Welteinheiten (Wandhöhe = 1, Augenhöhe stehend = 0.5)
HEAD = (0.76, 0.150)                       # (Mittelpunkt-Höhe, Radius)
TORSO = (0.36, 0.52, 0.205)                # (untere Höhe, obere Höhe, Radius)
LEG = (0.04, 0.29, 0.082, 0.10)            # (unten, oben, Radius, seitlicher Abstand)
ZONES = {"head": 1.0, "body": 1.0, "legs": 0.75}      # Schadensfaktor je Zone (Kopf: Waffenwert 'head')
BOT_TOP = 0.93


def _sphere(ro, rd, c, r):
    ox, oy, oz = ro[0] - c[0], ro[1] - c[1], ro[2] - c[2]
    b = ox * rd[0] + oy * rd[1] + oz * rd[2]
    cc = ox * ox + oy * oy + oz * oz - r * r
    h = b * b - cc
    if h < 0:
        return None
    t = -b - math.sqrt(h)
    if t < 0:
        t = -b + math.sqrt(h)
    return t if t > 0 else None


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _capsule(ro, rd, pa, pb, r):
    """Strahl gegen Kapsel (Strecke pa-pb, Radius r). Abstand t oder None."""
    ba = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
    oa = (ro[0] - pa[0], ro[1] - pa[1], ro[2] - pa[2])
    baba, bard, baoa, rdoa, oaoa = _dot(ba, ba), _dot(ba, rd), _dot(ba, oa), _dot(rd, oa), _dot(oa, oa)
    a = baba - bard * bard
    b = baba * rdoa - baoa * bard
    c = baba * oaoa - baoa * baoa - r * r * baba
    best = None
    if a > 1e-9:
        h = b * b - a * c
        if h >= 0:
            t = (-b - math.sqrt(h)) / a
            y = baoa + t * bard
            if t > 0 and 0 < y < baba:
                best = t
    for end in (pa, pb):
        t = _sphere(ro, rd, end, r)
        if t is not None and (best is None or t < best):
            best = t
    return best


def hit_bot(ro, rd, bx, by, side):
    """Strahl (Ursprung ro, Richtung rd, beide 3D) gegen einen stehenden Bot bei (bx, by).
    side = waagerechter Einheitsvektor quer zur Blickrichtung (die Bots sind dem Betrachter zugewandt gezeichnet).
    Gibt (Abstand, Zone) des nächsten Treffers zurück oder None."""
    best = None

    def take(t, zone):
        nonlocal best
        if t is not None and (best is None or t < best[0]):
            best = (t, zone)

    take(_sphere(ro, rd, (bx, by, HEAD[0]), HEAD[1]), "head")
    take(_capsule(ro, rd, (bx, by, TORSO[0]), (bx, by, TORSO[1]), TORSO[2]), "body")
    for s in (-1, 1):
        lx, ly = bx + side[0] * LEG[3] * s, by + side[1] * LEG[3] * s
        take(_capsule(ro, rd, (lx, ly, LEG[0] + LEG[2]), (lx, ly, LEG[1]), LEG[2]), "legs")
    return best


def hit_target(ro, rd, bx, by, bz, r):
    t = _sphere(ro, rd, (bx, by, bz), r)
    return (t, "target") if t is not None else None


def ray_dir(yaw, pitch):
    cp = math.cos(pitch)
    return (cp * math.cos(yaw), cp * math.sin(yaw), math.sin(pitch))
