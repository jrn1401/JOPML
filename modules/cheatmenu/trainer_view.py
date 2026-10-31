"""Rückstoß-Trainer – Übungsfeld (reines tkinter, damit es überall gleich aussieht und sich testen lässt).

Liest nur Mausereignisse in diesem Feld. Sendet keine Eingaben an Windows oder an Spiele.

Flüssig: Gezeichnet wird mit etwa 60 Bildern pro Sekunde, unabhängig vom Schusstakt (weapons.ShotClock). Das Fadenkreuz gleitet
zur Zielposition, die Spur der Treffer blendet aus, nur bewegte Teile werden pro Bild neu gezeichnet (der Hintergrund bleibt stehen).
"""
import random
import time
import tkinter as tk

from . import trainer, weapons

FRAME_MS = 16


class TrainerCanvas(tk.Canvas):
    def __init__(self, parent, on_result=None, width=560, height=440):
        self.sk = weapons.skin("Classic")
        super().__init__(parent, width=width, height=height, bg=self.sk["bg"], highlightthickness=0, cursor="crosshair")
        self.on_result = on_result          # Funktion(result: dict) nach jeder Runde
        self.pattern_name = "Gerade hoch"
        self.weapon_id = weapons.DEFAULT_WEAPON
        self.skin_name = "Classic"
        self.crosshair = "Ring"
        self.marker = "Dot"
        self.strength = 1.0
        self.rate = 10                      # Schuss pro Sekunde
        self.show_guide = True
        self.round = None
        self.last_round = None              # letzte fertige Runde (für die Wiederholung)
        self._mouse = (0, 0)
        self._disp = None                   # gleitende Anzeigeposition des Fadenkreuzes
        self._job = None
        self._clock = None
        self._t_last = 0.0
        self._hit_t: list = []              # Zeitpunkt jedes Treffers (für das Verblassen der Spur)
        self._mode = "idle"                 # idle | play | replay
        self._bg_size = None
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", lambda e: self._redraw_static())
        self._redraw_static()

    # ---- Design ----
    def set_skin(self, name: str) -> None:
        self.skin_name, self.sk = name, weapons.skin(name)
        self.configure(bg=self.sk["bg"])
        self._bg_size = None
        self._redraw_static()
        if self._job is None and self.round is not None:
            self._draw_dynamic(time.perf_counter())

    def _size(self):
        return max(self.winfo_width(), 560), max(self.winfo_height(), 300)

    def _redraw_static(self):
        """Hintergrund (Raster) nur neu zeichnen, wenn sich Größe oder Design geändert haben."""
        w, h = self._size()
        if self._bg_size == (w, h, self.skin_name):
            return
        self._bg_size = (w, h, self.skin_name)
        self.delete("all")
        for x in range(0, w, 40):
            self.create_line(x, 0, x, h, fill=self.sk["grid"], tags="bg")
        for y in range(0, h, 40):
            self.create_line(0, y, w, y, fill=self.sk["grid"], tags="bg")
        if self._job is None:
            self._idle_texts()

    def _idle_texts(self):
        self.delete("dyn")
        if self.round is not None:
            return
        w, _h = self._size()
        self.create_text(w // 2, 40, fill=self.sk["text"], font=("Segoe UI", 12, "bold"), tags="dyn",
                         text="Im oberen Drittel klicken und gedrückt halten")
        self.create_text(w // 2, 64, fill=self.sk["guide"], font=("Segoe UI", 10), tags="dyn",
                         text="Zieh die Maus gegen den Rückstoß, damit die Treffer im Ziel bleiben.")

    # ---- Zeichnen ----
    def _mark(self, x, y, size, color, style, width=1):
        if style == "Cross":
            self.create_line(x - size, y, x + size, y, fill=color, width=width, tags="dyn")
            self.create_line(x, y - size, x, y + size, fill=color, width=width, tags="dyn")
        elif style == "Ring":
            self.create_oval(x - size, y - size, x + size, y + size, outline=color, width=width, tags="dyn")
        else:
            self.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="", tags="dyn")

    def _draw_dynamic(self, now: float):
        self.delete("dyn")
        r, sk = self.round, self.sk
        if r is None:
            self._idle_texts()
            return
        sx, sy = r.start_pos
        for rad in (10, 25):
            self.create_oval(sx - rad, sy - rad, sx + rad, sy + rad, outline=sk["target"], tags="dyn")
        self.create_line(sx - 34, sy, sx + 34, sy, fill=sk["target"], tags="dyn")
        self.create_line(sx, sy - 34, sx, sy + 34, fill=sk["target"], tags="dyn")
        if self.show_guide:
            pts = [(sx, sy)] + trainer.ideal_path((sx, sy), r.pat)
            self.create_line(*[c for p in pts for c in p], fill=sk["guide"], dash=(4, 3), smooth=True, tags="dyn")
        # Spur: Linie von Treffer zu Treffer, ältere Stücke blenden in den Hintergrund aus
        for i in range(1, len(r.hits)):
            age = now - self._hit_t[i] if i < len(self._hit_t) else 9
            f = weapons.fade(age, 0.8) if self._mode != "idle" else 0.0
            if f > 0.02:
                self.create_line(*r.hits[i - 1], *r.hits[i], fill=weapons.mix(sk["bg"], sk["guide"], f), tags="dyn")
        for i, h in enumerate(r.hits):
            self._mark(h[0], h[1], 3.5, weapons.hit_color(sk, r.distance(h)), self.marker, 2 if self.marker != "Dot" else 1)
        if self._mode == "play" and not r.done and self._disp is not None:
            ax, ay = self._disp
            self._mark(ax, ay, 7 if self.crosshair != "Dot" else 3, sk["aim"], self.crosshair)
        self.create_text(10, 10, anchor="nw", fill=sk["text"], font=("Segoe UI", 10), tags="dyn",
                         text=f"{self.pattern_name}   Schuss {len(r.hits)}/{len(r.pat)}")

    # ---- Maus ----
    def _press(self, e):
        self.stop()
        w = weapons.weapon(self.weapon_id)
        seed = random.randrange(1 << 30)
        pat = trainer.scaled(weapons.pattern_for(self.weapon_id, self.pattern_name, seed), self.strength)
        self.round = trainer.Round(pat)
        self.round.start(e.x, e.y)
        self._mouse = (e.x, e.y)
        self._disp = (float(e.x), float(e.y))
        self._hit_t = []
        self._mode = "play"
        self._shots_total = int(w["shots"])
        now = time.perf_counter()
        self._clock = weapons.ShotClock(self.rate, now)
        self._t_last = now
        self._frame()

    def _move(self, e):
        self._mouse = (e.x, e.y)

    def _release(self, e):
        if self._mode == "play":
            self._finish()

    # ---- Bildschleife (~60 Bilder pro Sekunde) ----
    def _frame(self):
        self._job = None
        now = time.perf_counter()
        dt, self._t_last = now - self._t_last, now
        if self._mode == "play":
            r = self.round
            for _ in range(self._clock.due(now)):
                if r.shot(*self._mouse) is None:
                    break
                self._hit_t.append(now)
            if not r.done:
                self._disp = weapons.ease(self._disp or self._mouse, r.aim(*self._mouse), dt)
            self._draw_dynamic(now)
            if r.done:
                self._finish(running=True)
                return
        elif self._mode == "replay":
            r = self.round
            n = self._clock.due(now)
            self._replay_i = min(len(self._replay_hits), self._replay_i + n)
            r.hits = self._replay_hits[:self._replay_i]
            self._hit_t = [now] * len(r.hits)
            self._draw_dynamic(now)
            if self._replay_i >= len(self._replay_hits):
                self._mode = "idle"
                self._draw_dynamic(now)
                return
        else:
            return
        self._job = self.after(FRAME_MS, self._frame)

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def replay(self) -> bool:
        """Spielt die letzte Runde noch einmal ab (Treffer erscheinen im Takt der Waffe). False, wenn es keine gibt."""
        lr = self.last_round
        if lr is None or not lr.hits:
            return False
        self.stop()
        self.round = trainer.Round(lr.pat)
        self.round.start_pos = lr.start_pos
        self._replay_hits = list(lr.hits)
        self._replay_i = 0
        self._mode = "replay"
        now = time.perf_counter()
        self._clock = weapons.ShotClock(self.rate, now)
        self._t_last = now
        self._frame()
        return True

    def _finish(self, running=None):
        """Runde beenden (Maus losgelassen oder alle Schüsse abgegeben) und Ergebnis melden – nur einmal je Runde."""
        r = self.round
        was = self._job is not None if running is None else running
        self.stop()
        if self._mode != "play":
            return
        self._mode = "idle"
        if r is None or not r.hits or getattr(r, "reported", False) or not (was or r.done):
            return
        r.reported = True
        self.last_round = r
        self._draw_dynamic(time.perf_counter())
        res = r.result()
        res["pattern"], res["weapon"] = self.pattern_name, self.weapon_id
        res["hint"] = weapons.drift_hint(r.hits, r.start_pos)
        w, h = self._size()
        self.create_text(w // 2, h - 40, fill=self.sk["text"], font=("Segoe UI", 13, "bold"), tags="dyn",
                         text=f"{res['score']} Punkte – {res['rating']}")
        if self.on_result is not None:
            self.on_result(res)
