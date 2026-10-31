"""Kleines Fenster zum Ansehen und Speichern eines Textes, der live erzeugt wird (aktualisiert sich selbst, solange es offen ist)."""
from tkinter import filedialog

import customtkinter as ctk

from core import theme
from core.i18n import tr


def show(parent, title: str, make_text, filename: str = "text.txt", refresh_ms: int = 3000):
    """make_text() -> str wird beim Öffnen und danach regelmäßig neu aufgerufen; ändert sich der Text, wird die Anzeige erneuert."""
    top = ctk.CTkToplevel(parent, fg_color=theme.c("main"))
    top.title(title)
    top.geometry("820x640")
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    box = ctk.CTkTextbox(top, wrap="word", font=ctk.CTkFont(size=13))
    box.pack(fill="both", expand=True, padx=14, pady=(14, 6))
    state = {"text": None}

    def refresh():
        if not top.winfo_exists():
            return
        try:
            text = make_text()
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
        if text != state["text"]:
            pos = box.yview()[0]
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", text)
            box.configure(state="disabled")
            box.yview_moveto(pos)
            state["text"] = text
        top.after(refresh_ms, refresh)

    def save():
        path = filedialog.asksaveasfilename(parent=top, defaultextension=".txt", initialfile=filename, filetypes=[("Text", "*.txt"), ("Markdown", "*.md")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(state["text"] or "")

    def copy():
        top.clipboard_clear()
        top.clipboard_append(state["text"] or "")

    bar = ctk.CTkFrame(top, fg_color="transparent")
    bar.pack(pady=(0, 12))
    ctk.CTkButton(bar, text=tr("Download as file …"), width=170, command=save).pack(side="left", padx=6)
    ctk.CTkButton(bar, text=tr("Copy"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=copy).pack(side="left", padx=6)
    ctk.CTkButton(bar, text=tr("Close"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=top.destroy).pack(side="left", padx=6)
    refresh()
    return top
