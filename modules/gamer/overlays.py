"""Kleine, rahmenlose Overlay-Fenster (Systemwerte, Tasten).

Kein schwarzer Kasten mehr: Unter Windows/macOS ist der Fensterhintergrund durchsichtig, der Text hat eine dunkle Kontur.
Position, Schrift, Größe und Farbe kommen aus OverlayStyle. Entsperrt lässt sich das Fenster mit der Maus verschieben,
gesperrt gehen Klicks hindurch (wichtig im Spiel). Ein Overlay kann nur über Fenstern und randlosem Vollbild liegen –
über "Vollbild-Exklusiv" (DirectX) kann kein normales Programm zeichnen.
"""
import sys
import tkinter as tk

from core import ui

from . import keyoverlay, sysinfo, winflags
from .overlaystyle import OverlayStyle

KEY = "#010203"            # Farbe, die als "durchsichtig" gilt
BOX = "#101418"
RAISE_MS = 1500


def _make_transparent(w) -> bool:
    try:
        if sys.platform.startswith("win"):
            w.attributes("-transparentcolor", KEY)
            return True
        if sys.platform == "darwin":
            w.attributes("-transparent", True)
            w.configure(bg="systemTransparent")
            return True
    except Exception:
        pass
    return False


class _OverlayWindow:
    """Gemeinsame Hülle: durchsichtiges Fenster, Ziehen, Sperren, Position, immer oben."""

    def __init__(self, app, style: OverlayStyle):
        self.app, self.style = app, style
        self.win = None
        self.transparent = False

    @property
    def active(self):
        return self.win is not None

    def _open(self):
        w = tk.Toplevel(self.app)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=KEY)
        self.transparent = _make_transparent(w)
        if not self.transparent:
            w.configure(bg=BOX)
        try:
            w.attributes("-alpha", self.style.opacity / 100)
        except Exception:
            pass
        w.geometry(f"+{self.style.x}+{self.style.y}")
        w.bind("<ButtonPress-1>", self._down)
        w.bind("<B1-Motion>", self._move)
        self.win = w
        w.update_idletasks()
        winflags.prepare(w, self.style.locked)
        self._raise()
        return w

    def _raise(self):
        if self.win is None:
            return
        try:
            winflags.keep_on_top(self.win)
            self.win.after(RAISE_MS, self._raise)
        except tk.TclError:
            self.win = None

    def _down(self, e):
        if not self.style.locked:
            self._d = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _move(self, e):
        if not self.style.locked and getattr(self, "_d", None):
            self.style.x, self.style.y = e.x_root - self._d[0], e.y_root - self._d[1]
            self.win.geometry(f"+{self.style.x}+{self.style.y}")

    # ---- von der Seite aufgerufen
    def current_position(self) -> tuple[int, int]:
        if self.win is not None:
            try:
                return self.win.winfo_x(), self.win.winfo_y()
            except tk.TclError:
                pass
        return self.style.x, self.style.y

    def move_to(self, x: int, y: int) -> None:
        self.style.x, self.style.y = int(x), int(y)
        self.style.clamp()
        if self.win is not None:
            self.win.geometry(f"+{self.style.x}+{self.style.y}")

    def move_corner(self, name: str) -> None:
        w, h = (self.win.winfo_width(), self.win.winfo_height()) if self.win is not None else (200, 100)
        self.style.corner(name, self.app.winfo_screenwidth(), self.app.winfo_screenheight(), w, h)
        self.move_to(self.style.x, self.style.y)

    def lock(self, on: bool) -> None:
        self.style.locked = bool(on)
        if self.win is not None:
            winflags.prepare(self.win, self.style.locked)

    def restyle(self) -> None:
        """Aussehen geändert: Fenster neu aufbauen (nur wenn es sichtbar ist)."""
        if self.active:
            self.hide()
            self.show()

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


class StatsOverlay(_OverlayWindow):
    def __init__(self, app, style: OverlayStyle | None = None):
        super().__init__(app, style or OverlayStyle())
        self._stats: dict = {}
        self._run = False
        self._last_text = None
        self.show_flags = {"cpu": True, "ram": True, "gpu": True, "fps": True, "ping": True}
        self.fps = sysinfo.FpsMeter()

    def show(self):
        import threading
        self.hide()
        w = self._open()
        weight = "bold" if self.style.bold else "normal"
        import tkinter.font as tkfont
        self.font = tkfont.Font(root=self.app, family=self.style.font, size=self.style.size, weight=weight)
        self.canvas = tk.Canvas(w, bg=BOX if (self.style.background or not self.transparent) else KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._last_text = None
        self._run = True
        threading.Thread(target=self._sampler, daemon=True).start()
        self._refresh()

    def _sampler(self):
        import time
        while self._run:
            self._stats = sysinfo.sample(with_gpu=self.show_flags["gpu"], with_ping=self.show_flags["ping"],
                                        fps=self.fps if self.show_flags["fps"] else None)
            for _ in range(10):
                if not self._run:
                    return
                time.sleep(0.1)

    def _draw(self, text: str):
        c, f, st = self.canvas, self.font, self.style
        lines = text.split("\n")
        pad = 8
        width = max(f.measure(line) for line in lines) + 2 * pad + 2
        height = f.metrics("linespace") * len(lines) + 2 * pad + 2
        c.delete("all")
        c.configure(width=width, height=height)
        if st.outline:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (-1, -1)):
                c.create_text(pad + 1 + dx, pad + 1 + dy, anchor="nw", text=text, font=f, fill="#000000")
        c.create_text(pad + 1, pad + 1, anchor="nw", text=text, font=f, fill=st.color)

    def _refresh(self):
        if self.win is None:
            return
        try:
            text = sysinfo.format_stats(self._stats, self.show_flags) or "…"
            if text != self._last_text:
                self._last_text = text
                self._draw(text)
            self.win.after(500, self._refresh)
        except tk.TclError:
            self.win = None

    def hide(self):
        self._run = False
        super().hide()


class KeysOverlay(_OverlayWindow):
    def __init__(self, app, style: OverlayStyle | None = None):
        super().__init__(app, style or OverlayStyle(font="Segoe UI", size=11, color="#22d3ee", y=500))
        self.state, self.listener = keyoverlay.KeyState(), None
        self.cells: dict = {}
        self.error = ""

    def show(self) -> str:
        self.hide()
        self.state = keyoverlay.KeyState()
        self.listener = keyoverlay.KeyListener(self.state)
        self.error = self.listener.start()
        w = self._open()
        bg = KEY if self.transparent else BOX
        grid = tk.Frame(w, bg=bg)
        grid.pack(padx=8, pady=8)
        self.cells = {}
        for r, row in enumerate(keyoverlay.GRID):
            for c, k in enumerate(row):
                if k:
                    self.cells[k] = self._cell(grid, k.upper(), r, c)
        for i, k in enumerate(keyoverlay.EXTRA):
            self.cells[k] = self._cell(grid, k.capitalize(), 2, i, 1)
        self.cells["mouse_left"] = self._cell(grid, "L", 0, 3)
        self.cells["mouse_right"] = self._cell(grid, "R", 1, 3)
        self.recent = tk.Label(w, text="", fg=self.style.color, bg=bg, font=(self.style.font, max(8, self.style.size - 1)))
        self.recent.pack(pady=(0, 6))
        self._refresh()
        return self.error

    def _cell(self, parent, text, r, c, span=1):
        weight = "bold" if self.style.bold else "normal"
        lab = tk.Label(parent, text=text, width=6 if len(text) > 1 else 3, height=2, fg="#e5e7eb", bg="#2b3138",
                       font=(self.style.font, self.style.size, weight))
        lab.grid(row=r, column=c, padx=2, pady=2)
        return lab

    def _refresh(self):
        if self.win is None:
            return
        try:
            hi = self.style.color
            for k, lab in self.cells.items():
                down = self.state.is_down(k)
                ui.cfg(lab, bg=hi if down else "#2b3138", fg="#001014" if down else "#e5e7eb")
            ui.cfg(self.recent, text=" ".join(self.state.recent_keys()[-6:]))
            self.win.after(40, self._refresh)
        except tk.TclError:
            self.win = None

    def hide(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        super().hide()
