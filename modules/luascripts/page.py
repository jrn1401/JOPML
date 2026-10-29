"""Seite "Lua scripts": Liste der Skripte, Start/Stopp, Ausgabe."""
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import module_import, theme, ui
from core.i18n import tr

from .runner import lupa_available

MAX_LINES = 500


class LuaPage(ctk.CTkFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color="transparent")
        self.plugin = plugin
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="🌙  " + tr("Lua scripts"), font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=24, pady=(18, 0))
        ui.muted(self, "Run your own Lua scripts in a safe box. A script can calculate, print text, wait(ms) and run macro commands with macro(\"click left 500 300\"). "
                        "It cannot read or change files and cannot start programs. Stop button and the panic key end it at any time.").grid(
            row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=2, column=0, sticky="ew", padx=24)
        ctk.CTkButton(top, text=tr("Add script …"), width=140, command=self._add).pack(side="left")
        ctk.CTkButton(top, text=tr("Stop"), width=90, fg_color=theme.DANGER, command=self._stop).pack(side="left", padx=8)
        self.msg = ctk.CTkLabel(top, text="", anchor="w")
        self.msg.pack(side="left", padx=8)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", padx=24, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        self.listing = ctk.CTkScrollableFrame(body, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        self.listing.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.out = ctk.CTkTextbox(body, font=ctk.CTkFont(family="Consolas", size=12), wrap="word")
        self.out.grid(row=0, column=1, sticky="nsew")
        self.out.configure(state="disabled")
        if not lupa_available():
            self._say(tr("The Lua engine (lupa) is not installed in this version of the launcher."), False)
        plugin.on_line = self._line
        self.render()

    def _say(self, text, ok=True):
        if self.msg.winfo_exists():
            self.msg.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _line(self, text, ok=True):
        if not self.out.winfo_exists():
            return
        self.out.configure(state="normal")
        self.out.insert("end", ("" if ok else "! ") + str(text) + "\n")
        n = int(self.out.index("end-1c").split(".")[0])
        if n > MAX_LINES:
            self.out.delete("1.0", f"{n - MAX_LINES}.0")
        self.out.see("end")
        self.out.configure(state="disabled")

    def render(self):
        for w in self.listing.winfo_children():
            w.destroy()
        names = module_import.lua_scripts()
        if not names:
            ui.muted(self.listing, "No scripts yet. Press \"Add script …\".").pack(fill="x", padx=8, pady=8)
        for name in names:
            row = ctk.CTkFrame(self.listing, fg_color=theme.c("inset"), corner_radius=8)
            row.pack(fill="x", pady=2, padx=4)
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", padx=10, pady=6)
            ctk.CTkButton(row, text="✕", width=28, height=24, fg_color="gray35", hover_color="gray25", command=lambda n=name: self._remove(n)).pack(side="right", padx=4)
            ctk.CTkButton(row, text=tr("Start"), width=64, height=24, command=lambda n=name: self._start(n)).pack(side="right")

    def _start(self, name):
        err = self.plugin.run_script(name)
        self._say(err or "", False)

    def _stop(self):
        self.plugin.stop()

    def _remove(self, name):
        if messagebox.askyesno(tr("Remove script"), tr("Remove the script {n}?", n=name)):
            module_import.remove_lua(name)
            self.render()

    def _add(self):
        path = filedialog.askopenfilename(filetypes=[(tr("Lua scripts"), "*.lua *.txt")])
        if not path:
            return
        try:
            text = module_import.read_lua(path)
            name = module_import.clean_name(path)
            replace = False
            if name in module_import.lua_scripts():
                if not messagebox.askyesno(tr("Add script"), tr("A script named {n} already exists. Replace it?", n=name)):
                    return
                replace = True
            module_import.import_lua_script(text, name, replace=replace)
        except (module_import.ImportErrorJOPML, OSError) as exc:
            self._say(str(exc), False)
            return
        self._say(tr("Script {n} added.", n=name))
        self.render()

    def destroy(self):
        if self.plugin.on_line == self._line:
            self.plugin.on_line = None
        super().destroy()
