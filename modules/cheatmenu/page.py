"""Seite "Cheat-Menü": Reiter Minecraft / GTA 5 / Hilfe, jeder Cheat ist ein Knopf."""
import threading
import tkinter as tk

import customtkinter as ctk

from core.i18n import tr

from . import cheats, gta_input, trainer, weapons

try:
    from core import theme
    _MAIN = theme.c("main")
    _HOVER, _TEXT = theme.c("hover"), theme.TEXT
    _OK, _BAD = theme.OK, theme.DANGER
except Exception:                      # falls sich das Design-Modul nach einem Update ändert
    _MAIN, _OK, _BAD = "transparent", "#2e9d5b", "#e5484d"
    _HOVER, _TEXT = "gray35", "white"

_COLS = 3

HELP = """So benutzt du das Cheat-Menü

1. Spiel starten und in eine Welt bzw. den Story-Modus gehen.
2. Hier auf einen Cheat klicken. Du hast dann die eingestellte Start-Verzögerung (Standard 3 s), um ins Spiel zu wechseln.
3. Schneller: In Einstellungen > Hotkeys (Gruppe „Cheat menu“) jedem Cheat eine Taste geben. Mit Taste gibt es keine Wartezeit.

Minecraft (Java, ab 1.21.11 bzw. 1.26.x)
• Die Welt braucht „Cheats erlauben“. Bei einer bestehenden Welt: Esc > Im LAN öffnen > Cheats erlauben: AN.
• Das Menü öffnet den Chat (Taste T), tippt den Befehl und drückt Enter.
• Ab 1.21.11 heißen die Spielregeln anders (z. B. minecraft:keep_inventory statt keepInventory). Für ältere Versionen den eigenen Befehl benutzen.

GTA 5 Enhanced (nur Story-Modus)
• Es werden die offiziellen Cheat-Codes von Rockstar in die Cheat-Konsole getippt.
• Die Konsole liegt auf ~ (US-Tastatur) bzw. Ö (deutsche Tastatur). Geht sie nicht auf, oben „Taste links neben 1“ wählen.
• Solange Cheats aktiv sind, gibt es in dieser Sitzung keine Erfolge/Trophäen und kein Speichern. In GTA Online gehen Cheats nicht.

Rückstoß-Trainer
• Im Übungsfeld klicken und halten: Jeder Schuss reißt das Ziel nach oben. Zieh die Maus dagegen, damit die Treffer im blauen Ziel bleiben.
• Die gestrichelte Hilfslinie zeigt, wohin die Maus müsste. Für echtes Training später ausschalten.
• Bestenliste: Der Haken „Bestenliste“ (standardmäßig an) stellt feste Standardwerte ein (Stärke 1, 10 Schuss/s, Hilfslinie aus). Verstellst du Stärke, Schuss/s oder die Hilfslinie, geht der Haken aus und die Runde zählt nur für dich. Eine volle Runde (alle 30 Schüsse) geht dann automatisch an die Bestenliste des Musters in Community > Bestenlisten, wenn du ein Cloud-Konto und die Community eingerichtet hast. Die Punkte kommen von deinem Programm; der Server kann den Spielverlauf nicht prüfen.
• Waffe: fünf ausgedachte Übungswaffen (Standard, Pulse SMG, Heavy Driver, Burst Rifle, Ion Needler) mit eigener Stärke, Feuerrate, Schusszahl und Zugrichtung. Sie haben nichts mit echten Waffen oder Spielen zu tun. Nur „Standard“ zählt für die Bestenlisten; Bestwerte der anderen Waffen werden getrennt gespeichert.
• Design: fünf Farbschemata (Classic, Neon, Paper, Mono, Sunset), dazu Fadenkreuz (Ring, Kreuz, Punkt) und Treffer-Markierung. Alles wird gemerkt.
• Flüssig: das Feld zeichnet etwa 60 Bilder pro Sekunde, das Fadenkreuz gleitet, die Spur der Treffer blendet aus. „Wiederholen“ spielt die letzte Runde noch einmal ab.
• Nach jeder Runde zeigt ein Tipp, in welche Richtung deine Treffer im Mittel abgewichen sind. Darunter siehst du Runden, Bestwert, Durchschnitt, Trend und Serie sowie ein kleines Diagramm der letzten Runden (lokal, höchstens 50).
• Der Trainer liest die Maus nur im eigenen Feld und gibt selbst keine Eingaben ab – er trainiert deine Hand und wirkt nicht in Spielen.

Rückstoß 3D
• Derselbe Übungsgedanke in einem Raum mit echter Perspektive: Ziele auf die Scheibe an der Rückwand (nah 10 m, mittel 25 m, weit 50 m – je weiter, desto kleiner), klicke und halte. Die Scheibe steht fest oder pendelt seitlich.
• Gewertet wird, wie nah die Einschläge an der Scheibenmitte bleiben (Punkte und Trefferquote). Bestwerte gelten je Muster, Entfernung und Zielart und nur für dich – die Community-Bestenlisten gehören zum 2D-Trainer.
• „3D-Ansicht“ nach der Runde: Raum mit gedrückter Maustaste drehen, Mausrad zoomt. Du siehst alle Schüsse als Linien vom Schützen zur Wand.
• Auch hier kannst du Übungswaffe und Design wählen. Dieser Trainer liest die Maus nur im eigenen Feld, gibt selbst keine Eingaben ab und hat mit keinem Spiel zu tun.

Notaus und F7 aus dem Makro-Modul stoppen auch die Minecraft-Cheats."""


class CheatMenuPage(ctk.CTkFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=_MAIN)
        self.plugin = plugin
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="🕹️  Cheat-Menü", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(18, 0))
        self._settings_row().grid(row=1, column=0, sticky="ew", padx=24, pady=(6, 4))

        tabs = ctk.CTkTabview(self)
        tabs.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 4))
        for name in ("Minecraft", "GTA 5 Enhanced", "Rückstoß-Trainer", "Rückstoß 3D", "Hilfe"):
            tabs.add(name)
        self._minecraft(tabs.tab("Minecraft"))
        self._gta(tabs.tab("GTA 5 Enhanced"))
        self._trainer(tabs.tab("Rückstoß-Trainer"))
        self._trainer3d(tabs.tab("Rückstoß 3D"))
        self._help(tabs.tab("Hilfe"))

        self.msg = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=640)
        self.msg.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        plugin.on_status = self._say

    # ---- oben: Einstellungen ----
    def _settings_row(self):
        cfg = self.plugin.cfg()
        row = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(row, text="Start-Verzögerung (s)").pack(side="left")
        self.delay = ctk.CTkEntry(row, width=50)
        self.delay.insert(0, str(cfg["delay"]))
        self.delay.pack(side="left", padx=(6, 18))
        self.delay.bind("<FocusOut>", lambda e: self._save_delay())
        self.delay.bind("<Return>", lambda e: self._save_delay())

        ctk.CTkLabel(row, text="Minecraft-Chat").pack(side="left")
        chat = ctk.CTkOptionMenu(row, values=list(cheats.CHAT_KEYS), width=80,
                                 command=lambda v: self.plugin.set_cfg(chat_key=v))
        chat.set(cfg["chat_key"] if cfg["chat_key"] in cheats.CHAT_KEYS else "t")
        chat.pack(side="left", padx=(6, 18))

        ctk.CTkLabel(row, text="GTA-Konsole").pack(side="left")
        names = list(gta_input.CONSOLE_KEYS)
        cur = next((n for n, v in gta_input.CONSOLE_KEYS.items() if v == cfg["console"]), names[0])
        con = ctk.CTkOptionMenu(row, values=names, width=200,
                                command=lambda v: self.plugin.set_cfg(console=gta_input.CONSOLE_KEYS[v]))
        con.set(cur)
        con.pack(side="left", padx=(6, 18))
        ctk.CTkButton(row, text="Stopp", width=70, fg_color=_BAD, command=self._stop).pack(side="left")
        return row

    def _save_delay(self):
        try:
            v = max(0, min(30, float(self.delay.get().replace(",", "."))))
        except ValueError:
            self._say("Die Verzögerung muss eine Zahl zwischen 0 und 30 sein.", False)
            return
        self.plugin.set_cfg(delay=v)

    def _stop(self):
        self.plugin.stop()
        self._say("Gestoppt.")

    # ---- Reiter ----
    def _grid_of(self, parent, groups):
        area = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        area.pack(fill="both", expand=True)
        for c in range(_COLS):
            area.grid_columnconfigure(c, weight=1)
        r = 0
        for section, items in groups.items():
            ctk.CTkLabel(area, text=section, font=ctk.CTkFont(size=15, weight="bold")).grid(
                row=r, column=0, columnspan=_COLS, sticky="w", padx=6, pady=(12, 2))
            r += 1
            for i, ch in enumerate(items):
                self._button(area, ch).grid(row=r + i // _COLS, column=i % _COLS, sticky="ew", padx=4, pady=3)
            r += (len(items) + _COLS - 1) // _COLS
        return area, r

    def _button(self, parent, ch):
        box = ctk.CTkFrame(parent, corner_radius=10)
        ctk.CTkButton(box, text=ch.title, height=30, command=lambda cid=ch.id: self._run(cid)).pack(fill="x", padx=6, pady=(6, 2))
        hint = ch.desc
        if cheats.is_gta(ch.id):
            hint = (" + ".join(ch.commands) + (" – " + ch.desc if ch.desc else ""))
        if hint:
            ctk.CTkLabel(box, text=hint, font=ctk.CTkFont(size=11), text_color=("gray40", "gray60"),
                         wraplength=190, justify="left", anchor="w").pack(fill="x", padx=8, pady=(0, 6))
        return box

    def _minecraft(self, tab):
        area, r = self._grid_of(tab, cheats.sections(cheats.MINECRAFT))
        ctk.CTkLabel(area, text="Eigener Befehl", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=r, column=0, columnspan=_COLS, sticky="w", padx=6, pady=(12, 2))
        line = ctk.CTkFrame(area, fg_color="transparent")
        line.grid(row=r + 1, column=0, columnspan=_COLS, sticky="ew", padx=4)
        entry = ctk.CTkEntry(line, placeholder_text="/give @s minecraft:beacon")
        entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(line, text="Ausführen", width=100,
                      command=lambda: self._run("mc_custom", entry.get())).pack(side="left", padx=(6, 0))

    def _gta(self, tab):
        if not gta_input.available():
            ctk.CTkLabel(tab, text="⚠  Die GTA-Cheats funktionieren nur unter Windows.", text_color=_BAD).pack(anchor="w", padx=8)
        groups = {"Pakete": [cheats.ALL[k] for k in cheats.GTA_COMBOS]}
        groups.update(cheats.sections(cheats.GTA))
        self._grid_of(tab, groups)

    def _trainer(self, tab):
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        holder = ctk.CTkFrame(tab, fg_color="transparent")
        holder.pack(fill="both", expand=True)
        self.result = ctk.CTkLabel(tab, text="", anchor="w", justify="left")
        self.result.pack(fill="x", pady=(6, 0))
        try:
            from .trainer_view import TrainerCanvas
            canvas = TrainerCanvas(holder, on_result=self._trainer_result)
            canvas.pack(fill="both", expand=True)
        except Exception as exc:          # z. B. ohne Bildschirm
            ctk.CTkLabel(holder, text=f"Übungsfeld konnte nicht geladen werden: {exc}", text_color=_BAD).pack()
            return
        self.canvas = canvas

        desc = ctk.CTkLabel(tab, text="", anchor="w", justify="left", wraplength=640, text_color=("gray40", "gray60"))

        def pick(name):
            canvas.pattern_name = name
            desc.configure(text=trainer.PATTERNS[name])
            self._show_best()

        ctk.CTkLabel(top, text="Muster").pack(side="left")
        pm = ctk.CTkOptionMenu(top, values=list(trainer.PATTERNS), width=170, command=pick)
        pm.set(canvas.pattern_name)
        pm.pack(side="left", padx=(6, 14))

        def custom_changed():
            """Regler oder Hilfslinie verändert: die Runde zählt dann nicht mehr für die Bestenliste (Haken geht aus)."""
            if getattr(self, "_loading_std", False):
                return
            if ranked.get():
                ranked.deselect()
            self._show_best()

        def set_strength(v):
            canvas.strength = round(float(v), 2)
            custom_changed()

        def set_rate(v):
            canvas.rate = int(round(float(v)))
            custom_changed()

        def set_guide():
            canvas.show_guide = bool(guide.get())
            custom_changed()

        ctk.CTkLabel(top, text="Stärke").pack(side="left")
        st = ctk.CTkSlider(top, from_=0.5, to=2.0, width=110, command=set_strength)
        st.set(1.0)
        st.pack(side="left", padx=(6, 14))

        ctk.CTkLabel(top, text="Schuss/s").pack(side="left")
        rt = ctk.CTkSlider(top, from_=5, to=15, number_of_steps=10, width=110, command=set_rate)
        rt.set(10)
        rt.pack(side="left", padx=(6, 14))

        guide = ctk.CTkCheckBox(top, text="Hilfslinie", command=set_guide)
        guide.deselect()
        canvas.show_guide = False
        guide.pack(side="left", padx=(0, 14))

        def ranked_changed():
            """Haken an = feste Standardwerte (Stärke 1, 10 Schuss/s, keine Hilfslinie), damit alle gleich spielen. Die Regler bleiben immer bedienbar."""
            if ranked.get():
                self._loading_std = True
                try:
                    canvas.strength, canvas.rate, canvas.show_guide = 1.0, 10, False
                    canvas.weapon_id = "standard"
                    wm.set(weapons.weapon("standard")["name"])
                    st.set(1.0)
                    rt.set(10)
                    guide.deselect()
                finally:
                    self._loading_std = False
            self._show_best()

        ranked = ctk.CTkCheckBox(top, text="Bestenliste", command=ranked_changed)
        ranked.select()
        ranked.pack(side="left")
        self.ranked = ranked
        desc.pack(fill="x", before=holder, pady=(0, 4))

        # ---- Zeile 2: Waffe, Design, Fadenkreuz, Treffer-Markierung, Wiederholung
        prefs = self.plugin.cfg().get("trainer_prefs")
        prefs = dict(prefs) if isinstance(prefs, dict) else {}
        top2 = ctk.CTkFrame(tab, fg_color="transparent")
        top2.pack(fill="x", pady=(0, 4), before=holder)

        def save_prefs():
            self.plugin.set_cfg(trainer_prefs={"weapon": canvas.weapon_id, "skin": canvas.skin_name,
                                               "crosshair": canvas.crosshair, "marker": canvas.marker})

        def pick_weapon(name):
            wid = weapons.weapon_id(name)
            canvas.weapon_id = wid
            w = weapons.weapon(wid)
            self._loading_std = True
            try:
                canvas.strength, canvas.rate = float(w["strength"]), int(w["rate"])
                st.set(min(2.0, max(0.5, canvas.strength)))
                rt.set(min(15, max(5, canvas.rate)))
            finally:
                self._loading_std = False
            if wid != "standard" and ranked.get():
                ranked.deselect()
            wdesc.configure(text=tr(w["descr"]) + "  (" + tr("{n} shots", n=w["shots"]) + ")")
            save_prefs()
            self._show_best()

        def pick_skin(name):
            canvas.set_skin(name)
            self.spark.configure(bg=canvas.sk["bg"])
            self._show_stats()
            save_prefs()

        def pick_cross(name):
            canvas.crosshair = name
            save_prefs()

        def pick_marker(name):
            canvas.marker = name
            save_prefs()

        ctk.CTkLabel(top2, text=tr("Weapon")).pack(side="left")
        wm = ctk.CTkOptionMenu(top2, values=weapons.weapon_names(), width=130, command=pick_weapon)
        wm.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(top2, text=tr("Design")).pack(side="left")
        sm = ctk.CTkOptionMenu(top2, values=list(weapons.SKINS), width=100, command=pick_skin)
        sm.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(top2, text=tr("Crosshair")).pack(side="left")
        cm = ctk.CTkOptionMenu(top2, values=weapons.CROSSHAIRS, width=80, command=pick_cross)
        cm.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(top2, text=tr("Hit marks")).pack(side="left")
        mkm = ctk.CTkOptionMenu(top2, values=weapons.MARKERS, width=80, command=pick_marker)
        mkm.pack(side="left", padx=(6, 12))
        ctk.CTkButton(top2, text="↻ " + tr("Replay"), width=90, fg_color=_HOVER, text_color=_TEXT,
                      command=lambda: None if canvas.replay() else self._say(tr("Play a round first."), False)).pack(side="left")
        wdesc = ctk.CTkLabel(tab, text="", anchor="w", text_color=("gray40", "gray60"))
        wdesc.pack(fill="x", before=holder, pady=(0, 2))
        # gespeicherte Auswahl wiederherstellen
        wm.set(weapons.weapon(prefs.get("weapon", "")).get("name"))
        sm.set(prefs.get("skin") if prefs.get("skin") in weapons.SKINS else "Classic")
        cm.set(prefs.get("crosshair") if prefs.get("crosshair") in weapons.CROSSHAIRS else "Ring")
        mkm.set(prefs.get("marker") if prefs.get("marker") in weapons.MARKERS else "Dot")
        canvas.set_skin(sm.get())
        canvas.crosshair, canvas.marker = cm.get(), mkm.get()
        pick_weapon(wm.get())
        if canvas.weapon_id == "standard" and not ranked.get():
            ranked.select()
        # ---- Verlauf
        self.stats_label = ctk.CTkLabel(tab, text="", anchor="w", justify="left")
        self.stats_label.pack(fill="x")
        self.spark = tk.Canvas(tab, height=46, highlightthickness=0, bg=canvas.sk["bg"])
        self.spark.pack(fill="x", pady=(2, 0))
        self._show_stats()
        pick(canvas.pattern_name)

    def _show_stats(self):
        """Kennzahlen und kleines Liniendiagramm der letzten Runden (lokal gespeichert, höchstens 50)."""
        hist = self.plugin.cfg().get("recoil_history")
        s = weapons.stats(hist)
        if not s["rounds"]:
            self.stats_label.configure(text=tr("No rounds yet. Your history appears here."))
            self.spark.delete("all")
            return
        trend = f"{s['trend']:+g}" if s["rounds"] > 5 else "–"
        self.stats_label.configure(text=tr("Rounds: {n}   Best: {b}   Average: {a}   Trend: {t}   Streak ≥ 75: {s}",
                                           n=s["rounds"], b=s["best"], a=s["average"], t=trend, s=s["streak"]))
        self.spark.delete("all")
        w = max(self.spark.winfo_width(), 300)
        pts = weapons.sparkline(hist, w, 46)
        if len(pts) > 1:
            self.spark.create_line(*[c for p in pts for c in p], fill=self.canvas.sk["target"], width=2)

    def _trainer3d(self, tab):
        from . import trainer3d
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        holder = ctk.CTkFrame(tab, fg_color="transparent")
        holder.pack(fill="both", expand=True)
        self.result3d = ctk.CTkLabel(tab, text="", anchor="w", justify="left")
        self.result3d.pack(fill="x", pady=(6, 0))
        try:
            from .trainer3d_view import Trainer3DCanvas
            canvas = Trainer3DCanvas(holder, on_result=self._trainer3d_result)
            canvas.pack(fill="both", expand=True)
        except Exception as exc:
            ctk.CTkLabel(holder, text=f"3D-Übungsfeld konnte nicht geladen werden: {exc}", text_color=_BAD).pack()
            return
        self.canvas3d = canvas

        def pattern(v):
            canvas.pattern_name = v
            self._show_best3d()

        def dist(v):
            canvas.dist_name = v
            canvas.redraw()
            self._show_best3d()

        def mode(v):
            canvas.mode = v
            canvas.redraw()
            self._show_best3d()

        ctk.CTkLabel(top, text="Muster").pack(side="left")
        pm = ctk.CTkOptionMenu(top, values=list(trainer.PATTERNS), width=150, command=pattern)
        pm.set(canvas.pattern_name)
        pm.pack(side="left", padx=(6, 10))
        ctk.CTkLabel(top, text="Entfernung").pack(side="left")
        dm = ctk.CTkOptionMenu(top, values=list(trainer3d.DISTANCES), width=130, command=dist)
        dm.set(canvas.dist_name)
        dm.pack(side="left", padx=(6, 10))
        ctk.CTkLabel(top, text="Ziel").pack(side="left")
        mm = ctk.CTkOptionMenu(top, values=list(trainer3d.TARGET_MODES), width=130, command=mode)
        mm.set(canvas.mode)
        mm.pack(side="left", padx=(6, 10))

        def strength(v):
            canvas.strength = round(float(v), 2)

        def rate(v):
            canvas.rate = int(round(float(v)))

        top2 = ctk.CTkFrame(tab, fg_color="transparent")
        top2.pack(fill="x", pady=(0, 4), before=holder)
        ctk.CTkLabel(top2, text="Stärke").pack(side="left")
        st = ctk.CTkSlider(top2, from_=0.5, to=2.0, width=110, command=strength)
        st.set(1.0)
        st.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(top2, text="Schuss/s").pack(side="left")
        rt = ctk.CTkSlider(top2, from_=5, to=15, number_of_steps=10, width=110, command=rate)
        rt.set(10)
        rt.pack(side="left", padx=(6, 14))

        def pick_weapon3d(name):
            wid = weapons.weapon_id(name)
            canvas.weapon_id = wid
            w = weapons.weapon(wid)
            canvas.strength, canvas.rate = float(w["strength"]), int(w["rate"])
            st.set(min(2.0, max(0.5, canvas.strength)))
            rt.set(min(15, max(5, canvas.rate)))

        def pick_skin3d(name):
            canvas.set_skin(name)

        ctk.CTkLabel(top2, text=tr("Weapon")).pack(side="left")
        w3 = ctk.CTkOptionMenu(top2, values=weapons.weapon_names(), width=120, command=pick_weapon3d)
        w3.set(weapons.weapon(canvas.weapon_id)["name"])
        w3.pack(side="left", padx=(6, 10))
        ctk.CTkLabel(top2, text=tr("Design")).pack(side="left")
        s3 = ctk.CTkOptionMenu(top2, values=list(weapons.SKINS), width=90, command=pick_skin3d)
        s3.set(canvas.skin_name)
        s3.pack(side="left", padx=(6, 10))
        view_btn = ctk.CTkButton(top2, text="3D-Ansicht", width=120)

        def toggle():
            if canvas.view == "play":
                canvas.set_view("orbit")
                view_btn.configure(text="Zurück zum Üben")
            else:
                canvas.set_view("play")
                view_btn.configure(text="3D-Ansicht")
        view_btn.configure(command=toggle)
        view_btn.pack(side="left")
        top.pack_configure(before=top2)
        self._show_best3d()

    def _best3d_key(self):
        c = self.canvas3d
        return f"{c.pattern_name}|{c.dist_name}|{c.mode}" + ("" if c.weapon_id == "standard" else "|" + c.weapon_id)

    def _best3d(self) -> dict:
        b = self.plugin.cfg().get("recoil3d_best")
        return dict(b) if isinstance(b, dict) else {}

    def _show_best3d(self, extra=""):
        if getattr(self, "canvas3d", None) is None:
            return
        best = self._best3d().get(self._best3d_key())
        name = self._best3d_key().replace("|", ", ")
        text = f"Bestwert ({name}): {best} Punkte" if best is not None else f"Noch kein Bestwert für {name}."
        self.result3d.configure(text=(extra + "\n" if extra else "") + text)

    def _trainer3d_result(self, res):
        key = f"{res['pattern']}|{res['distance']}|{res['mode']}" + ("" if res.get("weapon", "standard") == "standard" else "|" + res["weapon"])
        best = self._best3d()
        new = res["score"] > best.get(key, -1)
        if new and res["shots"] >= 10:
            best[key] = res["score"]
            self.plugin.set_cfg(recoil3d_best=best)
        line = (f"{res['score']} Punkte – {res['hits']} von {res['shots']} Schüssen trafen die Scheibe ({res['accuracy']} %), "
                f"im Schnitt {res['avg']} Scheibenradien daneben.")
        if new and res["shots"] >= 10:
            line += "  Neuer Bestwert! 🏆"
        elif res["shots"] < 10:
            line += "  (Bestwerte zählen ab 10 Schüssen.)"
        self._show_best3d(line)

    def _best_key(self, pattern=None, weapon=None) -> str:
        """Bestwert je Muster; für andere Waffen als Standard je „Muster|Waffe“, damit sich die Werte nicht vermischen."""
        c = getattr(self, "canvas", None)
        pattern = pattern or getattr(c, "pattern_name", "")
        weapon = weapon or getattr(c, "weapon_id", "standard")
        return pattern if weapon == "standard" else f"{pattern}|{weapon}"

    def _best(self) -> dict:
        b = self.plugin.cfg().get("recoil_best")
        return dict(b) if isinstance(b, dict) else {}

    def _show_best(self, extra=""):
        name = self._best_key()
        best = self._best().get(name)
        text = f"Bestwert „{name}“: {best} Punkte" if best is not None else f"Noch kein Bestwert für „{name}“."
        self.result.configure(text=(extra + "\n" if extra else "") + text)

    def _trainer_result(self, res):
        best = self._best()
        key = self._best_key(res["pattern"], res.get("weapon"))
        new = res["score"] > best.get(key, -1)
        if new and res["shots"] >= 10:
            best[key] = res["score"]
            self.plugin.set_cfg(recoil_best=best)
        self.plugin.set_cfg(recoil_history=weapons.add_history(
            self.plugin.cfg().get("recoil_history"), {"score": res["score"], "avg": res["avg"], "shots": res["shots"],
                                                       "weapon": res.get("weapon", "standard"), "pattern": res["pattern"]}))
        self._show_stats()
        self._submit_board(res)
        line = (f"{res['score']} Punkte ({res['shots']} Schüsse) – Abstand zum Ziel im Schnitt {res['avg']} px, "
                f"ohne Ausgleich wären es {res['without']} px gewesen.")
        if new and res["shots"] >= 10:
            line += "  Neuer Bestwert! 🏆"
        elif res["shots"] < 10:
            line += "  (Bestwerte zählen ab 10 Schüssen.)"
        if res.get("hint"):
            line += "\n" + tr(res["hint"])
        self._show_best(line)

    def _submit_board(self, res):
        """Volle Standardrunde -> Punkte an die Bestenliste der Community (nur wenn ein Cloud-Konto und die Community eingerichtet sind)."""
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        kind = trainer.board_kind(res["pattern"], res["shots"], canvas.strength, canvas.rate, canvas.show_guide, res.get("weapon", "standard"))
        if not kind:
            if res.get("weapon", "standard") != "standard":
                why = tr("Not counted for the leaderboard: only the Standard weapon counts.")
            elif res["shots"] < trainer.SHOTS:
                why = "Nicht für die Bestenliste gezählt: Die Runde wurde vor dem letzten Schuss beendet (alle 30 Schüsse nötig)."
            else:
                why = "Nicht für die Bestenliste gezählt: Dafür den Haken „Bestenliste“ setzen (feste Standardwerte, keine Hilfslinie)."
            self._say(why, False)
            return
        app = self.plugin.app
        comm = app.plugin_by_id.get("community")

        def work():
            try:
                from modules.community.market import MarketService
                svc = comm.service() if comm else None
                if svc is None:
                    app.call_soon(self._say, tr("Not sent to the leaderboard: sign in with a cloud account and set up the community first."), False)
                    return
                best = MarketService(svc).submit_score(kind, res["score"])
                app.call_soon(self._say, tr("Sent to the leaderboard (Community > Leaderboards). Your best: {v}", v=f"{best:g}"))
            except Exception as exc:                  # ohne Konto oder Netz zählt die Runde nur lokal – aber das wird angezeigt
                app.call_soon(self._say, tr("Could not send the score to the leaderboard: {e}", e=str(exc)[:160]), False)
        threading.Thread(target=work, daemon=True).start()

    def _help(self, tab):
        box = ctk.CTkTextbox(tab, wrap="word")
        box.pack(fill="both", expand=True)
        box.insert("1.0", HELP)
        box.configure(state="disabled")

    # ---- Ausführen ----
    def _run(self, cheat_id, custom=""):
        self._save_delay()
        err = self.plugin.run(cheat_id, custom=custom)
        if err:
            self._say(err, False)

    def _say(self, text, ok=True):
        if self.winfo_exists():
            self.msg.configure(text=text, text_color=_OK if ok else _BAD)

    def destroy(self):
        if self.plugin.on_status == self._say:
            self.plugin.on_status = None
        super().destroy()
