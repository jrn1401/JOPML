"""Seite "Community": Einrichtung/Entsperren, dann Reiter Chats, Forum und (für Admins) Moderation."""
import threading
import tkinter as tk
import traceback

import customtkinter as ctk

from core import chatfilter, theme, ui
from core.i18n import tr

from . import dialogs
from .service import MIN_PASSPHRASE, CommunityError

RULES = ("Community rules\n\n"
         "• Be respectful. No insults, harassment, threats, hate or extremist content.\n"
         "• No sexual content, no content involving minors, no illegal content.\n"
         "• Do not share other people's private data.\n"
         "• Words that break these rules are blocked automatically; the filter is not perfect, so please report anything you see.\n"
         "• Server owners and admins can remove members; the operator can remove servers and suspend accounts after reports.\n"
         "• Chats are end-to-end encrypted: the operator cannot read them. When you report a message, you send its text to the operator.\n"
         "• You must be at least 16 years old.")


class CommunityPage(ctk.CTkFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self.svc, self.forum = plugin.service(), plugin.forum()
        self.alive = True
        self.active = ""
        self.views: dict = {}
        self.body = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ui.page_title(self, "Community", "Servers, direct messages and a public forum. Chats are end-to-end encrypted."
                      ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 4))
        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=760)
        self.status.grid(row=1, column=0, sticky="ew", padx=24)
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.grid(row=2, column=0, sticky="nsew")
        self.holder.grid_columnconfigure(0, weight=1)
        self.holder.grid_rowconfigure(0, weight=1)
        self.bind("<Destroy>", self._destroyed)
        if self.svc is None:
            self._info_card()
        else:
            threading.Thread(target=chatfilter._compiled, daemon=True).start()      # Filter vorladen (dauert ~2 s)
            self.run(self.svc.load_me, self._after_me)

    # ---------------------------------------------------------------- Hilfen
    def _destroyed(self, _e=None):
        self.alive = False

    def run(self, work, done=None, fail=None):
        """work() läuft im Hintergrund; done(ergebnis) bzw. fail(text) laufen danach im Oberflächen-Thread."""
        def job():
            try:
                res, err = work(), None
            except CommunityError as exc:
                res, err = None, str(exc)
            except Exception as exc:
                traceback.print_exc()
                res, err = None, f"{type(exc).__name__}: {exc}"
            self.app.call_soon(self._deliver, done, fail, res, err)
        threading.Thread(target=job, daemon=True).start()

    def _deliver(self, done, fail, res, err):
        if not self.alive:
            return
        if err:
            (fail or self.say_error)(err)
        elif done:
            done(res)

    def say(self, text: str, ok: bool = True):
        if self.alive:
            self.status.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def say_error(self, text: str):
        """Fehler in der Community: mit Fehlercode anzeigen und (anonym, zusammengefasst) melden – z. B. wenn ein Modul-Upload scheitert."""
        from core import errors
        code = errors.classify(text, "E-NET-002")
        try:
            self.app.record_error(code, text, "community")
        except Exception:
            pass
        self.say(errors.tag(text, code), False)

    def _fresh(self) -> ctk.CTkFrame:
        if self.body is not None:
            self.body.destroy()
        self.views = {}
        self.active = ""
        self.body = ctk.CTkFrame(self.holder, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        return self.body

    def _info_card(self):
        box = self._fresh()
        card = ui.card(box, "Cloud account needed")
        card.grid(row=0, column=0, sticky="new", padx=24, pady=8)
        ui.muted(card, "The community works with a cloud account (sign in with Google or create a JOPMakro account while the cloud "
                       "service is set up). Local-only accounts cannot use it.").pack(fill="x", padx=16, pady=(0, 14))

    # ---------------------------------------------------------------- Zustand
    def _after_me(self, me):
        self.say("")
        if not self.svc.registered:
            self._setup_view()
        elif self.svc.unlocked:
            self._main_view()
        elif self.plugin.stay_enabled() and self.plugin.stored_passphrase():
            pw = self.plugin.stored_passphrase()
            self.say(tr("Unlocking …"))

            def bad(_err):
                self.plugin.forget_passphrase()          # Passphrase stimmt nicht mehr: wieder normal fragen
                self.say("")
                self._unlock_view()
            self.run(lambda: self.svc.unlock(pw), lambda _: (self.say(""), self._main_view()), bad)
        else:
            self._unlock_view()

    def _field(self, parent, label, secret=False, value="", locked=False):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr(label), width=190, anchor="w").pack(side="left")
        e = ctk.CTkEntry(r, width=280, show="•" if secret else "")
        e.pack(side="left")
        if value:
            e.insert(0, value)
        if locked:
            e.configure(state="disabled")
        return e

    def _setup_view(self):
        box = self._fresh()
        card = ui.card(box, "Set up the community")
        card.grid(row=0, column=0, sticky="new", padx=24, pady=8)
        b = ctk.CTkFrame(card, fg_color="transparent")
        b.pack(fill="x", padx=16, pady=(0, 14))
        ui.muted(b, "Your keys are created on this computer and locked with a passphrase that only you know. The server cannot read "
                    "your messages. The passphrase cannot be reset: if you forget it, you can only start over (your servers, chats "
                    "and messages are deleted).").pack(fill="x", pady=(0, 8))
        fixed = (self.app.user or {}).get("username") or ""
        e_handle = self._field(b, "Username", value=fixed or (self.svc.me or {}).get("suggested_handle") or "", locked=bool(fixed))
        e_name = self._field(b, "Display name", value=(self.app.user or {}).get("display_name", ""))
        e_p1 = self._field(b, "Passphrase", secret=True)
        e_p2 = self._field(b, "Repeat passphrase", secret=True)
        ui.muted(b, "At least {n} characters. Use a sentence you can remember.", n=MIN_PASSPHRASE).pack(fill="x")
        var = tk.BooleanVar(value=False)
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=(10, 2))
        ctk.CTkCheckBox(r, text=tr("I am at least 16 years old and accept the community rules."), variable=var).pack(side="left")
        ctk.CTkButton(r, text=tr("Read the rules"), width=130, fg_color="gray35", hover_color="gray25",
                      command=lambda: dialogs.show_rules(self, RULES)).pack(side="left", padx=10)

        def go():
            if not var.get():
                return self.say_error(tr("Please accept the community rules first."))
            if e_p1.get() != e_p2.get():
                return self.say_error(tr("The two passphrases are different."))
            self.say(tr("Creating your keys …"))
            h, n, p = e_handle.get().strip().lower(), e_name.get().strip(), e_p1.get()
            self.run(lambda: self.svc.setup(h, n or h, p), lambda _: (self.say(tr("Done.")), self._main_view()))
        ctk.CTkButton(b, text=tr("Set up"), width=160, command=go).pack(anchor="w", pady=(8, 0))

    def _unlock_view(self):
        box = self._fresh()
        card = ui.card(box, "Unlock the community")
        card.grid(row=0, column=0, sticky="new", padx=24, pady=8)
        b = ctk.CTkFrame(card, fg_color="transparent")
        b.pack(fill="x", padx=16, pady=(0, 14))
        ui.muted(b, "Enter your passphrase to open your encryption keys on this computer.").pack(fill="x", pady=(0, 6))
        e = self._field(b, "Passphrase", secret=True)
        stay = tk.BooleanVar(value=self.plugin.stay_enabled())
        ctk.CTkCheckBox(b, text=tr("Stay signed in to the Community on this computer"), variable=stay).pack(anchor="w", pady=(6, 0))

        def go():
            p = e.get()
            self.say(tr("Unlocking …"))

            def ok(_r):
                self.plugin.set_stay(stay.get())
                if stay.get():
                    try:
                        self.plugin.remember_passphrase(p)
                    except Exception:
                        traceback.print_exc()
                self.say("")
                self._main_view()
            self.run(lambda: self.svc.unlock(p), ok)
        e.bind("<Return>", lambda _e: go())
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(anchor="w", pady=(8, 0))
        ctk.CTkButton(r, text=tr("Unlock"), width=140, command=go).pack(side="left")
        ctk.CTkButton(r, text=tr("Forgot the passphrase?"), width=190, fg_color="gray35", hover_color="gray25",
                      command=self._forgot).pack(side="left", padx=8)

    def _forgot(self):
        if not dialogs.confirm("Start over", "This deletes your community keys, your servers, your chats and your messages for good. "
                                             "Then you can set up again with a new passphrase.\nContinue?"):
            return
        self.run(self.svc.reset_identity, lambda _: self.run(self.svc.load_me, self._after_me))

    # ---------------------------------------------------------------- Hauptansicht
    def _main_view(self):
        box = self._fresh()
        box.grid_rowconfigure(1, weight=1)
        tabs = [("Chats", "chat"), ("Forum", "forum"), ("Marketplace", "market"), ("Modules", "modules"), ("Leaderboards", "boards"), ("News", "news")]
        if (self.svc.me or {}).get("is_admin"):
            tabs.append(("Moderation", "mod"))
        self._tabs = {tr(label): key for label, key in tabs}
        seg = ctk.CTkSegmentedButton(box, values=list(self._tabs), command=lambda lab: self._tab(self._tabs[lab]))
        seg.grid(row=0, column=0, sticky="w", padx=24, pady=(4, 6))
        seg.set(tr("Chats"))
        self._tab("chat")

    def _tab(self, key: str):
        for k, v in self.views.items():
            v.grid_forget()
        if key not in self.views:
            if key == "chat":
                from .chat_view import ChatView
                self.views[key] = ChatView(self.body, self)
            elif key == "forum":
                from .forum_view import ForumView
                self.views[key] = ForumView(self.body, self)
            elif key == "market":
                from .market_view import MarketView
                self.views[key] = MarketView(self.body, self)
            elif key == "modules":
                from .modules_view import ModulesView
                self.views[key] = ModulesView(self.body, self)
            elif key == "boards":
                from .boards_view import BoardsView
                self.views[key] = BoardsView(self.body, self)
            elif key == "news":
                from .news_view import NewsView
                self.views[key] = NewsView(self.body, self)
            else:
                from .mod_view import ModView
                self.views[key] = ModView(self.body, self)
        self.views[key].grid(row=1, column=0, sticky="nsew")
        self.active = key
        if hasattr(self.views[key], "on_show"):
            self.views[key].on_show()
