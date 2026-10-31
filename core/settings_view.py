"""Einstellungen in Bereichen: Konto, Aussehen, Sprache, System, Leistung, Rechtliches & Quellen.
Jeder Bereich wird erst beim Öffnen aufgebaut (spart Speicher und Startzeit)."""
import datetime
import json
from pathlib import Path
import threading
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk

from core.tabbar import WrapTabs

from core import accounts, appicon, background, config, i18n, layout, shortcuts, system_limits, theme, ui
from core.account_backup_ui import restore_account_file
from core.credits import CREDITS
from core.i18n import LANGS, tr
from core.identity import REMEMBER_CHOICES
from core.legal_text import legal_text
from core.login_view import days_to_setting, default_days, remember_label, remember_value
from core.version import APP_NAME, APP_VERSION, LEGAL_VERSION

SCALES = [80, 90, 100, 110, 125, 150]
SECTIONS = ["Account", "Appearance", "Layout", "Language", "System", "Notifications", "Hotkeys", "Performance", "Legal & sources"]
class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ui.page_title(self, "Settings").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        self.seg = WrapTabs(self, [tr(s) for s in SECTIONS], self._open)
        self.seg.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 2))
        self.area = None
        start = app.settings_section if app.settings_section in SECTIONS else "Account"
        self.seg.set(tr(start))
        self._open(tr(start))

    def _open(self, label):
        name = next((s for s in SECTIONS if tr(s) == label), "Account")
        self.app.settings_section = name
        if self.area is not None:
            self.area.destroy()
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
        self.area.grid(row=2, column=0, sticky="nsew")
        self.area.columnconfigure(0, weight=1)
        self._row = 0
        getattr(self, "_s_" + {"Legal & sources": "legal"}.get(name, name.lower()))()

    # ---------- Bausteine
    def _card(self, title):
        c = ui.card(self.area, title)
        c.grid(row=self._row, column=0, sticky="ew", padx=24, pady=6)
        self._row += 1
        body = ctk.CTkFrame(c, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    @staticmethod
    def _field(parent, label, value="", secret=False, width=260, lw=170):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=label, width=lw, anchor="w").pack(side="left")
        e = ctk.CTkEntry(r, width=width, show="•" if secret else "")
        e.pack(side="left")
        if value:
            e.insert(0, value)
        return e

    def _msg(self, parent):
        lab = ctk.CTkLabel(parent, text="", anchor="w", justify="left", wraplength=620)
        lab.pack(fill="x", pady=(4, 0))
        return lab

    @staticmethod
    def _say(label, text, ok=True):
        if label.winfo_exists():
            label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _me(self):
        return self.app.user

    def _threaded(self, work, done, label):
        def run():
            try:
                res, err = work(), None
            except accounts.AccountError as exc:
                res, err = None, str(exc)
            except Exception as exc:
                res, err = None, f"{type(exc).__name__}: {exc}"
            self.app.call_soon(lambda: self.winfo_exists() and (self._say(label, tr(err), False) if err else done(res)))
        threading.Thread(target=run, daemon=True).start()

    # ======================= Konto =======================
    def _s_account(self):
        me, ident = self._me(), self.app.identity
        body = self._card("Profile")
        where = tr("Cloud account (Supabase, encrypted)") if me.get("backend") == "cloud" else tr("Local account (only on this computer)")
        ui.muted(body, "{u}  ·  {w}", u=me["username"] or "Google", w=where).pack(fill="x", pady=(0, 6))
        self.e_display = self._field(body, tr("Display name"), me["display_name"])
        self.e_mail = self._field(body, tr("E-mail (optional)"), me["email"])
        ui.muted(body, "E-mail and real name are optional. Leave the e-mail empty to stay anonymous.").pack(fill="x")
        self.m_prof = self._msg(body)
        ctk.CTkButton(body, text=tr("Save"), width=120, command=self._save_profile).pack(anchor="w", pady=(4, 0))

        body = self._card("Password")
        ui.banner(body, "🔒 " + tr("The password cannot be changed after the account has been created (security rule). "
                                   "There is no recovery – if you lose it, create a new account."), color="#92400e").pack(fill="x")

        if me.get("backend") == "local" and me.get("has_password"):
            body = self._card("Account backup")
            ui.muted(body, "Save your local account in an encrypted file (protected by a passphrase you choose) to move it to another computer or restore it after a reinstall. "
                           "The backup does not contain your password in readable form and cannot bring back a forgotten password.").pack(fill="x", pady=(0, 6))
            self.m_acc_bak = self._msg(body)
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x")
            ctk.CTkButton(r, text=tr("Save account backup …"), width=190, command=self._account_backup_save).pack(side="left")
            ctk.CTkButton(r, text=tr("Restore account backup …"), width=200, command=self._account_backup_restore).pack(side="left", padx=8)

        body = self._card("Stay signed in")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkLabel(r, text=tr("Default duration"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=[tr(l) for l, _ in REMEMBER_CHOICES], width=190, command=self._set_remember)
        om.set(remember_label(default_days(self.app.settings)))
        om.pack(side="left")

        if ident.supports_2fa:
            body = self._card("Two-factor sign-in (2FA)")
            self.f2fa = ctk.CTkFrame(body, fg_color="transparent")
            self.f2fa.pack(fill="x")
            self.store = self.app.accounts
            self._render_2fa()

        body = self._card("Your data")
        ui.muted(body, "You can download everything stored about you, or delete the account for good.").pack(fill="x", pady=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkButton(r, text=tr("Export my data"), width=170, command=self._export).pack(side="left")
        self.e_del = self._field(body, tr("Password (to delete)"), secret=True) if me.get("has_password") and me.get("backend") == "local" else None
        self.m_del = self._msg(body)
        ctk.CTkButton(body, text=tr("Delete account"), width=170, fg_color="#b91c1c", hover_color="#7f1d1d",
                      command=self._delete_account).pack(anchor="w", pady=(6, 0))

    def _set_remember(self, label):
        self.app.settings["remember"] = days_to_setting(remember_value(label))
        self.app.save_settings()

    def _save_profile(self):
        d, m = self.e_display.get(), self.e_mail.get()
        me = self._me()

        def done(user):
            self.app.user = user
            self.app.refresh_user_labels()
            self._say(self.m_prof, tr("Saved."))
        self._threaded(lambda: self.app.identity.update_profile(me, d, m), done, self.m_prof)

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="jopml-data.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return

        def done(data):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            self._say(self.m_del, tr("Exported."))
        self._threaded(lambda: self.app.identity.export(self._me()), done, self.m_del)

    def _delete_account(self):
        if not messagebox.askyesno(tr("Delete account"), tr("Your account will be deleted permanently. This cannot be undone.\nContinue?")):
            return
        pw = self.e_del.get() if self.e_del else ""
        me = self._me()
        self._threaded(lambda: self.app.identity.delete(me, pw), lambda _: self.app.logout(forget=False), self.m_del)

    # ---- 2FA (nur lokale Konten)
    def _render_2fa(self, secret=None):
        for w in self.f2fa.winfo_children():
            w.destroy()
        me = self._me()
        self.m_2fa = self._msg(self.f2fa)
        if me["totp_enabled"]:
            ctk.CTkLabel(self.f2fa, text="✔ " + tr("2FA is active."), text_color=theme.OK, anchor="w").pack(fill="x")
            self.e_2fa_pw = self._field(self.f2fa, tr("Password"), secret=True) if me["has_password"] else None
            ctk.CTkButton(self.f2fa, text=tr("Turn off 2FA"), width=160, fg_color="gray35", hover_color="gray25",
                          command=self._disable_2fa).pack(anchor="w", pady=(4, 0))
        elif secret:
            pretty = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
            ctk.CTkLabel(self.f2fa, anchor="w", justify="left", wraplength=600,
                         text=tr("1. Open an authenticator app.\n2. Choose 'Enter key manually' and type this key:")).pack(fill="x")
            key = ctk.CTkEntry(self.f2fa, width=420, font=ctk.CTkFont(family="Consolas", size=15))
            key.insert(0, pretty)
            key.configure(state="readonly")
            key.pack(anchor="w", pady=4)
            ctk.CTkButton(self.f2fa, text=tr("Copy key"), width=160, command=lambda: self._copy(secret)).pack(anchor="w", pady=(0, 6))
            self.e_2fa_code = self._field(self.f2fa, tr("6-digit code"))
            r = ctk.CTkFrame(self.f2fa, fg_color="transparent")
            r.pack(anchor="w", pady=(4, 0))
            ctk.CTkButton(r, text=tr("Confirm"), width=120, command=self._confirm_2fa).pack(side="left")
            ctk.CTkButton(r, text=tr("Cancel"), width=120, fg_color="gray35", hover_color="gray25",
                          command=self._render_2fa).pack(side="left", padx=8)
        else:
            ui.muted(self.f2fa, "Protects your account additionally with a code from an authenticator app.").pack(fill="x")
            ctk.CTkButton(self.f2fa, text=tr("Set up 2FA"), width=160, command=self._start_2fa).pack(anchor="w", pady=(6, 0))

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._say(self.m_2fa, tr("Copied."))

    def _start_2fa(self):
        try:
            self._render_2fa(self.store.begin_totp(self._me()["username"]))
        except accounts.AccountError as exc:
            self._say(self.m_2fa, tr(str(exc)), False)

    def _confirm_2fa(self):
        try:
            self.store.confirm_totp(self._me()["username"], self.e_2fa_code.get())
        except accounts.AccountError as exc:
            self._say(self.m_2fa, tr(str(exc)), False)
            return
        self.app.user = self.store.public(self.store.users[self._me()["username"]])
        self._render_2fa()
        self._say(self.m_2fa, tr("2FA is now active. The code is asked at the next sign-in."))

    def _disable_2fa(self):
        pw = self.e_2fa_pw.get() if self.e_2fa_pw else ""

        def done(_):
            self.app.user = self.store.public(self.store.users[self._me()["username"]])
            self._render_2fa()
            self._say(self.m_2fa, tr("2FA was turned off."))
        self._threaded(lambda: self.store.disable_totp(self._me()["username"], pw), done, self.m_2fa)

    # ======================= Aussehen =======================
    def _s_appearance(self):
        s = self.app.settings
        body = self._card("Theme")
        iv = tk.BooleanVar(value=bool(s.get("colored_icons", True)))
        ctk.CTkSwitch(body, text=tr("Coloured menu icons (e.g. yellow ⚡ for Productivity)"), variable=iv,
                      command=lambda: self.app.apply_look({"colored_icons": iv.get()})).pack(anchor="w", pady=(0, 6))
        hv = tk.BooleanVar(value=bool(s.get("hover_effect", True)))
        ctk.CTkSwitch(body, text=tr("Highlight modules when the mouse is over them"), variable=hv,
                      command=lambda: self.app.apply_look({"hover_effect": hv.get()})).pack(anchor="w", pady=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Mode"), width=170, anchor="w").pack(side="left")
        seg = ctk.CTkSegmentedButton(r, values=[tr(k) for k in theme.MODES],
                                     command=lambda lab: self.app.apply_look({"appearance_mode": next(v for k, v in theme.MODES.items() if tr(k) == lab)}))
        seg.set(tr(next((k for k, v in theme.MODES.items() if v == s["appearance_mode"]), "Dark")))
        seg.pack(side="left")

        names = list(theme.PRESETS)
        for i in range(0, len(names), 4):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=tr("Presets") if i == 0 else "", width=170, anchor="w").pack(side="left")
            for name in names[i:i + 4]:
                ctk.CTkButton(r, text=tr(name), width=80, height=28, fg_color=theme.c("hover"), text_color=theme.TEXT,
                              command=lambda n=name: self._preset(n)).pack(side="left", padx=3)

        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkLabel(r, text=tr("Accent colour"), width=170, anchor="w").pack(side="left")
        for name, hx in theme.ACCENTS.items():
            ring = "white" if hx.lower() == s["accent"].lower() else hx
            ctk.CTkButton(r, text="✔" if ring == "white" else "", width=30, height=30, corner_radius=15, fg_color=hx,
                          hover_color=theme.shade(hx, 0.8), border_width=2, border_color=ring,
                          command=lambda h=hx: self.app.apply_look({"accent": h})).pack(side="left", padx=2)
        ctk.CTkButton(r, text=tr("Pick …"), width=70, height=30, command=lambda: self._pick("accent")).pack(side="left", padx=8)

        body = self._card("Your own colours (colour picker)")
        colors = s.get("colors") or {}
        defaults = {"main": theme.DEFAULT_PALETTE["main"][1], "sidebar": theme.DEFAULT_PALETTE["sidebar"][1],
                    "card": theme.DEFAULT_PALETTE["card"][1], "inset": theme.DEFAULT_PALETTE["inset"][1],
                    "hover": theme.DEFAULT_PALETTE["hover"][1], "text": "#e6e6e6"}
        for label, key in theme.COLOR_KEYS:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            cur = colors.get(key) or defaults[key]
            ctk.CTkButton(r, text="", width=44, height=26, fg_color=cur, hover_color=cur, border_width=1,
                          border_color="gray50", command=lambda k=key: self._pick(k)).pack(side="left")
            e = ctk.CTkEntry(r, width=100, placeholder_text="#rrggbb")
            e.insert(0, colors.get(key, ""))
            e.pack(side="left", padx=8)
            e.bind("<Return>", lambda _e, k=key, ent=e: self._set_hex(k, ent.get()))
            ctk.CTkButton(r, text=tr("Reset"), width=70, height=26, fg_color="gray35", hover_color="gray25",
                          command=lambda k=key: self._reset_color(k)).pack(side="left")
        self.m_look = self._msg(body)
        ctk.CTkButton(body, text=tr("Reset all colours"), width=170, fg_color="gray35", hover_color="gray25",
                      command=lambda: self._preset("Default")).pack(anchor="w", pady=(8, 0))

        body = self._card("App icon")
        self.icon_preview = ctk.CTkLabel(body, text="")
        self.icon_preview.pack(side="left", padx=(0, 16))
        col = ctk.CTkFrame(body, fg_color="transparent")
        col.pack(side="left", fill="x")
        ui.muted(col, "Change the background of the icon. The letters JOPML always stay visible.", wrap=440).pack(fill="x")
        r = ctk.CTkFrame(col, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text=tr("Background colour …"), width=170, command=lambda: self._pick("icon_bg")).pack(side="left")
        ctk.CTkButton(r, text=tr("Background image …"), width=170, command=self._icon_image).pack(side="left", padx=6)
        ctk.CTkButton(r, text=tr("Reset"), width=80, fg_color="gray35", hover_color="gray25",
                      command=self._icon_reset).pack(side="left")
        self._draw_icon_preview()

    def _preset(self, name):
        p = theme.PRESETS[name]
        self.app.apply_look({"appearance_mode": p["mode"], "accent": p["accent"], "colors": dict(p["colors"])})

    def _pick(self, key):
        s = self.app.settings
        start = {"accent": s["accent"], "icon_bg": s.get("icon_bg", "#4f8cff")}.get(key) or (s.get("colors") or {}).get(key)
        rgb, hx = colorchooser.askcolor(color=start if theme.is_hex(start) else None, parent=self, title=tr("Pick a colour"))
        if hx:
            self._set_hex(key, hx)

    def _set_hex(self, key, value):
        value = (value or "").strip()
        if value and not value.startswith("#"):
            value = "#" + value
        if not theme.is_hex(value):
            if hasattr(self, "m_look") and self.m_look.winfo_exists():
                self._say(self.m_look, tr("Please enter a colour like #4f8cff."), False)
            return
        value = value.lower()
        if key == "accent":
            self.app.apply_look({"accent": value})
        elif key == "icon_bg":
            self.app.settings["icon_bg"], self.app.settings["icon_image"] = value, ""
            self._apply_icon()
        else:
            colors = dict(self.app.settings.get("colors") or {})
            colors[key] = value
            self.app.apply_look({"colors": colors})

    def _reset_color(self, key):
        colors = dict(self.app.settings.get("colors") or {})
        colors.pop(key, None)
        self.app.apply_look({"colors": colors})

    def _icon_image(self):
        path = filedialog.askopenfilename(filetypes=[(tr("Images"), "*.png *.jpg *.jpeg *.bmp *.gif")])
        if path:
            self.app.settings["icon_image"] = path
            self._apply_icon()

    def _icon_reset(self):
        self.app.settings.update({"icon_bg": "#4f8cff", "icon_image": ""})
        self._apply_icon()

    def _apply_icon(self):
        self.app.save_settings()
        appicon.apply_to_window(self.app, self.app.settings)
        self._draw_icon_preview()

    def _draw_icon_preview(self):
        try:
            img = appicon.render(96, self.app.settings.get("icon_bg"), self.app.settings.get("icon_image") or None)
            self._icon_img = ctk.CTkImage(light_image=img, dark_image=img, size=(72, 72))
            self.icon_preview.configure(image=self._icon_img)
        except Exception as exc:
            self.icon_preview.configure(text=str(exc))

    # ======================= Layout =======================
    def _s_layout(self):
        app, s = self.app, self.app.settings
        body = self._card("Modules in the sidebar")
        ui.muted(body, "Choose which modules are shown and move them into any order. The dashboard and the settings always stay. "
                       "Hidden modules keep running in the background (e.g. their hotkeys); hiding only removes them from the menu.").pack(fill="x", pady=(0, 6))
        items = app.layout_items()
        ids = [i for i, _ in items]
        hidden = set(s.get("nav_hidden") or [])
        for n, (pid, label) in enumerate(items):
            r = ctk.CTkFrame(body, fg_color=theme.c("inset"), corner_radius=8)
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=label, anchor="w").pack(side="left", padx=12, pady=6)
            sw = ctk.CTkSwitch(r, text="", width=44)
            var = tk.BooleanVar(value=pid not in hidden)
            sw.configure(variable=var, command=lambda p=pid, v=var: app.set_layout(hidden=layout.set_hidden(s.get("nav_hidden"), p, not v.get())))
            sw.pack(side="right", padx=10)
            ctk.CTkButton(r, text="▼", width=30, height=26, state="normal" if n < len(items) - 1 else "disabled",
                          command=lambda p=pid: app.set_layout(order=layout.move(ids, s.get("nav_order"), p, 1))).pack(side="right", padx=2)
            ctk.CTkButton(r, text="▲", width=30, height=26, state="normal" if n > 0 else "disabled",
                          command=lambda p=pid: app.set_layout(order=layout.move(ids, s.get("nav_order"), p, -1))).pack(side="right", padx=2)
        ctk.CTkButton(body, text=tr("Reset layout"), width=150, fg_color="gray35", hover_color="gray25",
                      command=lambda: app.set_layout(order=[], hidden=[])).pack(anchor="w", pady=(8, 0))

        body = self._card("Your own background image")
        ui.muted(body, "The picture is shown as a banner at the top of every page. (Windows and macOS cannot place buttons on a "
                       "see-through picture, so it does not go behind the cards.) The picture stays on this computer.").pack(fill="x", pady=(0, 6))
        self.m_bg = self._msg(body)
        cur = s.get("bg_image") or ""
        ui.muted(body, "Current image: {p}", p=cur or tr("(none)")).pack(fill="x")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text=tr("Choose image …"), width=160, command=self._bg_choose).pack(side="left")
        ctk.CTkButton(r, text=tr("Remove image"), width=140, fg_color="gray35", hover_color="gray25",
                      command=self._bg_remove).pack(side="left", padx=6)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Darken"), width=170, anchor="w").pack(side="left")
        sl = ctk.CTkSlider(r, from_=0, to=layout.MAX_DIM, number_of_steps=layout.MAX_DIM // 5, width=240)
        sl.set(layout.clamp_dim(s.get("bg_dim")))
        sl.pack(side="left")
        sl.bind("<ButtonRelease-1>", lambda _e: self._bg_dim(sl.get()))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Banner height"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=[tr(k) for k in layout.HEIGHTS], width=140,
                               command=lambda lab: self._bg_height(next(k for k in layout.HEIGHTS if tr(k) == lab)))
        om.set(tr(s.get("bg_height") if s.get("bg_height") in layout.HEIGHTS else "Medium"))
        om.pack(side="left")

    def _bg_choose(self):
        path = filedialog.askopenfilename(filetypes=[(tr("Images"), "*.png *.jpg *.jpeg *.bmp *.gif *.webp")])
        if not path:
            return
        try:
            background.check(path)
        except background.BackgroundError as exc:
            self._say(self.m_bg, tr(str(exc)), False)
            return
        self.app.apply_look({"bg_image": path})

    def _bg_remove(self):
        self.app.apply_look({"bg_image": ""})

    def _bg_dim(self, value):
        self.app.apply_look({"bg_dim": layout.clamp_dim(value)})

    def _bg_height(self, name):
        self.app.apply_look({"bg_height": name})

    # ======================= Sprache =======================
    def _s_language(self):
        body = self._card("Language")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkLabel(r, text=tr("Language"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=list(LANGS.values()), width=190,
                               command=lambda lab: self.app.set_language(next(c for c, n in LANGS.items() if n == lab)))
        om.set(LANGS[i18n.get_language()])
        om.pack(side="left")
        ui.muted(body, "Menus and buttons are translated. The long legal text exists in German (authoritative) and English only.").pack(fill="x", pady=(8, 0))

    # ======================= System =======================
    def _s_system(self):
        body = self._card("Shortcut and autostart")
        self.m_sys = self._msg(body)
        v1 = tk.BooleanVar(value=self._safe(shortcuts.has_desktop_shortcut))
        v2 = tk.BooleanVar(value=self._safe(shortcuts.is_autostart))

        def toggle_short():
            try:
                shortcuts.create_desktop_shortcut() if v1.get() else shortcuts.remove_desktop_shortcut()
                self._say(self.m_sys, tr("Done."))
            except Exception as exc:
                v1.set(not v1.get())
                self._say(self.m_sys, str(exc), False)

        def toggle_auto():
            try:
                shortcuts.set_autostart(v2.get())
                self._say(self.m_sys, tr("Done."))
            except Exception as exc:
                v2.set(not v2.get())
                self._say(self.m_sys, str(exc), False)

        ctk.CTkSwitch(body, text=tr("Desktop shortcut"), variable=v1, command=toggle_short).pack(anchor="w", pady=4)
        ctk.CTkSwitch(body, text=tr("Start with the computer (autostart)"), variable=v2, command=toggle_auto).pack(anchor="w", pady=4)

        body = self._card("Interface size")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkLabel(r, text=tr("Size of the app"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=[f"{v} %" for v in SCALES], width=110, command=self._set_scale)
        om.set(f"{int(self.app.settings.get('ui_scale', 100))} %")
        om.pack(side="left")
        ui.muted(body, "Makes everything bigger or smaller. Only for this computer.").pack(fill="x", pady=(6, 0))

        body = self._card("Emergency stop")
        ui.muted(body, "Stops the autoclicker and macros at once – from anywhere, even when the launcher is in the background.").pack(fill="x")
        ctk.CTkLabel(body, text=tr("Shortcut") + ":  " + (self.app.settings.get("panic_hotkey") or ""), anchor="w",
                     font=ctk.CTkFont(family="Consolas", size=13)).pack(fill="x", pady=(6, 0))
        pk = self.app.panic_key
        err = pk.error if pk is not None else ""
        if err:
            ctk.CTkLabel(body, text=tr("The shortcut is not active:") + " " + err, text_color=theme.DANGER, anchor="w",
                         wraplength=560, justify="left").pack(fill="x", pady=(4, 0))
        ctk.CTkButton(body, text="■  " + tr("Emergency stop"), width=170, fg_color="#b91c1c", hover_color="#7f1d1d",
                      command=self.app.panic).pack(anchor="w", pady=(8, 0))

        body = self._card("Statistics")
        self._stats_body = body
        self._render_stats()

        body = self._card("Backup")
        ui.muted(body, "Saves your settings, macros and profiles in one file – for a new computer or as a safety copy. Passwords and keys are not included.").pack(fill="x", pady=(0, 6))
        self.m_bak = self._msg(body)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkButton(r, text=tr("Save backup …"), width=150, command=self._backup_save).pack(side="left")
        ctk.CTkButton(r, text=tr("Restore backup …"), width=150, command=self._backup_restore).pack(side="left", padx=8)

        self._import_card()

        body = self._card("About")
        ctk.CTkLabel(body, text=f"{APP_NAME}  ·  {tr('Version')} {APP_VERSION}", anchor="w").pack(fill="x")
        ui.muted(body, "Data folder: {p}", p=str(config.app_dir())).pack(fill="x", pady=(2, 8))
        ctk.CTkButton(body, text=tr("Check for updates"), width=170, command=lambda: self.app.check_updates(manual=True)).pack(anchor="w")

    # ---- Module aus Dateien importieren
    def _import_card(self):
        from core import module_import
        body = self._card("Import modules")
        ui.muted(body, "Add your own modules from a folder, a .zip file, a single .py file or by pasting code (a module needs a plugin.py with a class Plugin). "
                       "A module is program code and runs with all rights of this program: import only modules from sources you trust. "
                       "Imported modules are loaded at the next start and stay when the program is updated.").pack(fill="x", pady=(0, 6))
        msg = self._msg(body)
        listing = ctk.CTkFrame(body, fg_color="transparent")

        def render():
            for w in listing.winfo_children():
                w.destroy()
            for name in module_import.installed():
                row = ctk.CTkFrame(listing, fg_color=theme.c("inset"), corner_radius=8)
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", padx=10, pady=6)
                ctk.CTkButton(row, text=tr("Remove"), width=80, height=24, fg_color="gray35", hover_color="gray25",
                              command=lambda n=name: remove(n)).pack(side="right", padx=6)

        def remove(name):
            if messagebox.askyesno(tr("Remove module"), tr("Remove the module {n}? It disappears at the next start.", n=name)):
                module_import.remove_module(name)
                self._say(msg, tr("Module removed. Restart the program to finish."))
                render()

        def run_import(name, action):
            """Gemeinsamer Ablauf für Datei, Ordner und eingefügten Code: Namen prüfen, ggf. Ersetzen und die Warnung bestätigen lassen."""
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
                           "Import it only if you trust the source and understand the code.\n\nImport it?", n=name),
                        icon="warning"):
                    return False
                action(replace, builtin)
            except module_import.ImportErrorJOPML as exc:
                self._say(msg, str(exc), False)
                return False
            except OSError as exc:
                self._say(msg, f"{type(exc).__name__}: {exc}", False)
                return False
            self._say(msg, tr("Module {n} imported. Restart the program to use it.", n=name))
            render()
            return True

        def do_import(path):
            p = Path(path)
            name = module_import.clean_name(p.name if p.is_dir() else p.stem)
            run_import(name, lambda replace, builtin: module_import.import_module_files(p, name, replace=replace, builtin=builtin))

        def code_dialog():
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
                self._say(msg, "")
                if run_import(name, lambda replace, builtin: module_import.import_module_code(code, name, replace=replace, builtin=builtin)):
                    top.destroy()
                else:
                    self._say(err, msg.cget("text"), False)
            br = ctk.CTkFrame(top, fg_color="transparent")
            br.pack(pady=10)
            ctk.CTkButton(br, text=tr("Insert example"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT, command=example).pack(side="left", padx=6)
            ctk.CTkButton(br, text=tr("Import"), width=150, command=save).pack(side="left", padx=6)

        def pick_file():
            path = filedialog.askopenfilename(filetypes=[(tr("Modules"), "*.zip *.py *.lua")])
            if not path:
                return
            if path.lower().endswith(".lua"):
                add_lua(path)
            else:
                do_import(path)

        def add_lua(path=None):
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
                self._say(msg, str(exc), False)
                return
            self._say(msg, tr("Script {n} added. Start it in the menu item 'Lua scripts'.", n=name))

        def pick_folder():
            path = filedialog.askdirectory()
            if path:
                do_import(path)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=(4, 2))
        ctk.CTkButton(r, text=tr("Import file …"), width=150, command=pick_file).pack(side="left")
        ctk.CTkButton(r, text=tr("Import folder …"), width=150, command=pick_folder).pack(side="left", padx=8)
        ctk.CTkButton(r, text=tr("Add from code …"), width=150, command=code_dialog).pack(side="left")
        ctk.CTkButton(r, text=tr("Add Lua script …"), width=150, command=lambda: add_lua()).pack(side="left", padx=8)
        listing.pack(fill="x", pady=(6, 0))
        render()

    def _set_scale(self, label):
        try:
            v = int(label.split()[0])
        except ValueError:
            return
        self.app.apply_look({"ui_scale": v})

    def _render_stats(self):
        from core import stats
        body = self._stats_body
        for w in body.winfo_children():
            w.destroy()
        d = stats.load()
        rows = [(tr("Autoclicker runs"), str(d["runs"])), (tr("Clicks in total"), f"{int(d['clicks']):,}".replace(",", " ")),
                (tr("Time clicking"), stats.fmt_duration(d["seconds"])), (tr("Fastest run (clicks/s)"), f"{d['best_cps']:g}"),
                (tr("Macro runs"), str(d["macro_runs"])), (tr("Time in macros"), stats.fmt_duration(d["macro_seconds"]))]
        for a, b in rows:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x")
            ctk.CTkLabel(r, text=a, width=220, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=b, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ui.muted(body, "Only stored on this computer. Nothing is sent.").pack(fill="x", pady=(6, 0))
        ctk.CTkButton(body, text=tr("Reset statistics"), width=150, fg_color="gray35", hover_color="gray25",
                      command=lambda: (stats.reset(), self._render_stats())).pack(anchor="w", pady=(6, 0))

    def _ask(self, title, text):
        dlg = ctk.CTkInputDialog(title=title, text=text)
        v = dlg.get_input()
        return v if v else ""

    def _account_backup_save(self):
        from core import account_backup
        me = self._me()
        pw = self._ask(tr("Account backup"), tr("Your account password (to confirm):"))
        if not pw:
            return
        phrase = self._ask(tr("Account backup"), tr("Choose a passphrase for the backup file (at least {n} characters). Without it the file cannot be opened:", n=account_backup.MIN_PASSPHRASE))
        if not phrase:
            return
        try:
            text = account_backup.export_account(self.app.accounts, me["username"], pw, phrase)
        except (account_backup.BackupError, accounts.AccountError) as exc:
            self._say(self.m_acc_bak, str(exc), False)
            return
        path = filedialog.asksaveasfilename(defaultextension=".jopmacc", initialfile=f"{me['username']}.jopmacc", filetypes=[("JOPML account", "*.jopmacc")])
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            self._say(self.m_acc_bak, f"{type(exc).__name__}: {exc}", False)
            return
        self._say(self.m_acc_bak, tr("Account backup saved. Keep the file and the passphrase safe."))

    def _account_backup_restore(self):
        restore_account_file(self.app.accounts, self.m_acc_bak)

    def _backup_save(self):
        from core import backup
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="jopml-backup.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            data = backup.build()
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            self._say(self.m_bak, tr("Saved. {n} files.", n=len(data["files"])))
        except OSError as exc:
            self._say(self.m_bak, str(exc), False)

    def _backup_restore(self):
        from core import backup
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno(tr("Restore backup …"), tr("Settings and files with the same name will be overwritten.\nContinue?")):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                res = backup.restore(json.load(fh))
        except (OSError, ValueError) as exc:
            self._say(self.m_bak, tr(str(exc)) if isinstance(exc, ValueError) and "backup" in str(exc) else tr("This file could not be read."), False)
            return
        self.app.settings.update(config.load_settings())
        self._say(self.m_bak, tr("Restored: {s} settings, {f} files.", s=res["settings"], f=res["files"]))
        self.app.apply_look({})

    @staticmethod
    def _safe(fn):
        try:
            return bool(fn())
        except Exception:
            return False

    # ======================= Leistung =======================
    # ======================= Hotkeys =======================
    def _s_hotkeys(self):
        from tkinter import filedialog
        from core import hotkey_registry as hr
        from modules.autoclicker import keys as kcap
        reg = self.app.hotkeys
        top = self._card("Hotkeys")
        ui.muted(top, "All shortcuts of the app in one place. Click “Change”, then press the new key combination (Esc = cancel). "
                      "Red = the same key is used twice. A program name (part of the window title) makes a shortcut work only in that program.").pack(fill="x", pady=(0, 6))
        search_row = ctk.CTkFrame(top, fg_color="transparent")
        search_row.pack(fill="x", pady=2)
        search = ctk.CTkEntry(search_row, width=260, placeholder_text=tr("Search …"))
        search.pack(side="left")
        msg = self._msg(top)
        listbox = self._card("Shortcuts")
        state = {"cap": None}

        def stop_capture():
            if state["cap"] is not None:
                state["cap"].cancel()
                state["cap"] = None

        def render(*_):
            stop_capture()
            for w in listbox.winfo_children():
                w.destroy()
            needle = search.get().strip().lower()
            clash = reg.conflicts()
            clash_ids = {i for ids in clash.values() for i in ids}
            groups: dict[str, list] = {}
            for i, e in reg.entries.items():
                if needle and needle not in (tr(e.label) + " " + tr(e.group)).lower() and needle not in reg.key_of(i).lower():
                    continue
                groups.setdefault(e.group, []).append(i)
            if not groups:
                ui.muted(listbox, "Nothing found.").pack(fill="x")
            for g in sorted(groups):
                ctk.CTkLabel(listbox, text=tr(g), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(8, 2))
                for i in groups[g]:
                    row_for(i, i in clash_ids)

        def row_for(i, bad):
            e = reg.entries[i]
            r = ctk.CTkFrame(listbox, fg_color="transparent")
            r.pack(fill="x", pady=2)
            if not e.external:
                var = ctk.BooleanVar(value=reg.enabled(i))
                ctk.CTkSwitch(r, text="", width=40, variable=var,
                              command=lambda i=i, v=var: (reg.set_enabled(i, v.get()), render())).pack(side="left")
            else:
                ctk.CTkLabel(r, text="", width=46).pack(side="left")
            ctk.CTkLabel(r, text=tr(e.label), width=230, anchor="w").pack(side="left")
            key = ctk.CTkLabel(r, text=hr.pretty(reg.key_of(i)), width=170, corner_radius=6, fg_color=theme.c("inset"),
                               text_color=theme.DANGER if bad else theme.TEXT)
            key.pack(side="left", padx=4)

            def change(i=i, key=key):
                stop_capture()
                key.configure(text=tr("Press keys …"), text_color=theme.TEXT)

                holder = {}

                def done(result, i=i):
                    def apply():
                        if state["cap"] is not holder.get("cap"):
                            return                                  # eine neuere Aufnahme läuft schon
                        state["cap"] = None
                        if result:
                            err = reg.set_key(i, result)
                            self._say(msg, err or tr("Saved."), not err)
                        render()
                    self.app.call_soon(apply)
                try:
                    holder["cap"] = state["cap"] = kcap.KeyCapture(done, combo=True)
                    state["cap"].start()
                except Exception as exc:
                    self._say(msg, str(exc), False)
            ctk.CTkButton(r, text=tr("Change"), width=80, command=change).pack(side="left", padx=2)
            ctk.CTkButton(r, text="↺", width=30, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda i=i: (reg.reset(i), render())).pack(side="left", padx=2)
            if e.windowed and not e.external:
                w = ctk.CTkEntry(r, width=130, placeholder_text=tr("any program"))
                w.insert(0, reg.window_of(i))
                w.pack(side="left", padx=6)
                w.bind("<FocusOut>", lambda _e, i=i, w=w: reg.set_window(i, w.get()))
                w.bind("<Return>", lambda _e, i=i, w=w: (reg.set_window(i, w.get()), render()))

        search.bind("<KeyRelease>", render)
        tools = self._card("Profiles & backup")
        ui.muted(tools, "Save the current assignment as a profile (for example one per game) and load it later. Export/Import writes a file you can share.").pack(fill="x", pady=(0, 4))
        r = ctk.CTkFrame(tools, fg_color="transparent")
        r.pack(fill="x", pady=2)
        names = sorted(self.app.settings.get("hotkey_profiles", {}))
        pm = ctk.CTkOptionMenu(r, values=names or ["–"], width=180)
        pm.set(names[0] if names else "–")
        pm.pack(side="left")

        def load_profile():
            n = pm.get()
            if n in self.app.settings.get("hotkey_profiles", {}):
                cnt = reg.load_profile(n)
                self._say(msg, tr("{n} shortcuts loaded.", n=cnt))
                render()
        ctk.CTkButton(r, text=tr("Load"), width=80, command=load_profile).pack(side="left", padx=6)

        def delete_profile():
            n = pm.get()
            if n in self.app.settings.get("hotkey_profiles", {}):
                reg.delete_profile(n)
                self._open(tr("Hotkeys"))
        ctk.CTkButton(r, text=tr("Delete"), width=80, fg_color=theme.c("hover"), text_color=theme.TEXT, command=delete_profile).pack(side="left")
        r = ctk.CTkFrame(tools, fg_color="transparent")
        r.pack(fill="x", pady=4)
        name = ctk.CTkEntry(r, width=180, placeholder_text=tr("Profile name"))
        name.pack(side="left")

        def save_profile():
            err = reg.save_profile(name.get())
            self._say(msg, err or tr("Saved."), not err)
            if not err:
                self._open(tr("Hotkeys"))
        ctk.CTkButton(r, text=tr("Save profile"), width=120, command=save_profile).pack(side="left", padx=6)
        r = ctk.CTkFrame(tools, fg_color="transparent")
        r.pack(fill="x", pady=4)

        def export():
            f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="jopml-hotkeys.json")
            if f:
                import json
                try:
                    with open(f, "w", encoding="utf-8") as fh:
                        json.dump(reg.snapshot(), fh, indent=2, ensure_ascii=False)
                    self._say(msg, tr("Saved."))
                except OSError as exc:
                    self._say(msg, str(exc), False)

        def import_():
            f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if f:
                import json
                try:
                    with open(f, encoding="utf-8") as fh:
                        n = reg.load_snapshot(json.load(fh))
                    self._say(msg, tr("{n} shortcuts loaded.", n=n))
                    render()
                except (OSError, ValueError) as exc:
                    self._say(msg, str(exc), False)

        def reset_all():
            reg.reset()
            self._say(msg, tr("Reset to the defaults."))
            render()
        ctk.CTkButton(r, text=tr("Export …"), width=100, command=export).pack(side="left")
        ctk.CTkButton(r, text=tr("Import …"), width=100, command=import_).pack(side="left", padx=6)
        ctk.CTkButton(r, text=tr("Reset all to default"), width=170, fg_color="#c0392b", hover_color="#962d22", command=reset_all).pack(side="left")
        if reg.error:
            self._say(msg, reg.error, False)
        render()

    # ======================= Benachrichtigungen =======================
    def _s_notifications(self):
        from core import notify
        p = self.app.notifier.prefs()
        body = self._card("Notifications")
        ui.muted(body, "Choose when the launcher alerts you and how it looks and sounds. These settings apply only to this device.").pack(fill="x", pady=(0, 6))
        v = {}

        def switch(parent, key, label, value):
            v[key] = ctk.BooleanVar(value=value)
            ctk.CTkSwitch(parent, text=tr(label), variable=v[key]).pack(anchor="w", pady=3)

        def menu(parent, label, values, current, width=170):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            m = ctk.CTkOptionMenu(r, values=[tr(x) for x in values], width=width)
            m.set(tr(current))
            m.pack(side="left")
            return m

        def back(menu_widget, values):
            return next((x for x in values if tr(x) == menu_widget.get()), values[0])

        switch(body, "enabled", "Notifications on", p.enabled)
        ev = self._card("Which events")
        for k, label in notify.EVENTS.items():
            switch(ev, "ev_" + k, label, p.events.get(k, True))
        sd = self._card("Sound")
        m_sound = menu(sd, "Sound", notify.SOUNDS, p.sound)
        r = ctk.CTkFrame(sd, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Own sound file"), width=170, anchor="w").pack(side="left")
        e_path = ctk.CTkEntry(r, width=240)
        e_path.insert(0, p.custom_path)
        e_path.pack(side="left", padx=(0, 6))

        def choose():
            f = filedialog.askopenfilename(filetypes=[(tr("Sound files"), "*.wav *.mp3 *.aiff *.m4a *.ogg")])
            if f:
                e_path.delete(0, "end")
                e_path.insert(0, f)
        ctk.CTkButton(r, text=tr("Choose…"), width=90, command=choose).pack(side="left")
        ui.muted(sd, "Own sounds: WAV works everywhere; MP3 and others on Mac and Linux. Maximum 5 MB.").pack(fill="x")
        r = ctk.CTkFrame(sd, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Volume"), width=170, anchor="w").pack(side="left")
        sl_vol = ctk.CTkSlider(r, from_=0, to=100, number_of_steps=20, width=220)
        sl_vol.set(p.volume)
        sl_vol.pack(side="left")
        pp = self._card("Pop-up")
        switch(pp, "popup", "Show pop-up", p.popup)
        m_pos = menu(pp, "Position", notify.POSITIONS, p.position)
        e_dur = self._field(pp, tr("Display time (seconds)"), str(p.duration), width=80)
        r = ctk.CTkFrame(pp, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Opacity"), width=170, anchor="w").pack(side="left")
        sl_op = ctk.CTkSlider(r, from_=40, to=100, number_of_steps=12, width=220)
        sl_op.set(p.opacity)
        sl_op.pack(side="left")
        r = ctk.CTkFrame(pp, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Pop-up colour"), width=170, anchor="w").pack(side="left")
        col = {"v": p.color}
        sw_col = ctk.CTkButton(r, text="" if col["v"] else tr("Theme"), width=70, hover=False,
                               fg_color=col["v"] or theme.c("card"), text_color=theme.TEXT)

        def pick_color():
            c = colorchooser.askcolor(color=col["v"] or None, parent=self.app)[1]
            if c:
                col["v"] = c
                sw_col.configure(fg_color=c, text="")

        def reset_color():
            col["v"] = ""
            sw_col.configure(fg_color=theme.c("card"), text=tr("Theme"))
        sw_col.configure(command=pick_color)
        sw_col.pack(side="left")
        ctk.CTkButton(r, text=tr("Reset"), width=80, fg_color="gray40", command=reset_color).pack(side="left", padx=8)
        dn = self._card("Do not disturb & community")
        switch(dn, "dnd_fullscreen", "No pop-ups or sounds while a program is fullscreen (a summary follows afterwards)", p.dnd_fullscreen)
        switch(dn, "community_background", "Show community messages even when the Community page is closed or locked", p.community_background)
        ui.muted(dn, "With this on, the launcher asks the server every minute for new messages, invitations, announcements and marketplace macros "
                     "(only that something is new – nothing is decrypted). Needs a cloud account.").pack(fill="x", pady=(0, 6))
        muted = set(p.muted_servers)
        mute_vars = {}
        com = self.app.plugin_by_id.get("community")
        svc = getattr(com, "_svc", None) if com is not None else None
        spaces = [sp for sp in (getattr(svc, "spaces", None) or []) if sp.get("kind") == "server"]
        if not spaces:                                   # ohne Anmeldung: zuletzt bekannte Server aus dem Zwischenspeicher
            spaces = [sp for sp in (self.app.settings.get("community_cache") or []) if sp.get("id")]
        ctk.CTkLabel(dn, text=tr("Servers that may notify you"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(6, 2))
        if spaces:
            for sp in spaces:
                mute_vars[sp["id"]] = ctk.BooleanVar(value=sp["id"] not in muted)
                ctk.CTkSwitch(dn, text=sp.get("name", ""), variable=mute_vars[sp["id"]]).pack(anchor="w", pady=2)
        else:
            ui.muted(dn, "Open the Community page once to list your servers here.").pack(fill="x")
        cs = self._card("Community sign-in")
        ui.muted(cs, "You can change these settings without being signed in to the Community.").pack(fill="x", pady=(0, 4))
        stay = ctk.BooleanVar(value=bool(self.app.settings.get("community_stay")))

        def on_stay():
            if com is not None:
                com.set_stay(stay.get())
            else:
                self.app.settings["community_stay"] = stay.get()
                self.app.save_settings()
        ctk.CTkSwitch(cs, text=tr("Stay signed in to the Community on this computer"), variable=stay, command=on_stay).pack(anchor="w", pady=3)
        ui.muted(cs, "The passphrase is remembered on this computer (on Windows bound to your Windows account), so the Community opens "
                     "without asking. Turn this off on shared computers.").pack(fill="x")
        qh = self._card("Quiet hours")
        switch(qh, "quiet", "Mute during quiet hours", p.quiet)
        e_from = self._field(qh, tr("From (HH:MM)"), p.quiet_from, width=80)
        e_to = self._field(qh, tr("Until (HH:MM)"), p.quiet_to, width=80)
        msg = self._msg(qh)

        def collect():
            d = notify.Prefs.from_dict({
                "enabled": v["enabled"].get(), "sound": back(m_sound, notify.SOUNDS), "custom_path": e_path.get().strip(),
                "volume": int(sl_vol.get()), "popup": v["popup"].get(), "position": back(m_pos, notify.POSITIONS),
                "duration": e_dur.get().strip() or 5, "opacity": int(sl_op.get()), "color": col["v"],
                "events": {k: v["ev_" + k].get() for k in notify.EVENTS},
                "quiet": v["quiet"].get(), "quiet_from": e_from.get().strip(), "quiet_to": e_to.get().strip(),
                "dnd_fullscreen": v["dnd_fullscreen"].get(), "community_background": v["community_background"].get(),
                "muted_servers": sorted(({x for x in muted} - set(mute_vars)) | {i for i, var in mute_vars.items() if not var.get()})})
            return d

        def save():
            d = collect()
            self.app.settings["notify"] = d.to_dict()
            self.app.save_settings()
            if com is not None and hasattr(com, "apply_background"):
                com.apply_background()
            self._say(msg, tr("Saved."), True)

        def test_sound():
            self.app.notifier.play(collect())

        def test_popup():
            self.app.settings["notify"] = collect().to_dict()
            self.app.notifier.notify("chat", tr("Test notification"), tr("This is how your notifications look and sound."), force=True)
        row = ctk.CTkFrame(qh, fg_color="transparent")
        row.pack(anchor="w", pady=(8, 0))
        ctk.CTkButton(row, text=tr("Save"), width=110, command=save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text=tr("Test sound"), width=130, fg_color="gray40", command=test_sound).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text=tr("Test notification"), width=160, fg_color="gray40", command=test_popup).pack(side="left")


    def _s_performance(self):
        s = self.app.settings
        body = self._card("Potato mode")
        ui.muted(body, "For weak PCs: turns off the background picture, coloured icons and pre-building of pages, and polls overlays, cross-hair and window tracking three times less often.").pack(fill="x", pady=(0, 6))
        pv = tk.BooleanVar(value=bool(s.get("potato_mode")))
        ctk.CTkSwitch(body, text=tr("Potato mode"), variable=pv,
                      command=lambda: self.app.apply_look({"potato_mode": pv.get()})).pack(anchor="w", pady=3)
        fv = tk.BooleanVar(value=bool(s.get("resize_freeze", True)))
        ctk.CTkSwitch(body, text=tr("Hide the page while resizing the window (smoother)"), variable=fv,
                      command=lambda: (s.update({"resize_freeze": fv.get()}), self.app.save_settings())).pack(anchor="w", pady=3)
        body = self._card("Diagnostics")
        ui.muted(body, "Sends one sign of life per minute (version, operating system, open page) and error messages without personal data to the developer, so problems can be found and fixed. Cloud accounts only.").pack(fill="x", pady=(0, 6))
        dv = tk.BooleanVar(value=bool(s.get("diagnostics", True)))
        ctk.CTkSwitch(body, text=tr("Send anonymous diagnostics"), variable=dv,
                      command=lambda: (s.update({"diagnostics": dv.get()}), self.app.save_settings())).pack(anchor="w", pady=3)
        body = self._card("Performance & throttling")
        ram, cores = system_limits.total_ram_mb(), system_limits.cpu_count()
        self.info = ctk.CTkLabel(body, text_color=theme.MUTED, anchor="w", justify="left", wraplength=620)
        self.info.pack(fill="x", pady=(0, 6))
        self._refresh_info(cores, ram)
        ui.muted(body, "These limits apply only to this program, not to other programs or the whole PC. There is no GPU limit because the program does not use the graphics card.").pack(fill="x", pady=(0, 8))
        self.e_dl = self._field(body, tr("Download limit (KB/s)"), str(s["dl_limit_kbps"]), width=100)
        ui.muted(body, "0 = unlimited. Applies to program updates.").pack(fill="x")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("CPU priority"), width=170, anchor="w").pack(side="left")
        self.o_prio = ctk.CTkOptionMenu(r, values=[tr("Normal"), tr("Low")], width=120)
        self.o_prio.set(tr("Low") if s["cpu_priority"] == "low" else tr("Normal"))
        self.o_prio.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("CPU cores"), width=170, anchor="w").pack(side="left")
        self.o_cores = ctk.CTkOptionMenu(r, values=[tr("All")] + [str(i) for i in range(1, cores)], width=120)
        self.o_cores.set(str(s["cpu_cores"]) if 0 < s["cpu_cores"] < cores else tr("All"))
        self.o_cores.pack(side="left")
        self.e_ram = self._field(body, tr("RAM limit (MB)"), str(s["ram_limit_mb"]), width=100)
        if not system_limits.IS_WIN:
            self.e_ram.configure(state="disabled")
        ui.muted(body, "0 = no limit. Windows only, at least {n} MB. Too low values can crash the program.", n=system_limits.MIN_RAM_MB).pack(fill="x")
        self.m_perf = self._msg(body)
        ctk.CTkButton(body, text=tr("Save & apply"), width=180, command=self._save_perf).pack(anchor="w", pady=(6, 0))

    def _refresh_info(self, cores, ram):
        used = system_limits.process_ram_mb()
        text = tr("Your PC: {c} CPU cores", c=cores) + (f", {ram / 1024:.1f} GB RAM" if ram else "")
        if used:
            text += "  ·  " + tr("This program currently uses {n} MB", n=used)
        self.info.configure(text=text)

    def _save_perf(self):
        try:
            dl = float(self.e_dl.get().strip() or 0)
            ram = int(float(self.e_ram.get().strip() or 0))
            if dl < 0 or ram < 0:
                raise ValueError
        except ValueError:
            self._say(self.m_perf, tr("Please enter numbers from 0."), False)
            return
        cores_txt = self.o_cores.get()
        s = self.app.settings
        s.update({"dl_limit_kbps": dl if dl % 1 else int(dl), "cpu_priority": "low" if self.o_prio.get() == tr("Low") else "normal",
                  "cpu_cores": int(cores_txt) if cores_txt.isdigit() else 0, "ram_limit_mb": ram})
        self.app.save_settings()
        notes = self.app.apply_limits()
        self._refresh_info(system_limits.cpu_count(), system_limits.total_ram_mb())
        self._say(self.m_perf, tr("Saved and applied.") + ("\n" + "\n".join(notes) if notes else ""), not notes)

    # ======================= Rechtliches & Quellen =======================
    def _s_legal(self):
        s = self.app.settings
        body = self._card("Your agreement")
        when = datetime.datetime.fromtimestamp(s.get("legal_accepted_at") or 0).strftime("%Y-%m-%d %H:%M") if s.get("legal_accepted_at") else "–"
        ui.banner(body, "✔ " + tr("You have legally bindingly agreed to the terms of use and the disclaimer on {d} (version {v}).",
                                  d=when, v=s.get("legal_version") or LEGAL_VERSION) + "\n" + tr("No copyright / public domain."),
                  color="#166534").pack(fill="x")
        ctk.CTkButton(body, text=tr("Read the terms again"), width=190, command=self._show_terms).pack(anchor="w", pady=(10, 0))

        body = self._card("Credits & sources")
        ui.muted(body, "There is no imprint and no contact person (anonymous project). The following technologies are used; all names belong to their owners. None of these companies supports, endorses or is liable for this project.").pack(fill="x", pady=(0, 6))
        for name, role, lic, url in CREDITS:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x")
            ctk.CTkLabel(r, text=f"{name} – {tr(role)} · {lic}", font=ctk.CTkFont(size=11), text_color=theme.MUTED,
                         anchor="w", wraplength=520, justify="left").pack(side="left")
            ctk.CTkButton(r, text="↗", width=26, height=20, fg_color="transparent", text_color=theme.accent(),
                          hover_color=theme.c("hover"), command=lambda u=url: webbrowser.open(u)).pack(side="right")

    def _show_terms(self):
        top = ctk.CTkToplevel(self)
        top.title(tr("Terms of use and disclaimer"))
        top.geometry("820x640")
        box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", legal_text(i18n.get_language()))
        box.configure(state="disabled")
        top.after(80, top.lift)
