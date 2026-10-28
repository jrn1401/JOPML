"""Reiter "Moderation" (nur für Admin-Konten): offene Meldungen ansehen und bearbeiten."""
import customtkinter as ctk

from core import theme
from core.i18n import tr

from .chat_view import fmt_time


class ModView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.svc = page, page.svc
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        ctk.CTkButton(bar, text="⟳ " + tr("Reload"), width=110, command=self.reload).pack(side="left")
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
        self.area.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))

    def on_show(self):
        self.reload()

    def reload(self):
        self.page.run(self.svc.admin_reports, self._render)

    def _render(self, reports):
        for w in self.area.winfo_children():
            w.destroy()
        if not reports:
            ctk.CTkLabel(self.area, text=tr("No open reports."), text_color=theme.MUTED).pack(pady=24)
        for r in reports:
            f = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=10)
            f.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(f, text=f"#{r['id']} · {r['kind']} · {fmt_time(r['created_at'])} · " + tr("by {u}", u=r.get("reporter") or "?")
                         + (" · " + tr("about {u}", u=r["reported"]) if r.get("reported") else ""),
                         font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=560, justify="left").pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(f, text=tr("Reason: {r}", r=r["reason"]), anchor="w", wraplength=560, justify="left").pack(fill="x", padx=14)
            ev = (r.get("evidence") or "")
            if ev:
                text = ev
                try:
                    import json
                    d = json.loads(ev)
                    text = d.get("text") or tr("(text hidden by the filter)")
                except Exception:
                    pass
                ctk.CTkLabel(f, text="“" + text[:600] + "”", anchor="w", wraplength=560, justify="left", text_color=theme.MUTED).pack(fill="x", padx=14, pady=4)
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(2, 10))
            acts = [("Dismiss", "dismiss", "gray35")]
            if r["kind"] in ("message", "user", "server") and r.get("reported_id"):
                acts.append(("Suspend user", "suspend_user", "#b91c1c"))
            if r["kind"] == "server" and r.get("space_id"):
                acts.append(("Delete server", "delete_server", "#b91c1c"))
            if r["kind"] == "thread":
                acts.append(("Delete thread", "delete_thread", "#b91c1c"))
            if r["kind"] == "post":
                acts.append(("Delete post", "delete_post", "#b91c1c"))
            for label, action, color in acts:
                ctk.CTkButton(row, text=tr(label), width=120, height=28, fg_color=color, hover_color="gray25" if color == "gray35" else "#7f1d1d",
                              command=lambda i=r["id"], a=action: self._resolve(i, a)).pack(side="left", padx=(0, 6))

    def _resolve(self, report_id, action):
        self.page.run(lambda: self.svc.admin_resolve(report_id, action), lambda _: self.reload())
