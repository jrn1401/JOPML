"""Karte und Strahlverfolgung (Raycasting) der Arena - reine Mathematik, ohne Oberfläche."""
import math

MAP = [
    "111111111111111111111111",
    "1......................1",
    "1..2222....33333.......1",
    "1..2..........3....44..1",
    "1..2..........3....4...1",
    "1..2...1111...3........1",
    "1......1..1............1",
    "1......1..1....2222....1",
    "1..33..1..1....2..2....1",
    "1..3......1....2..2....1",
    "1..3...................1",
    "1.........44444........1",
    "1.........4............1",
    "1....1111.4....3333....1",
    "1....1.........3.......1",
    "1....1.........3.......1",
    "1..........22..........1",
    "1..4444....2.......11..1",
    "1..4.......2.......1...1",
    "1..4...............1...1",
    "1.......33333..........1",
    "1......................1",
    "1......................1",
    "111111111111111111111111",
]
H = len(MAP)
W = len(MAP[0])
MAX_DIST = 40.0


def _norm_row(r):
    return (r + "1" * W)[:W]


GRID = [_norm_row(r) for r in MAP]


def is_wall(x: float, y: float) -> bool:
    ix, iy = int(math.floor(x)), int(math.floor(y))
    if ix < 0 or iy < 0 or ix >= W or iy >= H:
        return True
    return GRID[iy][ix] != "."


def wall_kind(x: int, y: int) -> int:
    c = GRID[y][x] if 0 <= x < W and 0 <= y < H else "1"
    return (int(c) - 1) % 4 if c.isdigit() else 0


def cast(x: float, y: float, ang: float) -> tuple:
    """Strahl von (x, y) in Richtung ang. Gibt (Abstand, Wandsorte 0-3, Seite 0/1) zurück."""
    dx, dy = math.cos(ang), math.sin(ang)
    mx, my = int(math.floor(x)), int(math.floor(y))
    ddx = abs(1.0 / dx) if dx else 1e30
    ddy = abs(1.0 / dy) if dy else 1e30
    if dx < 0:
        sx, sdx = -1, (x - mx) * ddx
    else:
        sx, sdx = 1, (mx + 1.0 - x) * ddx
    if dy < 0:
        sy, sdy = -1, (y - my) * ddy
    else:
        sy, sdy = 1, (my + 1.0 - y) * ddy
    side = 0
    for _ in range(200):
        if sdx < sdy:
            sdx += ddx
            mx += sx
            side = 0
        else:
            sdy += ddy
            my += sy
            side = 1
        if mx < 0 or my < 0 or mx >= W or my >= H or GRID[my][mx] != ".":
            d = (sdx - ddx) if side == 0 else (sdy - ddy)
            return min(d, MAX_DIST), wall_kind(mx, my), side
    return MAX_DIST, 0, 0


def free_cells() -> list:
    return [(x + 0.5, y + 0.5) for y in range(H) for x in range(W) if GRID[y][x] == "."]


def can_stand(x: float, y: float, r: float = 0.22) -> bool:
    return not (is_wall(x - r, y - r) or is_wall(x + r, y - r) or is_wall(x - r, y + r) or is_wall(x + r, y + r))
