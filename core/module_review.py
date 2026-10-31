"""Dialoge für KI-Änderungen an eigenen Modulen: Änderungen ansehen und mit einem Klick annehmen (Diff-Ansicht) sowie Versionsverlauf mit Rückgängig.
Beide werden vom KI-Chat und von der Modul-Verwaltung benutzt (eine Stelle, damit nichts doppelt ist)."""
from tkinter import messagebox

import customtkinter as ctk

from core import module_history, module_import, theme, ui
from core.i18n import tr

ADD, REM, HEAD = "#16a34a", "#dc2626", "#2563eb"


def _fill_diff(box, lines):
    """Färbt + / - / @@ in einer Textbox (Tags, falls vorhanden)."""
    box.configure(state="normal")
    box.delete("1.0", "end")
    for ln in lines:
        tag = "add" if ln.startswith("+") and not ln.startswith("+++") else "rem" if ln.startswith("-") and not ln.startswith("---") else "head" if ln.startswith("@@") else ""
        box.insert("end", ln + "\n", tag) if tag else box.insert("end", ln + "\n")
    try:
        box.tag_config("add", foreground=ADD)
        box.tag_config("rem", foreground=REM)
        box.tag_config("head", foreground=HEAD)
    except Exception:
        pass
    box.configure(state="disabled")


def review_change(app, parent, name: str, new_code: str, on_done=None):
    """Zeigt, was sich im Modul `name` ändern würde; 'Accept' sichert den alten Stand, schreibt den neuen und startet den Launcher neu (nach Rückfrage).
    Gibt es das Modul noch nicht, ist es ein neues Modul (alles grün). on_done(text, ok) meldet das Ergebnis an den Aufrufer."""
    old = module_history.current_code(name)
    findings = module_import.scan_code(new_code)
    add, rem = module_history.stats(old or "", new_code)
    top = ctk.CTkToplevel(parent, fg_color=theme.c("main"))
    top.title(tr("Review the change"))
    top.geometry("820x600")
    top.transient(parent.winfo_toplevel())
    ctk.CTkLabel(top, text=tr("Module {n}", n=name) + ("  ·  " + tr("new module") if old is None else ""), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 2))
    ui.muted(top, tr("{a} lines added, {r} lines removed. Green = new, red = removed. The old version is saved first, so you can undo this in Modules > History.", a=add, r=rem), wrap=780).pack(fill="x", padx=16)
    box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="none")
    box.pack(fill="both", expand=True, padx=16, pady=8)
    _fill_diff(box, module_history.diff(old or "", new_code) if old is not None else ["+" + ln for ln in new_code.splitlines()])
    check = (tr("The automatic check found:") + "\n• " + "\n• ".join(tr(f) for f in findings)) if findings else tr("The automatic check found nothing unusual (this is no guarantee).")
    ctk.CTkLabel(top, text=check, anchor="w", justify="left", wraplength=780, text_color=theme.DANGER if findings else theme.MUTED).pack(fill="x", padx=16)

    def accept():
        if not messagebox.askokcancel(tr("Import module"), tr("The module {n} was written by an AI. It is program code and runs with all rights of this program: it can read, "
                                                           "change and send your files and data. Read the code first and add it only if you understand it.\n\nAdd it?", n=name), icon="warning"):
            return
        try:
            module_history.apply_code(name, new_code, builtin=module_import.builtin_names())
        except (module_import.ImportErrorJOPML, OSError) as exc:
            code = "E-MOD-008" if isinstance(exc, module_import.ImportErrorJOPML) else "E-APP-005"
            app.show_error(tr("Import module"), str(exc), code, top)
            if on_done:
                on_done(str(exc), False)
            return
        top.destroy()
        if on_done:
            on_done(tr("Module {n} saved. The launcher restarts now …", n=name), True)
        parent.after(1500, lambda: app.restart(ask=False))
    br = ctk.CTkFrame(top, fg_color="transparent")
    br.pack(pady=10)
    ctk.CTkButton(br, text="✔  " + tr("Accept change"), width=170, command=accept).pack(side="left", padx=6)
    ctk.CTkButton(br, text=tr("Cancel"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=top.destroy).pack(side="left", padx=6)
    return top


def show_history(app, parent, name: str, on_done=None):
    """Stände eines Moduls: auswählen, Unterschied zum aktuellen Stand sehen, wiederherstellen."""
    versions = module_history.list_versions(name)
    if not versions:
        messagebox.showinfo(tr("History"), tr("There are no older versions of {n} yet. Versions are saved when the AI changes a module or when you replace it.", n=name))
        return None
    top = ctk.CTkToplevel(parent, fg_color=theme.c("main"))
    top.title(tr("History"))
    top.geometry("820x560")
    top.transient(parent.winfo_toplevel())
    ctk.CTkLabel(top, text=tr("Older versions of {n}", n=name), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
    labels = {f"{when}  ({fn})": fn for fn, when in versions}
    pick = ctk.CTkOptionMenu(top, values=list(labels), width=360)
    pick.pack(anchor="w", padx=16)
    box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="none")
    box.pack(fill="both", expand=True, padx=16, pady=8)

    def show(_v=None):
        old = module_history.read_version(name, labels[pick.get()]) or ""
        cur = module_history.current_code(name) or ""
        _fill_diff(box, module_history.diff(cur, old) or [tr("Same as the current version.")])
    pick.configure(command=show)
    show()

    def restore():
        fn = labels[pick.get()]
        if not messagebox.askyesno(tr("History"), tr("Go back to this version? The current one is saved first, so you can undo this too.")):
            return
        try:
            module_history.restore(name, fn, builtin=module_import.builtin_names())
        except (module_import.ImportErrorJOPML, OSError) as exc:
            app.show_error(tr("History"), str(exc), "E-MOD-008", top)
            return
        top.destroy()
        if on_done:
            on_done(tr("Module {n} restored. The launcher restarts now …", n=name), True)
        parent.after(1500, lambda: app.restart(ask=False))
    br = ctk.CTkFrame(top, fg_color="transparent")
    br.pack(pady=10)
    ctk.CTkButton(br, text="↩  " + tr("Go back to this version"), width=220, command=restore).pack(side="left", padx=6)
    ctk.CTkButton(br, text=tr("Close"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=top.destroy).pack(side="left", padx=6)
    return top
