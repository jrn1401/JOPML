"""Kalibrierung der Fadenkreuz-Streuung: misst am Bildschirm, wie weit das Fadenkreuz des SPIELS beim Schießen auseinanderrückt,
und übernimmt Weite und Geschwindigkeit für das eigene Fadenkreuz.

Das ist reine Anzeige-Hilfe: Es liest nur die Pixel des eigenen Bildschirms um die Mitte (dieselben Striche, die du im Spiel siehst),
keinen Spielspeicher und nichts, was das Spiel nicht ohnehin anzeigt. Gesucht werden die Striche des Spiel-Fadenkreuzes in
seiner Farbe auf den vier Achsen; ihr Abstand zur Mitte ("Lücke") ist die Streuung.
"""
import statistics


class SpreadError(Exception):
    """Text darf dem Nutzer angezeigt werden (englischer Quelltext für tr())."""


def parse_hex(h: str):
    h = (h or "").strip().lstrip("#")
    if len(h) != 6:
        raise SpreadError("Colour must look like #ff8800.")
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        raise SpreadError("Colour must look like #ff8800.") from None


def _near(a, b, tol: int) -> bool:
    return max(abs(int(x) - int(y)) for x, y in zip(a[:3], b[:3])) <= tol


def gaps(img, target, tol: int, reach: int) -> list[int]:
    """Abstand (in Pixeln) vom Mittelpunkt bis zum ersten Pixel in Zielfarbe, für jede der vier Richtungen, in denen eines gefunden wird.
    Es werden drei benachbarte Linien geprüft, weil Striche oft 2 Pixel dick sind."""
    px = img.load()
    cx, cy = img.width // 2, img.height // 2
    reach = min(reach, cx - 2, cy - 2)
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for d in range(1, reach):
            hit = False
            for off in (0, -1, 1):
                x, y = (cx + dx * d + (off if dy else 0), cy + dy * d + (off if dx else 0))
                if _near(px[x, y], target, tol):
                    hit = True
                    break
            if hit:
                out.append(d)
                break
    return out


def gap_of(img, target, tol: int = 40, reach: int = 70):
    """Streuung des Fadenkreuzes in diesem Bild (Lücke zur Mitte, Median der Richtungen) oder None, wenn weniger als 2 Striche gefunden wurden."""
    g = gaps(img, target, tol, reach)
    return statistics.median(g) if len(g) >= 2 else None


def detect_color(img, reach: int = 70):
    """Rät die Farbe der Fadenkreuz-Striche: Auf den Achsen liegen vier gleichfarbige Punkte, auf den Diagonalen der Hintergrund.
    Gibt "#rrggbb" oder None zurück."""
    px = img.load()
    cx, cy = img.width // 2, img.height // 2
    reach = min(reach, cx - 2, cy - 2)
    best, best_score = None, 70            # mindestens so viel Unterschied zum Hintergrund
    for d in range(3, reach):
        diag = [px[cx + sx * d, cy + sy * d][:3] for sx in (-1, 1) for sy in (-1, 1)]
        bg = tuple(sum(c[i] for c in diag) / 4 for i in range(3))
        axis = [px[cx + d, cy][:3], px[cx - d, cy][:3], px[cx, cy + d][:3], px[cx, cy - d][:3]]
        if max(max(abs(a[i] - b[i]) for i in range(3)) for a in axis for b in axis) > 30:
            continue
        mean = tuple(sum(c[i] for c in axis) / 4 for i in range(3))
        score = max(abs(mean[i] - bg[i]) for i in range(3))
        if score > best_score:
            best, best_score = mean, score
    return "#%02x%02x%02x" % tuple(int(v) for v in best) if best else None


def analyze(idle_gap: float, series: list[tuple[float, float | None]], release_t: float) -> dict:
    """series: (Sekunden seit Feuerbeginn, Lücke oder None). release_t: Sekunde, in der die Maustaste losgelassen wurde.
    Ergebnis: spread_px, spread_rise_ms, spread_fall_ms."""
    pts = [(t, g) for t, g in series if g is not None]
    if len(pts) < 5:
        raise SpreadError("Too few usable pictures. Hold the left mouse button for about 2 seconds while aiming at a wall with details.")
    top = max(g for _, g in pts if _ <= release_t + 0.05) if any(t <= release_t + 0.05 for t, _ in pts) else max(g for _, g in pts)
    spread = top - idle_gap
    if spread < 1.5:
        raise SpreadError("The crosshair of the game did not spread while shooting. Check the colour and use a weapon whose crosshair spreads.")
    rise = next((t for t, g in pts if g - idle_gap >= 0.9 * spread), release_t)
    fall = next((t - release_t for t, g in pts if t > release_t and g - idle_gap <= 0.1 * spread), None)
    return {"spread_px": int(round(min(60, spread))), "spread_rise_ms": int(max(10, min(2000, rise * 1000))),
            "spread_fall_ms": int(max(10, min(3000, (fall if fall is not None else 0.25) * 1000)))}


def grab_center(reach: int = 80):
    """Bildausschnitt um die Bildschirmmitte (RGB). Wirft eine Exception, wenn der Bildschirm nicht gelesen werden darf."""
    from PIL import ImageGrab
    w, h = _screen_size()
    return ImageGrab.grab(bbox=(w // 2 - reach, h // 2 - reach, w // 2 + reach, h // 2 + reach)).convert("RGB")


def _screen_size():
    import sys
    if sys.platform.startswith("win"):
        import ctypes
        u = ctypes.windll.user32
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    return _SCREEN[0], _SCREEN[1]


_SCREEN = [1920, 1080]        # wird vom Plugin gesetzt (macOS/Linux)
