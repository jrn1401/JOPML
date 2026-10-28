"""Benachrichtigungen: Ton (eingebaut oder eigene Datei), Pop-up-Fenster, Ruhezeiten und Ereignis-Auswahl.

Die Einstellungen liegen in settings["notify"]. `Prefs` prüft und begrenzt alle Werte (auch aus Sicherungsdateien).
Ton und Fenster brauchen eine Oberfläche; `should_notify` und die Tonerzeugung sind reine Logik und testbar."""
import datetime
import math
import re
import shutil
import struct
import subprocess
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path

from core import config

EVENTS = {"chat": "New chat messages", "mention": "Mentions and replies", "invite": "Invitations", "timer": "Timer reminders"}
SOUNDS = ["System beep", "Chime", "Pop", "Ding", "Custom file", "Off"]
POSITIONS = ["Top right", "Top left", "Bottom right", "Bottom left"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_SOUND_BYTES = 5_000_000


@dataclass
class Prefs:
    enabled: bool = True
    sound: str = "Chime"
    custom_path: str = ""
    volume: int = 70
    popup: bool = True
    position: str = "Bottom right"
    duration: int = 5
    opacity: int = 95
    color: str = ""                 # Hintergrundfarbe des Pop-ups (#RRGGBB), leer = Farbe des Designs
    events: dict = field(default_factory=lambda: {k: True for k in EVENTS})
    quiet: bool = False
    quiet_from: str = "22:00"
    quiet_to: str = "07:00"

    def clamp(self) -> "Prefs":
        self.enabled, self.popup, self.quiet = bool(self.enabled), bool(self.popup), bool(self.quiet)
        self.sound = self.sound if self.sound in SOUNDS else "Chime"
        self.custom_path = str(self.custom_path or "")[:500]
        self.volume = max(0, min(100, int(self.volume)))
        self.position = self.position if self.position in POSITIONS else "Bottom right"
        self.duration = max(2, min(30, int(self.duration)))
        self.opacity = max(40, min(100, int(self.opacity)))
        self.color = self.color if isinstance(self.color, str) and _HEX.match(self.color) else ""
        ev = self.events if isinstance(self.events, dict) else {}
        self.events = {k: bool(ev.get(k, True)) for k in EVENTS}
        for a in ("quiet_from", "quiet_to"):
            if not _TIME.match(str(getattr(self, a))):
                setattr(self, a, "22:00" if a == "quiet_from" else "07:00")
        return self

    @classmethod
    def from_dict(cls, d) -> "Prefs":
        p = cls()
        if isinstance(d, dict):
            for k, v in d.items():
                if k in p.__dict__:
                    try:
                        setattr(p, k, v if k == "events" else type(getattr(p, k))(v))
                    except (TypeError, ValueError):
                        pass
        return p.clamp()

    def to_dict(self) -> dict:
        return dict(self.__dict__, events=dict(self.events))


def in_quiet_hours(p: Prefs, now: datetime.datetime) -> bool:
    if not p.quiet:
        return False
    def mins(t):
        h, m = t.split(":")
        return int(h) * 60 + int(m)
    a, b, cur = mins(p.quiet_from), mins(p.quiet_to), now.hour * 60 + now.minute
    if a == b:
        return False
    return a <= cur < b if a < b else (cur >= a or cur < b)      # über Mitternacht


def should_notify(p: Prefs, event: str, now: datetime.datetime | None = None) -> bool:
    return p.enabled and bool(p.events.get(event, False)) and not in_quiet_hours(p, now or datetime.datetime.now())


# ---------------------------------------------------------------- Töne
_TONES = {            # Name -> Liste (Frequenz Hz, Dauer s)
    "Chime": [(880, 0.12), (1320, 0.22)],
    "Pop": [(520, 0.05), (780, 0.07)],
    "Ding": [(1568, 0.35)],
}
RATE = 22050


def make_wav(path: Path, kind: str, volume: int) -> Path:
    """Erzeugt einen kurzen Ton (Sinus mit weichem Aus-Klang). Lautstärke 0–100 steckt in der Datei."""
    amp = 0.6 * max(0, min(100, volume)) / 100
    frames = bytearray()
    for freq, dur in _TONES[kind]:
        n = int(RATE * dur)
        for i in range(n):
            env = min(1.0, i / (RATE * 0.005)) * (1 - i / n) ** 1.5
            frames += struct.pack("<h", int(32767 * amp * env * math.sin(2 * math.pi * freq * i / RATE)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return path


def sound_file(p: Prefs) -> Path | None:
    """Datei, die gespielt werden soll (None = Systemton oder aus)."""
    if p.sound in _TONES:
        f = config.app_dir() / "sounds" / f"{p.sound.lower()}-{p.volume}.wav"
        if not f.exists():
            make_wav(f, p.sound, p.volume)
        return f
    if p.sound == "Custom file" and p.custom_path:
        f = Path(p.custom_path)
        if f.is_file() and f.suffix.lower() in (".wav", ".mp3", ".aiff", ".m4a", ".ogg") and f.stat().st_size <= MAX_SOUND_BYTES:
            return f
    return None


def play_file(f: Path, volume: int = 100) -> None:
    """Spielt eine Datei im Hintergrund. Fehler werden still ignoriert (ein fehlender Ton darf nie stören)."""
    try:
        if sys.platform.startswith("win"):
            import winsound
            if f.suffix.lower() == ".wav":
                winsound.PlaySound(str(f), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", "-v", f"{max(0.0, min(1.0, volume / 100)):.2f}", str(f)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for tool, args in (("paplay", []), ("aplay", ["-q"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"])):
                if shutil.which(tool):
                    subprocess.Popen([tool, *args, str(f)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
    except Exception:
        pass


# ---------------------------------------------------------------- Pop-up
TOAST_WIDTH, TOAST_KEY, MAX_TOAST_TEXT = 340, "#010203", 600


def round_rect_points(x0: float, y0: float, x1: float, y1: float, r: float) -> list[float]:
    """Eckpunkte eines Rechtecks mit abgerundeten Ecken für Canvas.create_polygon(..., smooth=True)."""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]


class Notifier:
    def __init__(self, app):
        self.app = app
        self._toasts: list = []

    def prefs(self) -> Prefs:
        return Prefs.from_dict(self.app.settings.get("notify"))

    def notify(self, event: str, title: str, text: str = "", force: bool = False) -> bool:
        """Zeigt Ton und/oder Pop-up gemäß den Einstellungen. force=True (Testknopf) ignoriert Ereignis-Auswahl und Ruhezeiten."""
        p = self.prefs()
        if not force and not should_notify(p, event):
            return False
        if p.enabled or force:
            self.play(p)
            if p.popup:
                try:
                    self._toast(p, title, text)
                except Exception:
                    pass
        return True

    def play(self, p: Prefs | None = None) -> None:
        p = p or self.prefs()
        if p.sound == "Off":
            return
        f = sound_file(p)
        if f is not None:
            play_file(f, p.volume)
        else:
            try:
                self.app.bell()
            except Exception:
                pass

    def _toast(self, p: Prefs, title: str, text: str) -> None:
        """Rundes Pop-up. Lange Texte werden umgebrochen: der Rest rutscht eine Zeile tiefer, das Fenster wächst mit."""
        import sys
        import tkinter as tk
        import customtkinter as ctk
        from core import theme
        dark = ctk.get_appearance_mode() == "Dark"
        pick = lambda pair: pair[1] if dark else pair[0]
        if p.color:
            bg = p.color
            fg = muted = theme.contrast_text(bg)
        else:
            bg, fg, muted = pick(theme.c("card")), pick(theme.TEXT), pick(theme.MUTED)
        acc = theme.accent()
        w, pad, radius = TOAST_WIDTH, 14, 18
        win = tk.Toplevel(self.app)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        key, rounded = TOAST_KEY, False
        try:
            if sys.platform.startswith("win"):
                win.attributes("-transparentcolor", key)
                rounded = True
            elif sys.platform == "darwin":
                win.attributes("-transparent", True)
                key, rounded = "systemTransparent", True
        except Exception:
            pass
        win.configure(bg=key if rounded else bg)
        try:
            win.attributes("-alpha", p.opacity / 100)
        except Exception:
            pass
        cv = tk.Canvas(win, width=w, height=100, bg=key if rounded else bg, highlightthickness=0, bd=0)
        cv.pack()
        wrap = w - 2 * pad - 4
        t1 = cv.create_text(pad + 2, pad, anchor="nw", text=title[:120], fill=fg, font=("Helvetica", 12, "bold"), width=wrap)
        y2 = cv.bbox(t1)[3] + 4
        t2 = cv.create_text(pad + 2, y2, anchor="nw", text=text[:MAX_TOAST_TEXT], fill=muted, font=("Helvetica", 11), width=wrap) if text else None
        bottom = cv.bbox(t2)[3] if t2 else cv.bbox(t1)[3]
        h = min(int(self.app.winfo_screenheight() * 0.6), bottom + pad)
        cv.configure(height=h)
        cv.create_polygon(round_rect_points(1, 1, w - 1, h - 1, radius), smooth=True, fill=bg, outline=acc, width=2, tags="shape")
        cv.tag_lower("shape")
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        used = sum(hh + 8 for _w, hh in self._toasts)
        x = sw - w - 20 if "right" in p.position.lower() else 20
        y = (60 + used) if p.position.startswith("Top") else sh - h - 80 - used
        win.geometry(f"{w}x{h}+{x}+{max(0, y)}")
        entry = (win, h)
        self._toasts.append(entry)

        def close(_e=None):
            if entry in self._toasts:
                self._toasts.remove(entry)
            try:
                win.destroy()
            except Exception:
                pass
        cv.bind("<Button-1>", close)
        win.bind("<Button-1>", close)
        win.after(p.duration * 1000, close)
