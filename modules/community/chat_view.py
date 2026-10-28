"""Reiter "Chats": Liste der Server/Direktnachrichten, Nachrichtenverlauf, Eingabe. Aktualisiert per Abfrage (alle paar Sekunden)."""
import datetime

import customtkinter as ctk

from core import theme
from core.i18n import tr

from . import dialogs
from .service import MAX_TEXT, Message

POLL_MS = 3000
SPACES_EVERY = 4            # alle 4 Nachrichten-Abfragen auch die Serverliste erneuern (~12 s)
INITIAL = 60


def poll_delay(idle_ticks: int, visible: bool) -> int:
    """Adaptive Abfrage-Pause: schnell solange etwas los ist, langsamer bei Ruhe oder wenn die Seite nicht offen ist."""
    base = POLL_MS if idle_ticks < 10 else 6000 if idle_ticks < 40 else 12000
    return base if visible else max(base, 12000)


def mentions(text: str, handle: str) -> bool:
    """Enthält der Text @handle (ganzes Wort, Groß-/Kleinschreibung egal)?"""
    import re
    return bool(handle) and re.search(r"(?<![\w.])@" + re.escape(handle) + r"(?![\w-])", text, re.I) is not None


def fmt_time(iso: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        today = datetime.datetime.now().astimezone().date()
        return dt.strftime("%H:%M") if dt.date() == today else dt.strftime("%d.%m. %H:%M")
    except Exception:
        return ""


class ChatView(ctk.CTkFrame):
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent")
        self.page, self.svc, self.plugin, self.app = page, page.svc, page.plugin, page.app
        self.cur_space: str | None = None
        self.cur_channel: str | None = None
        self.last_id = 0
        self._busy_msgs = self._busy_spaces = False
        self._ticks = 0
        self._idle = 0
        self._reply_to: dict | None = None
        self._unread_known: set[str] = set()
        self._channel_names: dict[str, str] = {}
        self.plugin.chat_active = True
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, width=240, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        left.grid(row=0, column=0, sticky="ns", padx=(24, 8), pady=(0, 12))
        left.grid_propagate(False)
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkButton(top, text="+ " + tr("Server"), width=100, height=28, command=self._new_server).pack(side="left")
        ctk.CTkButton(top, text=tr("Join"), width=70, height=28, command=self._join).pack(side="left", padx=6)
        ctk.CTkButton(left, text="✉ " + tr("New message"), height=28, command=self._new_dm).pack(fill="x", padx=10, pady=2)
        self.btn_inv = ctk.CTkButton(left, text=tr("Invitations"), height=28, fg_color=theme.c("hover"), text_color=theme.TEXT,
                                     command=self._show_invites)
        self.btn_inv.pack(fill="x", padx=10, pady=2)
        self.listbox = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.listbox.pack(fill="both", expand=True, padx=4, pady=(6, 6))

        right = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 24), pady=(0, 12))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.title = ctk.CTkLabel(head, text=tr("Choose a server or start a message"), font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.title.pack(side="left")
        self.btn_manage = ctk.CTkButton(head, text="⚙", width=34, height=28, command=self._manage)
        self.chan_menu = ctk.CTkOptionMenu(head, values=["-"], width=160, height=28, command=self._pick_channel)
        self.msgs = ctk.CTkScrollableFrame(right, fg_color=theme.c("main"))
        self.msgs.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.notice = ctk.CTkLabel(right, text="", text_color=theme.MUTED, anchor="w", wraplength=520, justify="left")
        self.notice.grid(row=2, column=0, sticky="ew", padx=14)
        self.reply_bar = ctk.CTkFrame(right, fg_color=theme.c("inset"), corner_radius=8)
        self.reply_lbl = ctk.CTkLabel(self.reply_bar, text="", anchor="w", text_color=theme.MUTED)
        self.reply_lbl.pack(side="left", padx=8, pady=3, fill="x", expand=True)
        ctk.CTkButton(self.reply_bar, text="✕", width=26, height=22, fg_color="transparent", text_color=theme.MUTED,
                      hover_color=theme.c("hover"), command=self._cancel_reply).pack(side="right", padx=4)
        inp = ctk.CTkFrame(right, fg_color="transparent")
        inp.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 10))
        inp.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(inp, placeholder_text=tr("Write a message …"))
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self._send())
        self.btn_send = ctk.CTkButton(inp, text=tr("Send"), width=90, command=self._send)
        self.btn_send.grid(row=0, column=1, padx=(8, 0))
        self._set_input(False)

    # ---------------------------------------------------------------- Anzeige-Zustand
    def on_show(self):
        self._refresh_spaces()
        self._schedule()

    def _visible(self) -> bool:
        return getattr(self.app, "current", None) == "community" and self.page.active == "chat"

    def _schedule(self):
        if self.page.alive:
            self._idle += 1
            self.after(poll_delay(self._idle, self._visible()), self._tick)

    def _tick(self):
        if not self.page.alive:
            return
        self._ticks += 1
        if self._visible():
            self._poll_messages()
        if self._ticks % SPACES_EVERY == 0:
            self._refresh_spaces()
        self._schedule()

    def destroy(self):
        self.plugin.chat_active = False
        super().destroy()

    def _set_input(self, on: bool):
        state = "normal" if on else "disabled"
        self.entry.configure(state=state)
        self.btn_send.configure(state=state)

    # ---------------------------------------------------------------- Serverliste
    def _refresh_spaces(self):
        if self._busy_spaces:
            return
        self._busy_spaces = True

        def work():
            spaces = self.svc.refresh()
            self.svc.housekeeping()                 # Admins: neue Mitglieder freischalten / Schlüssel erneuern
            self.svc.refresh()
            return spaces, self.svc.my_invites()

        def done(res):
            self._busy_spaces = False
            self._render_spaces()
            self._notify_unread()
            n = len(res[1])
            self.btn_inv.configure(text=tr("Invitations") + (f" ({n})" if n else ""))
            if len(res[1]) > getattr(self, "_inv_seen", len(res[1])):
                self.app.notifier.notify("invite", tr("New invitation"), tr("You were invited to a server."))
            self._inv_seen = len(res[1])
            self._invites = res[1]
            if self.cur_space:
                self._update_state()

        def fail(err):
            self._busy_spaces = False
            self.page.say_error(err)
        self.page.run(work, done, fail)

    def unread_total(self) -> int:
        return sum(1 for sp in self.svc.spaces for c in sp.get("channels", [])
                   if c["id"] != self.cur_channel and self.plugin.is_unread(c))

    def _notify_unread(self):
        """Zahl der ungelesenen Kanäle am Menüpunkt; Ton, wenn ein neuer Kanal ungelesen wird."""
        now = {c["id"] for sp in self.svc.spaces for c in sp.get("channels", [])
               if c["id"] != self.cur_channel and self.plugin.is_unread(c)}
        fresh = now - self._unread_known
        first = not hasattr(self, "_notified_once")
        self._notified_once = True
        self._unread_known = now
        if fresh and not first:
            self._idle = 0
            from .watcher import fresh_events, unread_map
            prefs = self.app.notifier.prefs()
            cur = {"unread": unread_map(self.svc.spaces, self.plugin.is_unread, self.cur_channel or ""), "invites": 0, "news": 0, "market": 0}
            prev = {"unread": {k: v for k, v in cur["unread"].items() if k not in fresh}, "invites": 0, "news": 0, "market": 0}
            for ev, title, text in fresh_events(prev, cur, prefs.muted_servers):
                self.app.notifier.notify(ev, tr(title), text)
        btn = self.app.nav.get(self.plugin.id)
        if btn is not None:
            try:
                base = btn.cget("text").split("  ●")[0].split("  (")[0]
                btn.configure(text=base + (f"  ({len(now)})" if now else ""))
            except Exception:
                pass

    def _render_spaces(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        servers = [s for s in self.svc.spaces if s["kind"] == "server"]
        dms = [s for s in self.svc.spaces if s["kind"] == "dm"]
        for group, label in ((servers, tr("SERVERS")), (dms, tr("DIRECT MESSAGES"))):
            if not group:
                continue
            ctk.CTkLabel(self.listbox, text=label, text_color=theme.MUTED, font=ctk.CTkFont(size=11, weight="bold"), anchor="w"
                         ).pack(fill="x", padx=8, pady=(8, 0))
            for s in group:
                unread = any(self.plugin.is_unread(c) for c in s.get("channels", []) if c["id"] != self.cur_channel)
                name = ("💬 " + s["peer"]["display_name"]) if s["kind"] == "dm" and s.get("peer") else "🖥 " + s["name"]
                if s["status"] == "pending":
                    name = "⏳ " + s["name"]
                active = s["id"] == self.cur_space
                ctk.CTkButton(self.listbox, text=name + ("  ●" if unread else ""), anchor="w", height=32, corner_radius=8,
                              fg_color=theme.accent() if active else "transparent",
                              text_color=theme.contrast_text(theme.accent()) if active else theme.TEXT,
                              hover_color=theme.c("hover"), command=lambda sid=s["id"]: self.open_space(sid)).pack(fill="x", padx=4, pady=1)

    # ---------------------------------------------------------------- Aktionen links
    def _new_server(self):
        def go(name):
            if name:
                self.page.run(lambda: self.svc.create_server(name), lambda r: (self._refresh_spaces(), self.open_space(r["space_id"], force=True)))
        dialogs.ask_text(self, "New server", "Name of the server", "Create", go)

    def _join(self):
        def go(code):
            if code:
                self.page.run(lambda: self.svc.redeem_invite(code), lambda r: (
                    self.page.say(tr("Joined '{n}'. An admin has to approve you; this happens automatically when one is online.", n=r["name"])),
                    self._refresh_spaces()))
        dialogs.ask_text(self, "Join a server", "Invitation code (JOPML-XXXX-XXXX-XXXX-XXXX)", "Join", go)

    def _new_dm(self):
        def go(handle):
            if handle:
                self.page.run(lambda: self.svc.open_dm(handle.strip().lstrip("@").lower()),
                              lambda r: (self._refresh_spaces(), self.open_space(r["space_id"], force=True)))
        dialogs.ask_text(self, "New message", "Username of the person (without @)", "Open chat", go)

    def _show_invites(self):
        invs = getattr(self, "_invites", [])
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Invitations"))
        top.geometry("460x320")
        if not invs:
            ctk.CTkLabel(top, text=tr("No open invitations."), text_color=theme.MUTED).pack(pady=30)
        for inv in invs:
            r = ctk.CTkFrame(top, fg_color=theme.c("card"), corner_radius=10)
            r.pack(fill="x", padx=14, pady=5)
            ctk.CTkLabel(r, text=tr("{s} – invited by {u}", s=inv["space_name"], u=inv.get("from") or "?"), anchor="w",
                         wraplength=250, justify="left").pack(side="left", padx=12, pady=10)

            def answer(accept, sid=inv["space_id"]):
                top.destroy()
                self.page.run(lambda: self.svc.answer_invite(sid, accept), lambda _: self._refresh_spaces())
            ctk.CTkButton(r, text=tr("Decline"), width=80, fg_color="gray35", hover_color="gray25", command=lambda a=answer: a(False)).pack(side="right", padx=6)
            ctk.CTkButton(r, text=tr("Accept"), width=80, command=lambda a=answer: a(True)).pack(side="right")

    # ---------------------------------------------------------------- Server/Kanal öffnen
    def open_space(self, space_id: str, force: bool = False):
        s = self.svc.space(space_id)
        if s is None and force:                     # frisch angelegt: Liste ist noch nicht neu geladen
            self.page.run(self.svc.refresh, lambda _: self.open_space(space_id))
            return
        if s is None:
            return
        self.cur_space = space_id
        title = s["peer"]["display_name"] if s["kind"] == "dm" and s.get("peer") else s["name"]
        self.title.configure(text=title)
        self.btn_manage.pack(side="right")
        chans = s.get("channels", [])
        self._channel_names = {c["id"]: c["name"] for c in chans}
        if s["kind"] == "server" and chans:
            self.chan_menu.configure(values=["# " + c["name"] for c in chans])
            self.chan_menu.pack(side="right", padx=6)
        else:
            self.chan_menu.pack_forget()
        self._render_spaces()
        if chans:
            self.open_channel(chans[0]["id"])
        else:
            self._clear_msgs()
            self.cur_channel = None
        self._update_state()

    def _pick_channel(self, label: str):
        name = label.lstrip("# ")
        cid = next((i for i, n in self._channel_names.items() if n == name), None)
        if cid:
            self.open_channel(cid)

    def open_channel(self, channel_id: str):
        self.cur_channel = channel_id
        self.last_id = 0
        self._clear_msgs()
        name = self._channel_names.get(channel_id)
        if name and (self.svc.space(self.cur_space) or {}).get("kind") == "server":
            self.chan_menu.set("# " + name)
        sid = self.cur_space

        def work():
            return self.svc.fetch(sid, channel_id, limit=INITIAL)

        def done(msgs):
            if channel_id == self.cur_channel:
                self._append(msgs)
        self.page.run(work, done)
        self._update_state()

    def _update_state(self):
        s = self.svc.space(self.cur_space) if self.cur_space else None
        if not s:
            self._set_input(False)
            return
        if s["status"] == "pending":
            self.notice.configure(text=tr("Waiting for approval. A server admin's launcher will give you the key automatically."))
            self._set_input(False)
        elif not self.svc.has_key(s["id"]):
            self.notice.configure(text=tr("You do not have the key for this chat yet. It arrives when an admin is online."))
            self._set_input(False)
        elif s.get("muted_until"):
            self.notice.configure(text=tr("You are muted on this server for now."))
            self._set_input(False)
        else:
            sm = int(s.get("slowmode") or 0)
            self.notice.configure(text=tr("Slow mode: one message every {n} seconds.", n=sm) if sm and s.get("role") == "member" else "")
            self._set_input(bool(self.cur_channel))

    # ---------------------------------------------------------------- Nachrichten
    def _clear_msgs(self):
        for w in self.msgs.winfo_children():
            w.destroy()

    def _poll_messages(self):
        if self._busy_msgs or not self.cur_channel or not self.cur_space:
            return
        sid, cid, last = self.cur_space, self.cur_channel, self.last_id
        s = self.svc.space(sid)
        if not s or s["status"] != "active":
            return
        self._busy_msgs = True

        def done(msgs):
            self._busy_msgs = False
            if cid == self.cur_channel and msgs:
                self._append(msgs)

        def fail(err):
            self._busy_msgs = False
        self.page.run(lambda: self.svc.fetch(sid, cid, after=last), done, fail)

    def _append(self, msgs: list[Message]):
        for m in msgs:
            if m.id <= self.last_id:
                continue
            self.last_id = m.id
            self._idle = 0
            self._add_message(m)
        if msgs and self.cur_channel:
            self.plugin.mark_seen(self.cur_channel, self.last_id)
            self._render_spaces()
        try:
            self.msgs._parent_canvas.yview_moveto(1.0)           # nach unten scrollen
        except Exception:
            pass

    def _add_message(self, m: Message):
        me = (self.svc.me or {}).get("handle", "") if hasattr(self.svc, "me") else ""
        hit = bool(m.ok and not m.mine and mentions(m.text, me))
        f = ctk.CTkFrame(self.msgs, fg_color=theme.c("hover") if hit else "transparent", corner_radius=8)
        f.pack(fill="x", padx=6, pady=(6, 0))
        if hit and self._ticks:
            self.app.notifier.notify("mention", tr("{name} mentioned you", name=m.name), m.text[:100])
        if m.reply:
            ctk.CTkLabel(f, text="↪ " + m.reply.get("n", "") + ": " + m.reply.get("s", ""), anchor="w", text_color=theme.MUTED,
                         font=ctk.CTkFont(size=11)).pack(fill="x", padx=4)
        head = ctk.CTkFrame(f, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=m.name, font=ctk.CTkFont(weight="bold"),
                     text_color=theme.accent() if m.mine else theme.TEXT).pack(side="left")
        mark = "" if not m.ok else ("  ✔" if m.verified else "  ⚠ " + tr("sender not verified"))
        ctk.CTkLabel(head, text=f"  {fmt_time(m.created_at)}{mark}", text_color=theme.MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        if m.ok:
            ctk.CTkButton(head, text="↩", width=26, height=20, fg_color="transparent", text_color=theme.MUTED, hover_color=theme.c("hover"),
                          command=lambda: self._start_reply(m)).pack(side="right")
            ctk.CTkButton(head, text="⚑", width=26, height=20, fg_color="transparent", text_color=theme.MUTED, hover_color=theme.c("hover"),
                          command=lambda: self._report(m)).pack(side="right")
            s = self.svc.space(self.cur_space) or {}
            if m.mine or s.get("role") in ("owner", "admin"):
                ctk.CTkButton(head, text="🗑", width=26, height=20, fg_color="transparent", text_color=theme.MUTED, hover_color=theme.c("hover"),
                              command=lambda: self._delete(m, f)).pack(side="right")
        ctk.CTkLabel(f, text=m.text, anchor="w", justify="left", wraplength=520,
                     text_color=theme.TEXT if m.ok else theme.MUTED).pack(fill="x")
        if m.filtered:
            ctk.CTkLabel(f, text=tr("Some words were hidden by the filter."), text_color=theme.MUTED, font=ctk.CTkFont(size=10), anchor="w").pack(fill="x")

    def _start_reply(self, m: Message):
        snippet = " ".join(m.text.split())[:80]
        self._reply_to = {"id": m.id, "n": m.name, "s": snippet}
        self.reply_lbl.configure(text="↪ " + tr("Reply to {name}:", name=m.name) + " " + snippet[:60])
        self.reply_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 0))
        self.entry.focus_set()

    def _cancel_reply(self):
        self._reply_to = None
        self.reply_bar.grid_forget()

    def _delete(self, m: Message, frame):
        if not dialogs.confirm("Delete message", "Delete this message for everyone?"):
            return
        self.page.run(lambda: self.svc.delete_message(m.id), lambda _: frame.destroy())

    def _report(self, m: Message):
        def go(reason):
            self.page.run(lambda: self.svc.report_message(self.cur_space, m, reason or "-"),
                          lambda _: self.page.say(tr("Thank you. The report was sent to the operator.")))
        dialogs.ask_text(self, "Report message",
                         "Why do you report this message? The text of the message is sent to the operator for review.", "Report", go)

    def _send(self):
        text = self.entry.get().strip()
        if not text or not self.cur_space or not self.cur_channel:
            return
        sid, cid, reply = self.cur_space, self.cur_channel, self._reply_to
        self.entry.delete(0, "end")
        self._cancel_reply()
        self._idle = 0

        def fail(err):
            self.page.say_error(err)
            self.entry.insert(0, text)
        self.page.run(lambda: self.svc.send(sid, cid, text, reply=reply), lambda _: (self.page.say(""), self._poll_messages()), fail)

    # ---------------------------------------------------------------- Verwaltung
    def _manage(self):
        s = self.svc.space(self.cur_space) if self.cur_space else None
        if s:
            from .manage import ManageDialog
            ManageDialog(self, s)

    def after_manage(self, left_space: bool = False):
        if left_space:
            self.cur_space = self.cur_channel = None
            self.title.configure(text=tr("Choose a server or start a message"))
            self._clear_msgs()
            self._set_input(False)
        self._refresh_spaces()
