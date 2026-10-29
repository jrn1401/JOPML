"""Rückstoß-Trainer – Übungsfeld (reines tkinter, damit es überall gleich aussieht und sich testen lässt).

Liest nur Mausereignisse in diesem Feld. Sendet keine Eingaben an Windows oder an Spiele.
"""
import random
import tkinter as tk

from . import trainer

BG = "#111418"
GRID = "#1f252c"
TARGET = "#4f8cff"
GUIDE = "#6b7280"
TEXT = "#d1d5db"


class TrainerCanvas(tk.Canvas):
    def __init__(self, parent, on_result=None, width=560, height=440):
        super().__init__(parent, width=width, height=height, bg=BG, highlightthickness=0, cursor="crosshair")
        self.on_result = on_result          # Funktion(result: dict) nach jeder Runde
        self.pattern_name = "Gerade hoch"
        self.strength = 1.0
        self.rate = 10                      # Schuss pro Sekunde
        self.show_guide = True
        self.round = None
        self._mouse = (0, 0)
        self._job = None
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", lambda e: self._idle_screen())
        self._idle_screen()

    # ---- Anzeige ----
    def _grid(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        for x in range(0, w, 40):
            self.create_line(x, 0, x, h, fill=GRID)
        for y in range(0, h, 40):
            self.create_line(0, y, w, y, fill=GRID)

    def _idle_screen(self):
        if self._job is not None:
            return
        self._grid()
        w = max(self.winfo_width(), 560)
        self.create_text(w // 2, 40, fill=TEXT, font=("Segoe UI", 12, "bold"),
                         text="Im oberen Drittel klicken und gedrückt halten")
        self.create_text(w // 2, 64, fill=GUIDE, font=("Segoe UI", 10),
                         text="Zieh die Maus gegen den Rückstoß, damit die Treffer im blauen Ziel bleiben.")

    def _draw(self):
        r = self.round
        self._grid()
        sx, sy = r.start_pos
        for rad in (10, 25):
            self.create_oval(sx - rad, sy - rad, sx + rad, sy + rad, outline=TARGET)
        self.create_line(sx - 34, sy, sx + 34, sy, fill=TARGET)
        self.create_line(sx, sy - 34, sx, sy + 34, fill=TARGET)
        if self.show_guide:
            pts = [(sx, sy)] + trainer.ideal_path((sx, sy), r.pat)
            self.create_line(*[c for p in pts for c in p], fill=GUIDE, dash=(4, 3), smooth=True)
        for h in r.hits:
            col = trainer.color_for(r.distance(h))
            self.create_oval(h[0] - 3, h[1] - 3, h[0] + 3, h[1] + 3, fill=col, outline="")
        if not r.done:
            ax, ay = r.aim(*self._mouse)
            self.create_oval(ax - 6, ay - 6, ax + 6, ay + 6, outline="#ffffff")
        self.create_text(10, 10, anchor="nw", fill=TEXT, font=("Segoe UI", 10),
                         text=f"{self.pattern_name}   Schuss {len(r.hits)}/{len(r.pat)}")

    # ---- Maus ----
    def _press(self, e):
        self.stop()
        pat = trainer.scaled(trainer.pattern(self.pattern_name, seed=random.randrange(1 << 30)), self.strength)
        self.round = trainer.Round(pat)
        self.round.start(e.x, e.y)
        self._mouse = (e.x, e.y)
        self._tick()

    def _move(self, e):
        self._mouse = (e.x, e.y)
        if self._job is not None:
            self._draw()

    def _release(self, e):
        self._finish()

    def _tick(self):
        r = self.round
        if r is None:
            return
        r.shot(*self._mouse)
        self._draw()
        if r.done:
            self._finish()
            return
        self._job = self.after(max(40, int(1000 / max(1, self.rate))), self._tick)

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _finish(self):
        """Runde beenden (Maus losgelassen oder alle Schüsse abgegeben) und Ergebnis melden – nur einmal je Runde."""
        r = self.round
        running = self._job is not None
        self.stop()
        if r is None or not r.hits or getattr(r, "reported", False) or not (running or r.done):
            return
        r.reported = True
        self._draw()
        res = r.result()
        res["pattern"] = self.pattern_name
        w, h = max(self.winfo_width(), 560), max(self.winfo_height(), 440)
        self.create_text(w // 2, h - 40, fill=TEXT, font=("Segoe UI", 13, "bold"),
                         text=f"{res['score']} Punkte – {res['rating']}")
        if self.on_result is not None:
            self.on_result(res)
