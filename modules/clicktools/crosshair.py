from core import perf
"""Fadenkreuz-Overlay: kleines, immer sichtbares Zielkreuz in der Bildschirmmitte (Form, Farbe, Größe, Deckkraft)."""
import re
import sys
from dataclasses import asdict, dataclass

COVER_SHAPES = ["Disc", "Square", "Cross"]
REACTIONS = ["Colour on fire", "Spread on fire"]
SHAPES = ["Cross", "Cross with gap", "Dot", "Circle", "Circle + dot", "T-shape"]
PRESETS = {
    "Classic green": {"shape": "Cross", "color": "#00ff00", "size": 16, "thickness": 2, "gap": 0, "opacity": 100},
    "Tactical": {"shape": "Cross with gap", "color": "#ffffff", "size": 14, "thickness": 2, "gap": 5, "opacity": 90},
    "Red dot": {"shape": "Dot", "color": "#ff2020", "size": 6, "thickness": 2, "gap": 0, "opacity": 100},
    "Ring": {"shape": "Circle + dot", "color": "#22d3ee", "size": 18, "thickness": 2, "gap": 0, "opacity": 85},
    "Sniper T": {"shape": "T-shape", "color": "#facc15", "size": 20, "thickness": 2, "gap": 3, "opacity": 100},
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class CrosshairConfig:
    shape: str = "Cross"
    color: str = "#00ff00"
    size: int = 16          # Halbe Länge / Radius in Pixeln
    thickness: int = 2
    gap: int = 0
    opacity: int = 100      # Prozent
    offset_x: int = 0
    offset_y: int = 0
    cover: bool = False             # deckt das Fadenkreuz des Spiels mit einer ausgefüllten Scheibe ab
    cover_size: int = 10            # Radius der Scheibe in Pixeln
    cover_color: str = "#101418"
    cover_shape: str = "Cross"      # Scheibe, Quadrat oder Kreuz (deckt nur die Striche des Spiel-Fadenkreuzes ab)
    cover_thickness: int = 6        # Strichbreite beim Kreuz in Pixeln
    cover_auto: bool = True         # Farbe aus der Umgebung des Fadenkreuzes nehmen statt einer festen Farbe
    react_on: bool = False          # Reaktion beim Schießen ein/aus
    react: str = "Colour on fire"   # Art der Reaktion (linke Maustaste gehalten)
    react_color: str = "#ff3030"
    spread_px: int = 6              # so weit rücken die Striche beim Schießen auseinander
    spread_rise_ms: int = 80        # Zeit bis zur vollen Streuung beim Schießen
    spread_fall_ms: int = 250       # Zeit, bis die Streuung nach dem Schießen wieder zurück ist
    keep_top: bool = True           # regelmäßig wieder über das Spiel holen
    hide_on_aim: bool = False       # beim Zielen (rechte Maustaste gehalten) ausblenden, z. B. wenn das Spiel ein Visier zeigt

    def clamp(self) -> "CrosshairConfig":
        self.shape = self.shape if self.shape in SHAPES else "Cross"
        self.color = self.color if _HEX.match(str(self.color)) else "#00ff00"
        self.size = max(2, min(80, int(self.size)))
        self.thickness = max(1, min(8, int(self.thickness)))
        self.gap = max(0, min(self.size - 1, int(self.gap)))
        self.opacity = max(20, min(100, int(self.opacity)))
        self.offset_x = max(-400, min(400, int(self.offset_x)))
        self.offset_y = max(-400, min(400, int(self.offset_y)))
        self.cover, self.hide_on_aim = bool(self.cover), bool(self.hide_on_aim)
        self.react_on, self.keep_top = bool(self.react_on), bool(self.keep_top)
        self.cover_size = max(2, min(120, int(self.cover_size)))
        self.cover_color = self.cover_color if _HEX.match(str(self.cover_color)) else "#101418"
        self.cover_shape = self.cover_shape if self.cover_shape in COVER_SHAPES else "Cross"
        self.cover_thickness = max(1, min(40, int(self.cover_thickness)))
        self.cover_auto = bool(self.cover_auto)
        self.spread_px = max(0, min(60, int(self.spread_px)))
        self.spread_rise_ms = max(10, min(2000, int(self.spread_rise_ms)))
        self.spread_fall_ms = max(10, min(3000, int(self.spread_fall_ms)))
        self.react = self.react if self.react in REACTIONS else REACTIONS[0]
        self.react_color = self.react_color if _HEX.match(str(self.react_color)) else "#ff3030"
        return self

    @classmethod
    def from_dict(cls, d) -> "CrosshairConfig":
        base = cls()
        if isinstance(d, dict):
            for k, v in d.items():
                if k in base.__dict__:
                    try:
                        cur = getattr(base, k)
                        setattr(base, k, (v if isinstance(v, bool) else bool(v)) if isinstance(cur, bool) else type(cur)(v))
                    except (TypeError, ValueError):
                        pass
        if isinstance(d, dict) and "react_on" not in d and d.get("react") in REACTIONS:
            base.react_on = True            # Einstellung aus Version 1.5.2 (Art der Reaktion war zugleich der Schalter)
        return base.clamp()

    def to_dict(self) -> dict:
        return asdict(self)


def state_look(cfg: CrosshairConfig, firing: bool, aiming: bool) -> tuple[str, int, bool]:
    """(Farbe, Ziel-Streuung in Pixeln, sichtbar) für den aktuellen Zustand. Die Streuung läuft im Overlay weich auf dieses Ziel zu."""
    if aiming and cfg.hide_on_aim:
        return cfg.color, 0, False
    if firing and cfg.react_on and cfg.react == "Colour on fire":
        return cfg.react_color, 0, True
    if firing and cfg.react_on and cfg.react == "Spread on fire":
        return cfg.color, cfg.spread_px, True
    return cfg.color, 0, True


def step_spread(cur: float, target: float, cfg: CrosshairConfig, dt_ms: float) -> float:
    """Ein Zeitschritt der Streuung: steigt in spread_rise_ms auf spread_px und fällt in spread_fall_ms wieder auf 0."""
    full = max(1, cfg.spread_px)
    if target > cur:
        return min(target, cur + full * dt_ms / cfg.spread_rise_ms)
    return max(target, cur - full * dt_ms / cfg.spread_fall_ms)


def extent(cfg: CrosshairConfig) -> int:
    """Größte Ausdehnung vom Mittelpunkt aus (für die Fenstergröße)."""
    r = cfg.size + (cfg.spread_px if cfg.react_on and cfg.react == "Spread on fire" else 0)
    return max(r, cfg.cover_size if cfg.cover else 0)


def cover_shapes(cfg: CrosshairConfig) -> list[tuple]:
    """Gefüllte Abdeckung relativ zur Mitte: (Name, Art, x1, y1, x2, y2). Name: "all", "h" oder "v" (Farbe pro Achse)."""
    r, t = cfg.cover_size, max(1, cfg.cover_thickness)
    h = t / 2
    if cfg.cover_shape == "Disc":
        return [("all", "oval", -r, -r, r, r)]
    if cfg.cover_shape == "Square":
        return [("all", "rect", -r, -r, r, r)]
    return [("h", "rect", -r, -h, r, h), ("v", "rect", -h, -r, h, r)]


def primitives(cfg: CrosshairConfig, extra_gap: int = 0) -> list[tuple]:
    """Zeichenbefehle relativ zur Mitte (0, 0): ("line", x1, y1, x2, y2) oder ("oval", x1, y1, x2, y2, filled)."""
    s, g = cfg.size + extra_gap, cfg.gap + extra_gap
    out: list[tuple] = []
    if cfg.shape in ("Cross", "Cross with gap"):
        g = g if cfg.shape == "Cross with gap" else 0
        out += [("line", -s, 0, -g, 0), ("line", g, 0, s, 0), ("line", 0, -s, 0, -g), ("line", 0, g, 0, s)]
    elif cfg.shape == "T-shape":
        out += [("line", -s, 0, -g, 0), ("line", g, 0, s, 0), ("line", 0, g, 0, s)]
    if cfg.shape in ("Dot", "Circle + dot"):
        r = max(1, cfg.thickness) if cfg.shape == "Circle + dot" else s
        out.append(("oval", -r, -r, r, r, True))
    if cfg.shape in ("Circle", "Circle + dot"):
        out.append(("oval", -s, -s, s, s, False))
    return out


class CrosshairOverlay:
    """Rahmenloses, durchsichtiges Fenster. Klick-durchlässig unter Windows; auf macOS/Linux ist die Durchsichtigkeit je nach
    Desktop eingeschränkt (siehe Hinweis in der App). Mit "cover" liegt eine ausgefüllte Form (Scheibe, Quadrat oder nur ein Kreuz)
    unter dem Fadenkreuz und verdeckt das Fadenkreuz des Spiels; ihre Farbe kann live aus der Umgebung genommen werden, damit
    nichts Dunkles stört. "react" und "hide_on_aim" folgen den Maustasten, die Streuung läuft weich."""
    KEY = "#010203"       # wird unter Windows komplett durchsichtig
    RING = 6              # so breit ist der Streifen um das Fenster, aus dem die Umgebungsfarbe gelesen wird

    def __init__(self, app):
        self.app = app
        self.win = None
        self.canvas = None
        self.cfg = CrosshairConfig()
        self.firing = self.aiming = False
        self._listener = None
        self._looks = None
        self.spread = 0.0

    @property
    def active(self) -> bool:
        return self.win is not None

    def show(self, cfg: CrosshairConfig):
        import tkinter as tk
        self.hide()
        cfg = self.cfg = CrosshairConfig.from_dict(cfg.to_dict())
        box = extent(cfg) * 2 + 8
        w = tk.Toplevel(self.app)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        sx, sy = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry(f"{box}x{box}+{sx // 2 - box // 2 + cfg.offset_x}+{sy // 2 - box // 2 + cfg.offset_y}")
        bg = self.KEY
        try:
            if sys.platform.startswith("win"):
                w.attributes("-transparentcolor", bg)
            elif sys.platform == "darwin":
                w.attributes("-transparent", True)
                bg = "systemTransparent"
            w.attributes("-alpha", cfg.opacity / 100)
        except Exception:
            pass
        w.configure(bg=bg)
        self.canvas = tk.Canvas(w, width=box, height=box, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._box = box
        self.win = w
        self.firing = self.aiming = False
        self.spread = 0.0
        self._looks = None
        self._draw()
        w.update_idletasks()
        from modules.gamer import winflags
        winflags.prepare(w, True)              # Klicks gehen hindurch, kein Fokus
        if cfg.keep_top:
            self._raise()
        if cfg.react_on or cfg.hide_on_aim:
            self._start_listener()
        if cfg.cover and cfg.cover_auto:
            self._cover_colors()
        if cfg.react_on and cfg.react == "Spread on fire":
            self._animate()

    def _draw(self):
        if self.win is None:
            return
        color, target, visible = state_look(self.cfg, self.firing, self.aiming)
        extra = int(round(self.spread)) if self.cfg.react == "Spread on fire" and self.cfg.react_on else 0
        looks = (color, extra, visible)
        if looks == self._looks:
            return
        self._looks = looks
        c, cfg, m = self.canvas, self.cfg, self._box / 2
        c.delete("all")
        if not visible:
            return
        if cfg.cover:
            for name, kind, x1, y1, x2, y2 in cover_shapes(cfg):
                draw = c.create_oval if kind == "oval" else c.create_rectangle
                draw(m + x1, m + y1, m + x2, m + y2, fill=cfg.cover_color, outline=cfg.cover_color, tags=("cover", "cover_" + name))
            self._cover_apply()
        for p in primitives(cfg, extra):
            if p[0] == "line":
                c.create_line(m + p[1], m + p[2], m + p[3], m + p[4], fill=color, width=cfg.thickness)
            else:
                c.create_oval(m + p[1], m + p[2], m + p[3], m + p[4], outline=color, width=cfg.thickness,
                              fill=color if p[5] else "")

    # ---- Abdeckung in Umgebungsfarbe
    def _cover_colors(self):
        """Liest alle 250 ms die Farbe direkt um das Fenster und färbt die Abdeckung so, dass sie nicht als dunkler Fleck auffällt."""
        if self.win is None or not (self.cfg.cover and self.cfg.cover_auto):
            return
        try:
            from PIL import ImageGrab
            r, box = self.RING, self._box
            x0, y0 = self.win.winfo_rootx() - r, self.win.winfo_rooty() - r
            img = ImageGrab.grab(bbox=(x0, y0, x0 + box + 2 * r, y0 + box + 2 * r)).convert("RGB")
            self._ring = ring_colors(img, box, r)
            self._cover_apply()
        except Exception:
            self._ring = None
        try:
            self.win.after(250, self._cover_colors)
        except Exception:
            pass

    def _cover_apply(self):
        ring = getattr(self, "_ring", None)
        if not (self.cfg.cover and self.cfg.cover_auto and ring) or self.canvas is None:
            return
        hexc = lambda rgb: "#%02x%02x%02x" % rgb
        both = hexc(mix(ring["left"], ring["right"], ring["top"], ring["bottom"]))
        colors = {"all": both, "h": hexc(mix(ring["left"], ring["right"])), "v": hexc(mix(ring["top"], ring["bottom"]))}
        for name, col in colors.items():
            try:
                self.canvas.itemconfig("cover_" + name, fill=col, outline=col)
            except Exception:
                pass

    # ---- weiche Streuung beim Schießen
    def _animate(self, last=None):
        if self.win is None or not (self.cfg.react_on and self.cfg.react == "Spread on fire"):
            return
        import time
        now = time.perf_counter()
        dt = 30.0 if last is None else min(100.0, (now - last) * 1000)
        _c, target, visible = state_look(self.cfg, self.firing, self.aiming)
        self.spread = step_spread(self.spread, target, self.cfg, dt)
        self._draw()
        self.win.after(perf.ms(30), lambda: self._animate(now))

    def _raise(self):
        if self.win is None:
            return
        try:
            from modules.gamer import winflags
            winflags.keep_on_top(self.win)
            self.win.after(1500, self._raise)
        except Exception:
            pass

    def _start_listener(self):
        try:
            from pynput import mouse

            def on_click(_x, _y, button, pressed):
                name = str(button)
                if name == "Button.left":
                    self.firing = bool(pressed)
                elif name == "Button.right":
                    self.aiming = bool(pressed)
                else:
                    return
                self.app.call_soon(self._draw)
            self._listener = mouse.Listener(on_click=on_click)
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            self._listener = None

    def hide(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


def mix(*colors) -> tuple[int, int, int]:
    """Mittelwert mehrerer RGB-Farben."""
    n = len(colors)
    return tuple(int(sum(c[i] for c in colors) / n) for i in range(3))


def ring_colors(img, box: int, ring: int) -> dict:
    """Farben direkt außerhalb des Fensters (links, rechts, oben, unten), jeweils Mittel aus drei Bildpunkten.
    img ist der Bildausschnitt mit einem Rand von `ring` Pixeln um das Fenster."""
    mid = ring + box // 2
    near = ring // 2

    def avg(points):
        return mix(*[img.getpixel(p) for p in points])
    span = (-1, 0, 1)
    return {"left": avg([(near, mid + d) for d in span]), "right": avg([(ring + box + near, mid + d) for d in span]),
            "top": avg([(mid + d, near) for d in span]), "bottom": avg([(mid + d, ring + box + near) for d in span])}
