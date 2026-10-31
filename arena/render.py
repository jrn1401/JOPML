"""Bild der Arena als Liste einfacher Rechtecke (Raycasting). Die Oberfläche zeichnet sie; die Tests und to_image() erzeugen daraus ein Bild."""
import math

from . import game as G
from . import world

FOV = math.radians(68)


def shade(hexcolor: str, f: float) -> str:
    f = max(0.0, min(1.0, f))
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * f):02x}{int(g * f):02x}{int(b * f):02x}"


def focal(w: int) -> float:
    return (w / 2) / math.tan(FOV / 2)


def build_frame(g, w: int, h: int, cols: int = 160) -> list:
    """[(x0, y0, x1, y1, farbe)] von hinten nach vorn."""
    th, f = g.theme, focal(w)
    horizon = h / 2 - math.tan(g.pitch) * f
    ops = [(0, 0, w, horizon, th["sky"])]
    bands = 6
    for i in range(bands):                                  # Boden mit Farbverlauf zum Horizont hin dunkler
        y0 = horizon + (h - horizon) * i / bands
        y1 = horizon + (h - horizon) * (i + 1) / bands
        ops.append((0, y0, w, y1 + 1, shade(th["floor"], 0.45 + 0.55 * (i + 1) / bands)))
    strip = w / cols
    zbuf = []
    for c in range(cols):
        off = ((c + 0.5) / cols - 0.5) * 2 * math.tan(FOV / 2)
        ray = g.ang + math.atan(off)
        d, kind, side = world.cast(g.x, g.y, ray)
        perp = max(0.05, d * math.cos(ray - g.ang))
        zbuf.append(perp)
        top = horizon - (1 - G.EYE) * f / perp
        bot = horizon + G.EYE * f / perp
        col = shade(th["walls"][kind], (1.0 if side == 0 else 0.78) * max(0.25, 1 - perp / 20))
        ops.append((c * strip, top, (c + 1) * strip + 0.5, bot, col))
    for b in sorted((b for b in g.bots if b.alive), key=lambda b: -((b.x - g.x) ** 2 + (b.y - g.y) ** 2)):
        vx, vy = b.x - g.x, b.y - g.y
        d = math.hypot(vx, vy)
        rel = (math.atan2(vy, vx) - g.ang + math.pi) % (2 * math.pi) - math.pi
        if abs(rel) > FOV / 2 + 0.3 or d < 0.2:
            continue
        perp = d * math.cos(rel)
        if perp < 0.15:
            continue
        sx = w / 2 + math.tan(rel) * f
        half = G.BOT_R * f / perp
        y = lambda z: horizon + (G.EYE - z) * f / perp
        base = th["bot"] if b.team == 0 else th["bot2"]
        if b.flash > 0:
            base = "#ffffff"
        fog = max(0.35, 1 - perp / 22)
        parts = ((0.0, 0.38, shade(base, 0.55 * fog), 0.9), (0.38, 0.7, shade(base, fog), 1.0), (0.7, G.BOT_H, shade(th["head"], fog), 0.55))
        for c in range(max(0, int((sx - half) / strip)), min(cols, int((sx + half) / strip) + 1)):
            if zbuf[c] <= perp:
                continue
            cx = (c + 0.5) * strip
            for z0, z1, colr, wid in parts:
                if abs(cx - sx) <= half * wid:
                    ops.append((c * strip, y(z1), (c + 1) * strip + 0.5, y(z0), colr))
    return ops


def to_image(ops, w: int, h: int):
    """Für Tests und Vorschaubilder (benötigt Pillow, das nur hier gebraucht wird, nicht im Spiel)."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), "#000000")
    d = ImageDraw.Draw(im)
    for x0, y0, x1, y1, col in ops:
        d.rectangle([x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)], fill=col)
    return im
