"""Reiter "News": Ankündigungen des Betreibers; jede Version hat eine aufklappbare Release-Note (beim Upload automatisch eingetragen)."""
import customtkinter as ctk

from core import theme
from core.i18n import tr
from core.version import APP_VERSION

from .market import MarketService
from .market_view import dialogs


def local_changelog() -> list[str]:
    """Liest RELEASE_NOTES.txt (eine Zeile, Versionen mit 'Version x.y.z:' getrennt) und gibt eine Zeile je Version zurück."""
    import re
    try:
        from pathlib import Path
        text = (Path(__file__).resolve().parents[2] / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    except OSError:
        return []
    return [x.strip() for x in re.split(r"(?=Version \d+\.\d+\.\d+:)", text) if x.strip()]


class NewsView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.app = page, page.app
        self.market = MarketService(page.svc)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        self.area.grid(row=0, column=0, sticky="nsew", padx=24, pady=(0, 12))
        self.msg = ctk.CTkLabel(self, text="", anchor="w")
        self.msg.grid(row=2, column=0, sticky="ew", padx=24)
        if (page.svc.me or {}).get("is_admin"):
            ctk.CTkButton(self, text="+ " + tr("Post an announcement"), width=200, command=self.post).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 6))

    def on_show(self):
        self.page.run(self.market.news, self._render, lambda e: self.msg.configure(text=e, text_color=theme.DANGER))

    def _render(self, rows):
        for w in self.area.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.area, text=tr("Announcements"), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        if not rows:
            ctk.CTkLabel(self.area, text=tr("No announcements yet."), text_color=theme.MUTED).pack(anchor="w", padx=10)
        first_version = True
        for r in rows:
            f = ctk.CTkFrame(self.area, fg_color=theme.c("inset"), corner_radius=8)
            f.pack(fill="x", padx=6, pady=4)
            when = r["created_at"][:10]
            if r.get("version"):                                  # Release-Note: je Version aufklappbar, die neueste ist offen
                body = ctk.CTkLabel(f, text=r.get("body") or "", anchor="w", justify="left", wraplength=640)
                state = {"open": first_version}
                first_version = False
                head = ctk.CTkButton(f, anchor="w", fg_color="transparent", hover_color=theme.c("hover"), text_color=theme.TEXT, height=32)

                def toggle(h=head, b=body, st=state, t=r["title"], d=when):
                    st["open"] = not st["open"]
                    self._fold(h, b, st["open"], t, d)
                head.configure(command=toggle)
                head.pack(fill="x", padx=4, pady=(4, 0))
                self._fold(head, body, state["open"], r["title"], when)
            else:
                ctk.CTkLabel(f, text=r["title"], font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 0))
                ctk.CTkLabel(f, text=when, text_color=theme.MUTED, font=ctk.CTkFont(size=10), anchor="w").pack(fill="x", padx=10)
                if r.get("body"):
                    ctk.CTkLabel(f, text=r["body"], anchor="w", justify="left", wraplength=640).pack(fill="x", padx=10, pady=(2, 8))
            if (self.page.svc.me or {}).get("is_admin"):
                ctk.CTkButton(f, text="🗑", width=30, height=22, fg_color="gray35", hover_color="gray25",
                              command=lambda i=r["id"]: self.page.run(lambda: self.market.delete_news(i), lambda _: self.on_show())).pack(anchor="e", padx=8, pady=(0, 6))
        if not any(r.get("version") for r in rows):               # Rückfall, solange der Server noch keine Release-Notes hat
            ctk.CTkLabel(self.area, text=tr("Changes in this version") + f" ({APP_VERSION})", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(14, 2))
            for line in local_changelog()[:6]:
                ctk.CTkLabel(self.area, text="• " + line, anchor="w", justify="left", wraplength=660, text_color=theme.MUTED).pack(fill="x", padx=10, pady=2)

    @staticmethod
    def _fold(head, body, opened, title, when):
        head.configure(text=("▾  " if opened else "▸  ") + f"{title}   ·   {when}")
        if opened:
            body.pack(fill="x", padx=14, pady=(0, 8))
        else:
            body.pack_forget()

    def post(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Post an announcement"))
        top.geometry("480x340")
        top.after(120, top.lift)
        t = ctk.CTkEntry(top, placeholder_text=tr("Title"))
        t.pack(fill="x", padx=16, pady=(16, 6))
        b = ctk.CTkTextbox(top, height=150)
        b.pack(fill="x", padx=16)
        ctk.CTkButton(top, text=tr("Post"), width=100, command=lambda: self.page.run(
            lambda: self.market.post_news(t.get(), b.get("1.0", "end").strip()), lambda _: (top.destroy(), self.on_show()),
            lambda e: self.msg.configure(text=e, text_color=theme.DANGER))).pack(anchor="w", padx=16, pady=10)
