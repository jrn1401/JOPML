"""Prozedurale Texturen (numpy): Wände, Boden, Decke. Alles wird beim Start aus den Themenfarben berechnet - keine Bilddateien nötig."""
import numpy as np

T = 64


def _rgb(hexcolor: str) -> np.ndarray:
    return np.array([int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


def _noise(rng, amp):
    n = rng.normal(0, amp, (T, T)).astype(np.float32)
    big = rng.normal(0, amp * 1.6, (T // 8, T // 8)).astype(np.float32)
    return n + np.kron(big, np.ones((8, 8), dtype=np.float32))


def _concrete(rng):
    g = 0.82 + _noise(rng, 0.03)
    seam = np.zeros((T, T), np.float32)
    seam[:, [0, 31, 32]] = -0.18
    seam[[0, 31, 32], :] = -0.18
    for y, x in ((6, 6), (6, 57), (57, 6), (57, 57), (6, 38), (57, 38), (6, 25), (57, 25)):
        seam[y - 1:y + 2, x - 1:x + 2] = -0.1
    return np.clip(g + seam, 0, 1.2)


def _brick(rng):
    g = np.zeros((T, T), np.float32)
    mortar = 0.62
    for row in range(4):
        y0, off = row * 16, (row % 2) * 16
        for col in range(-1, 3):
            x0 = col * 32 + off
            shade = 0.72 + rng.uniform(-0.12, 0.12)
            ys, xs = slice(y0 + 1, y0 + 15), slice(max(0, x0 + 1), min(T, x0 + 31))
            if xs.start < xs.stop:
                g[ys, xs] = shade
        g[y0, :] = mortar
    g[g == 0] = mortar
    return np.clip(g + _noise(rng, 0.035), 0, 1.2)


def _metal(rng):
    g = 0.78 + _noise(rng, 0.02)
    for x in range(0, T, 16):
        g[:, x:x + 2] -= 0.16
        g[:, x + 2:x + 3] += 0.08
    g[:6, :] -= 0.0
    for y in (3, 60):
        for x in range(4, T, 16):
            g[y - 1:y + 2, x - 1:x + 2] += 0.12
    # Warnstreifen unten
    yy, xx = np.mgrid[0:T, 0:T]
    stripe = ((xx + yy) // 8) % 2
    band = yy >= T - 10
    g = np.where(band, 0.45 + 0.4 * stripe, g)
    return np.clip(g, 0, 1.2)


def _tile(rng):
    yy, xx = np.mgrid[0:T, 0:T]
    g = 0.86 + _noise(rng, 0.015)
    g += (1 - np.abs(((xx % 32) - 16) / 16)) * 0.04 + (1 - np.abs(((yy % 32) - 16) / 16)) * 0.04
    g[(xx % 32 == 0) | (yy % 32 == 0)] -= 0.25
    gloss = np.clip(1 - np.abs(xx + yy - 40) / 14, 0, 1) * 0.1
    return np.clip(g + gloss, 0, 1.2)


def _emit(accent):
    """Leuchtende Anteile der Wände (additiv): Lichtleiste, Punkte, Kantenlicht. Gibt (4, T, T, 3) zurück."""
    e = np.zeros((4, T, T, 3), np.float32)
    col = _rgb(accent)
    e[0, 29:33, :, :] = col * 0.95            # Betonplatten: waagerechte Lichtleiste in Augenhöhe
    e[0, 28, :, :] = col * 0.25
    e[0, 33, :, :] = col * 0.25
    for x in (14, 50):                          # Metall: zwei Kontrollpunkte
        e[2, 14:18, x - 2:x + 2, :] = col * 0.9
    e[3, :, 0:2, :] = col * 0.55                # Fliesen: Kantenlicht
    e[1, 4:6, :, :] = col * 0.2                 # Ziegel: schwacher Streifen oben
    return e


def make(theme: dict, seed: int = 4) -> dict:
    """{'walls': (4,T,T,3), 'wemit': (4,T,T,3), 'floor': (T,T,3), 'ceil': (T,T,3)} float32, Werte 0..255."""
    rng = np.random.default_rng(seed)
    accent = theme.get("accent", "#ffd479")
    pats = [_concrete(rng), _brick(rng), _metal(rng), _tile(rng)]
    walls = np.stack([p[..., None] * _rgb(theme["walls"][i]) for i, p in enumerate(pats)]).astype(np.float32)
    yy, xx = np.mgrid[0:T, 0:T]
    fl = 0.9 + _noise(rng, 0.02)
    fl = np.where(((xx // 32) + (yy // 32)) % 2 == 0, fl, fl * 0.86)
    line = ((xx % 32 == 0) | (yy % 32 == 0))
    fl[line] *= 0.7
    floor = (fl[..., None] * _rgb(theme["floor"]) * 1.25).astype(np.float32)
    floor[line] += _rgb(accent) * 0.16          # feine, leuchtende Rasterlinien im Boden
    ce = 0.9 + _noise(rng, 0.015)
    ce[(xx % 32 == 0) | (yy % 32 == 0)] *= 0.65
    ce[8:24, 8:24] = 1.35                         # Leuchtfeld
    ceil = (np.clip(ce, 0, 1.6)[..., None] * _rgb(theme["sky"]) * 1.5).astype(np.float32)
    return {"walls": np.clip(walls, 0, 255), "wemit": _emit(accent), "floor": np.clip(floor, 0, 255), "ceil": np.clip(ceil, 0, 255)}
