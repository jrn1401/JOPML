"""Hilfe > Fehlercodes: alle Codes mit Bedeutung und Lösungsvorschlag, durchsuchbar. Von dort: KI fragen oder melden (eine Stelle für Fehlerhilfe)."""
import customtkinter as ctk

from core import errors, theme, ui
from core.i18n import tr


class ErrorCatalogView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
        ctk.CTkLabel(head, text=tr("Error codes"), font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
        ui.muted(head, "Every message in the launcher has a code like E-NET-001. Find it here to see what it means and what you can do. "
                       "Still stuck? Ask the AI about the code or send a report.", wrap=720).pack(anchor="w")
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=24, pady=6)
        self.search = ctk.CTkEntry(bar, placeholder_text=tr("Search a code or a word …"), width=320)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda _e: self.render())
        ctk.CTkButton(bar, text="← " + tr("Help assistant"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: app.show("assistant")).pack(side="right")
        self.list = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        self.list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.focus = ""
        self.render()

    def focus_code(self, code: str):
        """Springt zu einem Code (aus dem Fehlerfenster): Suche setzen und Liste filtern."""
        self.focus = code or ""
        self.search.delete(0, "end")
        self.search.insert(0, self.focus)
        self.render()

    def render(self):
        for w in self.list.winfo_children():
            w.destroy()
        rows = search(self.search.get())
        if not rows:
            ui.muted(self.list, "No code matches. Try a shorter word.", wrap=640).pack(fill="x", padx=10, pady=10)
        for code, meaning, fix in rows:
            card = ctk.CTkFrame(self.list, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(card, text=code, anchor="w", font=ctk.CTkFont(size=15, weight="bold")).pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=tr(meaning), anchor="w", justify="left", wraplength=620).pack(fill="x", padx=12)
            ctk.CTkLabel(card, text="💡 " + tr(fix), anchor="w", justify="left", wraplength=620, text_color=theme.MUTED).pack(fill="x", padx=12, pady=(2, 4))
            br = ctk.CTkFrame(card, fg_color="transparent")
            br.pack(anchor="w", padx=8, pady=(0, 8))
            ctk.CTkButton(br, text="🤖 " + tr("Ask AI"), width=110, height=26,
                          command=lambda c=code, m=meaning: self.app.ask_ai(errors.explain_prompt(c, m), "Explain an error")).pack(side="left", padx=4)
            ctk.CTkButton(br, text="🚩 " + tr("Report"), width=100, height=26, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda c=code, m=meaning: self.app.open_report(c, m)).pack(side="left", padx=4)


def search(query: str) -> list[tuple[str, str, str]]:
    """Katalog gefiltert nach Suchtext (Code, Bedeutung oder Lösung; Groß/Klein egal; auch übersetzte Texte)."""
    q = (query or "").strip().lower()
    out = []
    for code, meaning, fix in errors.catalog():
        hay = " ".join((code, meaning, fix, tr(meaning), tr(fix))).lower()
        if all(part in hay for part in q.split()):
            out.append((code, meaning, fix))
    return out
