"""Seite "Recoil Arena": Spiel herunterladen, starten, aktualisieren."""
import threading
from tkinter import filedialog

import customtkinter as ctk

from core import theme, ui
from core.i18n import tr

from . import plugin as P


class ArenaPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self._busy = False
        ui.page_title(self, "Recoil Arena", "A separate practice game: look around, move, shoot bots and learn to control recoil.").pack(anchor="w", padx=24, pady=(20, 8))
        c = ui.card(self, "Recoil trainer game")
        c.pack(fill="x", padx=24, pady=6)
        ui.muted(c, "The game opens as its own program in a full-screen window. You walk through a textured map, look around with the mouse and shoot rounded bots that walk around. "
                    "Choose a play style: 'Tactical' and 'Precision' punish moving while shooting (stand still to shoot), 'Arcade' lets you run and gun. "
                    "Five invented weapons have their own recoil. Afterwards you see accuracy, headshots, how often you stood still and your spray error.",
                 wrap=620).pack(fill="x", padx=16, pady=(0, 6))
        ui.muted(c, "All weapons and styles are invented. They do not copy real games or their recoil patterns. The game reads mouse and keyboard only in its own window "
                    "and sends nothing to other programs or games.", wrap=620).pack(fill="x", padx=16, pady=(0, 10))
        self.status = ctk.CTkLabel(c, text="", anchor="w", wraplength=620, justify="left", font=ctk.CTkFont(size=13, weight="bold"))
        self.status.pack(fill="x", padx=16, pady=(0, 6))
        row = ui.row(c)
        row.pack(fill="x", padx=16, pady=(0, 6))
        self.btn_start = ctk.CTkButton(row, text="▶  " + tr("Start game"), width=170, height=40, font=ctk.CTkFont(size=14, weight="bold"), command=self.start)
        self.btn_start.pack(side="left")
        self.btn_dl = ctk.CTkButton(row, text="⬇  " + tr("Download recoil trainer game"), width=260, height=40, command=self.download)
        self.btn_dl.pack(side="left", padx=8)
        self.bar = ctk.CTkProgressBar(c, width=420)
        self.bar.set(0)
        self.msg = ctk.CTkLabel(c, text="", anchor="w", wraplength=620, justify="left")
        self.msg.pack(fill="x", padx=16, pady=(0, 10))
        adv = ui.card(self, "More")
        adv.pack(fill="x", padx=24, pady=6)
        r2 = ui.row(adv)
        r2.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(r2, text=tr("Install Arena ZIP …"), width=170, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.install).pack(side="left")
        ctk.CTkButton(r2, text=tr("Save Arena as ZIP …"), width=170, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.export).pack(side="left", padx=8)
        self.btn_np = ctk.CTkButton(r2, text=tr("Install graphics component (numpy)"), width=250, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.get_numpy)
        ui.muted(adv, "The textured graphics need the free Python package numpy. Without it the game still runs with simple graphics.", wrap=620).pack(fill="x", padx=16, pady=(0, 10))
        self.refresh()

    def refresh(self):
        f = P.find_install()
        if f is None:
            self.status.configure(text=tr("Not installed yet. Press Download."), text_color=theme.MUTED)
        else:
            v = P.bundled_version() if f[0] == "builtin" else P.installed_version()
            self.status.configure(text=(tr("Built into the launcher") if f[0] == "builtin" else tr("Installed")) + (f" · v{v}" if v else ""), text_color=theme.OK)
        self.btn_start.configure(state="normal" if f else "disabled")
        self.btn_dl.configure(text="⬇  " + (tr("Update recoil trainer game") if f else tr("Download recoil trainer game")))

    def _say(self, text, ok=True):
        self.msg.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    # ---- Aktionen
    def start(self):
        err = self.plugin.launch()
        self._say(err or tr("The game is starting in its own window."), not err)

    def download(self):
        if self._busy:
            return
        self._busy = True
        self.btn_dl.configure(state="disabled")
        self.bar.pack(padx=16, pady=(0, 6), before=self.msg)
        self.bar.set(0)
        self._say(tr("Downloading …"), True)

        def work():
            try:
                text, ok = self.plugin.download_game(lambda p: self.app.call_soon(self.bar.set, p)), True
            except Exception as exc:
                text, ok = str(exc), False
            self.app.call_soon(self._downloaded, text, ok)
        threading.Thread(target=work, daemon=True).start()

    def _downloaded(self, text, ok):
        self._busy = False
        if not self.winfo_exists():
            return
        self.bar.pack_forget()
        self.btn_dl.configure(state="normal")
        self._say(text, ok)
        self.refresh()
        if ok and not P.numpy_ready():
            self.btn_np.pack(side="left", padx=8)
            self._say(text + "  " + tr("For textured graphics install the graphics component below."), True)

    def get_numpy(self):
        self._say(tr("Installing … this can take a minute."), True)

        def work():
            err = self.plugin.install_numpy()
            self.app.call_soon(self._say, err or tr("Graphics component installed."), not err)
        threading.Thread(target=work, daemon=True).start()

    def install(self):
        path = filedialog.askopenfilename(title=tr("Install Arena ZIP …"), filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        try:
            n = self.plugin.install(path)
        except Exception as exc:
            self._say(str(exc), False)
            return
        self._say(tr("Installed ({n} files).", n=n))
        self.refresh()

    def export(self):
        path = filedialog.asksaveasfilename(title=tr("Save Arena as ZIP …"), defaultextension=".zip", initialfile="jopml-arena.zip", filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        try:
            n = self.plugin.export_zip(path)
        except (ValueError, OSError) as exc:
            self._say(str(exc), False)
            return
        self._say(tr("Saved ({n} files).", n=n))
