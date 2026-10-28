"""Aussehen und Position der Overlays (Systemwerte, Tasten). Reine Logik: prüft und begrenzt alle Werte."""
import re
from dataclasses import dataclass

FONTS = ["Consolas", "Segoe UI", "Arial", "Verdana", "Courier New", "Helvetica"]
CORNERS = ["Top left", "Top right", "Bottom left", "Bottom right"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LIMITS = {"size": (8, 60), "opacity": (30, 100), "x": (-200, 10000), "y": (-200, 10000)}


@dataclass
class OverlayStyle:
    font: str = "Consolas"
    size: int = 14
    color: str = "#e5e7eb"
    bold: bool = True
    outline: bool = True            # dunkle Kontur statt Kasten: bleibt auf jedem Hintergrund lesbar
    background: bool = False        # optional: dunkler Kasten hinter dem Text
    opacity: int = 100
    x: int = 20
    y: int = 60
    locked: bool = False            # gesperrt = Mausklicks gehen durch das Overlay hindurch (nötig im Spiel)

    def clamp(self) -> "OverlayStyle":
        self.font = self.font if self.font in FONTS else FONTS[0]
        self.color = self.color if isinstance(self.color, str) and _HEX.match(self.color) else "#e5e7eb"
        for k, (lo, hi) in LIMITS.items():
            setattr(self, k, max(lo, min(hi, int(getattr(self, k)))))
        self.bold, self.outline, self.background, self.locked = (bool(self.bold), bool(self.outline), bool(self.background), bool(self.locked))
        return self

    @classmethod
    def from_dict(cls, d, **defaults) -> "OverlayStyle":
        s = cls(**defaults)
        if isinstance(d, dict):
            for k, v in d.items():
                if k in s.__dict__:
                    try:
                        setattr(s, k, v if k in ("font", "color") else (bool(v) if isinstance(getattr(s, k), bool) else int(v)))
                    except (TypeError, ValueError):
                        pass
        return s.clamp()

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    def corner(self, name: str, screen_w: int, screen_h: int, win_w: int, win_h: int, margin: int = 20) -> None:
        """Setzt x/y auf eine Bildschirmecke."""
        right, bottom = "right" in name.lower(), name.lower().startswith("bottom")
        self.x = screen_w - win_w - margin if right else margin
        self.y = screen_h - win_h - margin - (40 if bottom else 0) if bottom else margin
        self.clamp()
