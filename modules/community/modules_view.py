"""Reiter "Modules": Module anderer ansehen und installieren, eigene Module teilen, melden; Admins geben neue Module frei."""
from tkinter import messagebox

import customtkinter as ctk

from core import module_import, theme
from core.i18n import tr

from . import dialogs
from .modshare import ModShareService, collect_installed, risk_notes

STATUS_TEXT = {"pending": "Waiting for review", "approved": "Shared", "rejected": "Rejected"}


class ModulesView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.app = page, page.app
        self.mods = ModShareService(page.svc)
        self.review_mode = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.q = ctk.CTkEntry(bar, width=220, placeholder_text=tr("Search …"))
        self.q.pack(side="left")
        self.q.bind("<Return>", lambda _e: self.reload())
        ctk.CTkButton(bar, text=tr("Search"), width=80, command=self.reload).pack(side="left", padx=8)
        ctk.CTkButton(bar, text="+ " + tr("Share a module"), width=150, command=self.share).pack(side="right")
        if self._is_admin():
            self.review_btn = ctk.CTkButton(bar, text=tr("Review queue"), width=130, fg_color="gray35", hover_color="gray25", command=self.toggle_review)
            self.review_btn.pack(side="right", padx=8)
        self.list = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        self.list.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 12))
        self.note = ctk.CTkLabel(self, text="", anchor="w", wraplength=700, justify="left")
        self.note.grid(row=2, column=0, sticky="ew", padx=24)

    def _is_admin(self) -> bool:
        return bool((self.page.svc.me or {}).get("is_admin"))

    def on_show(self):
        self.reload()

    def say(self, text, ok=True):
        self.note.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def toggle_review(self):
        self.review_mode = not self.review_mode
        self.review_btn.configure(text=tr("Back to all modules") if self.review_mode else tr("Review queue"))
        self.reload()

    def reload(self):
        if self.review_mode:
            self.page.run(self.mods.pending, self._render, lambda e: self.say(e, False))
        else:
            q = self.q.get().strip()
            self.page.run(lambda: self.mods.browse(q), self._render, lambda e: self.say(e, False))

    def _render(self, rows):
        for w in self.list.winfo_children():
            w.destroy()
        if not rows:
            text = tr("Nothing is waiting for review.") if self.review_mode else tr("No modules here yet. Be the first to share one!")
            ctk.CTkLabel(self.list, text=text, text_color=theme.MUTED).pack(pady=20)
        for r in rows:
            f = ctk.CTkFrame(self.list, fg_color=theme.c("inset"), corner_radius=8)
            f.pack(fill="x", padx=6, pady=4)
            head = ctk.CTkFrame(f, fg_color="transparent")
            head.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(head, text=r["title"], font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(head, text=f"   v{r.get('version', '1.0.0')}   ⬇ {r.get('downloads', 0)}   @{r.get('author') or '?'}   {r.get('size', 0) // 1024 + 1} KB",
                         text_color=theme.MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
            status = r.get("status", "approved")
            if r.get("hidden"):
                ctk.CTkLabel(head, text="  ⚑ " + tr("Hidden after reports"), text_color=theme.DANGER).pack(side="left")
            elif status != "approved":
                ctk.CTkLabel(head, text="  " + tr(STATUS_TEXT.get(status, status)), text_color=theme.DANGER if status == "rejected" else theme.MUTED).pack(side="left")
            if r.get("descr"):
                ctk.CTkLabel(f, text=r["descr"], anchor="w", justify="left", wraplength=640, text_color=theme.MUTED).pack(fill="x", padx=10)
            if r.get("note") and r.get("mine"):
                ctk.CTkLabel(f, text=tr("Note from the reviewer: {n}", n=r["note"]), anchor="w", justify="left", wraplength=640,
                             text_color=theme.MUTED).pack(fill="x", padx=10)
            btns = ctk.CTkFrame(f, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(4, 8))
            ctk.CTkButton(btns, text=tr("View code & install"), width=150, height=26, command=lambda i=r["id"]: self.open_module(i)).pack(side="left")
            if self.review_mode:
                ctk.CTkButton(btns, text=tr("Approve"), width=90, height=26, command=lambda i=r["id"]: self.review(i, True)).pack(side="left", padx=6)
                ctk.CTkButton(btns, text=tr("Reject"), width=90, height=26, fg_color="#b91c1c", hover_color="#991b1b",
                              command=lambda i=r["id"]: self.review(i, False)).pack(side="left")
            elif r.get("mine") or self._is_admin():
                ctk.CTkButton(btns, text="🗑", width=34, height=26, fg_color="gray35", hover_color="gray25",
                              command=lambda i=r["id"]: self.delete(i)).pack(side="left", padx=6)

    def delete(self, mid):
        if dialogs.confirm("Delete module", "Remove this module from the community list?"):
            self.page.run(lambda: self.mods.delete(mid), lambda _: self.reload(), lambda e: self.say(e, False))

    def review(self, mid, approve):
        def done(note=""):
            self.page.run(lambda: self.mods.review(mid, approve, note or ""), lambda _: (self.say(tr("Saved.")), self.reload()), lambda e: self.say(e, False))
        if approve:
            if not messagebox.askyesno(tr("Approve module"), tr("Did you read the whole code? Approved modules become visible to everyone.")):
                return
            done()
        else:
            dialogs.ask_text(self, "Reject module", "Short reason for the author (optional)", "Reject", done)

    # ---------------------------------------------------------------- Ansehen / Installieren
    def open_module(self, mid):
        self.page.run(lambda: self.mods.get(mid), self._show, lambda e: self.say(e, False))

    def _show(self, d):
        files = d["files"]
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(d["title"])
        top.geometry("720x680")
        top.after(120, top.lift)
        ctk.CTkLabel(top, text=f"{d['title']}  ·  v{d.get('version', '1.0.0')}  ·  @{d.get('author') or '?'}",
                     font=ctk.CTkFont(size=17, weight="bold"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        if d.get("descr"):
            ctk.CTkLabel(top, text=d["descr"], anchor="w", justify="left", wraplength=680, text_color=theme.MUTED).pack(fill="x", padx=16)
        names = sorted(files, key=lambda n: (n != "plugin.py", n))
        box = ctk.CTkTextbox(top, height=300, font=ctk.CTkFont(family="Consolas", size=12), fg_color=theme.c("inset"), wrap="none")

        def show_file(n):
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", files[n])
            box.configure(state="disabled")
        pick = ctk.CTkOptionMenu(top, values=names, width=260, command=show_file)
        pick.pack(anchor="w", padx=16, pady=(8, 4))
        box.pack(fill="x", padx=16)
        show_file(names[0])
        notes = risk_notes(files)
        ctk.CTkLabel(top, text=tr("Conspicuous places in the code:") + "\n" + ("\n".join("• " + n for n in notes) if notes else "• " + tr("Nothing conspicuous found (this is no guarantee).")),
                     anchor="w", justify="left", wraplength=680, text_color=theme.DANGER if notes else theme.TEXT).pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(top, text=tr("A module is program code. After installing it runs with all rights of this program and of your account and can read, change and send "
                                  "your files and data. It was written by another user. Approval by an admin is not a security guarantee. Install it only if you read the "
                                  "code above and understand it."),
                     text_color=theme.MUTED, anchor="w", justify="left", wraplength=680).pack(fill="x", padx=16, pady=6)
        r = ctk.CTkFrame(top, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)

        def do_install():
            name = d["name"]
            builtin = module_import.builtin_names()
            try:
                module_import.check_name(name, builtin)
                replace = False
                if name in module_import.installed():
                    if not messagebox.askyesno(tr("Install module"), tr("A module named {n} is already imported. Replace it?", n=name)):
                        return
                    replace = True
                if not messagebox.askokcancel(tr("Install module"), tr("Install the module {n}? It runs with all rights of this program.", n=name), icon="warning"):
                    return
                from .modshare import install
                install(files, name, replace=replace, builtin=builtin)
            except module_import.ImportErrorJOPML as exc:
                self.say(str(exc), False)
                return
            except OSError as exc:
                self.say(f"{type(exc).__name__}: {exc}", False)
                return
            self.say(tr("Module {n} imported. Restart the program to use it.", n=name))
            top.destroy()
        if d.get("status") == "approved" or self._is_admin():
            ctk.CTkButton(r, text=tr("Install"), width=110, command=do_install).pack(side="left")
        ctk.CTkButton(r, text="⚑ " + tr("Report"), width=90, fg_color="gray35", hover_color="gray25",
                      command=lambda: dialogs.ask_text(top, "Report module", "Why do you report this module?", "Report", lambda reason: self.page.run(
                          lambda: self.mods.report(d["id"], reason or "-"), lambda _: self.say(tr("Thank you. The report was sent.")),
                          lambda e: self.say(e, False)))).pack(side="left", padx=8)

    # ---------------------------------------------------------------- Teilen
    def share(self):
        installed = module_import.installed()
        if not installed:
            dialogs.info("Share a module", "You have no imported modules yet. Add one in Settings > System > Import modules first.")
            return
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Share a module"))
        top.geometry("560x600")
        top.after(120, top.lift)
        ctk.CTkLabel(top, text=tr("Module (from Settings > System > Import modules)"), anchor="w").pack(fill="x", padx=16, pady=(14, 0))
        pick = ctk.CTkOptionMenu(top, values=installed, width=260)
        pick.pack(anchor="w", padx=16)
        ctk.CTkLabel(top, text=tr("Title"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        title = ctk.CTkEntry(top)
        title.pack(fill="x", padx=16)
        ctk.CTkLabel(top, text=tr("Description"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        descr = ctk.CTkEntry(top)
        descr.pack(fill="x", padx=16)
        ctk.CTkLabel(top, text=tr("Version"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        version = ctk.CTkEntry(top, width=100)
        version.insert(0, "1.0.0")
        version.pack(anchor="w", padx=16)
        info = ctk.CTkLabel(top, text=tr("Only the module's text files are uploaded (.py .json .txt .md .csv, at most 300 KB). Never share code that contains passwords, keys or "
                                         "personal data. Only share what you wrote yourself or what you are allowed to pass on (respect licences)."),
                            text_color=theme.MUTED, anchor="w", justify="left", wraplength=520)
        info.pack(fill="x", padx=16, pady=10)
        msg = ctk.CTkLabel(top, text="", wraplength=520, justify="left", anchor="w")
        msg.pack(fill="x", padx=16)

        def go():
            name = pick.get()
            try:
                files = collect_installed(name)
            except Exception as exc:
                msg.configure(text=str(exc), text_color=theme.DANGER)
                return
            if not messagebox.askyesno(tr("Share a module"), tr("Everyone in the community will be able to read and install this module after an admin approved it "
                                                                "(admins' own modules are visible at once). Continue?")):
                return
            self.page.run(lambda: self.mods.publish(name, title.get(), descr.get(), files, version.get().strip()),
                          lambda res: (top.destroy(), self.say(tr("Shared. Thank you!") if res.get("status") == "approved"
                                                               else tr("Sent. An admin has to approve it before others see it.")), self.reload()),
                          lambda e: msg.configure(text=e, text_color=theme.DANGER))
        ctk.CTkButton(top, text=tr("Share"), width=120, command=go).pack(anchor="w", padx=16, pady=8)
