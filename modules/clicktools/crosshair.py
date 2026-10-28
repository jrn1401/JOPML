"""Fadenkreuz-Overlay: kleines, immer sichtbares Zielkreuz in der Bildschirmmitte (Form, Farbe, Größe, Deckkraft)."""
import re
import sys
from dataclasses import asdict, dataclass

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
    react_on: bool = False          # Reaktion beim Schießen ein/aus
    react: str = "Colour on fire"   # Art der Reaktion (linke Maustaste gehalten)
    react_color: str = "#ff3030"
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


SPREAD = 6        # so viele Pixel rücken die Striche beim Schießen auseinander


def state_look(cfg: CrosshairConfig, firing: bool, aiming: bool) -> tuple[str, int, bool]:
    """(Farbe, zusätzliche Lücke, sichtbar) für den aktuellen Zustand."""
    if aiming and cfg.hide_on_aim:
        return cfg.color, 0, False
    if firing and cfg.react_on and cfg.react == "Colour on fire":
        return cfg.react_color, 0, True
    if firing and cfg.react_on and cfg.react == "Spread on fire":
        return cfg.color, SPREAD, True
    return cfg.color, 0, True


def extent(cfg: CrosshairConfig) -> int:
    """Größte Ausdehnung vom Mittelpunkt aus (für die Fenstergröße)."""
    r = cfg.size + (SPREAD if cfg.react_on and cfg.react == "Spread on fire" else 0)
    return max(r, cfg.cover_size if cfg.cover else 0)


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
    Desktop eingeschränkt (siehe Hinweis in der App). Mit "cover" liegt eine ausgefüllte Scheibe unter dem Fadenkreuz und
    verdeckt das Fadenkreuz des Spiels; "react" und "hide_on_aim" folgen den Maustasten."""
    KEY = "#010203"       # wird unter Windows komplett durchsichtig

    def __init__(self, app):
        self.app = app
        self.win = None
        self.canvas = None
        self.cfg = CrosshairConfig()
        self.firing = self.aiming = False
        self._listener = None
        self._looks = None

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
        self._looks = None
        self._draw()
        w.update_idletasks()
        from modules.gamer import winflags
        winflags.prepare(w, True)              # Klicks gehen hindurch, kein Fokus
        if cfg.keep_top:
            self._raise()
        if cfg.react_on or cfg.hide_on_aim:
            self._start_listener()

    def _draw(self):
        if self.win is None:
            return
        color, extra, visible = state_look(self.cfg, self.firing, self.aiming)
        looks = (color, extra, visible)
        if looks == self._looks:
            return
        self._looks = looks
        c, cfg, m = self.canvas, self.cfg, self._box / 2
        c.delete("all")
        if not visible:
            return
        if cfg.cover:
            r = cfg.cover_size
            c.create_oval(m - r, m - r, m + r, m + r, fill=cfg.cover_color, outline=cfg.cover_color)
        for p in primitives(cfg, extra):
            if p[0] == "line":
                c.create_line(m + p[1], m + p[2], m + p[3], m + p[4], fill=color, width=cfg.thickness)
            else:
                c.create_oval(m + p[1], m + p[2], m + p[3], m + p[4], outline=color, width=cfg.thickness,
                              fill=color if p[5] else "")

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
