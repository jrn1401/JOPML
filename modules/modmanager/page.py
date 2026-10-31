"""Seite "Modules": Liste aller hinzugefügten Module und Lua-Skripte, Hinzufügen und Entfernen."""
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import module_import, module_review, theme, ui
from core.i18n import tr


def _size_text(root: Path) -> str:
    files = [p for p in root.rglob("*") if p.is_file()] if root.is_dir() else []
    total = sum(p.stat().st_size for p in files)
    return tr("{n} files, {k} KB", n=len(files), k=max(1, round(total / 1024)))


class ModulesPage(ctk.CTkFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color="transparent")
        self.plugin = plugin
        self.selected = None            # ("mod", name) oder ("lua", name)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="🧩  " + tr("Modules"), font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=24, pady=(18, 0))
        ui.muted(self, "Add your own modules (folder, .zip, .py file or pasted code) and Lua scripts. Every added module is listed here; select one to see details or remove it. "
                       "A module is program code and runs with all rights of this program: add only modules from sources you trust. "
                       "Added modules are loaded at the next start and stay when the program is updated.").grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=24)
        for text, cmd in (("Add file …", self._pick_file), ("Add folder …", self._pick_folder), ("Add from code …", self._code_dialog), ("Add Lua script …", lambda: self._add_lua())):
            ctk.CTkButton(bar, text=tr(text), width=140, command=cmd).pack(side="left", padx=(0, 8), pady=2)
        ctk.CTkButton(bar, text="📋  " + tr("View module requirements"), width=220, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=self._requirements).pack(side="left", padx=(8, 0), pady=2)
        self.msg = ctk.CTkLabel(self, text="", anchor="w", wraplength=700, justify="left")
        self.msg.grid(row=4, column=0, sticky="ew", padx=24)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", padx=24, pady=8)
        body.grid_columnconfigure(0, weight=1, uniform="m")
        body.grid_columnconfigure(1, weight=1, uniform="m")
        body.grid_rowconfigure(0, weight=1)
        self.listing = ctk.CTkScrollableFrame(body, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        self.listing.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.detail = ctk.CTkScrollableFrame(body, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.render()

    # ---- Anzeige
    def _say(self, text, ok=True):
        if self.msg.winfo_exists():
            self.msg.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def render(self):
        for w in self.listing.winfo_children():
            w.destroy()
        loaded = self.plugin.user_plugins()
        failed = self.plugin.failed()
        mods = module_import.installed()
        ctk.CTkLabel(self.listing, text=tr("Added modules ({n})", n=len(mods)), anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=8, pady=(6, 2))
        if not mods:
            ui.muted(self.listing, "No modules added yet. Use the buttons above.", wrap=300).pack(fill="x", padx=8, pady=4)
        for name in mods:
            if name in failed:
                state, color = tr("error"), theme.DANGER
            elif name in loaded:
                state, color = tr("active"), theme.OK
            else:
                state, color = tr("loads at next start"), theme.MUTED if hasattr(theme, "MUTED") else "gray60"
            self._row(("mod", name), name, state, color)
        luas = module_import.lua_scripts()
        ctk.CTkLabel(self.listing, text=tr("Lua scripts ({n})", n=len(luas)), anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=8, pady=(12, 2))
        if not luas:
            ui.muted(self.listing, "No Lua scripts yet.", wrap=300).pack(fill="x", padx=8, pady=4)
        for name in luas:
            self._row(("lua", name), name, ".lua", "gray60")
        self.render_detail()

    def _row(self, key, name, state, color):
        sel = self.selected == key
        row = ctk.CTkFrame(self.listing, fg_color=theme.c("hover") if sel else theme.c("inset"), corner_radius=8, cursor="hand2")
        row.pack(fill="x", pady=2, padx=4)
        lab = ctk.CTkLabel(row, text=name, anchor="w")
        lab.pack(side="left", padx=10, pady=6)
        st = ctk.CTkLabel(row, text=state, text_color=color, anchor="e")
        st.pack(side="right", padx=10)
        for w in (row, lab, st):
            w.bind("<Button-1>", lambda _e, k=key: self._select(k))

    def _select(self, key):
        self.selected = key
        self.render()

    def render_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        if not self.selected:
            ui.muted(self.detail, "Select a module or script in the list to see details.", wrap=300).pack(fill="x", padx=10, pady=10)
            return
        kind, name = self.selected
        ctk.CTkLabel(self.detail, text=name, anchor="w", font=ctk.CTkFont(size=16, weight="bold")).pack(fill="x", padx=10, pady=(10, 4))
        lines = []
        if kind == "mod":
            root = module_import.user_dir() / name
            if not root.is_dir():
                self.selected = None
                return self.render_detail()
            lines.append(_size_text(root))
            p = self.plugin.user_plugins().get(name)
            err = self.plugin.failed().get(name)
            if p is not None:
                lines += [f"{tr('Name')}: {p.name}", f"{tr('Version')}: {getattr(p, 'version', '')}", str(getattr(p, "description", "") or "")]
            elif err:
                lines.append(tr("It could not be loaded:") + "\n" + err)
            else:
                lines.append(tr("Not loaded yet. Restart the launcher to use it."))
        else:
            try:
                text = module_import.read_lua(name)
                lines.append(tr("{n} lines, {k} KB", n=text.count("\n") + 1, k=max(1, round(len(text.encode()) / 1024))))
                lines.append(tr("Start it in the menu item 'Lua scripts'."))
            except module_import.ImportErrorJOPML as exc:
                lines.append(str(exc))
        for ln in lines:
            if ln:
                ctk.CTkLabel(self.detail, text=ln, anchor="w", justify="left", wraplength=300).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(self.detail, text=tr("Remove"), width=120, fg_color=theme.DANGER, command=self._remove).pack(anchor="w", padx=10, pady=(12, 4))
        if kind == "mod":
            ctk.CTkButton(self.detail, text="🤖  " + tr("Fix with AI"), width=160, command=lambda n=name: self._fix_with_ai(n)).pack(anchor="w", padx=10, pady=4)
            ctk.CTkButton(self.detail, text="↩  " + tr("History"), width=160, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda n=name: module_review.show_history(self.plugin.app, self, n, self._say)).pack(anchor="w", padx=10, pady=4)
            ctk.CTkButton(self.detail, text=tr("Restart launcher"), width=160, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=self.plugin.app.restart).pack(anchor="w", padx=10, pady=4)

    def _fix_with_ai(self, name):
        """Springt in den KI-Chat mit diesem Modul als Projekt (Vorlage 'Fix a module'); der Fehlertext des Moduls wird mitgegeben."""
        app = self.plugin.app
        if "aichat" not in app.plugin_by_id:
            self._say(tr("The AI chat is switched off."), False)
            return
        app.show("aichat")
        page = app.pages.get("aichat")
        if page is not None and hasattr(page, "open_fix"):
            page.open_fix(name, self.plugin.failed().get(name, "")[:600])

    def _remove(self):
        if not self.selected:
            return
        kind, name = self.selected
        if kind == "mod":
            if not messagebox.askyesno(tr("Remove module"), tr("Remove the module {n}? It disappears at the next start.", n=name)):
                return
            module_import.remove_module(name)
            self._say(tr("Module removed. The launcher restarts now …"))
            self._auto_restart()
        else:
            if not messagebox.askyesno(tr("Remove script"), tr("Remove the script {n}?", n=name)):
                return
            module_import.remove_lua(name)
            self._say(tr("Script removed."))
        self.selected = None
        self.render()

    def _fail(self, text, code=None):
        """Importfehler: mit Fehlercode anzeigen, automatisch melden (zusammengefasst auf dem Server) und "Ask AI" anbieten."""
        from core import errors
        code = code or errors.classify(text, "E-MOD-007")
        self.plugin.app.record_error(code, text, "module-import")
        self._say(errors.tag(text, code), False)
        try:
            from core import error_dialog
            error_dialog.show_error(self.plugin.app, tr("Import module"), text, code, self.winfo_toplevel(), auto_report=False)
        except Exception:
            pass

    def _auto_restart(self):
        """Nach Hinzufügen/Entfernen eines Moduls startet der Launcher selbst neu (Anmeldung bleibt)."""
        self.after(1500, lambda: self.plugin.app.restart(ask=False))

    # ---- Hinzufügen
    def _run_import(self, name, action, findings=None):
        """Name prüfen, ggf. Ersetzen und die Sicherheitswarnung bestätigen lassen, dann importieren."""
        builtin = module_import.builtin_names()
        try:
            module_import.check_name(name, builtin)
            replace = False
            if name in module_import.installed():
                if not messagebox.askyesno(tr("Import module"), tr("A module named {n} is already imported. Replace it?", n=name)):
                    return False
                replace = True
            if not messagebox.askokcancel(
                    tr("Import module"),
                    tr("The module {n} is program code. It runs with all rights of this program and can read, change and send your files and data. "
                       "Import it only if you trust the source and understand the code.\n\nImport it?", n=name)
                    + ("\n\n" + tr("The automatic check found:") + "\n• " + "\n• ".join(tr(f) for f in findings) if findings else
                       "\n\n" + tr("The automatic check found nothing unusual (this is no guarantee).")),
                    icon="warning"):
                return False
            action(replace, builtin)
        except module_import.ImportErrorJOPML as exc:
            self._fail(str(exc))
            return False
        except OSError as exc:
            self._fail(f"{type(exc).__name__}: {exc}", "E-APP-005")
            return False
        self._say(tr("Module {n} imported. The launcher restarts now …", n=name))
        self.selected = ("mod", name)
        self.render()
        self._auto_restart()
        return True

    def _do_import(self, path):
        p = Path(path)
        name = module_import.clean_name(p.name if p.is_dir() else p.stem)
        self._run_import(name, lambda replace, builtin: module_import.import_module_files(p, name, replace=replace, builtin=builtin),
                         module_import.scan_path(p))

    def _pick_file(self):
        path = filedialog.askopenfilename(filetypes=[(tr("Modules"), "*.zip *.py *.lua")])
        if not path:
            return
        if path.lower().endswith(".lua"):
            self._add_lua(path)
        else:
            self._do_import(path)

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            self._do_import(path)

    def _add_lua(self, path=None):
        path = path or filedialog.askopenfilename(filetypes=[(tr("Lua scripts"), "*.lua *.txt")])
        if not path:
            return
        try:
            text = module_import.read_lua_file(path)
            name = module_import.clean_name(path)
            replace = name in module_import.lua_scripts()
            if replace and not messagebox.askyesno(tr("Add script"), tr("A script named {n} already exists. Replace it?", n=name)):
                return
            module_import.import_lua_script(text, name, replace=replace)
        except (module_import.ImportErrorJOPML, OSError) as exc:
            self._say(str(exc), False)
            return
        self._say(tr("Script {n} added. Start it in the menu item 'Lua scripts'.", n=name))
        self.selected = ("lua", name)
        self.render()

    def _requirements(self):
        from core import doc_viewer, i18n, requirements_doc as rd
        lang = "de" if i18n.get_language() == "de" else "en"
        doc_viewer.show(self, tr("Module requirements"), lambda: rd.modules_text(lang), "jopml-module-requirements.txt")

    def _code_dialog(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Add a module from code"))
        top.geometry("720x560")
        top.transient(self.winfo_toplevel())
        ui.muted(top, "Paste the code of a module (the content of its plugin.py). It needs a class named Plugin.").pack(fill="x", padx=16, pady=(14, 6))
        nr = ctk.CTkFrame(top, fg_color="transparent")
        nr.pack(fill="x", padx=16)
        ctk.CTkLabel(nr, text=tr("Module name"), anchor="w").pack(side="left", padx=(0, 8))
        name_e = ctk.CTkEntry(nr, width=220, placeholder_text="mein_modul")
        name_e.pack(side="left")
        box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="none")
        box.pack(fill="both", expand=True, padx=16, pady=8)
        err = ctk.CTkLabel(top, text="", anchor="w", wraplength=660, justify="left")
        err.pack(fill="x", padx=16)

        def example():
            box.delete("1.0", "end")
            box.insert("1.0", module_import.TEMPLATE)
            if not name_e.get().strip():
                name_e.insert(0, "mein_modul")

        def save():
            name = name_e.get().strip()
            code = box.get("1.0", "end")
            self._say("")
            if self._run_import(name, lambda replace, builtin: module_import.import_module_code(code, name, replace=replace, builtin=builtin), module_import.scan_code(code)):
                top.destroy()
            else:
                err.configure(text=self.msg.cget("text"), text_color=theme.DANGER)
        br = ctk.CTkFrame(top, fg_color="transparent")
        br.pack(pady=10)
        ctk.CTkButton(br, text=tr("Insert example"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT, command=example).pack(side="left", padx=6)
        ctk.CTkButton(br, text=tr("Import"), width=150, command=save).pack(side="left", padx=6)
