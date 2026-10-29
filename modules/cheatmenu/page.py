"""Seite "Cheat-Menü": Reiter Minecraft / GTA 5 / Hilfe, jeder Cheat ist ein Knopf."""
import threading

import customtkinter as ctk

from core.i18n import tr

from . import cheats, gta_input, trainer

try:
    from core import theme
    _MAIN = theme.c("main")
    _OK, _BAD = theme.OK, theme.DANGER
except Exception:                      # falls sich das Design-Modul nach einem Update ändert
    _MAIN, _OK, _BAD = "transparent", "#2e9d5b", "#e5484d"

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
• Bestenliste: Eine volle Runde (alle 30 Schüsse) mit Standardwerten (Stärke 1, 10 Schuss/s, Hilfslinie aus) geht automatisch an die Bestenliste des Musters in Community > Bestenlisten, wenn du ein Cloud-Konto und die Community eingerichtet hast. Die Punkte kommen von deinem Programm; der Server kann den Spielverlauf nicht prüfen.
• Der Trainer liest die Maus nur im eigenen Feld und gibt selbst keine Eingaben ab – er trainiert deine Hand und wirkt nicht in Spielen.

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
        for name in ("Minecraft", "GTA 5 Enhanced", "Rückstoß-Trainer", "Hilfe"):
            tabs.add(name)
        self._minecraft(tabs.tab("Minecraft"))
        self._gta(tabs.tab("GTA 5 Enhanced"))
        self._trainer(tabs.tab("Rückstoß-Trainer"))
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

        ctk.CTkLabel(top, text="Stärke").pack(side="left")
        st = ctk.CTkSlider(top, from_=0.5, to=2.0, width=110, command=lambda v: setattr(canvas, "strength", float(v)))
        st.set(1.0)
        st.pack(side="left", padx=(6, 14))

        ctk.CTkLabel(top, text="Schuss/s").pack(side="left")
        rt = ctk.CTkSlider(top, from_=5, to=15, number_of_steps=10, width=110, command=lambda v: setattr(canvas, "rate", int(v)))
        rt.set(10)
        rt.pack(side="left", padx=(6, 14))

        guide = ctk.CTkCheckBox(top, text="Hilfslinie", command=lambda: setattr(canvas, "show_guide", bool(guide.get())))
        guide.select()
        guide.pack(side="left")
        desc.pack(fill="x", before=holder, pady=(0, 4))
        pick(canvas.pattern_name)

    def _best(self) -> dict:
        b = self.plugin.cfg().get("recoil_best")
        return dict(b) if isinstance(b, dict) else {}

    def _show_best(self, extra=""):
        name = getattr(getattr(self, "canvas", None), "pattern_name", "")
        best = self._best().get(name)
        text = f"Bestwert „{name}“: {best} Punkte" if best is not None else f"Noch kein Bestwert für „{name}“."
        self.result.configure(text=(extra + "\n" if extra else "") + text)

    def _trainer_result(self, res):
        best = self._best()
        new = res["score"] > best.get(res["pattern"], -1)
        if new and res["shots"] >= 10:
            best[res["pattern"]] = res["score"]
            self.plugin.set_cfg(recoil_best=best)
        self._submit_board(res)
        line = (f"{res['score']} Punkte ({res['shots']} Schüsse) – Abstand zum Ziel im Schnitt {res['avg']} px, "
                f"ohne Ausgleich wären es {res['without']} px gewesen.")
        if new and res["shots"] >= 10:
            line += "  Neuer Bestwert! 🏆"
        elif res["shots"] < 10:
            line += "  (Bestwerte zählen ab 10 Schüssen.)"
        self._show_best(line)

    def _submit_board(self, res):
        """Volle Standardrunde -> Punkte an die Bestenliste der Community (nur wenn ein Cloud-Konto und die Community eingerichtet sind)."""
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        kind = trainer.board_kind(res["pattern"], res["shots"], canvas.strength, canvas.rate, canvas.show_guide)
        if not kind:
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
