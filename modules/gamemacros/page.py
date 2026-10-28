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
        for p in preset.params:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=tr(p.label), width=200, anchor="w").pack(side="left")
            if p.kind == "choice":
                w = ctk.CTkOptionMenu(r, values=p.choices, width=120)
                w.set(p.default)
                widgets[p.key] = w.get
            else:
                w = ctk.CTkEntry(r, width=300 if p.kind == "text" else 90)
                w.insert(0, str(p.default))
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
        r = ctk.CTkFrame(c, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkButton(r, text="▶  " + tr("Start"), width=110, command=start).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r, text="■  " + tr("Stop"), width=100, fg_color="#c0392b", hover_color="#962d22", command=stop).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r, text=tr("Save to My macros"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT, command=save).pack(side="left")
        msg.pack(fill="x", padx=16, pady=(2, 12))
