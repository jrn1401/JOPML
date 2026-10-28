"""Sammel-Seite mit Reitern: mehrere kleine Werkzeuge teilen sich einen Menüpunkt (hält die Seitenleiste übersichtlich)."""
import customtkinter as ctk

from core import theme, ui
from core.tabbar import WrapTabs
from core.i18n import tr


class HubPage(ctk.CTkFrame):
    """tabs: Liste aus (Beschriftung, fabrik) oder (Beschriftung, fabrik, True).
    Normal füllt fabrik(bereich, plugin) einen scrollbaren Bereich (wird beim ersten Öffnen gebaut).
    Mit True liefert fabrik(hub, plugin) eine fertige, selbst scrollende Seite (z. B. die Seite eines anderen Moduls), die als Reiter dient."""

    def __init__(self, parent, plugin, title: str, subtitle: str, tabs: list):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self._tabs = {tr(t[0]): t[1] for t in tabs}
        self._own = {tr(t[0]) for t in tabs if len(t) > 2 and t[2]}
        self._views: dict = {}
        self._cur = None
        self.seg = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ui.page_title(self, title, subtitle).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 6))
        first = list(self._tabs)[0]
        if len(self._tabs) > 1:
            self.seg = WrapTabs(self, list(self._tabs), self.open)
            self.seg.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 2))
            self.seg.set(first)
        self.open(first)

    def open(self, label: str):
        if self.seg is not None and self.seg.get() != label:
            self.seg.set(label)
        if self._cur is not None:
            self._cur.grid_forget()
        if label not in self._views:
            if label in self._own:
                area = self._tabs[label](self, self.plugin)
            else:
                area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
                area.columnconfigure(0, weight=1)
                self._tabs[label](area, self.plugin)
            self._views[label] = area
        self._cur = self._views[label]
        self._cur.grid(row=2, column=0, sticky="nsew")

    # Hilfen für die Reiter
    @staticmethod
    def card(parent, title: str, row: int):
        c = ui.card(parent, title)
        c.grid(row=row, column=0, sticky="ew", padx=24, pady=6)
        body = ctk.CTkFrame(c, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body
