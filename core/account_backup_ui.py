"""Oberfläche für das Wiederherstellen eines Konto-Backups (.jopmacc). Gemeinsam für Einstellungen und Anmeldung."""
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import account_backup, theme
from core.i18n import tr


def restore_account_file(store, label=None) -> bool:
    """Backup-Datei wählen, Passphrase abfragen, Konto wiederherstellen. True bei Erfolg. Meldungen im Label (oder als Fenster)."""
    def say(text, ok=True):
        if label is not None and label.winfo_exists():
            label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)
        elif ok:
            messagebox.showinfo(tr("Account backup"), text)
        else:
            messagebox.showerror(tr("Account backup"), text)
    path = filedialog.askopenfilename(filetypes=[("JOPML account", "*.jopmacc *.json")])
    if not path:
        return False
    phrase = ctk.CTkInputDialog(title=tr("Account backup"), text=tr("Passphrase of the backup file:")).get_input()
    if not phrase:
        return False
    try:
        text = Path(path).read_text(encoding="utf-8")
        try:
            name = account_backup.restore_account(store, text, phrase)
        except account_backup.BackupExists:
            if not messagebox.askyesno(tr("Account backup"), tr("An account with this username already exists on this computer. Replace it with the backup?")):
                return False
            name = account_backup.restore_account(store, text, phrase, overwrite=True)
    except account_backup.BackupError as exc:
        say(str(exc), False)
        return False
    except (OSError, UnicodeError):
        say(tr("This file could not be read."), False)
        return False
    say(tr("Account {n} restored. You can sign in with its password.", n=name))
    return True
