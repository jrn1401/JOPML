"""Kleine Dialoge der Community-Seite."""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core import theme
from core.i18n import tr


def _top(parent, title: str, size: str) -> ctk.CTkToplevel:
    top = ctk.CTkToplevel(parent, fg_color=theme.c("main"))
    top.title(tr(title))
    top.geometry(size)
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    top.after(120, top.lift)
    return top


def ask_text(parent, title: str, label: str, ok_text: str, on_ok, secret: bool = False, initial: str = "", multiline: bool = False):
    """Fragt einen Text ab; ruft on_ok(text) beim Bestätigen auf."""
    top = _top(parent, title, "460x260" if multiline else "460x170")
    ctk.CTkLabel(top, text=tr(label), anchor="w", wraplength=420, justify="left").pack(fill="x", padx=20, pady=(18, 4))
    if multiline:
        box = ctk.CTkTextbox(top, height=110)
        box.pack(fill="x", padx=20)
        get = lambda: box.get("1.0", "end").strip()      # noqa: E731
    else:
        e = ctk.CTkEntry(top, show="•" if secret else "")
        e.pack(fill="x", padx=20)
        if initial:
            e.insert(0, initial)
        e.bind("<Return>", lambda _e: go())
        get = lambda: e.get().strip()                    # noqa: E731

    def go():
        value = get()
        top.destroy()
        on_ok(value)

    row = ctk.CTkFrame(top, fg_color="transparent")
    row.pack(pady=14)
    ctk.CTkButton(row, text=tr(ok_text), width=120, command=go).pack(side="left", padx=6)
    ctk.CTkButton(row, text=tr("Cancel"), width=100, fg_color="gray35", hover_color="gray25", command=top.destroy).pack(side="left", padx=6)
    return top


def show_text(parent, title: str, text: str, big: bool = False):
    """Zeigt einen Text, der kopiert werden kann (z. B. Einladungscode, Sicherheitsnummer)."""
    top = _top(parent, title, "520x230")
    ctk.CTkLabel(top, text=tr(title), font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(18, 6))
    e = ctk.CTkEntry(top, width=440, font=ctk.CTkFont(family="Consolas", size=18 if big else 14), justify="center")
    e.insert(0, text)
    e.configure(state="readonly")
    e.pack(pady=6)

    def copy():
        top.clipboard_clear()
        top.clipboard_append(text)

    row = ctk.CTkFrame(top, fg_color="transparent")
    row.pack(pady=12)
    ctk.CTkButton(row, text=tr("Copy"), width=110, command=copy).pack(side="left", padx=6)
    ctk.CTkButton(row, text=tr("Close"), width=110, fg_color="gray35", hover_color="gray25", command=top.destroy).pack(side="left", padx=6)
    return top


def confirm(title: str, text: str) -> bool:
    return messagebox.askyesno(tr(title), tr(text))


def info(title: str, text: str) -> None:
    messagebox.showinfo(tr(title), tr(text))


def show_rules(parent, text: str):
    top = _top(parent, "Community rules", "560x420")
    box = ctk.CTkTextbox(top, wrap="word")
    box.pack(fill="both", expand=True, padx=14, pady=14)
    box.insert("1.0", tr(text))
    box.configure(state="disabled")
    return top
