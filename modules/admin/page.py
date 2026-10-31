"""Admin-Seite: Reiter Übersicht, Konten, Berechtigungen, KI (Kosten, Budget, Standard-Limits), Tickets, Meldungen, Fehler, Veröffentlichen."""
import threading
import time
import tkinter as tk

import customtkinter as ctk

from core import theme, ui
from core.hub import HubPage
from core.i18n import tr

from . import logic

COLORS = {"ok": "#2ecc71", "warn": "#f1c40f", "bad": "#e74c3c"}


class AdminPage(HubPage):
    def __init__(self, parent, plugin):
        super().__init__(parent, plugin, "Admin",
                         "Server overview, accounts, AI costs, error tickets and publishing. Only visible for admin accounts.", [
            ("Overview", self.tab_overview), ("Accounts", self.tab_accounts), ("Permissions", self.tab_permissions), ("AI", self.tab_ai), ("Tickets", self.tab_tickets),
            ("User reports", self.tab_reports), ("Automatic errors", self.tab_errors),
            ("Publish", self._publish_page, True)])

    # ---- gemeinsame Hilfe: im Hintergrund laden, Ergebnis im UI-Thread
    def _load(self, widget, call, done):
        def work():
            try:
                res, err = call(), None
            except Exception as exc:
                res, err = None, f"{type(exc).__name__}: {exc}"
            self.app.call_soon(lambda: widget.winfo_exists() and done(res, err))
        threading.Thread(target=work, daemon=True).start()

    # ---- Übersicht
    def tab_overview(self, area, plugin):
        body = self.card(area, "Server status", 0)
        self._status = ctk.CTkLabel(body, text="…", anchor="w", font=ctk.CTkFont(size=15, weight="bold"))
        self._status.pack(fill="x", pady=(0, 6))
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        for c in (0, 1):
            grid.columnconfigure(c, weight=1, uniform="a")
        self._grid = grid
        self._extra = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=620, text_color=theme.MUTED)
        self._extra.pack(fill="x", pady=(8, 0))
        self._ov_budget = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=620, text_color=COLORS["warn"])
        self._ov_budget.pack(fill="x")
        r = ui.row(body)
        r.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(r, text="↻  " + tr("Refresh"), width=120, command=self.refresh_overview).pack(side="left")
        self._auto = tk.BooleanVar(value=False)
        ctk.CTkSwitch(r, text=tr("Refresh every 30 s"), variable=self._auto, command=self._auto_tick).pack(side="left", padx=12)
        ui.muted(body, "RAM and disk of the server itself are not visible to the app: Supabase manages the machine. "
                       "Database size, connections, uptime and cache rate come straight from the database; "
                       "for the host’s RAM/CPU/disk see the Supabase dashboard (Reports).").pack(fill="x", pady=(8, 0))
        self.refresh_overview()

    def refresh_overview(self):
        t0 = time.monotonic()
        self._load(self._grid, lambda: self.plugin.rpc("jopml_admin_overview"), lambda r, e: self._show_overview(r, e, t0))
        self._load(self._ov_budget, lambda: self.plugin.rpc("jopml_admin_ai_budget"), self._show_budget_warning)

    def _show_budget_warning(self, res, err):
        b = (res[0] if isinstance(res, list) and res else res) or {}
        warn = "" if err else logic.budget_warning(b, tr)
        self._ov_budget.configure(text=("⚠ " + warn + " – " + tr("see the tab 'AI'.")) if warn else "")

    def _show_overview(self, o, err, t0):
        if err:
            self._status.configure(text="● " + tr("Server not reachable"), text_color=COLORS["bad"])
            self._extra.configure(text=err)
            return
        level, text = logic.health(o)
        ms = int((time.monotonic() - t0) * 1000)
        self._status.configure(text=f"● {tr('Server is on')} · {tr(text)} · {ms} ms", text_color=COLORS[level])
        for w in self._grid.winfo_children():
            w.destroy()
        for i, (label, val) in enumerate(logic.summarize(o)):
            cell = ctk.CTkFrame(self._grid, fg_color=theme.c("inset"), corner_radius=10)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(cell, text=tr(label), text_color=theme.MUTED, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(cell, text=val, anchor="w", font=ctk.CTkFont(size=16, weight="bold")).pack(fill="x", padx=12, pady=(0, 8))
        vers = ", ".join(f"v{v['v']}: {v['n']}" for v in o.get("versions") or [])
        tabs = ", ".join(f"{t['t'].replace('jopml_', '')} {logic.fmt_bytes(t['b'])}" for t in o.get("top_tables") or [])
        self._extra.configure(text=(tr("Versions in use (7 days)") + f": {vers or '–'}\n") + (tr("Largest tables") + f": {tabs or '–'}"))

    def _auto_tick(self):
        if not self._auto.get():
            return
        try:
            if self._grid.winfo_exists():
                if self._grid.winfo_ismapped():
                    self.refresh_overview()
                self._grid.after(30000, self._auto_tick)
        except Exception:
            pass

    # ---- Konten
    def tab_accounts(self, area, plugin):
        body = self.card(area, "Registered accounts", 0)
        self._acc_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED)
        self._acc_info.pack(fill="x")
        ctk.CTkButton(body, text="↻  " + tr("Refresh"), width=120, command=self.refresh_accounts).pack(anchor="w", pady=6)
        self._acc_box = ctk.CTkFrame(body, fg_color="transparent")
        self._acc_box.pack(fill="x")
        self.refresh_accounts()

    def refresh_accounts(self):
        self._load(self._acc_box, lambda: self.plugin.rpc("jopml_admin_users", {"p_limit": 200}), self._show_accounts)

    def _show_accounts(self, rows, err):
        for w in self._acc_box.winfo_children():
            w.destroy()
        if err:
            self._acc_info.configure(text=err, text_color=theme.DANGER)
            return
        rows = rows or []
        self._acc_info.configure(text=tr("{n} accounts shown (newest first); green dot = online now.", n=len(rows)), text_color=theme.MUTED)
        for u in rows:
            r = ctk.CTkFrame(self._acc_box, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text="●", text_color=COLORS["ok"] if u.get("online") else "#6b7280", width=18).pack(side="left")
            ctk.CTkLabel(r, text=u.get("email") or "–", anchor="w", width=300).pack(side="left")
            ctk.CTkLabel(r, text=tr("seen {t} ago", t=logic.fmt_ago(u.get("last_seen"))) if u.get("last_seen") else tr("never seen"),
                         text_color=theme.MUTED, anchor="w", width=150).pack(side="left")
            ctk.CTkLabel(r, text=tr("joined {t} ago", t=logic.fmt_ago(u.get("created_at"))), text_color=theme.MUTED, anchor="w").pack(side="left")

    # ---- Berechtigungen: Admin-Rolle und persönliche KI-Regeln pro Konto (die Standard-Regeln stehen im Reiter "AI")
    def tab_permissions(self, area, plugin):
        body2 = self.card(area, "Permissions", 0)
        ui.muted(body2, "Give an account admin rights or take them away, or set personal AI rules for one account ('Limits …'). "
                        "A personal rule replaces the standard (tab AI) for that account; empty = standard. Every change is logged on the server. "
                        "Admins can upload versions, see all accounts and error reports and approve modules: only give it to people you trust.").pack(fill="x", pady=(0, 6))
        self._perm_info = ctk.CTkLabel(body2, text="…", anchor="w", text_color=theme.MUTED, wraplength=720, justify="left")
        self._perm_info.pack(fill="x")
        ctk.CTkButton(body2, text="↻  " + tr("Refresh"), width=120, command=self.refresh_permissions).pack(anchor="w", pady=6)
        self._perm_box = ctk.CTkFrame(body2, fg_color="transparent")
        self._perm_box.pack(fill="x")
        self.refresh_permissions()

    @staticmethod
    def _fill(entry, n):
        entry.delete(0, "end")
        entry.insert(0, "maximum" if n > 0 else "no limit")

    def refresh_permissions(self):
        self._load(self._perm_box, lambda: self.plugin.rpc("jopml_admin_people", {"p_limit": 200}), self._show_permissions)

    def _show_defaults(self, rows, err):
        if err:
            self._def_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        row = (rows[0] if isinstance(rows, list) and rows else rows) or {}
        self._defaults = {"requests": row.get("daily_requests"), "answer": row.get("max_answer"), "tokens": row.get("daily_tokens")}
        for kind, e in self._def_entries.items():
            e.delete(0, "end")
            v = self._defaults.get(kind)
            if v is not None:
                e.insert(0, "no limit" if v == logic.UNLIMITED else str(v))
        self._def_info.configure(text=tr("Current standard: {a} messages/day · {b} tokens per answer · {c} tokens/day",
                                         a=tr(logic.fmt_limit(self._defaults["requests"], "requests")),
                                         b=tr(logic.fmt_limit(self._defaults["answer"], "answer")),
                                         c=tr(logic.fmt_limit(self._defaults["tokens"], "tokens"))), text_color=theme.MUTED)

    def _save_defaults(self):
        vals = {}
        for kind, e in self._def_entries.items():
            n, err = logic.parse_value(e.get(), kind)
            if n is None:
                self._def_info.configure(text=f"{tr(logic.LIMIT_KINDS[kind][0])}: {tr(err)}", text_color=theme.DANGER)
                return
            vals[kind] = n
        self._perm_call("jopml_admin_set_ai_defaults", {"p_requests": vals["requests"], "p_answer": vals["answer"], "p_tokens": vals["tokens"]},
                        tr("Saved."), self._def_info, self.refresh_ai)

    def _show_permissions(self, rows, err):
        for w in self._perm_box.winfo_children():
            w.destroy()
        if err:
            self._perm_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        rows = rows or []
        self._perm_info.configure(text=tr("{n} accounts shown (newest first).", n=len(rows)), text_color=theme.MUTED)
        for u in rows:
            r = ctk.CTkFrame(self._perm_box, fg_color=theme.c("card"), corner_radius=8)
            r.pack(fill="x", pady=2)
            top = ctk.CTkFrame(r, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(top, text=u.get("email") or "–", anchor="w", width=290).pack(side="left")
            if u.get("is_admin"):
                ctk.CTkLabel(top, text="ADMIN", text_color=COLORS["ok"], width=60).pack(side="left")
            ctk.CTkLabel(top, anchor="w", text_color=theme.MUTED,
                         text=tr("AI today: {n} messages, {t} tokens", n=u.get("ai_today", 0), t=u.get("tokens_today", 0))).pack(side="left", padx=8)
            bot = ctk.CTkFrame(r, fg_color="transparent")
            bot.pack(fill="x", padx=10, pady=(2, 6))
            if u.get("is_admin"):
                ctk.CTkButton(bot, text=tr("Remove admin"), width=130, fg_color=theme.DANGER, hover_color="#b3363a",
                              command=lambda x=u: self._set_admin(x, False)).pack(side="left", padx=(0, 10))
            else:
                ctk.CTkButton(bot, text=tr("Make admin"), width=130, command=lambda x=u: self._set_admin(x, True)).pack(side="left", padx=(0, 10))
            ctk.CTkButton(bot, text=tr("Limits …"), width=100, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda x=u: self._limits_dialog(x)).pack(side="left")
            ctk.CTkLabel(bot, anchor="w", text_color=theme.MUTED, text="  " + tr("Personal: {a} msg/day · {b} per answer · {c} tokens/day",
                         a=tr(logic.fmt_limit(u.get("ai_requests"), "requests")), b=tr(logic.fmt_limit(u.get("ai_answer"), "answer")),
                         c=tr(logic.fmt_limit(u.get("ai_tokens"), "tokens")))).pack(side="left")

    def _limits_dialog(self, u):
        """Persönliche KI-Regeln eines Kontos: je Wert Zahl, 'Maximum', 'No limit' oder 'Default' (leer = Standard)."""
        top = ctk.CTkToplevel(self)
        top.title(tr("Limits …"))
        top.geometry("560x290")
        top.transient(self.winfo_toplevel())
        ctk.CTkLabel(top, text=u.get("email") or "–", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(14, 6))
        cur = {"requests": u.get("ai_requests"), "answer": u.get("ai_answer"), "tokens": u.get("ai_tokens")}
        ents = {}
        for kind, (label, mx) in logic.LIMIT_KINDS.items():
            row = ctk.CTkFrame(top, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=tr(label), width=190, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, width=110, placeholder_text=tr("Default"))
            e.pack(side="left")
            if cur[kind] is not None:
                e.insert(0, "no limit" if cur[kind] == logic.UNLIMITED else str(cur[kind]))
            ents[kind] = e
            ctk.CTkButton(row, text=tr("Maximum"), width=80, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda en=e: self._fill(en, 1)).pack(side="left", padx=(6, 2))
            ctk.CTkButton(row, text=tr("No limit"), width=80, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda en=e: self._fill(en, -1)).pack(side="left", padx=2)
            ctk.CTkButton(row, text=tr("Default"), width=70, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda en=e: en.delete(0, "end")).pack(side="left", padx=2)
        msg = ctk.CTkLabel(top, text="", text_color=theme.DANGER, anchor="w", wraplength=500)
        msg.pack(fill="x", padx=20, pady=4)

        def save():
            vals = {}
            for kind, e in ents.items():
                t = e.get().strip()
                if not t:
                    vals[kind] = None
                    continue
                n, err = logic.parse_value(t, kind)
                if n is None:
                    msg.configure(text=f"{tr(logic.LIMIT_KINDS[kind][0])}: {tr(err)}")
                    return
                vals[kind] = n
            top.destroy()
            self._perm_call("jopml_admin_set_ai_user", {"p_user": u["user_id"], "p_requests": vals["requests"], "p_answer": vals["answer"],
                                                         "p_tokens": vals["tokens"]}, tr("Saved."))
        ctk.CTkButton(top, text=tr("Save"), width=140, command=save).pack(pady=8)

    def _perm_say(self, text, ok=True, label=None):
        label = label or self._perm_info
        if label is not None and label.winfo_exists():
            label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _perm_call(self, name, params, done_text, label=None, then=None):
        def work():
            try:
                self.plugin.rpc(name, params)
                self.app.call_soon(self._perm_say, done_text, True, label)
                self.app.call_soon(then or self.refresh_permissions)
            except Exception as exc:
                self.app.call_soon(self._perm_say, tr(logic.friendly_rpc_error(str(exc))), False, label)
        threading.Thread(target=work, daemon=True).start()

    def _set_admin(self, u, make):
        from tkinter import messagebox
        who = u.get("email") or "?"
        q = tr("Give {w} admin rights? Admins see all accounts and error reports, can upload versions and approve modules.", w=who) if make \
            else tr("Take admin rights away from {w}?", w=who)
        if not messagebox.askyesno(tr("Permissions"), q):
            return
        self._perm_call("jopml_admin_set_admin", {"p_user": u["user_id"], "p_admin": bool(make)}, tr("Saved."))

    # ---- KI: Kosten pro Tag und Anbieter, Budget mit Warnung ab 80 %, Standard-Regeln
    def tab_ai(self, area, plugin):
        body = self.card(area, "AI usage and budget", 0)
        ui.muted(body, "What the AI chat and the help assistant used: tokens (or messages) per day and AI provider, for the last 14 days. The budget is the limit for ALL accounts together per day; "
                       "from 80 % you get a warning here and in the Overview, at 100 % the AI answers 'limit reached' until midnight (UTC), or the other AI takes over if it is set up. "
                       "Costs: both providers are used on their free plans, so there is no money to pay as long as you stay inside their free limits – the budget keeps you inside.").pack(fill="x", pady=(0, 6))
        self._ai_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED, wraplength=720, justify="left")
        self._ai_info.pack(fill="x")
        self._ai_bars = ctk.CTkFrame(body, fg_color="transparent")
        self._ai_bars.pack(fill="x", pady=4)
        self._ai_what = tk.StringVar(value="tokens")
        r = ui.row(body)
        r.pack(fill="x", pady=4)
        ctk.CTkButton(r, text="↻  " + tr("Refresh"), width=120, command=self.refresh_ai).pack(side="left")
        seg = ctk.CTkSegmentedButton(r, values=[tr("Tokens"), tr("Messages")], command=lambda _v: self._draw_chart())
        seg.set(tr("Tokens"))
        seg.pack(side="left", padx=10)
        self._ai_seg = seg
        self._ai_chart = ctk.CTkFrame(body, fg_color=theme.c("inset"), corner_radius=10)
        self._ai_chart.pack(fill="x", pady=6)
        self._ai_rows: list = []
        br = ui.row(body)
        br.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(br, text=tr("Budget per day (all accounts)"), anchor="w").pack(side="left", padx=(0, 8))
        self._bud_entries = {}
        for kind, label in (("requests", "Messages"), ("tokens", "Tokens")):
            ctk.CTkLabel(br, text=tr(label)).pack(side="left", padx=(8, 4))
            e = ctk.CTkEntry(br, width=110)
            e.pack(side="left")
            self._bud_entries[kind] = e
        ctk.CTkButton(br, text=tr("Save budget"), width=130, command=self._save_budget).pack(side="left", padx=10)
        ui.muted(body, "Empty or 'no limit' = no budget. Single accounts are limited by the standard rules below.").pack(fill="x", pady=(2, 0))
        self._budget: dict = {}

        body = self.card(area, "AI limits (standard for everyone)", 2)
        ui.muted(body, "Standard rules for all accounts: how many AI messages per day, how long one answer may be (tokens) and how many tokens one account may use per day "
                       "(help assistant and AI chat share them). For every value you can type a number, press 'Maximum' (largest value the system allows) or 'No limit'. "
                       "Note: a single answer is always capped technically at 16 384 tokens.").pack(fill="x", pady=(0, 6))
        self._def_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED, wraplength=720, justify="left")
        self._def_info.pack(fill="x")
        self._def_box = ctk.CTkFrame(body, fg_color="transparent")
        self._def_box.pack(fill="x", pady=4)
        self._defaults: dict = {}
        self._def_entries: dict = {}
        for kind, (label, _top) in logic.LIMIT_KINDS.items():
            row = ctk.CTkFrame(self._def_box, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=tr(label), width=210, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, width=120)
            e.pack(side="left")
            self._def_entries[kind] = e
            ctk.CTkButton(row, text=tr("Maximum"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda k=kind: self._fill(self._def_entries[k], logic.LIMIT_KINDS[k][1])).pack(side="left", padx=(6, 2))
            ctk.CTkButton(row, text=tr("No limit"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda k=kind: self._fill(self._def_entries[k], logic.UNLIMITED)).pack(side="left", padx=2)
        ctk.CTkButton(body, text=tr("Save standard"), width=160, command=self._save_defaults).pack(anchor="w", pady=6)

        self.refresh_ai()

    def refresh_ai(self):
        self._load(self._ai_bars, lambda: (self.plugin.rpc("jopml_admin_ai_budget"), self.plugin.rpc("jopml_admin_ai_stats", {"p_days": 14})), self._show_ai)
        self._load(self._def_box, lambda: self.plugin.rpc("jopml_admin_ai_defaults"), self._show_defaults)

    def _show_ai(self, res, err):
        for w in self._ai_bars.winfo_children():
            w.destroy()
        if err:
            self._ai_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        bud, rows = res
        b = (bud[0] if isinstance(bud, list) and bud else bud) or {}
        self._budget, self._ai_rows = b, rows if isinstance(rows, list) else []
        warn = logic.budget_warning(b, tr)
        fb = logic.fallback_total(self._ai_rows)
        self._ai_info.configure(text=(("⚠ " + warn + "  ") if warn else "") + tr("Automatic switches to the other AI in 14 days: {n}", n=fb),
                                text_color=COLORS["warn"] if warn else theme.MUTED)
        for used_k, bud_k, label in (("requests_today", "requests_budget", "Messages today"), ("tokens_today", "tokens_budget", "Tokens today")):
            frac, st = logic.budget_state(b.get(used_k), b.get(bud_k))
            row = ctk.CTkFrame(self._ai_bars, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=tr(label), width=150, anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(row, width=300)
            bar.set(min(1.0, frac))
            bar.configure(progress_color=COLORS["bad"] if st == "full" else COLORS["warn"] if st == "warn" else COLORS["ok"])
            bar.pack(side="left", padx=8)
            bv = b.get(bud_k)
            ctk.CTkLabel(row, text=f"{int(b.get(used_k) or 0):,}".replace(",", ".") + " / " + (tr("no limit") if bv is None or int(bv) < 0 else f"{int(bv):,}".replace(",", ".")),
                         text_color=theme.MUTED).pack(side="left")
        for kind, key in (("requests", "requests_budget"), ("tokens", "tokens_budget")):
            e = self._bud_entries[kind]
            e.delete(0, "end")
            v = b.get(key)
            e.insert(0, "no limit" if v is None or int(v) < 0 else str(v))
        self._draw_chart()

    def _draw_chart(self):
        for w in self._ai_chart.winfo_children():
            w.destroy()
        field = "tokens" if self._ai_seg.get() == tr("Tokens") else "hits"
        labels, series = logic.chart_series(self._ai_rows, 14, field)
        if not series:
            ctk.CTkLabel(self._ai_chart, text=tr("No AI usage recorded yet."), text_color=theme.MUTED).pack(padx=12, pady=16)
            return
        totals = [sum(v[i] for v in series.values()) for i in range(len(labels))]
        top = max(totals) or 1
        height = 110
        cols = ctk.CTkFrame(self._ai_chart, fg_color="transparent")
        cols.pack(fill="x", padx=12, pady=(10, 2))
        for i, day in enumerate(labels):
            col = ctk.CTkFrame(cols, fg_color="transparent", width=34, height=height + 16)
            col.pack(side="left", padx=2)
            col.pack_propagate(False)
            ctk.CTkLabel(col, text=day[8:] + "." + day[5:7], font=ctk.CTkFont(size=9), text_color=theme.MUTED).pack(side="bottom")
            for prov, vals in series.items():
                h = int(height * vals[i] / top)
                if h > 0:
                    ctk.CTkFrame(col, fg_color=logic.PROVIDER_COLORS.get(prov, "#9ca3af"), width=24, height=h, corner_radius=2).pack(side="bottom")
        leg = ctk.CTkFrame(self._ai_chart, fg_color="transparent")
        leg.pack(fill="x", padx=12, pady=(0, 8))
        for prov, vals in series.items():
            ctk.CTkLabel(leg, text="■", text_color=logic.PROVIDER_COLORS.get(prov, "#9ca3af")).pack(side="left")
            ctk.CTkLabel(leg, text=f"{prov.capitalize()}: {sum(vals):,}".replace(",", "."), text_color=theme.MUTED).pack(side="left", padx=(2, 12))

    def _save_budget(self):
        vals = {}
        for kind, e in self._bud_entries.items():
            t = e.get().strip().lower().replace(".", "").replace(" ", "")
            if t in ("", "nolimit", "none", "-1"):
                vals[kind] = -1
            elif t.isdigit() and int(t) <= (1_000_000 if kind == "requests" else 10_000_000_000):
                vals[kind] = int(t)
            else:
                self._ai_info.configure(text=tr("Enter a whole number or 'no limit'."), text_color=theme.DANGER)
                return
        self._perm_call("jopml_admin_set_ai_budget", {"p_requests": vals["requests"], "p_tokens": vals["tokens"]}, tr("Saved."), self._ai_info, self.refresh_ai)

    # ---- Fehler-Tickets: eine Fehlergruppe wird zu einem Ticket mit Status (neu / in Arbeit / behoben)
    def tab_tickets(self, area, plugin):
        body = self.card(area, "Error tickets", 0)
        ui.muted(body, "A ticket collects one problem: create it from a group in 'Automatic errors' (the button 'Create ticket'). Reports from players with the same error code are linked "
                       "automatically; you can link others by hand in 'User reports'. Set the status New → In progress → Fixed. When a ticket is Fixed, the players who reported it "
                       "see 'Fixed' in their report list.").pack(fill="x", pady=(0, 6))
        self._tk_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED, wraplength=720, justify="left")
        self._tk_info.pack(fill="x")
        ctk.CTkButton(body, text="↻  " + tr("Refresh"), width=120, command=self.refresh_tickets).pack(anchor="w", pady=6)
        self._tk_box = ctk.CTkFrame(body, fg_color="transparent")
        self._tk_box.pack(fill="x")
        self._tickets: list = []
        self.refresh_tickets()

    def refresh_tickets(self):
        self._load(self._tk_box, lambda: self.plugin.rpc("jopml_admin_tickets"), self._show_tickets)

    def _show_tickets(self, rows, err):
        for w in self._tk_box.winfo_children():
            w.destroy()
        if err:
            self._tk_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        rows = rows or []
        self._tickets = rows
        c = logic.ticket_counts(rows)
        self._tk_info.configure(text=(tr("{a} new · {b} in progress · {c} fixed", a=c["new"], b=c["in_progress"], c=c["fixed"]) if rows else tr("No tickets yet.")), text_color=theme.MUTED)
        for t in rows:
            card = ctk.CTkFrame(self._tk_box, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=3)
            st = t.get("status") if t.get("status") in logic.TICKET_STATUS else "new"
            head = f"#{t.get('id')}  {t.get('code') or '–'}  ·  {tr(logic.TICKET_STATUS[st])}  ·  {tr('{n} reports', n=t.get('reports') or 0)}  ·  {tr('{t} ago', t=logic.fmt_ago(t.get('updated_at')))}"
            ctk.CTkLabel(card, text=head, anchor="w", text_color=COLORS["ok"] if st == "fixed" else COLORS["warn"] if st == "in_progress" else theme.MUTED).pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=t.get("title") or "", anchor="w", justify="left", wraplength=640).pack(fill="x", padx=10)
            note = ctk.CTkEntry(card, placeholder_text=tr("Note (what you found / what you changed)"))
            if t.get("note"):
                note.insert(0, t["note"])
            note.pack(fill="x", padx=10, pady=4)
            br = ctk.CTkFrame(card, fg_color="transparent")
            br.pack(fill="x", padx=6, pady=(0, 6))
            for key, label in logic.TICKET_STATUS.items():
                ctk.CTkButton(br, text=tr(label), width=110, height=26, fg_color=theme.accent() if key == st else theme.c("hover"),
                              text_color="white" if key == st else theme.TEXT,
                              command=lambda i=t.get("id"), k=key, n=note: self._ticket_set(i, k, n.get())).pack(side="left", padx=3)

    def _ticket_set(self, tid, status, note):
        self._perm_call("jopml_admin_ticket_set", {"p_id": tid, "p_status": status, "p_note": note or None}, tr("Saved."), self._tk_info, self.refresh_tickets)

    def create_ticket(self, g):
        self._perm_call("jopml_admin_ticket_from_group", {"p_fingerprint": g.get("fingerprint"), "p_title": logic.ticket_title(g)},
                        tr("Ticket created. See the tab 'Tickets'."), self._err_info, self.refresh_errors)

    # ---- Meldungen von Nutzern (Knopf "Report")
    def tab_reports(self, area, plugin):
        body = self.card(area, "User reports", 0)
        ui.muted(body, "Messages that players sent with the 'Report' button or from an error window. Shown with category, error code, version and the account's e-mail. "
                       "Reports older than 180 days are deleted automatically.").pack(fill="x", pady=(0, 6))
        self._rep_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED)
        self._rep_info.pack(fill="x")
        r = ui.row(body)
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text="↻  " + tr("Refresh"), width=120, command=self.refresh_reports).pack(side="left")
        ctk.CTkButton(r, text=tr("Delete all"), width=120, fg_color="#c0392b", hover_color="#962d22",
                      command=lambda: self._clear("reports", self._rep_info, self.refresh_reports)).pack(side="left", padx=8)
        self._rep_box = ctk.CTkFrame(body, fg_color="transparent")
        self._rep_box.pack(fill="x")
        self.refresh_reports()

    def refresh_reports(self):
        self._load(self._rep_box, lambda: self.plugin.rpc("jopml_admin_user_reports", {"p_limit": 200}), self._show_reports)

    def _show_reports(self, rows, err):
        for w in self._rep_box.winfo_children():
            w.destroy()
        if err:
            self._rep_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        rows = rows or []
        cats: dict = {}
        for x in rows:
            cats[x.get("category") or "?"] = cats.get(x.get("category") or "?", 0) + 1
        self._rep_info.configure(text=(tr("{n} reports (newest first).", n=len(rows)) + "  " + " · ".join(f"{tr(logic.REPORT_CATEGORIES.get(k, k))}: {v}" for k, v in cats.items()))
                                 if rows else tr("No user reports. 🎉"), text_color=theme.MUTED)
        for x in rows:
            card = ctk.CTkFrame(self._rep_box, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=3)
            head = (f"[{tr(logic.REPORT_CATEGORIES.get(x.get('category'), x.get('category') or '?'))}]  {x.get('code') or ''}  v{x.get('version') or '?'} · "
                    f"{x.get('os') or '?'} · {x.get('email') or '–'} · {tr('{t} ago', t=logic.fmt_ago(x.get('created_at')))}")
            ctk.CTkLabel(card, text=head, anchor="w", text_color=theme.MUTED, wraplength=640, justify="left").pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=x.get("message") or "", anchor="w", justify="left", wraplength=640).pack(fill="x", padx=10)
            if x.get("context"):
                ctk.CTkLabel(card, text=tr("Context") + ": " + str(x["context"]), anchor="w", text_color=theme.MUTED, wraplength=640, justify="left").pack(fill="x", padx=10)
            if x.get("ticket_id"):
                st = x.get("ticket_status") if x.get("ticket_status") in logic.TICKET_STATUS else "new"
                ctk.CTkLabel(card, text=f"🎫 #{x['ticket_id']} · {tr(logic.TICKET_STATUS[st])}", anchor="w", text_color=theme.accent()).pack(fill="x", padx=10)
            if x.get("reply"):
                ctk.CTkLabel(card, text="↩ " + tr("Your reply") + ": " + x["reply"], anchor="w", justify="left", wraplength=640, text_color=COLORS["ok"]).pack(fill="x", padx=10)
            br = ctk.CTkFrame(card, fg_color="transparent")
            br.pack(fill="x", padx=6, pady=(2, 6))
            ctk.CTkButton(br, text="↩ " + tr("Reply …"), width=100, height=24, command=lambda r=x: self._reply_dialog(r)).pack(side="left", padx=2)
            ctk.CTkButton(br, text="🎫 " + tr("Link to ticket …"), width=140, height=24, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda r=x: self._link_dialog(r)).pack(side="left", padx=2)
            ctk.CTkButton(br, text=tr("Delete"), width=80, height=24, fg_color="transparent", text_color=theme.DANGER, hover_color=theme.c("hover"),
                          command=lambda i=x.get("id"): self._clear("report", self._rep_info, self.refresh_reports, i)).pack(side="left", padx=2)

    def _reply_dialog(self, r):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Reply to the reporter"))
        top.geometry("520x320")
        top.transient(self.winfo_toplevel())
        ui.muted(top, "The player sees your answer in 'Report' > 'My reports'. Write short and friendly; do not include private data.", wrap=480).pack(fill="x", padx=16, pady=(14, 6))
        box = ctk.CTkTextbox(top, wrap="word")
        box.pack(fill="both", expand=True, padx=16)
        if r.get("reply"):
            box.insert("1.0", r["reply"])
        msg = ctk.CTkLabel(top, text="", anchor="w", text_color=theme.DANGER)
        msg.pack(fill="x", padx=16)

        def send():
            text = box.get("1.0", "end").strip()
            if len(text) < 2:
                msg.configure(text=tr("Please write an answer."))
                return
            top.destroy()
            self._perm_call("jopml_admin_report_reply", {"p_report": r.get("id"), "p_text": text[:1000]}, tr("Reply sent."), self._rep_info, self.refresh_reports)
        ctk.CTkButton(top, text=tr("Send reply"), width=150, command=send).pack(pady=10)

    def _link_dialog(self, r):
        def work():
            try:
                tickets = self.plugin.rpc("jopml_admin_tickets") or []
            except Exception as exc:
                self.app.call_soon(self._rep_info.configure, text=tr(logic.friendly_rpc_error(str(exc))), text_color=theme.DANGER)
                return
            self.app.call_soon(self._link_dialog_show, r, [t for t in tickets if t.get("status") != "fixed"])
        threading.Thread(target=work, daemon=True).start()

    def _link_dialog_show(self, r, tickets):
        if not tickets:
            self._rep_info.configure(text=tr("There is no open ticket. Create one from a group in 'Automatic errors' first."), text_color=theme.DANGER)
            return
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Link to ticket"))
        top.geometry("520x200")
        top.transient(self.winfo_toplevel())
        names = {f"#{t['id']} {(t.get('code') or '–')} – {(t.get('title') or '')[:50]}": t["id"] for t in tickets}
        pick = ctk.CTkOptionMenu(top, values=list(names), width=470)
        pick.pack(padx=16, pady=(20, 10))

        def link():
            top.destroy()
            self._perm_call("jopml_admin_report_link", {"p_report": r.get("id"), "p_ticket": names[pick.get()]}, tr("Saved."), self._rep_info, self.refresh_reports)
        ctk.CTkButton(top, text=tr("Link"), width=130, command=link).pack()

    def _clear(self, what, label, then, ident=None):
        def work():
            try:
                self.plugin.rpc("jopml_admin_clear_reports", {"p_what": what, "p_id": ident})
                self.app.call_soon(then)
            except Exception as exc:
                self.app.call_soon(label.configure, text=tr(logic.friendly_rpc_error(str(exc))), text_color=theme.DANGER)
        threading.Thread(target=work, daemon=True).start()

    # ---- Automatische Fehler (komprimiert: eine Zeile je Fehlergruppe)
    def tab_errors(self, area, plugin):
        body = self.card(area, "Automatic errors", 0)
        ui.muted(body, "Errors the program noticed by itself (crashes, failed module uploads or imports, update and AI problems), grouped by error code and text: "
                       "one line per group with count, first/last time, versions and systems. 'Analyze with AI' lets Gemini/Groq explain likely causes and fixes "
                       "(only the shortened, cleaned group texts are sent, never account data).").pack(fill="x", pady=(0, 6))
        self._err_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED, wraplength=700, justify="left")
        self._err_info.pack(fill="x")
        r = ui.row(body)
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text="↻  " + tr("Refresh"), width=120, command=self.refresh_errors).pack(side="left")
        ctk.CTkButton(r, text="🤖  " + tr("Analyze top errors with AI"), width=230, command=self.analyze_all).pack(side="left", padx=8)
        ctk.CTkButton(r, text=tr("Delete all"), width=120, fg_color="#c0392b", hover_color="#962d22",
                      command=lambda: self._clear("groups", self._err_info, self.refresh_errors)).pack(side="left")
        self._err_ai = ctk.CTkTextbox(body, height=0, wrap="word")
        self._err_box = ctk.CTkFrame(body, fg_color="transparent")
        self._err_box.pack(fill="x")
        self._groups: list = []
        self.refresh_errors()

    def refresh_errors(self):
        self._load(self._err_box, lambda: self.plugin.rpc("jopml_admin_error_groups", {"p_limit": 200}), self._show_errors)

    def _show_errors(self, rows, err):
        for w in self._err_box.winfo_children():
            w.destroy()
        if err:
            self._err_info.configure(text=tr(logic.friendly_rpc_error(err)), text_color=theme.DANGER)
            return
        rows = sorted(rows or [], key=lambda g: -int(g.get("hits") or 0))
        self._groups = rows
        n, hits, top, ver = logic.summary_parts(rows)
        self._err_info.configure(text=(tr("{n} groups · {h} occurrences · top: {top} · most affected version: {v}", n=n, h=hits, top=top, v=ver or "–")
                                       if rows else tr("No error reports. 🎉")), text_color=theme.MUTED)
        for g in rows:
            card = ctk.CTkFrame(self._err_box, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=3)
            vers = ", ".join(f"{k} ×{v}" for k, v in logic.top_counts([g], "versions", 3))
            syst = ", ".join(f"{k} ×{v}" for k, v in logic.top_counts([g], "systems", 2))
            head = (f"{g.get('code') or '–'}  [{g.get('kind') or '?'}]  ×{g.get('hits')}  ·  "
                    f"{tr('first {t} ago', t=logic.fmt_ago(g.get('first_seen')))}  ·  {tr('last {t} ago', t=logic.fmt_ago(g.get('last_seen')))}")
            ctk.CTkLabel(card, text=head, anchor="w", text_color=theme.MUTED, wraplength=640, justify="left").pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=g.get("message") or "", anchor="w", justify="left", wraplength=640).pack(fill="x", padx=10)
            ctk.CTkLabel(card, text=f"v: {vers}  ·  {syst}", anchor="w", text_color=theme.MUTED, wraplength=640, justify="left").pack(fill="x", padx=10)
            if g.get("analysis"):
                ctk.CTkLabel(card, text="🤖 " + g["analysis"], anchor="w", justify="left", wraplength=640, text_color=theme.accent()).pack(fill="x", padx=10, pady=(2, 0))
            br = ctk.CTkFrame(card, fg_color="transparent")
            br.pack(fill="x", padx=6, pady=(2, 6))
            ctk.CTkButton(br, text="🤖 " + tr("Analyze with AI"), width=150, height=24, command=lambda x=g: self.analyze_group(x)).pack(side="left", padx=4)
            ctk.CTkButton(br, text="🎫 " + tr("Create ticket"), width=130, height=24, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda x=g: self.create_ticket(x)).pack(side="left", padx=4)
            tr_txt = g.get("sample_trace") or ""
            if tr_txt:
                lab = ctk.CTkLabel(card, text="", anchor="w", justify="left", wraplength=640, font=ctk.CTkFont(family="Consolas", size=10), text_color=theme.MUTED)
                btn = ctk.CTkButton(br, text=tr("Details"), width=80, height=24, fg_color="transparent", text_color=theme.accent(), hover_color=theme.c("hover"))

                def toggle(lab=lab, txt=tr_txt, br=br):
                    if lab.cget("text"):
                        lab.configure(text="")
                        lab.pack_forget()
                    else:
                        lab.configure(text=txt[-1500:])
                        lab.pack(fill="x", padx=10, after=br)
                btn.configure(command=toggle)
                btn.pack(side="left")

    def _analyze(self, groups, done, label_text=None):
        client = getattr(getattr(self.app, "identity", None), "client", None)
        if client is None or not getattr(client, "session", None):
            self._err_info.configure(text=tr("The AI analysis needs a cloud account."), text_color=theme.DANGER)
            return
        text = logic.groups_for_ai(groups)
        if not text:
            return
        self._err_info.configure(text=tr("The AI is analysing …"), text_color=theme.MUTED)
        from core.i18n import get_language

        def work():
            try:
                res = client.analyze_errors(text, get_language())
                self.app.call_soon(done, res.get("reply", ""), None)
            except Exception as exc:
                self.app.call_soon(done, None, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def analyze_group(self, g):
        def done(reply, err):
            if err or not reply:
                self._err_info.configure(text=tr(err or "Empty answer from the AI."), text_color=theme.DANGER)
                return

            def save():
                try:
                    self.plugin.rpc("jopml_admin_set_analysis", {"p_fingerprint": g["fingerprint"], "p_text": reply})
                except Exception:
                    pass
                self.app.call_soon(self.refresh_errors)
            threading.Thread(target=save, daemon=True).start()
        self._analyze([g], done)

    def analyze_all(self):
        def done(reply, err):
            if err or not reply:
                self._err_info.configure(text=tr(err or "Empty answer from the AI."), text_color=theme.DANGER)
                return
            self._err_info.configure(text=tr("AI analysis of the top errors:"), text_color=theme.MUTED)
            self._err_ai.configure(height=260)
            self._err_ai.pack(fill="x", pady=6, before=self._err_box)
            self._err_ai.configure(state="normal")
            self._err_ai.delete("1.0", "end")
            self._err_ai.insert("1.0", reply)
            self._err_ai.configure(state="disabled")
        self._analyze(self._groups, done)

    # ---- Veröffentlichen (bestehende Seite als Reiter)
    def _publish_page(self, hub, plugin):
        from modules.publisher.page import PublisherPage
        pub = self.app.plugin_by_id.get("publisher") or plugin
        return PublisherPage(hub, pub)
