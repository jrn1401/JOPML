"""Module verschieben - direkt aus der Seitenleiste, ohne Einstellungen: Reihenfolge, ganz nach oben, ein-/ausblenden."""
import tkinter as tk

import customtkinter as ctk

from core import layout, theme
from core.i18n import tr


def open_editor(app):
    existing = getattr(app, "_layout_win", None)
    if existing is not None and existing.winfo_exists():
        existing.focus_force()
        return
    top = ctk.CTkToplevel(app, fg_color=theme.c("main"))
    app._layout_win = top
    top.title(tr("Move modules"))
    top.geometry("420x520")
    top.transient(app)
    ctk.CTkLabel(top, text=tr("Put the modules you use most at the top. Changes apply immediately."), text_color=theme.MUTED,
                 wraplength=380, justify="left").pack(fill="x", padx=14, pady=(12, 4))
    area = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"))
    area.pack(fill="both", expand=True, padx=12, pady=6)
    s = app.settings

    def render():
        for w in area.winfo_children():
            w.destroy()
        items = app.layout_items()
        ids = [i for i, _ in items]
        hidden = set(s.get("nav_hidden") or [])

        def order(new):
            app.set_layout(order=new)
            top.after(150, render)

        def show(pid, var):
            app.set_layout(hidden=layout.set_hidden(s.get("nav_hidden"), pid, not var.get()))

        for n, (pid, label) in enumerate(items):
            r = ctk.CTkFrame(area, fg_color=theme.c("inset"), corner_radius=8)
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=label, anchor="w").pack(side="left", padx=10, pady=5)
            var = tk.BooleanVar(value=pid not in hidden)
            ctk.CTkSwitch(r, text="", width=40, variable=var, command=lambda p=pid, v=var: show(p, v)).pack(side="right", padx=8)
            ctk.CTkButton(r, text="▼", width=28, height=26, state="normal" if n < len(items) - 1 else "disabled",
                          command=lambda p=pid: order(layout.move(ids, s.get("nav_order"), p, 1))).pack(side="right", padx=1)
            ctk.CTkButton(r, text="▲", width=28, height=26, state="normal" if n > 0 else "disabled",
                          command=lambda p=pid: order(layout.move(ids, s.get("nav_order"), p, -1))).pack(side="right", padx=1)
            ctk.CTkButton(r, text="⤒", width=28, height=26, state="normal" if n > 0 else "disabled",
                          command=lambda p=pid: order(layout.move_to_top(ids, s.get("nav_order"), p))).pack(side="right", padx=1)

    render()
    row = ctk.CTkFrame(top, fg_color="transparent")
    row.pack(fill="x", padx=12, pady=(0, 12))
    ctk.CTkButton(row, text=tr("Reset layout"), width=130, fg_color="gray35", hover_color="gray25",
                  command=lambda: (app.set_layout(order=[], hidden=[]), top.after(150, render))).pack(side="left")
    ctk.CTkButton(row, text=tr("Close"), width=100, command=top.destroy).pack(side="right")
