"""Reiter "Leaderboards": Bestenlisten für den Rückstoß-Trainer (je Muster), den CPS-Test und den Reaktionstest."""
import customtkinter as ctk

from core import theme
from core.i18n import tr

from .market import MarketService

# (Name der Liste, Schlüssel auf dem Server, Anzeigeformat)
BOARDS = (
    ("Recoil trainer – Straight up", "recoil_up", "{v:g} points"),
    ("Recoil trainer – Up, then right", "recoil_right", "{v:g} points"),
    ("Recoil trainer – Zigzag", "recoil_zigzag", "{v:g} points"),
    ("Recoil trainer – Random", "recoil_random", "{v:g} points"),
    ("CPS test (5 s)", "cps5", "{v:g} CPS"),
    ("Reaction test", "reaction", "{v:g} ms"),
)


class BoardsView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page = page
        self.market = MarketService(page.svc)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.names = {tr(n): (k, f) for n, k, f in BOARDS}
        self.pick = ctk.CTkOptionMenu(bar, values=list(self.names), width=300, command=lambda _v: self.reload())
        self.pick.pack(side="left")
        ctk.CTkButton(bar, text="⟳ " + tr("Reload"), width=100, command=self.reload).pack(side="left", padx=8)
        self.list = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        self.list.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 6))
        self.note = ctk.CTkLabel(self, text=tr("The Recoil trainer scores (Cheat menu > Recoil trainer) count for a full round with the standard settings. "
                                              "Scores are sent by the players' programs and are not checked by the server."),
                                 text_color=theme.MUTED, anchor="w", justify="left", wraplength=700)
        self.note.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))

    def on_show(self):
        self.reload()

    def reload(self):
        kind, fmt = self.names.get(self.pick.get(), BOARDS[0][1:])
        self.page.run(lambda: self.market.top(kind), lambda rows: self._render(rows, fmt), lambda e: self._render([], fmt, e))

    def _render(self, rows, fmt, error=""):
        if not self.list.winfo_exists():
            return
        for w in self.list.winfo_children():
            w.destroy()
        if error:
            ctk.CTkLabel(self.list, text=error, text_color=theme.DANGER).pack(pady=20)
            return
        if not rows:
            ctk.CTkLabel(self.list, text=tr("No scores yet."), text_color=theme.MUTED).pack(pady=20)
        for i, r in enumerate(rows, 1):
            ctk.CTkLabel(self.list, text=f"{i}.  {r['display_name']} (@{r['handle']})  –  " + tr(fmt, v=float(r["value"])), anchor="w",
                         text_color=theme.accent() if r["mine"] else theme.TEXT).pack(fill="x", padx=10, pady=2)
