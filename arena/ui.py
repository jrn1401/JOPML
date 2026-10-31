"""Fenster der Arena (tkinter): modernes Menü, Vollbild-Spiel mit eingefangener Maus, HUD, Waffe in der Hand, Leuchtspuren und Auswertung."""
import base64
import math
import sys
import time
import tkinter as tk

from . import VERSION, game as G, hud, settings, weapons
from .grab import Grab
from .ui_stats import stat_bars

try:
    import numpy as np
    from . import rend, viewmodel
except Exception:                  # ohne numpy: einfache Rechteck-Darstellung
    np = None
    rend = None
    viewmodel = None
from . import render as simple

BG, PANEL, EDGE, ACC, TXT, MUT = "#0b0f17", "#131a24", "#222d3d", "#4cc9f0", "#e8eef6", "#8795a8"
FONT = "Segoe UI"
KEYMAP = {"w": "w", "a": "a", "s": "s", "d": "d", "shift_l": "shift", "shift_r": "shift", "control_l": "ctrl", "control_r": "ctrl",
          "left": "left", "right": "right", "up": "up", "down": "down", "space": "space"}
SCALE = {"Auto": 3, "Low": 4, "Medium": 3, "High": 2}
STYLE_SHORT = {"Tactical – stand still to shoot": "Tactical", "Precision – one shot counts": "Precision", "Arcade – run and gun": "Arcade"}
MODES = {"bots": ("Bots", "Enemies walk around (and can shoot back)."), "targets": ("Targets", "Glowing spheres appear in front of you – like an aim trainer.")}
ARROW_LOOK = 460.0            # Bildpunkte pro Sekunde beim Umsehen mit den Pfeiltasten


class ArenaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"JOPML Arena {VERSION}")
        self.configure(bg=BG)
        self.geometry("1260x800")
        self.minsize(900, 600)
        self.cfg = settings.load()
        self.game = None
        self.grab = None
        self.keys, self.firing, self.aim_held, self.aim_on = set(), False, False, False
        self.paused = True
        self.renderer = None
        self.photo = None
        self.img_item = self.vm_item = None
        self.vm_cache, self._thumbs = {}, {}
        self.muzzle_px = (0, 0)
        self._warm = []
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<F3>", lambda e: self._toggle_hitboxes())
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.bind("<FocusOut>", lambda e: self._lost_focus(e))
        self.show_menu()

    # ================================================================== Menü
    def _label(self, parent, text, size=11, color=TXT, bold=False, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", PANEL), fg=color, font=(FONT, size, "bold" if bold else "normal"), **kw)

    def show_menu(self):
        if self.grab:
            self.grab.stop()
        self.game, self.renderer = None, None
        self.img_item = self.vm_item = None
        self.attributes("-fullscreen", False)
        for w in self.winfo_children():
            w.destroy()
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=26, pady=18)
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="JOPML", bg=BG, fg=ACC, font=(FONT, 12, "bold")).pack(side="left")
        tk.Label(head, text="  ARENA", bg=BG, fg=TXT, font=(FONT, 12, "bold")).pack(side="left")
        tk.Label(head, text=f"v{VERSION}", bg=BG, fg=MUT, font=(FONT, 10)).pack(side="right")
        tk.Label(root, text="Train your aim and recoil control", bg=BG, fg=TXT, font=(FONT, 24, "bold")).pack(anchor="w", pady=(8, 0))
        tk.Label(root, text="Invented weapons and maps. Nothing here is a real game, and nothing is sent to other programs.",
                 bg=BG, fg=MUT, font=(FONT, 10)).pack(anchor="w", pady=(0, 12))
        # Start-Leiste ZUERST unten festlegen: so bleibt der Knopf auch in kleinen Fenstern sichtbar (die Spalten scrollen)
        bottom = tk.Frame(root, bg=BG)
        bottom.pack(side="bottom", fill="x")
        area = tk.Frame(root, bg=BG)
        area.pack(fill="both", expand=True)
        sc = tk.Canvas(area, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(area, orient="vertical", command=sc.yview)
        sc.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)
        cols = tk.Frame(sc, bg=BG)
        win = sc.create_window(0, 0, window=cols, anchor="nw")
        cols.bind("<Configure>", lambda e: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>", lambda e: sc.itemconfigure(win, width=e.width))
        self.bind("<MouseWheel>", lambda e: sc.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Button-4>", lambda e: sc.yview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: sc.yview_scroll(1, "units"))
        self.bind("<Return>", lambda e: self.start() if self.game is None else None)
        for i in range(4):
            cols.grid_columnconfigure(i, weight=1, uniform="c")
        cols.grid_rowconfigure(0, weight=1)
        c = self.cfg
        self.v_mode, self.v_style, self.v_weapon = tk.StringVar(value=c["mode"]), tk.StringVar(value=c["style"]), tk.StringVar(value=c["weapon"])
        self.v_theme, self.v_chstyle, self.v_chcolor = tk.StringVar(value=c["theme"]), tk.StringVar(value=c["crosshair"]), tk.StringVar(value=c["crosshair_color"])
        self.v_bots, self.v_shoot, self.v_full = tk.IntVar(value=c["bots"]), tk.BooleanVar(value=c["bots_shoot"]), tk.BooleanVar(value=c["fullscreen"])
        self.v_sens, self.v_ads_sens, self.v_fov = tk.DoubleVar(value=c["sens"]), tk.DoubleVar(value=c["ads_sens"]), tk.DoubleVar(value=c["fov"])
        self.v_toggle, self.v_invert, self.v_boxes = tk.BooleanVar(value=c["ads_toggle"]), tk.BooleanVar(value=c["invert_y"]), tk.BooleanVar(value=c["hitboxes"])
        self.v_quality = tk.StringVar(value=c["quality"])
        self.vars = {"mode": self.v_mode, "style": self.v_style, "weapon": self.v_weapon, "theme": self.v_theme, "chstyle": self.v_chstyle, "chcolor": self.v_chcolor}
        self.cards = {}
        # --- Modus + Spielstil
        p1 = self._panel(cols, 0, "MODE")
        for key, (title, descr) in MODES.items():
            self._choice(p1, "mode", key, title, descr)
        self._label(p1, "PLAY STYLE", 9, MUT, True).pack(anchor="w", pady=(14, 2))
        for st, info in weapons.STYLES.items():
            self._choice(p1, "style", st, STYLE_SHORT[st], info["descr"])
        # --- Waffe
        p2 = self._panel(cols, 1, "WEAPON")
        for wid, w in weapons.WEAPONS.items():
            self._weapon_card(p2, wid, w)
        # --- Aussehen
        p3 = self._panel(cols, 2, "LOOK")
        sw = tk.Frame(p3, bg=PANEL)
        sw.pack(fill="x", pady=(0, 6))
        for i, (th, d) in enumerate(weapons.THEMES.items()):
            cv = tk.Canvas(sw, width=78, height=48, bg=PANEL, highlightthickness=2, highlightbackground=PANEL, cursor="hand2")
            cv.create_rectangle(0, 0, 78, 24, fill=d["sky"], outline="")
            cv.create_rectangle(0, 24, 78, 48, fill=d["floor"], outline="")
            for k, col in enumerate(d["walls"]):
                cv.create_rectangle(7 + k * 16, 11, 20 + k * 16, 36, fill=col, outline="")
            cv.create_rectangle(0, 22, 78, 25, fill=d.get("accent", "#ffffff"), outline="")
            cv.create_oval(32, 15, 45, 28, fill=d["bot"], outline="")
            cv.bind("<Button-1>", lambda e, t=th: self._pick("theme", t))
            cv.grid(row=i // 3, column=i % 3, padx=3, pady=3)
            self.cards[("theme", th)] = cv
        self._label(p3, "CROSSHAIR", 9, MUT, True).pack(anchor="w", pady=(10, 4))
        row = tk.Frame(p3, bg=PANEL)
        row.pack(fill="x")
        for name in weapons.CROSSHAIR_STYLES:
            tk.Radiobutton(row, text=name, value=name, variable=self.v_chstyle, bg=PANEL, fg=TXT, selectcolor=BG, activebackground=PANEL, font=(FONT, 10),
                           indicatoron=False, padx=10, pady=2, relief="flat", bd=0).pack(side="left", padx=3)
        row = tk.Frame(p3, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        for name, col in weapons.CROSSHAIR_COLORS.items():
            cv = tk.Canvas(row, width=26, height=26, bg=PANEL, highlightthickness=2, highlightbackground=PANEL, cursor="hand2")
            cv.create_oval(5, 5, 21, 21, fill=col, outline="")
            cv.bind("<Button-1>", lambda e, n=name: self._pick("chcolor", n))
            cv.pack(side="left", padx=3)
            self.cards[("chcolor", name)] = cv
        self._label(p3, "GRAPHICS", 9, MUT, True).pack(anchor="w", pady=(14, 4))
        q = tk.Frame(p3, bg=PANEL)
        q.pack(fill="x")
        for name in SCALE:
            tk.Radiobutton(q, text=name, value=name, variable=self.v_quality, bg=PANEL, fg=TXT, selectcolor=BG, activebackground=PANEL,
                           font=(FONT, 10), indicatoron=False, padx=10, pady=2, relief="flat", bd=0).pack(side="left", padx=3)
        for text, var in (("Fullscreen", self.v_full), ("Show hitboxes (F3 in game)", self.v_boxes)):
            self._check(p3, text, var)
        if np is None:
            self._label(p3, "Tip: install numpy (pip install numpy) for textured graphics and the weapon models.", 9, "#fbbf24", wraplength=250, justify="left").pack(fill="x", pady=(10, 0))
        # --- Steuerung
        p4 = self._panel(cols, 3, "CONTROLS")
        self._slider(p4, "Bots / targets", self.v_bots, 0, 12, 1)
        self._slider(p4, "Mouse sensitivity", self.v_sens, 0.2, 4.0, 0.05)
        self._slider(p4, "Aiming (right mouse) sensitivity", self.v_ads_sens, 0.3, 2.0, 0.05)
        self._slider(p4, "Field of view", self.v_fov, 60, 110, 1)
        for text, var in (("Bots shoot back", self.v_shoot), ("Aim: toggle instead of hold", self.v_toggle), ("Invert mouse up/down", self.v_invert)):
            self._check(p4, text, var)
        play = tk.Button(bottom, text="▶  PLAY", font=(FONT, 15, "bold"), bg=ACC, fg="#04121a", activebackground="#7fdcf7", activeforeground="#04121a",
                         relief="flat", bd=0, padx=44, pady=8, cursor="hand2", command=self.start)
        play.pack(pady=(12, 4))
        tk.Label(bottom, text="WASD move · Space jump · Shift run · Ctrl hold / C toggle crouch · Mouse look · Left click fire · Right click aim · R reload · 1–5 / wheel weapon · Q last weapon · Esc pause · F3 hitboxes · F11 fullscreen",
                 bg=BG, fg=MUT, font=(FONT, 9)).pack()
        self._refresh_choices()

    def _panel(self, parent, col, title):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=EDGE)
        f.grid(row=0, column=col, sticky="nsew", padx=5)
        self._label(f, title, 9, MUT, True).pack(anchor="w", padx=14, pady=(12, 6))
        inner = tk.Frame(f, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        return inner

    def _check(self, parent, text, var):
        tk.Checkbutton(parent, text=text, variable=var, bg=PANEL, fg=TXT, selectcolor=BG, activebackground=PANEL, activeforeground=TXT,
                       font=(FONT, 10), anchor="w").pack(fill="x", pady=2)

    def _choice(self, parent, var, value, title, descr):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=2, highlightbackground=PANEL, cursor="hand2")
        f.pack(fill="x", pady=4)
        a = self._label(f, title, 13, TXT, True, anchor="w", cursor="hand2")
        a.pack(fill="x", padx=10, pady=(8, 0))
        b = self._label(f, descr, 9, MUT, anchor="w", justify="left", wraplength=230, cursor="hand2")
        b.pack(fill="x", padx=10, pady=(0, 8))
        for w in (f, a, b):
            w.bind("<Button-1>", lambda e, v=value: self._pick(var, v))
        self.cards[(var, value)] = f

    def _thumb(self, wid):
        """Kleines Bild der Waffe für die Karte (eigene Oberfläche je Waffe); None ohne numpy."""
        if viewmodel is None:
            return None
        try:
            if wid not in self._thumbs:
                data = viewmodel.png(viewmodel.thumbnail(weapons.WEAPONS[wid]["look"], 150, "#4cc9f0"))
                self._thumbs[wid] = tk.PhotoImage(data=base64.b64encode(data))
            return self._thumbs[wid]
        except Exception:
            return None

    def _weapon_card(self, parent, wid, w):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=2, highlightbackground=PANEL, cursor="hand2")
        f.pack(fill="x", pady=3)
        top = tk.Frame(f, bg=PANEL, cursor="hand2")
        top.pack(fill="x", padx=8, pady=(4, 0))
        img = self._thumb(wid)
        widgets = [f, top]
        if img is not None:
            pic = tk.Label(top, image=img, bg=PANEL, cursor="hand2")
            pic.pack(side="right")
            widgets.append(pic)
        a = self._label(top, w["name"], 11, TXT, True, anchor="w", cursor="hand2")
        a.pack(side="left", pady=(6, 0))
        widgets.append(a)
        c = tk.Canvas(f, height=30, bg=PANEL, highlightthickness=0, cursor="hand2")
        c.pack(fill="x", padx=10, pady=(0, 6))
        for i, (name, v) in enumerate(stat_bars(wid)):
            x = 4 + i * 62
            c.create_text(x, 5, anchor="w", text=name, fill=MUT, font=(FONT, 7))
            c.create_line(x, 19, x + 52, 19, fill=EDGE, width=5, capstyle="round")
            c.create_line(x, 19, x + max(2, 52 * v), 19, fill=ACC, width=5, capstyle="round")
        widgets.append(c)
        for widget in widgets:
            widget.bind("<Button-1>", lambda e, k=wid: self._pick("weapon", k))
        self.cards[("weapon", wid)] = f

    def _slider(self, parent, label, var, lo, hi, step):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=2)
        self._label(f, label, 10, MUT).pack(anchor="w")
        tk.Scale(f, from_=lo, to=hi, resolution=step, orient="horizontal", variable=var, bg=PANEL, fg=TXT, troughcolor=BG, highlightthickness=0,
                 bd=0, activebackground=ACC, sliderrelief="flat", font=(FONT, 9)).pack(fill="x")

    def _pick(self, var, value):
        self.vars[var].set(value)
        self._refresh_choices()

    def _refresh_choices(self):
        cur = {k: v.get() for k, v in self.vars.items()}
        for (var, value), w in self.cards.items():
            w.configure(highlightbackground=ACC if cur[var] == value else PANEL)

    # ================================================================== Spiel
    def _read_cfg(self):
        return settings.clean({"weapon": self.v_weapon.get(), "style": self.v_style.get(), "theme": self.v_theme.get(), "bots": int(self.v_bots.get()),
                               "bots_shoot": self.v_shoot.get(), "sens": float(self.v_sens.get()), "fullscreen": self.v_full.get(),
                               "quality": self.v_quality.get(), "mode": self.v_mode.get(), "fov": float(self.v_fov.get()),
                               "ads_sens": float(self.v_ads_sens.get()), "ads_toggle": self.v_toggle.get(), "invert_y": self.v_invert.get(),
                               "crosshair": self.v_chstyle.get(), "crosshair_color": self.v_chcolor.get(), "hitboxes": self.v_boxes.get()})

    def start(self):
        self.cfg = self._read_cfg()
        settings.save(self.cfg)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Return>"):      # Menü-Bindungen (Scrollen, Enter) enden mit dem Menü
            try:
                self.unbind(seq)
            except Exception:
                pass
        for w in self.winfo_children():
            w.destroy()
        if self.cfg["fullscreen"]:
            self.attributes("-fullscreen", True)
        c = self.cfg
        self.game = G.Game(c["weapon"], c["style"], c["bots"], c["bots_shoot"], theme=c["theme"], mode=c["mode"], fov=c["fov"], ads_sens=c["ads_sens"], invert=c["invert_y"])
        self.game.sens = G.SENS * c["sens"]
        self.canvas = tk.Canvas(self, bg="#000000", highlightthickness=0, cursor="none")
        self.canvas.pack(fill="both", expand=True)
        self.grab = Grab(self.canvas)
        cv = self.canvas
        cv.bind("<ButtonPress-1>", self._click)
        cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "firing", False))
        for btn in ((2, 3) if sys.platform == "darwin" else (3,)):
            cv.bind(f"<ButtonPress-{btn}>", self._aim_down)
            cv.bind(f"<ButtonRelease-{btn}>", self._aim_up)
        cv.bind("<MouseWheel>", lambda e: self._wheel(1 if e.delta > 0 else -1))
        cv.bind("<Button-4>", lambda e: self._wheel(1))
        cv.bind("<Button-5>", lambda e: self._wheel(-1))
        self.bind("<KeyPress>", self._kd)
        self.bind("<KeyRelease>", self._ku)
        self.keys, self.firing, self.paused, self._buttons = set(), False, False, []
        self.aim_held = self.aim_on = False
        self.crouch_t, self.prev_weapon, self.auto_s, self._auto_t = False, None, 3, time.perf_counter()
        self.renderer, self.img_item, self.vm_item = None, None, None
        self.sway, self.raise_t, self.show_boxes = [0.0, 0.0], time.perf_counter() - 1, bool(c["hitboxes"])
        self._warm = [(x, a) for x in weapons.weapon_ids() for a in (False, True) if (x, a) != (c["weapon"], False)]
        self._fps_t, self._fps, self._frames = time.perf_counter(), 0.0, 0
        self.t_last = time.perf_counter()
        self.focus_force()
        self.canvas.focus_set()
        self.after(250, self._capture)                  # sofort im Spiel - kein Klicken ins Fenster nötig
        self._frame()

    def _capture(self):
        if self.game is None:
            return
        self._clear_pause_ui()
        self.paused = False
        self.canvas.update_idletasks()
        self.grab.start()
        self.t_last = time.perf_counter()

    def _pause(self):
        self.paused, self.firing, self.aim_held = True, False, False
        self.keys.clear()
        self.crouch_t = False
        self.grab.stop()
        self.canvas.configure(cursor="arrow")

    def _lost_focus(self, e):
        if self.game is not None and not self.paused and e.widget is self:
            self._pause()

    def _click(self, e):
        if not self.paused:
            self.firing = True

    def _aim_down(self, e):
        if self.paused:
            return
        if self.cfg["ads_toggle"]:
            self.aim_on = not self.aim_on
        else:
            self.aim_held = True

    def _aim_up(self, e):
        self.aim_held = False

    def _aiming(self):
        return self.aim_held or self.aim_on

    def _wheel(self, d):
        if self.game is None or self.paused:
            return
        ids = weapons.weapon_ids()
        self._switch(ids[(ids.index(self.game.weapon_id) - d) % len(ids)])

    def _switch(self, wid):
        if wid != self.game.weapon_id:
            self.prev_weapon = self.game.weapon_id
            self.game.set_weapon(wid)
            self.aim_on = False
            self.raise_t = time.perf_counter()

    def _toggle_hitboxes(self):
        self.show_boxes = not getattr(self, "show_boxes", False)

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))
        if self.game is not None and not self.paused:
            self.after(200, lambda: (self.grab.stop(), self.grab.start()))

    def _kd(self, e):
        if self.game is None:
            return
        ks = e.keysym.lower()
        k = KEYMAP.get(ks)
        if k:
            self.keys.add(k)
        elif ks == "escape":
            self._pause() if not self.paused else self._capture()
        elif self.paused:
            return
        elif ks == "r":
            self.game.reload()
        elif ks == "c":
            self.crouch_t = not self.crouch_t
        elif ks == "q" and self.prev_weapon in weapons.weapon_ids():
            self._switch(self.prev_weapon)
        elif len(ks) == 1 and ks in "12345":
            self._switch(weapons.weapon_ids()[int(ks) - 1])

    def _ku(self, e):
        k = KEYMAP.get(e.keysym.lower())
        if k:
            self.keys.discard(k)

    def _quit(self):
        try:
            if self.grab:
                self.grab.stop()
        finally:
            self.destroy()

    # ================================================================== Bildschleife
    def _frame(self):
        g = self.game
        if g is None:
            return
        now = time.perf_counter()
        dt, self.t_last = now - self.t_last, now
        dmx, dmy = self.grab.delta() if not self.paused else (0, 0)
        if not self.paused:
            step = ARROW_LOOK * min(dt, 0.05)                 # Umsehen mit den Pfeiltasten, falls die Maus nicht reicht
            dmx += step * (("right" in self.keys) - ("left" in self.keys))
            dmy += step * (("down" in self.keys) - ("up" in self.keys))
            g.update(dt, (self.keys | {"ctrl"}) if self.crouch_t else self.keys, dmx, dmy, self.firing, self._aiming())
            # Waffe schwingt leicht hinter der Mausbewegung her
            tx, ty = max(-26.0, min(26.0, -dmx * 0.9)), max(-18.0, min(18.0, -dmy * 0.9))
            self.sway[0] += (tx - self.sway[0]) * min(1.0, dt * 9)
            self.sway[1] += (ty - self.sway[1]) * min(1.0, dt * 9)
        self._draw(dt)
        self._frames += 1
        if now - self._fps_t >= 0.5:
            self._fps, self._fps_t, self._frames = self._frames / (now - self._fps_t), now, 0
            self._auto_quality(now)
        spent = (time.perf_counter() - now) * 1000
        self.after(max(1, int(16 - spent)), self._frame)

    def _auto_quality(self, now):
        """Qualität 'Auto': bei niedriger Bildrate gröber rendern, bei viel Reserve wieder schärfer (höchstens alle 1,5 s ein Schritt)."""
        if self.cfg["quality"] != "Auto" or self.paused or now - self._auto_t < 1.5:
            return
        if self._fps < 45 and self.auto_s < 4:
            self.auto_s += 1
            self._auto_t = now
        elif self._fps > 80 and self.auto_s > 2:
            self.auto_s -= 1
            self._auto_t = now

    def _ensure_renderer(self, w, h):
        base = self.auto_s if self.cfg["quality"] == "Auto" else SCALE[self.cfg["quality"]]
        s = max(base, math.ceil(w / 720))
        iw, ih = max(160, w // s), max(100, h // s)
        if self.renderer is None or (self.renderer.w, self.renderer.h) != (iw, ih):
            if self.renderer is None:
                self.renderer = rend.Renderer(iw, ih, self.game.theme)
            else:
                self.renderer.resize(iw, ih)
            self.scale = s
        return self.renderer

    def _draw(self, dt):
        g, c = self.game, self.canvas
        w, h = max(c.winfo_width(), 320), max(c.winfo_height(), 200)
        if np is not None:
            r = self._ensure_renderer(w, h)
            arr = r.frame(g)
            small = tk.PhotoImage(data=b"P6 %d %d 255\n" % (r.w, r.h) + arr.tobytes())
            self.photo = small.zoom(self.scale) if self.scale > 1 else small
            if self.img_item is None:
                self.img_item = c.create_image(w // 2, h // 2, image=self.photo)
            else:
                c.itemconfigure(self.img_item, image=self.photo)
                c.coords(self.img_item, w // 2, h // 2)
            self._place_viewmodel(w, h)
            if self._warm:                                  # die anderen Waffen nach und nach vorbereiten (kein Ruckeln beim Wechseln)
                wid, aimed = self._warm.pop()
                self._vm_image(w, wid, aimed)
        else:
            self._draw_simple(w, h)
        c.delete("hud")
        self._hud(w, h, dt)

    def _draw_simple(self, w, h):
        c, pool = self.canvas, self.__dict__.setdefault("_pool", [])
        ops = simple.build_frame(self.game, w, h, 160)
        for i, (x0, y0, x1, y1, col) in enumerate(ops):
            if i < len(pool):
                it, last = pool[i]
                c.coords(it, x0, y0, x1, y1)
                if last != col:
                    c.itemconfigure(it, fill=col)
                    pool[i] = (it, col)
            else:
                pool.append((c.create_rectangle(x0, y0, x1, y1, fill=col, outline=""), col))
        for i in range(len(ops), len(pool)):
            c.coords(pool[i][0], -5, -5, -4, -4)
        c.tag_lower("hud")

    # ================================================================== Waffe in der Hand
    def _vm_image(self, w, wid=None, aimed=False):
        """(PhotoImage, Mündung, Visierpunkt) der Waffe (Standard: die aktuelle) in passender Größe; None, wenn nicht verfügbar.
        aimed=True: waagerechte Fassung für das Visieren, sonst die leicht gedrehte Hüftfassung."""
        g = self.game
        wid = wid or g.weapon_id
        wp = int(max(360, min(820, w * 0.45)))
        key = (wid, wp, aimed)
        if key not in self.vm_cache:
            try:
                rgba, muz, sight = viewmodel.make(weapons.WEAPONS[wid]["look"], wp, weapons.accent(g.theme), theta=0.0 if aimed else viewmodel.TILT)
                self.vm_cache[key] = (tk.PhotoImage(data=base64.b64encode(viewmodel.png(rgba))), muz, sight)
            except Exception:
                self.vm_cache[key] = None
        return self.vm_cache[key]

    def _place_viewmodel(self, w, h):
        g, c = self.game, self.canvas
        vm = self._vm_image(w, None, g.ads > 0.5) if viewmodel is not None else None
        if vm is None:
            self.muzzle_px = (w * 0.62, h * 0.62)
            if self.vm_item is not None:
                c.itemconfigure(self.vm_item, state="hidden")
            return
        photo, muz, sight = vm
        k = max(0.0, 1 - (time.perf_counter() - self.raise_t) / 0.28)
        mx, my = hud.vm_place(g, w, h, muz, sight, tuple(self.sway), k * k)
        self.muzzle_px = (mx, my)
        scoped = g.weapon_id == "dmr" and g.ads > 0.85
        if self.vm_item is None:
            self.vm_item = c.create_image(mx - muz[0], my - muz[1], image=photo, anchor="nw")
        else:
            c.itemconfigure(self.vm_item, image=photo, state="hidden" if scoped else "normal")
            c.coords(self.vm_item, mx - muz[0], my - muz[1])

    # ================================================================== HUD
    def _bar(self, x0, y, x1, frac, color, track="#1f2937", width=10):
        c = self.canvas
        c.create_line(x0, y, x1, y, fill=track, width=width, capstyle="round", tags="hud")
        if frac > 0.01:
            c.create_line(x0, y, x0 + (x1 - x0) * frac, y, fill=color, width=width, capstyle="round", tags="hud")

    def _label_hud(self, x, y, text, size, color, anchor):
        self.canvas.create_text(x, y, anchor=anchor, text=text, fill=color, font=(FONT, size, "bold"), tags="hud")

    def _crosshair(self, w, h):
        g, c = self.game, self.canvas
        cx, cy = w / 2, h / 2
        col = weapons.CROSSHAIR_COLORS.get(self.cfg["crosshair_color"], "#ffffff")
        style = self.cfg["crosshair"]
        if g.weapon_id == "dmr" and g.ads > 0.6:               # Zielfernrohr: eigenes Fadenkreuz im Kreis
            rad = h * 0.36
            c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, outline="#000000", width=4, tags="hud")
            c.create_line(cx - rad, cy, cx + rad, cy, fill="#000000", width=2, tags="hud")
            c.create_line(cx, cy - rad, cx, cy + rad, fill="#000000", width=2, tags="hud")
            for i in range(-4, 5):
                if i:
                    c.create_line(cx + i * rad / 5, cy - 5, cx + i * rad / 5, cy + 5, fill="#000000", width=2, tags="hud")
            c.create_oval(cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5, fill=col, outline="", tags="hud")
            return
        gap = hud.crosshair_gap(g, w)
        if style == "Cross":
            for colr, wd, ext in (("#000000", 4, 1), (col, 2, 0)):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    c.create_line(cx + dx * gap, cy + dy * gap, cx + dx * (gap + 9 + ext), cy + dy * (gap + 9 + ext), fill=colr, width=wd, tags="hud")
        elif style == "Circle":
            r = gap + 7
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#000000", width=4, tags="hud")
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=2, tags="hud")
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#000000", outline="", tags="hud")
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=col, outline="", tags="hud")

    def _effects(self, cam, w, h):
        """Leuchtspuren, Funken, Schadenszahlen und (auf Wunsch) Hitbox-Umrisse."""
        g, c = self.game, self.canvas
        acc = weapons.accent(g.theme)
        for t0, p, kind in g.tracers:
            seg = hud.tracer_segment(cam, p, g.t - t0, self.muzzle_px)
            if seg:
                c.create_line(*seg[0], *seg[1], fill=acc, width=5, capstyle="round", tags="hud")
                c.create_line(*seg[0], *seg[1], fill="#ffffff", width=2, capstyle="round", tags="hud")
        spark_col = {"wall": "#ffd9a0", "body": "#ff6b6b", "head": "#ffe066"}
        for t0, p, kind in g.sparks:
            for a, b in hud.spark_lines(cam, p, g.t - t0, t0):
                c.create_line(*a, *b, fill=spark_col.get(kind, "#ffffff"), width=2, tags="hud")
        num_col = {"head": "#fde047", "body": "#ffffff", "legs": "#9ca3af", "target": "#4ade80"}
        for t0, p, text, zone in g.numbers:
            pr = cam.project(p)
            if pr:
                age = g.t - t0
                c.create_text(pr[0] + 14, pr[1] - 10 - age * 55, text=text, fill=num_col.get(zone, "#ffffff"), font=(FONT, 13 if zone != "head" else 15, "bold"), tags="hud")
        if self.show_boxes:
            zone_col = {"head": "#fde047", "body": "#4ade80", "legs": "#60a5fa", "target": "#4ade80"}
            for b in g.bots:
                if b.alive:
                    for x0, y0, x1, y1, zone in hud.hitbox_ovals(cam, b, (g.x, g.y)):
                        c.create_oval(x0, y0, x1, y1, outline=zone_col[zone], width=2, tags="hud")
            c.create_text(w - 14, 14, anchor="ne", text=f"{self._fps:.0f} FPS", fill=MUT, font=(FONT, 9), tags="hud")

    def _hud(self, w, h, dt):
        g, c = self.game, self.canvas
        cx, cy = w / 2, h / 2
        cam = hud.Cam(g, w, h)
        self._effects(cam, w, h)
        if g.t - g.last_shot < 0.05 and not (g.weapon_id == "dmr" and g.ads > 0.85):          # Mündungsfeuer
            fx, fy = self.muzzle_px
            r = 22 if g.weapon_id != "sidearm" else 16
            c.create_polygon(fx, fy - r, fx + r * 1.7, fy, fx, fy + r, fx - r * 0.5, fy, fill="#fde68a", outline="", tags="hud")
            c.create_polygon(fx, fy - r * 0.5, fx + r * 0.9, fy, fx, fy + r * 0.5, fill="#ffffff", outline="", tags="hud")
        if np is None or self.vm_item is None or self._vm_image(w, None, g.ads > 0.5) is None:
            self._viewmodel_fallback(w, h)
        self._crosshair(w, h)
        for kind, colr in (("hit", "#ffffff"), ("head", "#fde047"), ("kill", "#ef4444")):
            if g.recent_events(kind, 0.2):
                for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                    c.create_line(cx + dx * 8, cy + dy * 8, cx + dx * 16, cy + dy * 16, fill=colr, width=3, tags="hud")
        for t, kind in g.events[-4:]:
            age = g.t - t
            if age < 1.0 and kind in ("kill", "head") and g.mode == "bots":
                c.create_text(cx, cy - 56 - age * 40, text="HEADSHOT" if kind == "head" else "ELIMINATED", fill="#fde047" if kind == "head" else "#ef4444",
                              font=(FONT, 14, "bold"), tags="hud")
        # Leben
        hp = max(0, g.hp)
        self._label_hud(36, h - 62, "HEALTH", 9, MUT, "sw")
        c.create_text(36, h - 36, anchor="sw", text=str(int(hp)), fill="#ffffff", font=(FONT, 28, "bold"), tags="hud")
        self._bar(36, h - 22, 236, hp / 100, "#34d399" if hp > 35 else "#ef4444")
        # Munition und Waffenleiste
        wpn = g.w
        self._label_hud(w - 36, h - 62, wpn["name"].upper(), 9, MUT, "se")
        c.create_text(w - 36 - 74, h - 36, anchor="se", text=str(g.ammo), fill="#ffffff" if g.ammo > wpn["mag"] * 0.25 else "#ef4444", font=(FONT, 34, "bold"), tags="hud")
        c.create_text(w - 36, h - 40, anchor="se", text=f"/ {wpn['mag']}", fill=MUT, font=(FONT, 14), tags="hud")
        for i, wid in enumerate(weapons.weapon_ids()):
            x = cx + (i - 2) * 34
            on = wid == g.weapon_id
            c.create_text(x, h - 24, text=str(i + 1), fill=weapons.accent(g.theme) if on else "#4b5563", font=(FONT, 12 if on else 10, "bold"), tags="hud")
        if g.reload_until:
            frac = 1 - max(0, g.reload_until - g.t) / wpn["reload"]
            self._bar(w - 236, h - 22, w - 36, frac, ACC)
            self._label_hud(cx, cy + 90, "RELOADING", 11, "#ffffff", "center")
        elif g.ammo == 0:
            self._label_hud(cx, cy + 90, "PRESS R", 11, "#ef4444", "center")
        # Kopfzeile
        s = g.summary()
        if g.mode == "targets":
            pill = f"{s['kills']} HITS   ·   {s['accuracy']}% ACC   ·   {s['avg_time']:.2f}s AVG TIME   ·   {s['spray_error']}° SPRAY"
        else:
            pill = f"{s['kills']} KILLS   ·   {s['accuracy']}% ACC   ·   {s['headshots']}% HEAD   ·   {s['still']}% STILL   ·   {s['spray_error']}° SPRAY"
        c.create_text(cx, 22, text=pill, fill="#e5e7eb", font=(FONT, 10, "bold"), tags="hud")
        if g.eye < 0.45:
            self._label_hud(36, h - 100, "CROUCHED", 9, ACC, "sw")
        if not g.alive:
            c.create_rectangle(0, 0, w, h, fill="#7f1d1d", stipple="gray25", outline="", tags="hud")
            self._label_hud(cx, cy, "YOU WERE ELIMINATED", 26, "#fecaca", "center")
        if self.paused:
            self._pause_ui(w, h, s)

    def _viewmodel_fallback(self, w, h):
        """Einfache Waffe aus Vielecken, falls keine Bilder erzeugt werden können (ohne numpy)."""
        g, c = self.game, self.canvas
        mx, my = hud.vm_place(g, w, h, (0, 0), (0, 0), tuple(getattr(self, "sway", (0, 0))))
        ox, oy = mx + w * 0.08, my + h * 0.12
        long = {"sidearm": 0.55, "smg": 0.75, "rifle": 1.0, "dmr": 1.15, "lmg": 1.1}.get(g.weapon_id, 1.0)
        L, T = 300 * long * (w / 1280), 26 * (w / 1280)
        pts = [(ox, oy + 120), (ox + 30, oy + 8), (ox + L * 0.7, oy - T * 0.4), (ox + L, oy - T * 0.2), (ox + L, oy + T * 0.8), (ox + 120, oy + T * 1.4), (ox + 90, oy + 120)]
        c.create_polygon([v for p in pts for v in p], fill="#1b2230", outline="#394456", width=2, tags="hud")
        c.create_line(ox + 50, oy + 6, ox + L * 0.95, oy - T * 0.18, fill=ACC, width=3, tags="hud")
        self.muzzle_px = (ox + L, oy + T * 0.3)

    # ================================================================== Pause
    def _clear_pause_ui(self):
        for b in getattr(self, "_buttons", []):
            try:
                b.destroy()
            except Exception:
                pass
        self._buttons = []
        self.canvas.delete("hud_win")

    def _pause_ui(self, w, h, s):
        c = self.canvas
        c.create_rectangle(0, 0, w, h, fill="#000000", stipple="gray50", outline="", tags="hud")
        pw, ph = 480, 390
        x0, y0 = (w - pw) / 2, (h - ph) / 2
        c.create_rectangle(x0, y0, x0 + pw, y0 + ph, fill=PANEL, outline=EDGE, width=2, tags="hud")
        c.create_text(w / 2, y0 + 34, text="PAUSED", fill="#ffffff", font=(FONT, 20, "bold"), tags="hud")
        lines = [("Shots", s["shots"]), ("Accuracy", f"{s['accuracy']}%")]
        if self.game.mode == "targets":
            lines += [("Targets hit", s["kills"]), ("Average time per target", f"{s['avg_time']:.2f} s")]
        else:
            lines += [("Headshots", f"{s['headshots']}%"), ("Kills / deaths", f"{s['kills']} / {s['deaths']}")]
        lines += [("Shots standing still", f"{s['still']}%"), ("Average spray error", f"{s['spray_error']}°")]
        for i, (k, v) in enumerate(lines):
            c.create_text(x0 + 40, y0 + 80 + i * 24, anchor="w", text=k, fill=MUT, font=(FONT, 11), tags="hud")
            c.create_text(x0 + pw - 40, y0 + 80 + i * 24, anchor="e", text=str(v), fill="#ffffff", font=(FONT, 11, "bold"), tags="hud")
        if not getattr(self, "_buttons", None):
            def mk(text, cmd, colr, y):
                b = tk.Button(c, text=text, font=(FONT, 11, "bold"), bg=colr, fg="white", activebackground=colr, relief="flat", bd=0, cursor="hand2", command=cmd)
                c.create_window(w / 2, y, window=b, width=200, height=34, tags="hud_win")
                self._buttons.append(b)
            mk("Resume", self._capture, ACC, y0 + ph - 100)
            mk("Back to menu", self.show_menu, "#374151", y0 + ph - 58)
        c.create_text(w / 2, y0 + ph - 16, text="Esc also resumes", fill=MUT, font=(FONT, 9), tags="hud")


def main():
    ArenaApp().mainloop()
