"""Reiter "Forum": öffentliche Foren, Themen und Antworten (nicht verschlüsselt, vom Server gefiltert)."""
import customtkinter as ctk

from core import theme
from core.i18n import tr

from . import dialogs
from .chat_view import fmt_time
from .forum import BOARDS


class ForumView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.forum, self.svc = page, page.forum, page.svc
        self.admin = bool((self.svc.me or {}).get("is_admin"))
        self.board = "general"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.bar = ctk.CTkFrame(self, fg_color="transparent")
        self.bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
        self.area.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        self._loaded = False

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            self.show_board()

    def _clear(self):
        for w in self.area.winfo_children():
            w.destroy()
        for w in self.bar.winfo_children():
            w.destroy()

    # ---------------------------------------------------------------- Themenliste
    def show_board(self, board: str | None = None):
        self.board = board or self.board
        self._clear()
        labels = {tr(v): k for k, v in BOARDS.items()}
        om = ctk.CTkOptionMenu(self.bar, values=list(labels), width=190, command=lambda lab: self.show_board(labels[lab]))
        om.set(tr(BOARDS[self.board]))
        om.pack(side="left")
        ctk.CTkButton(self.bar, text="+ " + tr("New thread"), width=130, command=self._new_thread).pack(side="left", padx=8)
        ctk.CTkButton(self.bar, text="⟳", width=34, fg_color="gray35", hover_color="gray25", command=self.show_board).pack(side="left")
        ctk.CTkLabel(self.area, text=tr("Loading …"), text_color=theme.MUTED).pack(pady=20)
        board = self.board

        def done(threads):
            if board != self.board:
                return
            for w in self.area.winfo_children():
                w.destroy()
            if not threads:
                ctk.CTkLabel(self.area, text=tr("No threads yet. Start the first one!"), text_color=theme.MUTED).pack(pady=24)
            for t in threads:
                r = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=10)
                r.pack(fill="x", padx=6, pady=3)
                mark = ("📌 " if t["pinned"] else "") + ("🔒 " if t["locked"] else "")
                ctk.CTkLabel(r, text=mark + t["title"], font=ctk.CTkFont(size=14, weight="bold"), anchor="w", wraplength=520, justify="left"
                             ).pack(anchor="w", padx=14, pady=(10, 0))
                ctk.CTkLabel(r, text=tr("{u} · {n} replies · {t}", u=t.get("author_name") or tr("[deleted]"), n=t["replies"], t=fmt_time(t["last_at"])),
                             text_color=theme.MUTED, font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w", padx=14, pady=(0, 10))
                r.bind("<Button-1>", lambda _e, i=t["id"]: self.show_thread(i))
                for child in r.winfo_children():
                    child.bind("<Button-1>", lambda _e, i=t["id"]: self.show_thread(i))
                ctk.CTkButton(r, text=tr("Open"), width=70, height=26, command=lambda i=t["id"]: self.show_thread(i)).place(relx=1.0, rely=0.5, x=-12, anchor="e")
        self.page.run(lambda: self.forum.threads(board), done)

    def _new_thread(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("New thread"))
        top.geometry("520x380")
        ctk.CTkLabel(top, text=tr("Title"), anchor="w").pack(fill="x", padx=20, pady=(16, 2))
        e = ctk.CTkEntry(top)
        e.pack(fill="x", padx=20)
        ctk.CTkLabel(top, text=tr("Text"), anchor="w").pack(fill="x", padx=20, pady=(10, 2))
        box = ctk.CTkTextbox(top, height=170)
        box.pack(fill="x", padx=20)
        msg = ctk.CTkLabel(top, text="", text_color=theme.DANGER, wraplength=460, justify="left")
        msg.pack(pady=4)

        def go():
            title, body, board = e.get().strip(), box.get("1.0", "end").strip(), self.board
            self.page.run(lambda: self.forum.new_thread(board, title, body),
                          lambda tid: (top.destroy(), self.show_thread(tid)), lambda err: msg.configure(text=err))
        ctk.CTkButton(top, text=tr("Post"), width=120, command=go).pack(pady=6)

    # ---------------------------------------------------------------- Thema lesen
    def show_thread(self, thread_id: int):
        self._clear()
        ctk.CTkButton(self.bar, text="← " + tr("Back"), width=90, fg_color="gray35", hover_color="gray25", command=self.show_board).pack(side="left")
        ctk.CTkLabel(self.area, text=tr("Loading …"), text_color=theme.MUTED).pack(pady=20)

        def done(data):
            for w in self.area.winfo_children():
                w.destroy()
            t = data["thread"]
            can_mod = data.get("can_moderate")
            if can_mod:
                ctk.CTkButton(self.bar, text=tr("Unpin") if t["pinned"] else tr("Pin"), width=80, fg_color="gray35", hover_color="gray25",
                              command=lambda: self._flags(thread_id, pinned=not t["pinned"])).pack(side="left", padx=6)
                ctk.CTkButton(self.bar, text=tr("Unlock") if t["locked"] else tr("Lock"), width=80, fg_color="gray35", hover_color="gray25",
                              command=lambda: self._flags(thread_id, locked=not t["locked"])).pack(side="left")
            self._post(t["title"], t["body"], t.get("author_name"), t["created_at"], "thread", thread_id, t["mine"] or can_mod, t.get("author"), big=True)
            for p in data["posts"]:
                self._post(None, p["body"], p.get("author_name"), p["created_at"], "post", p["id"], p["mine"] or can_mod, p.get("author"))
            if t["locked"]:
                ctk.CTkLabel(self.area, text="🔒 " + tr("This thread is locked."), text_color=theme.MUTED).pack(pady=10)
                return
            box = ctk.CTkTextbox(self.area, height=80)
            box.pack(fill="x", padx=8, pady=(14, 4))
            msg = ctk.CTkLabel(self.area, text="", text_color=theme.DANGER, wraplength=520, justify="left", anchor="w")
            msg.pack(fill="x", padx=8)

            def reply():
                body = box.get("1.0", "end").strip()
                if body:
                    self.page.run(lambda: self.forum.reply(thread_id, body), lambda _: self.show_thread(thread_id), lambda err: msg.configure(text=err))
            ctk.CTkButton(self.area, text=tr("Reply"), width=110, command=reply).pack(anchor="w", padx=8, pady=6)
        self.page.run(lambda: self.forum.thread(thread_id), done)

    def _post(self, title, body, author, created, kind, item_id, can_delete, handle, big=False):
        f = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=10)
        f.pack(fill="x", padx=6, pady=4)
        head = ctk.CTkFrame(f, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(head, text=(author or tr("[deleted]")), font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(head, text="  " + fmt_time(created), text_color=theme.MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkButton(head, text="⚑", width=26, height=20, fg_color="transparent", text_color=theme.MUTED, hover_color=theme.c("hover"),
                      command=lambda: self._report(kind, item_id, handle, body)).pack(side="right")
        if can_delete:
            ctk.CTkButton(head, text="🗑", width=26, height=20, fg_color="transparent", text_color=theme.MUTED, hover_color=theme.c("hover"),
                          command=lambda: self._delete(kind, item_id)).pack(side="right")
        if title:
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=17, weight="bold"), anchor="w", wraplength=560, justify="left").pack(fill="x", padx=14, pady=(4, 0))
        ctk.CTkLabel(f, text=body, anchor="w", justify="left", wraplength=560).pack(fill="x", padx=14, pady=(2, 12))

    def _flags(self, thread_id, **kw):
        self.page.run(lambda: self.forum.set_flags(thread_id, **kw), lambda _: self.show_thread(thread_id))

    def _delete(self, kind, item_id):
        if not dialogs.confirm("Delete", "Delete this entry?"):
            return
        self.page.run(lambda: self.forum.delete(kind, item_id), lambda _: self.show_board() if kind == "thread" else self.show_board())

    def _report(self, kind, item_id, handle, text):
        def go(reason):
            self.page.run(lambda: self.forum.report(kind, item_id, handle or "", reason or "-", text),
                          lambda _: self.page.say(tr("Thank you. The report was sent to the operator.")))
        dialogs.ask_text(self, "Report", "Why do you report this entry?", "Report", go)
