"""Seite "Game macros": Reiter je Spiel/Bereich, jede Karte ist ein fertiges Makro."""
import tkinter as tk

import customtkinter as ctk

from core import theme, ui
from core.hub import HubPage
from core.i18n import tr

from . import library


def _say(label, text, ok=True):
    if label.winfo_exists():
        label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)


class GameMacrosPage(HubPage):
    def __init__(self, parent, plugin):
        tabs = [("General", lambda hub, plugin: self._recoil_page(), True)]
        tabs += [(label, lambda area, plugin, c=cat: self._tab(area, c)) for cat, label in library.CATEGORIES.items()]
        super().__init__(parent, plugin, "Game macros", "Ready-made macros for your games. Pick a game, set a few values and press Start.", tabs)

    def _recoil_page(self):
        from modules.recoil.page import RecoilPage
        return RecoilPage(self, self.app.plugin_by_id["recoil"], embedded=True)

    def _tab(self, area, category):
        ui.banner(area, "⚠  " + tr("Use macros only where the game allows it: single player, idle games or your own server. "
                                   "Do not use them to cheat in online games."), color="#92400e").grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        for i, preset in enumerate([p for p in library.PRESETS if p.category == category], start=1):
            self._card(area, preset, i)

    def _card(self, area, preset, row):
        c = ui.card(area, "")
        c.grid(row=row, column=0, sticky="ew", padx=24, pady=6)
        ctk.CTkLabel(c, text=tr(preset.title), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ui.muted(c, preset.desc).pack(fill="x", padx=16, pady=(0, 6))
        body = ctk.CTkFrame(c, fg_color="transparent")
        body.pack(fill="x", padx=16)
        widgets = {}
        saved = self.plugin.params_for(preset)
        for p in preset.params:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=tr(p.label), width=200, anchor="w").pack(side="left")
            if p.kind == "choice":
                w = ctk.CTkOptionMenu(r, values=p.choices, width=120)
                w.set(saved.get(p.key) if saved.get(p.key) in p.choices else p.default)
                widgets[p.key] = w.get
            else:
                w = ctk.CTkEntry(r, width=360 if p.kind == "text" else 90)
                w.insert(0, str(saved.get(p.key, p.default)))
                widgets[p.key] = w.get
            w.pack(side="left")
        msg = ctk.CTkLabel(c, text="", anchor="w", justify="left", wraplength=560)

        def raw():
            return {k: g() for k, g in widgets.items()}

        def start():
            err = self.plugin.run_preset(preset, raw())
            _say(msg, err or tr("Running – stop with the Stop button, F7 or the emergency stop."), not err)

        def stop():
            self.plugin.stop()
            _say(msg, tr("Stopped."))

        def save():
            err = self.plugin.save_preset(preset, raw(), preset.id)
            _say(msg, err or tr("Saved under “My macros” as {n}.", n=preset.id), not err)
        self._hotkey_rows(c, preset, raw, msg)
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkButton(r, text="▶  " + tr("Start"), width=110, command=start).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r, text="■  " + tr("Stop"), width=100, fg_color="#c0392b", hover_color="#962d22", command=stop).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r, text=tr("Save to My macros"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT, command=save).pack(side="left")
        msg.pack(fill="x", padx=16, pady=(2, 12))

    def _hotkey_rows(self, card, preset, raw, msg):
        """Start-Hotkey (schaltet um, wenn kein Stopp-Hotkey gesetzt ist), optionaler Stopp-Hotkey und Beschränkung auf ein Programm."""
        from core import hotkey_registry as hr
        from modules.autoclicker import keys as kcap
        reg = self.app.hotkeys
        sid, stid = self.plugin.hotkey_ids(preset)
        box = ctk.CTkFrame(card, fg_color="transparent")
        box.pack(fill="x", padx=16, pady=(6, 0))
        labels = {}
        cap = {"obj": None}

        def show():
            if not box.winfo_exists():
                return
            labels["start"].configure(text=hr.pretty(reg.key_of(sid)))
            labels["stop"].configure(text=hr.pretty(reg.key_of(stid)) if stid in reg.entries else "–")

        def record(which):
            if cap["obj"] is not None:
                cap["obj"].cancel()
            labels[which].configure(text=tr("Press keys …"))

            def done(result):
                def apply():
                    cap["obj"] = None
                    if result:
                        err = (self.plugin.set_start_key(preset, result, raw()) if which == "start" else self.plugin.set_stop_key(preset, result))
                        _say(msg, err or tr("Saved."), not err)
                    show()
                self.app.call_soon(apply)
            try:
                cap["obj"] = kcap.KeyCapture(done, combo=True)
                cap["obj"].start()
            except Exception as exc:
                _say(msg, str(exc), False)

        def clear(which):
            if which == "start":
                reg.set_key(sid, "")
            else:
                self.plugin.set_stop_key(preset, "")
            show()
        for which, text in (("start", tr("Start key (toggles without a stop key)")), ("stop", tr("Stop key (optional)"))):
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=text, width=230, anchor="w", text_color=theme.MUTED).pack(side="left")
            labels[which] = ctk.CTkLabel(r, text="–", width=150, corner_radius=6, fg_color=theme.c("inset"))
            labels[which].pack(side="left", padx=4)
            ctk.CTkButton(r, text=tr("Record"), width=80, command=lambda w=which: record(w)).pack(side="left", padx=2)
            ctk.CTkButton(r, text="✕", width=30, fg_color=theme.c("hover"), text_color=theme.TEXT, command=lambda w=which: clear(w)).pack(side="left", padx=2)
        r = ctk.CTkFrame(box, fg_color="transparent")
        r.pack(fill="x", pady=1)
        ctk.CTkLabel(r, text=tr("Only in this program (part of the window title)"), width=230, anchor="w", text_color=theme.MUTED).pack(side="left")
        win = ctk.CTkEntry(r, width=150, placeholder_text=tr("any program"))
        win.insert(0, reg.window_of(sid))
        win.pack(side="left", padx=4)

        def save_win(_e=None):
            reg.set_window(sid, win.get())
            if stid in reg.entries:
                reg.set_window(stid, win.get())
        win.bind("<FocusOut>", save_win)
        win.bind("<Return>", save_win)
        show()
