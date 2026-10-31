"""Rückstoß-Trainer 3D – Übungsfeld (reines tkinter). Liest nur Mausereignisse in diesem Feld, sendet nichts an Windows oder Spiele."""
import random
import tkinter as tk

from . import trainer, trainer3d, weapons

BG = "#111418"
TEXT = "#d1d5db"


class Trainer3DCanvas(tk.Canvas):
    def __init__(self, parent, on_result=None, width=560, height=440):
        super().__init__(parent, width=width, height=height, bg=BG, highlightthickness=0, cursor="crosshair")
        self.on_result = on_result
        self.weapon_id = weapons.DEFAULT_WEAPON
        self.skin_name = "Classic"
        self.sk = weapons.skin("Classic")
        self.pattern_name = "Gerade hoch"
        self.dist_name = "Mittel (25 m)"
        self.mode = "Fest"
        self.strength = 1.0
        self.rate = 10
        self.view = "play"                 # "play" (Schützen-Sicht) oder "orbit" (frei drehbar)
        self.round = None
        self.last = None                   # letzte fertige Runde (für die 3D-Ansicht)
        self.camera = trainer3d.Camera()
        self._mouse = (0, 0)
        self._drag = None
        self._job = None
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<Motion>", self._hover)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._zoom(0.9))
        self.bind("<Button-5>", lambda e: self._zoom(1.1))
        self.bind("<Configure>", lambda e: self.redraw())
        self.redraw()

    # ---- Größe und Hilfsrunde für die Ruhe-Ansicht
    def _size(self):
        return max(self.winfo_width(), 200), max(self.winfo_height(), 200)

    def _idle_round(self):
        w, h = self._size()
        return trainer3d.Round3D(self.pattern_name, self.dist_name, self.mode, self.strength, self.rate, 0, w / 2, h / 2, self.weapon_id)

    def set_skin(self, name):
        self.skin_name, self.sk = name, weapons.skin(name)
        self.configure(bg=self.sk["bg"])
        self.redraw()

    def set_view(self, view):
        self.view = view
        self.cget("cursor")
        self.configure(cursor="fleur" if view == "orbit" else "crosshair")
        self.redraw()

    # ---- Zeichnen
    def _render(self, prims):
        self.delete("all")
        for p in prims:
            kind = p[0]
            if kind == "line" and len(p[1]) >= 2:
                self.create_line(*[c for pt in p[1] for c in pt], fill=p[2], width=p[3])
            elif kind == "oval":
                self.create_oval(*p[1], outline=p[2], fill=p[3])
            elif kind == "text":
                self.create_text(p[1][0], p[1][1], anchor="nw", fill=self.sk["text"] if p[3] == TEXT else p[3], font=("Segoe UI", 10), text=p[2])

    def redraw(self):
        w, h = self._size()
        self.camera.w, self.camera.h = w, h
        if self.view == "orbit":
            rd = self.last or self.round
            if rd is None:
                self._render([("text", (12, 12), "Erst eine Runde spielen – dann kannst du hier den Raum drehen.", TEXT)])
                return
            self._render(trainer3d.orbit_primitives(self.camera, rd))
            return
        rd = self.round if (self.round is not None and self._job is not None) else None
        if rd is None:
            rd = self._idle_round()
            prims = trainer3d.play_primitives(rd, self._mouse, 0.0, w, h)
            prims.append(("text", (w / 2 - 190, 40), "Auf die Scheibe zielen, klicken und gedrückt halten", TEXT))
            self._render(prims)
            self.create_oval(self._mouse[0] - 6, self._mouse[1] - 6, self._mouse[0] + 6, self._mouse[1] + 6, outline="#ffffff")
            return
        t = trainer3d.Round3D.time_of(rd, len(rd.shots))
        self._render(trainer3d.play_primitives(rd, self._mouse, t, w, h))

    # ---- Maus
    def _hover(self, e):
        self._mouse = (e.x, e.y)
        if self.view == "play" and self._job is None:
            self.redraw()

    def _press(self, e):
        self._mouse = (e.x, e.y)
        if self.view == "orbit":
            self._drag = (e.x, e.y)
            return
        self.stop()
        w, h = self._size()
        self.round = trainer3d.Round3D(self.pattern_name, self.dist_name, self.mode, self.strength, self.rate,
                                       random.randrange(1 << 30), w / 2, h / 2, self.weapon_id)
        self._tick()

    def _move(self, e):
        if self.view == "orbit":
            if self._drag is not None:
                dx, dy = e.x - self._drag[0], e.y - self._drag[1]
                self.camera.rotate(-dx * 0.01, dy * 0.01)
                self._drag = (e.x, e.y)
                self.redraw()
            return
        self._mouse = (e.x, e.y)
        if self._job is not None:
            self.redraw()

    def _release(self, e):
        self._drag = None
        if self.view == "play":
            self._finish()

    def _wheel(self, e):
        self._zoom(0.9 if e.delta > 0 else 1.1)

    def _zoom(self, f):
        if self.view == "orbit":
            self.camera.zoom(f)
            self.redraw()

    def _tick(self):
        rd = self.round
        if rd is None:
            return
        rd.shoot(*self._mouse)
        self.redraw()
        if rd.done:
            self._finish(running=True)
            return
        self._job = self.after(max(40, int(1000 / max(1, self.rate))), self._tick)

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _finish(self, running=None):
        rd = self.round
        was = self._job is not None if running is None else running
        self.stop()
        if rd is None or not rd.shots or getattr(rd, "reported", False) or not (was or rd.done):
            return
        rd.reported = True
        self.last = rd
        self.redraw()
        res = rd.result()
        res.update(pattern=self.pattern_name, distance=self.dist_name, mode=self.mode, weapon=self.weapon_id)
        w, h = self._size()
        self.create_text(w // 2, h - 40, fill=self.sk["text"], font=("Segoe UI", 13, "bold"), text=f"{res['score']} Punkte – {res['accuracy']} % Treffer")
        if self.on_result is not None:
            self.on_result(res)
