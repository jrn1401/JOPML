"""Befehlspalette (Strg+P): tippen, Treffer wählen, Enter. Springt zu Menüpunkten und startet ein paar Aktionen."""
import customtkinter as ctk

from core import theme
from core.i18n import tr


def entries(app) -> list:
    """[(Beschriftung, Funktion)] - Seiten aus dem Menü und feste Aktionen."""
    out = []
    names = {"dashboard": tr("Dashboard"), "settings": tr("Settings"), "assistant": tr("Help assistant"), "contact": tr("Contact")}
    for pid, name in names.items():
        out.append((tr("Go to {n}", n=name), lambda pid=pid: app.show(pid)))
    for p in getattr(app, "plugins", []):
        if getattr(p, "nav", True) and getattr(p, "id", None) not in names:
            out.append((tr("Go to {n}", n=tr(p.name)), lambda pid=p.id: app.show(pid)))
    out.append((tr("Panic: stop everything"), app.panic))
    out.append((tr("Mini mode"), app.enter_mini))
    out.append((tr("Move modules"), app.open_layout_editor))
    out.append((tr("Restart launcher"), app.restart))
    out.append((tr("Check for updates"), lambda: app.check_updates(manual=True)))
    return out


def match(items: list, text: str) -> list:
    """Alle Einträge, in denen jedes Wort des Suchtexts vorkommt (Groß/Klein egal); Treffer am Wortanfang zuerst."""
    words = text.lower().split()
    hits = [it for it in items if all(w in it[0].lower() for w in words)]
    hits.sort(key=lambda it: (not any(part.startswith(words[0]) for part in it[0].lower().split()) if words else False, it[0].lower()))
    return hits


def open_palette(app):
    existing = getattr(app, "_palette", None)
    if existing is not None and existing.winfo_exists():
        existing.focus_force()
        return
    top = ctk.CTkToplevel(app, fg_color=theme.c("main"))
    app._palette = top
    top.title(tr("Command palette"))
    top.geometry("460x360")
    top.transient(app)
    top.update_idletasks()
    try:
        top.geometry(f"+{app.winfo_rootx() + (app.winfo_width() - 460) // 2}+{app.winfo_rooty() + 80}")
    except Exception:
        pass
    items = entries(app)
    entry = ctk.CTkEntry(top, placeholder_text=tr("Type to search … (Enter = run, Esc = close)"))
    entry.pack(fill="x", padx=12, pady=(12, 6))
    area = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"))
    area.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    state = {"hits": [], "sel": 0}

    def run(i):
        if 0 <= i < len(state["hits"]):
            fn = state["hits"][i][1]
            top.destroy()
            app.after(50, fn)

    def render(*_):
        for w in area.winfo_children():
            w.destroy()
        state["hits"] = match(items, entry.get())
        state["sel"] = min(state["sel"], max(0, len(state["hits"]) - 1))
        for i, (label, _fn) in enumerate(state["hits"]):
            b = ctk.CTkButton(area, text=label, anchor="w", height=30, fg_color=theme.c("hover") if i == state["sel"] else "transparent",
                              text_color=theme.TEXT, hover_color=theme.c("hover"), command=lambda i=i: run(i))
            b.pack(fill="x", pady=1)
        if not state["hits"]:
            ctk.CTkLabel(area, text=tr("Nothing found."), anchor="w").pack(fill="x", padx=8, pady=8)

    def move(d):
        state["sel"] = max(0, min(len(state["hits"]) - 1, state["sel"] + d))
        render()
        return "break"

    entry.bind("<KeyRelease>", lambda e: render() if e.keysym not in ("Up", "Down", "Return", "Escape") else None)
    entry.bind("<Down>", lambda e: move(1))
    entry.bind("<Up>", lambda e: move(-1))
    entry.bind("<Return>", lambda e: run(state["sel"]))
    top.bind("<Escape>", lambda e: top.destroy())
    render()
    top.after(120, entry.focus_force)
