"""Reiter "Marktplatz": Makros anderer ansehen, importieren, bewerten, melden und eigene teilen."""
import customtkinter as ctk

from core import theme
from core.i18n import tr
from modules.macros import dsl

from . import dialogs
from .market import MarketService, analyze, check_for_publish

SORTS = {"New": "new", "Top rated": "top", "Most downloaded": "popular"}


class MarketView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.app = page, page.app
        self.market = MarketService(page.svc)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.q = ctk.CTkEntry(bar, width=220, placeholder_text=tr("Search …"))
        self.q.pack(side="left")
        self.q.bind("<Return>", lambda _e: self.reload())
        self.sort = ctk.CTkOptionMenu(bar, values=[tr(k) for k in SORTS], width=150, command=lambda _v: self.reload())
        self.sort.pack(side="left", padx=8)
        ctk.CTkButton(bar, text=tr("Search"), width=80, command=self.reload).pack(side="left")
        ctk.CTkButton(bar, text="+ " + tr("Share a macro"), width=150, command=self.share).pack(side="right")
        self.list = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        self.list.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 12))
        self.note = ctk.CTkLabel(self, text="", anchor="w", wraplength=700, justify="left")
        self.note.grid(row=2, column=0, sticky="ew", padx=24)

    def on_show(self):
        self.reload()

    def say(self, text, ok=True):
        self.note.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def reload(self):
        sort = next((v for k, v in SORTS.items() if tr(k) == self.sort.get()), "new")
        q = self.q.get().strip()
        self.page.run(lambda: self.market.browse(q, sort), self._render, lambda e: self.say(e, False))

    def _render(self, rows):
        for w in self.list.winfo_children():
            w.destroy()
        if not rows:
            ctk.CTkLabel(self.list, text=tr("No macros here yet. Be the first to share one!"), text_color=theme.MUTED).pack(pady=20)
        for r in rows:
            f = ctk.CTkFrame(self.list, fg_color=theme.c("inset"), corner_radius=8)
            f.pack(fill="x", padx=6, pady=4)
            head = ctk.CTkFrame(f, fg_color="transparent")
            head.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(head, text=r["title"], font=ctk.CTkFont(weight="bold")).pack(side="left")
            stars = f"★ {r['stars']:g} ({r['votes']})" if r["votes"] else "☆ –"
            ctk.CTkLabel(head, text=f"   {stars}   ⬇ {r['downloads']}   @{r.get('author') or '?'}", text_color=theme.MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left")
            if r.get("descr"):
                ctk.CTkLabel(f, text=r["descr"], anchor="w", justify="left", wraplength=640, text_color=theme.MUTED).pack(fill="x", padx=10)
            btns = ctk.CTkFrame(f, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(4, 8))
            ctk.CTkButton(btns, text=tr("View & import"), width=120, height=26, command=lambda i=r["id"]: self.open_macro(i)).pack(side="left")
            if r["mine"] or (self.page.svc.me or {}).get("is_admin"):
                ctk.CTkButton(btns, text="🗑", width=34, height=26, fg_color="gray35", hover_color="gray25",
                              command=lambda i=r["id"]: self.delete(i)).pack(side="left", padx=6)

    def delete(self, mid):
        if dialogs.confirm("Delete macro", "Remove this macro from the marketplace?"):
            self.page.run(lambda: self.market.delete(mid), lambda _: self.reload(), lambda e: self.say(e, False))

    # ---------------------------------------------------------------- Ansehen / Importieren
    def open_macro(self, mid):
        self.page.run(lambda: self.market.get(mid), self._show_macro, lambda e: self.say(e, False))

    def _show_macro(self, d):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(d["title"])
        top.geometry("560x560")
        top.after(120, top.lift)
        ctk.CTkLabel(top, text=d["title"], font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        try:
            notes = analyze(d["script"])
        except dsl.MacroError:
            notes = [tr("This macro is not valid.")]
        text = ctk.CTkTextbox(top, height=240, font=ctk.CTkFont(family="Consolas", size=12), fg_color=theme.c("inset"))
        text.pack(fill="x", padx=16, pady=6)
        text.insert("1.0", d["script"])
        text.configure(state="disabled")
        ctk.CTkLabel(top, text=tr("Check before you run it:") + "\n" + ("\n".join("• " + n for n in notes) if notes else "• " + tr("Nothing unusual found.")),
                     anchor="w", justify="left", wraplength=520).pack(fill="x", padx=16)
        ctk.CTkLabel(top, text=tr("Macros only click, press keys and type text. They cannot run programs. Always test in a harmless place."),
                     text_color=theme.MUTED, anchor="w", justify="left", wraplength=520).pack(fill="x", padx=16, pady=4)
        r = ctk.CTkFrame(top, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=6)

        def do_import():
            plugin = self.app.plugin_by_id.get("macros")
            if plugin is None:
                return
            try:
                name = plugin.safe_name(d["title"])
                n, i = name, 2
                while (plugin.folder() / f"{n}.jopm").exists():
                    n, i = f"{name} {i}", i + 1
                plugin.save(n, d["script"])
                plugin.current_text = d["script"]
            except (ValueError, dsl.MacroError) as exc:
                self.say(tr(str(exc)), False)
                return
            self.say(tr("Imported as '{n}'. Open it on the Add macros page.", n=n))
            top.destroy()
        ctk.CTkButton(r, text=tr("Import"), width=100, command=do_import).pack(side="left")
        stars = ctk.CTkOptionMenu(r, values=["★" * i for i in range(1, 6)], width=100, command=lambda v: self.page.run(
            lambda: self.market.rate(d["id"], len(v)), lambda _: (self.say(tr("Thanks for rating!")), self.reload()), lambda e: self.say(e, False)))
        stars.set(tr("Rate"))
        stars.pack(side="left", padx=8)
        ctk.CTkButton(r, text="⚑ " + tr("Report"), width=90, fg_color="gray35", hover_color="gray25",
                      command=lambda: dialogs.ask_text(top, "Report macro", "Why do you report this macro?", "Report", lambda reason: self.page.run(
                          lambda: self.market.report(d["id"], reason or "-"), lambda _: self.say(tr("Thank you. The report was sent.")),
                          lambda e: self.say(e, False)))).pack(side="left")

    # ---------------------------------------------------------------- Teilen
    def share(self):
        plugin = self.app.plugin_by_id.get("macros")
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Share a macro"))
        top.geometry("540x520")
        top.after(120, top.lift)
        ctk.CTkLabel(top, text=tr("Title"), anchor="w").pack(fill="x", padx=16, pady=(14, 0))
        title = ctk.CTkEntry(top)
        title.pack(fill="x", padx=16)
        ctk.CTkLabel(top, text=tr("Description"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        descr = ctk.CTkEntry(top)
        descr.pack(fill="x", padx=16)
        ctk.CTkLabel(top, text=tr("Macro (from the Add macros editor, or choose a saved one)"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        saved = plugin.list_macros() if plugin else []
        pick = ctk.CTkOptionMenu(top, values=[tr("Current editor text")] + saved, width=240)
        pick.pack(anchor="w", padx=16)
        box = ctk.CTkTextbox(top, height=200, font=ctk.CTkFont(family="Consolas", size=12), fg_color=theme.c("inset"))
        box.pack(fill="x", padx=16, pady=8)
        box.insert("1.0", (plugin.current_text if plugin else "") or "")
        pick.configure(command=lambda v: (box.delete("1.0", "end"), box.insert("1.0", plugin.load(v) if v in saved else (plugin.current_text or ""))))
        msg = ctk.CTkLabel(top, text="", wraplength=500, justify="left", anchor="w")
        msg.pack(fill="x", padx=16)

        def go():
            script = box.get("1.0", "end").strip()
            err = check_for_publish(title.get(), descr.get(), script)
            if err:
                msg.configure(text=err, text_color=theme.DANGER)
                return
            if not dialogs.confirm("Share a macro", "Everyone in the community will be able to see and import this macro. Continue?"):
                return
            self.page.run(lambda: self.market.publish(title.get(), descr.get(), script),
                          lambda _: (top.destroy(), self.say(tr("Shared. Thank you!")), self.reload()),
                          lambda e: msg.configure(text=e, text_color=theme.DANGER))
        ctk.CTkButton(top, text=tr("Share"), width=120, command=go).pack(anchor="w", padx=16, pady=6)
