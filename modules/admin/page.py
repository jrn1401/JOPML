"""Admin-Seite: Reiter Übersicht, Konten, Fehler, Veröffentlichen."""
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
                         "Server overview, accounts, error reports and publishing. Only visible for admin accounts.", [
            ("Overview", self.tab_overview), ("Accounts", self.tab_accounts), ("Errors", self.tab_errors),
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

    # ---- Fehler
    def tab_errors(self, area, plugin):
        body = self.card(area, "Error reports", 0)
        self._err_info = ctk.CTkLabel(body, text="…", anchor="w", text_color=theme.MUTED)
        self._err_info.pack(fill="x")
        r = ui.row(body)
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text="↻  " + tr("Refresh"), width=120, command=self.refresh_errors).pack(side="left")
        ctk.CTkButton(r, text=tr("Delete all"), width=120, fg_color="#c0392b", hover_color="#962d22", command=self.clear_errors).pack(side="left", padx=8)
        self._err_box = ctk.CTkFrame(body, fg_color="transparent")
        self._err_box.pack(fill="x")
        self.refresh_errors()

    def refresh_errors(self):
        self._load(self._err_box, lambda: self.plugin.rpc("jopml_admin_errors", {"p_limit": 100}), self._show_errors)

    def clear_errors(self):
        self._load(self._err_box, lambda: self.plugin.rpc("jopml_admin_clear_errors"), lambda r, e: self.refresh_errors())

    def _show_errors(self, rows, err):
        for w in self._err_box.winfo_children():
            w.destroy()
        if err:
            self._err_info.configure(text=err, text_color=theme.DANGER)
            return
        rows = rows or []
        self._err_info.configure(text=tr("{n} reports (newest first).", n=len(rows)) if rows else tr("No error reports. 🎉"), text_color=theme.MUTED)
        for e in rows:
            card = ctk.CTkFrame(self._err_box, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=3)
            head = f"[{e.get('kind') or '?'}]  v{e.get('version') or '?'} · {e.get('os') or '?'} · {tr('{t} ago', t=logic.fmt_ago(e.get('created_at')))}"
            ctk.CTkLabel(card, text=head, anchor="w", text_color=theme.MUTED).pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=e.get("message") or "", anchor="w", justify="left", wraplength=600).pack(fill="x", padx=10)
            tr_txt = e.get("trace") or ""
            if tr_txt:
                lab = ctk.CTkLabel(card, text="", anchor="w", justify="left", wraplength=600, font=ctk.CTkFont(family="Consolas", size=10), text_color=theme.MUTED)
                btn = ctk.CTkButton(card, text=tr("Details"), width=80, height=22, fg_color="transparent", text_color=theme.accent(), hover_color=theme.c("hover"))

                def toggle(lab=lab, btn=btn, txt=tr_txt):
                    if lab.cget("text"):
                        lab.configure(text="")
                        lab.pack_forget()
                    else:
                        lab.configure(text=txt[-1500:])
                        lab.pack(fill="x", padx=10, after=btn)
                btn.configure(command=toggle)
                btn.pack(anchor="w", padx=6, pady=(0, 6))

    # ---- Veröffentlichen (bestehende Seite als Reiter)
    def _publish_page(self, hub, plugin):
        from modules.publisher.page import PublisherPage
        pub = self.app.plugin_by_id.get("publisher") or plugin
        return PublisherPage(hub, pub)
