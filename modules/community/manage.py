"""Verwaltungsfenster eines Servers / einer Direktnachricht: Einladen, Mitglieder, Kanäle, Sicherheit."""
import customtkinter as ctk

from core import theme
from core.i18n import tr

from . import crypto, dialogs

ROLE_LABEL = {"owner": "Owner", "admin": "Admin", "member": "Member"}


class ManageDialog(ctk.CTkToplevel):
    def __init__(self, chat, space: dict):
        super().__init__(chat, fg_color=theme.c("main"))
        self.chat, self.page, self.svc, self.space = chat, chat.page, chat.svc, space
        self.is_server = space["kind"] == "server"
        self.is_mod = space["role"] in ("owner", "admin")
        title = space["name"] if self.is_server else space["peer"]["display_name"]
        self.title(tr("Manage: {n}", n=title))
        self.geometry("620x520")
        try:
            self.transient(chat.winfo_toplevel())
        except Exception:
            pass
        self.after(120, self.lift)
        tabs = []
        if self.is_server:
            tabs += [("Invite", self._tab_invite), ("Members", self._tab_members)]
            if self.is_mod:
                tabs.append(("Channels", self._tab_channels))
        tabs += [("Security", self._tab_security), ("More", self._tab_more)]
        self._tabs = {tr(label): fn for label, fn in tabs}
        self.seg = ctk.CTkSegmentedButton(self, values=list(self._tabs), command=self._open)
        self.seg.pack(anchor="w", padx=16, pady=(14, 6))
        self.area = None
        first = tr(tabs[0][0])
        self.seg.set(first)
        self._open(first)

    def _open(self, label):
        if self.area is not None:
            self.area.destroy()
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
        self.area.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.msg = ctk.CTkLabel(self.area, text="", anchor="w", justify="left", wraplength=540)
        self.msg.pack(fill="x", padx=6)
        self._tabs[label]()

    def say(self, text, ok=True):
        if self.winfo_exists():
            self.msg.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _run(self, work, done=None):
        self.page.run(work, done, lambda err: self.say(err, False))

    def _card(self, title):
        c = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=10)
        c.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(c, text=tr(title), font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        b = ctk.CTkFrame(c, fg_color="transparent")
        b.pack(fill="x", padx=14, pady=(0, 12))
        return b

    # ---------------------------------------------------------------- Einladen
    def _tab_invite(self):
        sid = self.space["id"]
        b = self._card("Invite with a code")
        ctk.CTkLabel(b, text=tr("Anyone with the code can ask to join. An admin still has to approve them."), anchor="w",
                     wraplength=520, justify="left", text_color=theme.MUTED).pack(fill="x")
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=6)
        hours = ctk.CTkOptionMenu(r, values=["1", "24", "72", "168"], width=80)
        hours.set("24")
        uses = ctk.CTkOptionMenu(r, values=["1", "5", "10", "50", "100"], width=80)
        uses.set("10")
        ctk.CTkLabel(r, text=tr("valid hours")).pack(side="left")
        hours.pack(side="left", padx=6)
        ctk.CTkLabel(r, text=tr("max. uses")).pack(side="left")
        uses.pack(side="left", padx=6)

        def create():
            self._run(lambda: self.svc.create_invite(sid, int(hours.get()), int(uses.get())),
                      lambda inv: dialogs.show_text(self, "Invitation code", inv["code"], big=True))
        ctk.CTkButton(b, text=tr("Create code"), width=150, command=create).pack(anchor="w")

        b = self._card("Invite by username")
        e = ctk.CTkEntry(b, width=260, placeholder_text=tr("username"))
        e.pack(side="left")

        def go():
            h = e.get().strip().lstrip("@").lower()
            if h:
                self._run(lambda: self.svc.invite_user(sid, h), lambda _: (self.say(tr("Invitation sent.")), e.delete(0, "end")))
        ctk.CTkButton(b, text=tr("Invite"), width=100, command=go).pack(side="left", padx=8)

        b = self._card("Invite by email address")
        ctk.CTkLabel(b, text=tr("The person gets the invitation in the launcher if an account with this address exists. For privacy you always see "
                                "“sent”, whether or not an account was found."), anchor="w", wraplength=520, justify="left",
                     text_color=theme.MUTED).pack(fill="x", pady=(0, 6))
        em = ctk.CTkEntry(b, width=300, placeholder_text="name@example.com")
        em.pack(side="left")

        def go_mail():
            addr = em.get().strip()
            if addr:
                self._run(lambda: self.svc.invite_email(sid, addr),
                          lambda _: (self.say(tr("If there is an account with this address, the invitation was sent.")), em.delete(0, "end")))
        ctk.CTkButton(b, text=tr("Invite"), width=100, command=go_mail).pack(side="left", padx=8)

    # ---------------------------------------------------------------- Mitglieder
    def _tab_members(self):
        sid = self.space["id"]
        if self.is_mod:
            sm = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=8)
            sm.pack(fill="x", padx=6, pady=3)
            ctk.CTkLabel(sm, text=tr("Slow mode (seconds between messages, 0 = off)"), anchor="w").pack(side="left", padx=12, pady=8)
            ent = ctk.CTkEntry(sm, width=70)
            ent.insert(0, str(int(self.space.get("slowmode") or 0)))
            ent.pack(side="right", padx=8)

            def save_slow():
                try:
                    n = max(0, min(3600, int(ent.get().strip() or 0)))
                except ValueError:
                    self.say(tr("Please enter a number."), False)
                    return
                self.space["slowmode"] = n
                self._run(lambda: self.svc.set_slowmode(sid, n), lambda _: (self.say(tr("Saved.")), self.chat.after_manage()))
            ctk.CTkButton(sm, text=tr("Save"), width=70, height=26, command=save_slow).pack(side="right")
        holder = ctk.CTkFrame(self.area, fg_color="transparent")
        holder.pack(fill="x")

        def render(members):
            for w in holder.winfo_children():
                w.destroy()
            for m in sorted(members.values(), key=lambda x: (x["role"] != "owner", x["role"] != "admin", x["handle"])):
                r = ctk.CTkFrame(holder, fg_color=theme.c("card"), corner_radius=8)
                r.pack(fill="x", padx=6, pady=3)
                label = f"{m['display_name']}  (@{m['handle']})  ·  {tr(ROLE_LABEL[m['role']])}"
                if m["status"] == "pending":
                    label += "  ·  " + tr("waiting for approval")
                ctk.CTkLabel(r, text=label, anchor="w").pack(side="left", padx=12, pady=8)
                if m["user_id"] == self.svc.my_id or m["role"] == "owner":
                    continue
                if self.space["role"] == "owner":
                    nxt = "member" if m["role"] == "admin" else "admin"
                    ctk.CTkButton(r, text=tr("Remove admin") if nxt == "member" else tr("Make admin"), width=110, height=26,
                                  fg_color="gray35", hover_color="gray25",
                                  command=lambda u=m["user_id"], n=nxt: self._act(lambda: self.svc.set_role(sid, u, n))).pack(side="right", padx=4)
                if self.is_mod and not (self.space["role"] == "admin" and m["role"] == "admin"):
                    muted = bool(m.get("muted_until"))
                    ctk.CTkButton(r, text=tr("Unmute") if muted else tr("Mute 1 h"), width=80, height=26, fg_color="gray35", hover_color="gray25",
                                  command=lambda u=m["user_id"], mm=(0 if muted else 60): self._act(lambda: self.svc.mute(sid, u, mm))
                                  ).pack(side="right", padx=4)
                    ctk.CTkButton(r, text=tr("Ban"), width=60, height=26, fg_color="#b91c1c", hover_color="#7f1d1d",
                                  command=lambda u=m["user_id"]: self._kick(u, True)).pack(side="right", padx=4)
                    ctk.CTkButton(r, text=tr("Remove"), width=70, height=26, fg_color="gray35", hover_color="gray25",
                                  command=lambda u=m["user_id"]: self._kick(u, False)).pack(side="right", padx=4)
        self._render_members = render
        self._members_sid = sid
        self._run(lambda: self.svc.members(sid), render)

    def _act(self, work):
        self._run(work, lambda _: (self._open(self.seg.get()), self.chat.after_manage()))

    def _kick(self, user_id, ban):
        text = "Remove this person and ban them from rejoining?" if ban else "Remove this person from the server?"
        if dialogs.confirm("Remove member", text):
            self._act(lambda: self.svc.kick(self.space["id"], user_id, ban))

    # ---------------------------------------------------------------- Kanäle
    def _tab_channels(self):
        sid = self.space["id"]
        for c in self.space.get("channels", []):
            r = ctk.CTkFrame(self.area, fg_color=theme.c("card"), corner_radius=8)
            r.pack(fill="x", padx=6, pady=3)
            ctk.CTkLabel(r, text="# " + c["name"], anchor="w").pack(side="left", padx=12, pady=8)
            if len(self.space["channels"]) > 1:
                ctk.CTkButton(r, text=tr("Delete"), width=70, height=26, fg_color="#b91c1c", hover_color="#7f1d1d",
                              command=lambda cid=c["id"]: self._delete_channel(cid)).pack(side="right", padx=8)
        b = self._card("New channel")
        e = ctk.CTkEntry(b, width=260, placeholder_text="general-talk")
        e.pack(side="left")

        def go():
            n = e.get().strip().lower()
            if n:
                self._run(lambda: self.svc.create_channel(sid, n), lambda _: (self.chat.after_manage(), self.destroy()))
        ctk.CTkButton(b, text=tr("Create"), width=100, command=go).pack(side="left", padx=8)
        ctk.CTkLabel(b, text="").pack()

    def _delete_channel(self, cid):
        if dialogs.confirm("Delete channel", "Delete this channel and all of its messages?"):
            self._run(lambda: self.svc.delete_channel(cid), lambda _: (self.chat.after_manage(), self.destroy()))

    # ---------------------------------------------------------------- Sicherheit
    def _tab_security(self):
        b = self._card("Encryption")
        ctk.CTkLabel(b, anchor="w", justify="left", wraplength=520,
                     text=tr("Messages are encrypted on your computer and can only be read by the members of this chat. "
                             "The server only stores unreadable data. Epoch (key version): {e}", e=self.space["epoch"])).pack(fill="x")
        b = self._card("Your security number")
        ctk.CTkLabel(b, text=self.svc.my_fingerprint(), font=ctk.CTkFont(family="Consolas", size=13)).pack(anchor="w")
        if not self.is_server:
            b = self._card("Security number of this chat")
            ctk.CTkLabel(b, anchor="w", justify="left", wraplength=520, text_color=theme.MUTED,
                         text=tr("Compare this number with the other person (for example by phone). If it is identical on both sides, "
                                 "nobody can have swapped the keys.")).pack(fill="x")
            ctk.CTkLabel(b, text=self.svc.safety_number(self.space["id"]) or "-", font=ctk.CTkFont(family="Consolas", size=16)).pack(anchor="w", pady=4)

    # ---------------------------------------------------------------- Mehr
    def _tab_more(self):
        sid = self.space["id"]
        b = self._card("Leave or delete")
        if self.is_server and self.space["role"] != "owner":
            ctk.CTkButton(b, text=tr("Leave server"), width=180, fg_color="#b91c1c", hover_color="#7f1d1d", command=self._leave).pack(anchor="w", pady=3)
        if (self.is_server and self.space["role"] == "owner") or not self.is_server:
            ctk.CTkButton(b, text=tr("Delete server") if self.is_server else tr("Delete this chat"), width=180, fg_color="#b91c1c",
                          hover_color="#7f1d1d", command=self._delete).pack(anchor="w", pady=3)
        if self.is_server:
            ctk.CTkButton(b, text=tr("Report this server"), width=180, fg_color="gray35", hover_color="gray25",
                          command=self._report).pack(anchor="w", pady=3)

    def _leave(self):
        if dialogs.confirm("Leave server", "Leave this server? You can only rejoin with a new invitation."):
            self._run(lambda: self.svc.leave(self.space["id"]), lambda _: (self.chat.after_manage(True), self.destroy()))

    def _delete(self):
        if dialogs.confirm("Delete", "This deletes everything in here for all members and cannot be undone.\nContinue?"):
            self._run(lambda: self.svc.delete_space(self.space["id"]), lambda _: (self.chat.after_manage(True), self.destroy()))

    def _report(self):
        sid = self.space["id"]

        def go(reason):
            self._run(lambda: self.svc.report_server(sid, reason or "-"), lambda _: self.say(tr("Thank you. The report was sent to the operator.")))
        dialogs.ask_text(self, "Report this server", "Why do you report this server?", "Report", go)
