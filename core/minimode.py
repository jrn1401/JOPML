"""Mini-Modus: das Hauptfenster verschwindet, ein kleines Fenster (immer oben) zeigt, was läuft, und hat Notaus und "Zurück"."""
import tkinter as tk

from core import panic
from core.i18n import tr

BG, FG, OK, BAD = "#1f2430", "#e5e7eb", "#34d399", "#b91c1c"


def status_text(active_ids: list, names: dict | None = None) -> str:
    """'Idle' oder 'Running: Macros, Autoclicker' - rein, damit testbar."""
    if not active_ids:
        return tr("Idle – nothing is running")
    names = names or {}
    return tr("Running") + ": " + ", ".join(tr(names.get(i, i)) for i in active_ids)


class MiniWindow:
    def __init__(self, app):
        self.app = app
        self.win = None

    @property
    def open(self) -> bool:
        return self.win is not None

    def show(self):
        if self.win is not None:
            return
        app = self.app
        w = tk.Toplevel(app)
        self.win = w
        w.title("JOPML")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        try:
            w.overrideredirect(False)
        except Exception:
            pass
        self.dot = tk.Label(w, text="●", fg=OK, bg=BG, font=("Segoe UI", 14))
        self.dot.grid(row=0, column=0, padx=(10, 4), pady=8)
        self.label = tk.Label(w, text="", fg=FG, bg=BG, font=("Segoe UI", 10), anchor="w", width=26)
        self.label.grid(row=0, column=1, pady=8)
        tk.Button(w, text="■ " + tr("Stop"), bg=BAD, fg="white", relief="flat", command=app.panic).grid(row=0, column=2, padx=4)
        tk.Button(w, text="⤢", bg="#374151", fg="white", relief="flat", width=3, command=self.hide_and_restore).grid(row=0, column=3, padx=(0, 10))
        pos = (app.settings.get("mini_pos") or [])
        if isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos):
            w.geometry(f"+{pos[0]}+{pos[1]}")
        w.protocol("WM_DELETE_WINDOW", self.hide_and_restore)
        app.withdraw()
        self._tick()

    def _tick(self):
        if self.win is None:
            return
        try:
            ids = panic.active(self.app)
            names = {p.id: p.name for p in getattr(self.app, "plugins", [])}
            self.label.configure(text=status_text(ids, names))
            self.dot.configure(fg=OK if ids else "#6b7280")
            self.win.after(500, self._tick)
        except tk.TclError:
            self.win = None

    def hide_and_restore(self):
        w, self.win = self.win, None
        if w is not None:
            try:
                self.app.settings["mini_pos"] = [int(w.winfo_x()), int(w.winfo_y())]
                self.app.save_settings()
            except Exception:
                pass
            try:
                w.destroy()
            except Exception:
                pass
        self.app.deiconify()
        try:
            self.app.lift()
        except Exception:
            pass
