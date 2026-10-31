"""Hauptfenster: Erststart, Anmeldung, Seitenleiste (mit Werbefläche), Dashboard, Plugin-Seiten, Einstellungen."""
import os
import queue
import threading
import time
import traceback

import customtkinter as ctk

from core.notify import Notifier
from core import accounts, ads, appicon, background, config, i18n, identity, layout, system_limits, theme, updater
from core.i18n import tr
from core.plugin_manager import discover
from core.version import APP_NAME, APP_VERSION

TICK_MS = 100          # UI-Warteschlange: selten genug für wenig CPU, schnell genug für flüssige Bedienung


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, app, info: updater.UpdateInfo, arena=None):
        super().__init__(app, fg_color=theme.c("main"))
        self.app, self.info, self.arena = app, info, arena
        self.title(tr("Update available"))
        self.geometry("440x360")
        self.resizable(False, False)
        self.transient(app)
        ctk.CTkLabel(self, text=tr("Version {v} is available", v=info.version), font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(self, text=tr("Installed: {v}", v=APP_VERSION), text_color=theme.MUTED).pack()
        notes = ctk.CTkTextbox(self, height=100, width=380)
        notes.insert("1.0", info.notes or tr("No release notes."))
        notes.configure(state="disabled")
        notes.pack(pady=(12, 4))
        ctk.CTkLabel(self, text="🎯  " + (tr("Recoil Arena {a} will be updated too.", a=arena["available"]) if arena
                                          else tr("The Recoil Arena is installed or updated together with this update.")),
                     text_color=theme.MUTED, wraplength=380).pack(pady=(0, 8))
        self.bar = ctk.CTkProgressBar(self, width=380)
        self.bar.set(0)
        self.status = ctk.CTkLabel(self, text="", wraplength=380)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=4)
        self.btn = ctk.CTkButton(row, text=tr("Update now"), command=self._start)
        self.btn.pack(side="left", padx=6)
        ctk.CTkButton(row, text=tr("Later"), fg_color="gray30", hover_color="gray20", command=self.destroy).pack(side="left", padx=6)

    def _start(self):
        self.btn.configure(state="disabled")
        self.app.keep_login_for_restart()
        try:
            from core import module_import
            module_import.snapshot()
        except Exception:
            pass
        self.bar.pack(pady=4)
        self.status.pack()
        self.status.configure(text=tr("Downloading …"), text_color=theme.TEXT)
        limit = self.app.settings.get("dl_limit_kbps", 0)

        def work():
            try:
                # Zuerst die Arena (klein, nur Fehler ignorieren), dann der Launcher selbst.
                try:
                    from modules.arena import plugin as arena_plugin
                    self.app.call_soon(self.status.configure, text=tr("Updating Recoil Arena …"))
                    arena_plugin.sync(install_if_missing=True)
                except Exception:
                    traceback.print_exc()
                self.app.call_soon(self.status.configure, text=tr("Downloading …"))
                path = updater.download(self.info, lambda p: self.app.call_soon(self._progress, p), max_kbps=limit)
                self.app.call_soon(self.status.configure, text=tr("Installing …"))
                restart = updater.apply(path)
                self.app.call_soon(self._done, restart, None)
            except Exception as exc:
                self.app.call_soon(self._done, False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, p):
        if self.winfo_exists():
            self.bar.set(p)

    def _done(self, restart: bool, error):
        if not self.winfo_exists():
            return
        if error:
            try:
                self.app.record_error("E-UPD-002", str(error), "update")
            except Exception:
                pass
            self.status.configure(text=tr("Error: {e}", e=error) + " [E-UPD-002]", text_color=theme.DANGER)
            self.btn.configure(state="normal")
        elif restart:
            self.app.close()
        else:
            self.status.configure(text=tr("Downloaded – please replace the file manually."))


class ArenaUpdateDialog(ctk.CTkToplevel):
    """Kleiner Hinweis, wenn nur die Recoil Arena eine neue Fassung hat (der Launcher ist aktuell)."""

    def __init__(self, app, info: dict):
        super().__init__(app, fg_color=theme.c("main"))
        self.app = app
        self.title(tr("Recoil Arena update"))
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(app)
        ctk.CTkLabel(self, text="🎯  " + tr("New Recoil Arena version {v}", v=info["available"]), font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(22, 4))
        ctk.CTkLabel(self, text=tr("Installed: {v}", v=info["installed"] or "?"), text_color=theme.MUTED).pack()
        self.bar = ctk.CTkProgressBar(self, width=360)
        self.bar.set(0)
        self.status = ctk.CTkLabel(self, text=tr("Close the game before updating."), text_color=theme.MUTED, wraplength=360)
        self.status.pack(pady=10)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=4)
        self.btn = ctk.CTkButton(row, text=tr("Update now"), command=self._start)
        self.btn.pack(side="left", padx=6)
        ctk.CTkButton(row, text=tr("Later"), fg_color="gray30", hover_color="gray20", command=self.destroy).pack(side="left", padx=6)

    def _start(self):
        self.btn.configure(state="disabled")
        self.bar.pack(pady=4)
        self.status.configure(text=tr("Downloading …"), text_color=theme.TEXT)

        def work():
            from modules.arena import plugin as arena_plugin
            state, text = arena_plugin.sync(progress=lambda p: self.app.call_soon(self._progress, p))
            self.app.call_soon(self._done, state, text)

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, p):
        if self.winfo_exists():
            self.bar.set(p)

    def _done(self, state, text):
        if not self.winfo_exists():
            return
        if state == "error":
            self.status.configure(text=tr("Error: {e}", e=text), text_color=theme.DANGER)
            self.btn.configure(state="normal")
        else:
            self.bar.set(1)
            self.status.configure(text=tr("Recoil Arena is now version {v}.", v=text), text_color=theme.TEXT)
            self.btn.configure(state="disabled")


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        name = app.user["display_name"]
        self.welcome = ctk.CTkLabel(self, text=tr("Welcome, {name}!", name=name) + " 👋", font=ctk.CTkFont(size=28, weight="bold"))
        self.welcome.pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text=tr("Nice to see you. This is {app} · version {v}.", app=APP_NAME, v=APP_VERSION),
                     text_color=theme.MUTED).pack(anchor="w", padx=24)
        self._build_ai_hero()
        upd = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        upd.pack(fill="x", padx=24, pady=(0, 8))
        self.update_label = ctk.CTkLabel(upd, text=app.update_text, anchor="w", wraplength=480, justify="left")
        self.update_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(upd, text=tr("Check for updates"), width=170, command=lambda: app.check_updates(manual=True)).pack(side="right", padx=16)
        self.fav_box = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        self.fav_box.pack(fill="x", padx=24, pady=(0, 8))
        self.refresh_favorites()
        # Aufklappbare Modul-Übersicht (standardmäßig zu)
        self._mods_open = False
        self._mods_btn = ctk.CTkButton(self, text="▸  " + tr("Module overview"), anchor="w", height=40, fg_color=theme.c("card"),
                                       text_color=theme.TEXT, hover_color=theme.c("hover"), corner_radius=theme.CARD_RADIUS,
                                       font=ctk.CTkFont(size=16, weight="bold"), command=self._toggle_modules)
        self._mods_btn.pack(fill="x", padx=24, pady=(10, 4))
        self._mods = ctk.CTkFrame(self, fg_color="transparent")
        for p in app.visible_plugins():
            card = ctk.CTkFrame(self._mods, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
            card.pack(fill="x", pady=5)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", padx=16, pady=12)
            ctk.CTkLabel(text, text=f"{tr(p.name)}  ·  v{p.version}", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(text, text=tr(p.dashboard_summary()), text_color=theme.MUTED, anchor="w", wraplength=480, justify="left").pack(anchor="w")
            ctk.CTkButton(card, text=tr("Open"), width=90, command=lambda pid=p.id: app.show(pid)).pack(side="right", padx=16)

            def paint(inside, card=card):
                if app.settings.get("hover_effect", True):
                    card.configure(fg_color=theme.hover_tint() if inside else theme.c("card"),
                                   border_color=theme.accent() if inside else theme.c("hover"))
            hover_area(card, paint, extra=tuple(text.winfo_children()) + (text,))
        for name, err in app.failed + app.load_failed:
            ctk.CTkLabel(self, text=tr("Module '{m}' could not be loaded: {e}", m=name, e=err), text_color=theme.DANGER,
                         wraplength=640, justify="left").pack(anchor="w", padx=24, pady=4)

    HERO_CHIPS = ("Build me a module", "Write a macro that clicks every 5 seconds", "What can this launcher do?")

    def _build_ai_hero(self):
        """Großer KI-Assistent oben im Dashboard: Begrüßung, Eingabe – beim Senden öffnet sich das Modul "AI Chat" und die Nachricht wird dort beantwortet."""
        app = self.app
        hero = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=2, border_color=theme.accent())
        hero.pack(fill="x", padx=24, pady=(18, 10))
        ctk.CTkLabel(hero, text="🤖  " + tr("Your AI assistant"), font=ctk.CTkFont(size=24, weight="bold"), anchor="w").pack(fill="x", padx=22, pady=(18, 6))
        bubble = ctk.CTkFrame(hero, fg_color=theme.c("hover"), corner_radius=14)
        bubble.pack(fill="x", padx=22, pady=(0, 10))
        ctk.CTkLabel(bubble, text=tr("Hi {name}! 👋 I'm your AI assistant. Ask me anything about the launcher, or just tell me what you need: "
                                     "I write macros and can build complete modules for you – code, window and all. Type your wish below.",
                                     name=app.user["display_name"]),
                     wraplength=700, justify="left", anchor="w", font=ctk.CTkFont(size=15)).pack(fill="x", padx=16, pady=14)
        row = ctk.CTkFrame(hero, fg_color="transparent")
        row.pack(fill="x", padx=22)
        row.grid_columnconfigure(0, weight=1)
        self.hero_entry = ctk.CTkEntry(row, height=48, font=ctk.CTkFont(size=15), placeholder_text=tr("Write a message …"))
        self.hero_entry.grid(row=0, column=0, sticky="ew")
        self.hero_entry.bind("<Return>", lambda e: self._hero_send())
        ctk.CTkButton(row, text=tr("Send"), width=120, height=48, font=ctk.CTkFont(size=15, weight="bold"),
                      command=self._hero_send).grid(row=0, column=1, padx=(8, 0))
        chips = ctk.CTkFrame(hero, fg_color="transparent")
        chips.pack(fill="x", padx=22, pady=(8, 18))
        for q in self.HERO_CHIPS:
            ctk.CTkButton(chips, text=tr(q), height=28, width=10, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda q=q: self._hero_send(tr(q))).pack(side="left", padx=(0, 6))

    def _hero_send(self, text=None):
        text = (text or self.hero_entry.get()).strip()
        if not text:
            return
        self.hero_entry.delete(0, "end")
        from modules.aichat import logic as ai_logic
        if ai_logic.guess_target(text) == "help" and self.app.ask_help(text):      # eine Weiche: Bedienfragen -> Hilfe, Schreiben/Bauen/Fehler -> KI-Chat
            return
        self.app.ask_ai(text, ai_logic.guess_preset(text))

    def refresh_favorites(self):
        """Karte "Favorite macros": je Favorit ein Knopf zum Starten. Ohne Favoriten ist die Karte nur ein kurzer Hinweis."""
        for w in self.fav_box.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.fav_box, text="★  " + tr("Favorite macros"), font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(
            fill="x", padx=20, pady=(14, 4))
        plug = self.app.plugin_by_id.get("macros")
        favs = plug.favorites() if plug is not None else []
        if not favs:
            ctk.CTkLabel(self.fav_box, text=tr("No favorites yet. Mark a saved macro with ★ on the macro page."), text_color=theme.MUTED,
                         anchor="w", wraplength=620, justify="left").pack(fill="x", padx=20, pady=(0, 14))
            return
        for name in favs:
            row = ctk.CTkFrame(self.fav_box, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left")
            ctk.CTkButton(row, text="▶  " + tr("Run"), width=90, height=28, fg_color="#2e9d5b", hover_color="#247a47",
                          command=lambda n=name: self._run_fav(n)).pack(side="right")
        self.fav_msg = ctk.CTkLabel(self.fav_box, text="", anchor="w", text_color=theme.MUTED)
        self.fav_msg.pack(fill="x", padx=20, pady=(2, 12))

    def _run_fav(self, name):
        err = self.app.plugin_by_id["macros"].run_saved(name)
        self.fav_msg.configure(text=err or tr("Running … (F7 or Stop ends it)"), text_color=theme.DANGER if err else theme.OK)

    def _toggle_modules(self):
        self._mods_open = not self._mods_open
        if self._mods_open:
            self._mods.pack(fill="x", padx=24, after=self._mods_btn)
        else:
            self._mods.pack_forget()
        self._mods_btn.configure(text=("▾  " if self._mods_open else "▸  ") + tr("Module overview"))

    def set_update_text(self, text: str):
        self.update_label.configure(text=text)


def hover_area(widget, on_change, extra=()) -> None:
    """Meldet on_change(True/False), sobald die Maus über `widget` (samt Kindern) ist bzw. es verlässt.
    Es wird die echte Mausposition geprüft: das verhindert Flackern, wenn die Maus über ein Kind-Widget (z. B. das Symbol) wandert."""
    def inside() -> bool:
        try:
            px, py = widget.winfo_pointerxy()
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            return x <= px < x + widget.winfo_width() and y <= py < y + widget.winfo_height()
        except Exception:
            return False

    def check(_e=None):
        try:
            on_change(inside())
        except Exception:
            pass

    def leave(_e=None):
        try:
            widget.after(20, check)
        except Exception:
            pass
    for w in (widget, *extra):
        try:
            w.bind("<Enter>", check, add="+")
            w.bind("<Leave>", leave, add="+")
        except Exception:
            pass


def _builtin_pages() -> dict:
    def settings(parent, app):
        from core.settings_view import SettingsView
        return SettingsView(parent, app)

    def assistant(parent, app):
        from core.assistant_view import AssistantView
        return AssistantView(parent, app)

    def contact(parent, app):
        from core.contact_view import ContactView
        return ContactView(parent, app)

    def errorcodes(parent, app):
        from core.error_catalog_view import ErrorCatalogView
        return ErrorCatalogView(parent, app)

    return {"settings": settings, "assistant": assistant, "contact": contact, "errorcodes": errorcodes}


class LauncherApp(ctk.CTk):
    def __init__(self):
        self.settings = config.load_settings()
        if int(self.settings.get("nav_version") or 0) < 2:           # Menü wurde in 1.5.0 neu geordnet: gespeicherte Reihenfolge verwerfen
            self.settings["nav_order"] = []
            self.settings["nav_version"] = 2
            config.save_settings(self.settings)
        i18n.set_language(self.settings.get("language", "en"))
        theme.apply(self.settings)
        super().__init__(fg_color=theme.c("backdrop"))
        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(940, 620)
        self._ui_q: queue.Queue = queue.Queue()
        self.accounts = accounts.AccountStore()
        self.identity = identity.make_identity(self.accounts)
        self.panic_key = None
        self.notifier = Notifier(self)
        from core.hotkey_registry import Registry
        self.hotkeys = Registry(self)
        self.user: dict | None = None
        self.is_admin = False
        self.update_text = tr("Update status: not checked yet")
        self.settings_section = "Account"
        self.plugins, self.failed = discover(self)
        self.plugin_by_id = {p.id: p for p in self.plugins}
        self.load_failed: list = []
        self._loaded = False
        self._push_job = None
        self._builtin = _builtin_pages()
        self.root_frame = None
        self.nav, self.pages, self.current = {}, {}, None
        self.previous = None            # zuvor geöffnete Seite (für passende KI-Fragen)
        self.trail: list[str] = []      # zuletzt besuchte Seiten (nur Namen); geht nur mit, wenn der Nutzer "Fehler-Kontext mitsenden" einschaltet
        self.mini = None
        self.dashboard = None

        self._resize_job = None
        self._rebuild_job = None
        self._prewarm_job = None
        self._compact = None
        self._frozen = False
        self._soft_scopes: set = set()
        self._soft_job = None
        from core.telemetry import Telemetry
        self.telemetry = Telemetry(self)
        self.telemetry.install_hooks()
        self._last_size = None
        self._last_input = time.monotonic()
        self.bind("<Configure>", self._on_resize)
        self.bind_all("<Control-p>", self._open_palette)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(TICK_MS, self._drain)
        self.apply_limits()
        appicon.apply_to_window(self, self.settings)
        self.start_flow()

    # ---------- Ablauf beim Start
    def start_flow(self):
        from core import firstrun_view
        if not self.settings.get("first_run_done"):
            self._show_gate("full")
        elif firstrun_view.needs_legal(self.settings):
            self._show_gate("legal")
        else:
            self.after_legal()

    def _show_gate(self, mode):
        from core.firstrun_view import FirstRunView
        self._reset_root()
        FirstRunView(self.root_frame, self, mode, self.after_legal).pack(fill="both", expand=True)

    @staticmethod
    def _sync_bundled_arena():
        """Nach einem Launcher-Update: ist die installierte Arena älter als die mitgelieferte, wird sie still ersetzt (ohne Netz)."""
        try:
            from modules.arena import plugin as arena_plugin
            arena_plugin.sync(use_server=False)
        except Exception:
            traceback.print_exc()

    def after_legal(self):
        user = None
        threading.Thread(target=self._sync_bundled_arena, daemon=True).start()
        try:
            from core import module_import
            module_import.restore_if_missing()
        except Exception:
            traceback.print_exc()
        try:
            user = self.identity.resume()
        except Exception:
            traceback.print_exc()
        if user:
            if self.settings.get("temp_session"):          # kurze Sitzung nur für den Neustart: jetzt wieder entfernen
                self.settings["temp_session"] = False
                config.save_settings(self.settings)
                try:
                    self.identity.forget_file() if hasattr(self.identity, "forget_file") else self.accounts.clear_session()
                except Exception:
                    traceback.print_exc()
            self.login_done(user, None, resumed=True)
        else:
            self.show_login()

    def exit_now(self):
        """'Ablehnen': Programm sofort beenden (Gegenstück zu Environment.Exit(0) im C#-Zweig)."""
        try:
            self.destroy()
        finally:
            os._exit(0)

    # ---------- Rahmen
    def _reset_root(self):
        if self.root_frame is not None:
            self.root_frame.destroy()
        self.root_frame = ctk.CTkFrame(self, fg_color=theme.c("backdrop"), corner_radius=0)
        self.root_frame.pack(fill="both", expand=True)
        self.nav, self.pages, self.current, self.dashboard = {}, {}, None, None

    def show_login(self):
        from core.login_view import LoginView
        self._reset_root()
        LoginView(self.root_frame, self).pack(fill="both", expand=True)

    def login_done(self, user: dict, days, resumed: bool = False):
        self.user = user
        self.telemetry.start()
        if not resumed:
            try:
                self.identity.remember(user, days)
            except Exception:
                traceback.print_exc()
        try:
            remote = self.identity.pull_settings(user)
            if remote:
                for k in identity.SYNC_KEYS:
                    if k in remote:
                        self.settings[k] = remote[k]
                config.save_settings(self.settings)
                i18n.set_language(self.settings.get("language", "en"))
                theme.apply(self.settings)
                self.configure(fg_color=theme.c("backdrop"))
                appicon.apply_to_window(self, self.settings)
        except Exception:
            traceback.print_exc()
        if not self._loaded:
            self.load_failed = []
            for p in self.plugins:
                try:
                    p.on_load()
                except Exception as exc:
                    traceback.print_exc()
                    self.load_failed.append((p.id, str(exc)))
                    self.record_error("E-APP-002", f"{p.id}: {type(exc).__name__}: {exc}", "module", traceback.format_exc())
            self._loaded = True
        self.is_admin = False
        self._start_panic()
        self.hotkeys.apply()
        self.build_main()
        self.show("dashboard")
        self.after(1500, self.check_updates)
        self.after(9000, self._auto_backup)
        self._check_admin()
        self.after(6000, self._check_replies)

    def _check_replies(self):
        """Gibt es eine neue Antwort des Betreibers auf eine Meldung? Dann ein Hinweis (einmal pro Start); nur Cloud-Konten."""
        client = getattr(self.identity, "client", None)
        if client is None or not getattr(client, "session", None):
            return

        def work():
            from core import error_dialog
            n = error_dialog.unseen_replies(self)
            if n:
                self.call_soon(self._reply_toast, n)
        threading.Thread(target=work, daemon=True).start()

    def _reply_toast(self, n):
        self.notifier.notify("news", tr("Answer to your report"), tr("You have {n} new answer(s). Open 'Report' > 'My reports'.", n=n), force=True)

    def _check_admin(self):
        """Fragt den Server, ob dieses Konto Admin ist (nur Cloud-Konten). Die echte Prüfung passiert serverseitig."""
        client = getattr(self.identity, "client", None)
        if client is None or not getattr(client, "session", None):
            return
        user = self.user

        def work():
            ok = False
            try:
                ok = client.is_admin()
            except Exception:
                traceback.print_exc()
            if ok:
                self.call_soon(self._admin_result, user)

        threading.Thread(target=work, daemon=True).start()

    def _admin_result(self, user):
        if self.user is not user or self.is_admin:
            return
        self.is_admin = True
        self._rebuild_keep_page()

    def logout(self, forget: bool = True):
        try:
            if forget:
                self.identity.forget(self.user)
            else:
                self.identity.forget_file() if hasattr(self.identity, "forget_file") else self.accounts.clear_session()
        except Exception:
            traceback.print_exc()
        self._shutdown_plugins()
        self.is_admin = False
        self.user = None
        self.show_login()

    # ---------- Notaus
    def _start_panic(self):
        from core.panic import Panic
        if self.panic_key is None:
            self.panic_key = Panic(self)
        self.panic_key.start()
        from core.hotkey_registry import Entry

        def set_panic(key):
            if not key:
                return "Please enter a shortcut."
            self.settings["panic_hotkey"] = key
            self.save_settings()
            return self.panic_key.start() or None
        self.hotkeys.register(Entry("panic", "Emergency stop", "General", config.DEFAULT_SETTINGS["panic_hotkey"],
                                    get_key=lambda: self.settings.get("panic_hotkey") or "", set_key=set_panic))

    def panic(self):
        """Stoppt Autoclicker und Makros sofort."""
        from core.panic import stop_everything
        done = stop_everything(self)
        self.update_idletasks()
        return done

    def open_layout_editor(self):
        if self.user is None:
            return
        from core import layout_dialog
        layout_dialog.open_editor(self)

    def enter_mini(self):
        """Mini-Modus: kleines Fenster mit Status und Notaus statt des Hauptfensters."""
        if self.user is None:
            return
        from core.minimode import MiniWindow
        if getattr(self, "mini", None) is None:
            self.mini = MiniWindow(self)
        self.mini.show()

    def _open_palette(self, _e=None):
        if self.user is None:
            return
        from core import palette
        palette.open_palette(self)

    def _auto_backup(self):
        """Fällige automatische Sicherung (Einstellungen > Backup). Fehler dürfen den Start nie stören."""
        try:
            from core import backup
            if backup.run_auto(self.settings) is not None:
                self.save_settings()
        except Exception:
            traceback.print_exc()

    def keep_login_for_restart(self):
        """Damit ein Neustart (Update, Modulwechsel) niemanden abmeldet: gibt es keine gemerkte Sitzung, wird eine kurze (1 Tag)
        angelegt und nach dem Wiederanmelden sofort wieder entfernt."""
        try:
            if self.user is None:
                return
            from pathlib import Path
            sp = getattr(self.identity, "session_path", None) or getattr(getattr(self.identity, "store", None), "session_path", None)
            if sp is not None and Path(sp).exists():
                return
            self.identity.remember(self.user, 1)
            self.settings["temp_session"] = True
            config.save_settings(self.settings)
        except Exception:
            traceback.print_exc()

    def restart(self, ask: bool = True):
        """Startet den Launcher neu (fragt vorher nach; laufende Makros und Skripte werden gestoppt). Die Anmeldung bleibt erhalten."""
        from tkinter import messagebox
        if ask and not messagebox.askyesno(tr("Restart launcher"), tr("Restart the launcher now? Running macros and scripts are stopped.")):
            return
        self.keep_login_for_restart()
        from core import relaunch, shortcuts
        try:
            self.panic()
        except Exception:
            traceback.print_exc()
        try:
            relaunch.spawn(shortcuts.command())
        except Exception as exc:
            relaunch.log(f"restart failed: {type(exc).__name__}: {exc}")
            self.show_error(tr("Restart launcher"), tr("Error: {e}", e=f"{type(exc).__name__}: {exc}"), "E-APP-004")
            return
        self.close()

    def _shutdown_plugins(self):
        self.hotkeys.shutdown()
        if self.panic_key is not None:
            self.panic_key.stop()
        if self._loaded:
            for p in self.plugins:
                try:
                    p.on_shutdown()
                except Exception as exc:
                    print("Shutdown error:", exc)
            self._loaded = False

    # ---------- Hauptansicht
    def build_main(self):
        self._reset_root()
        root = self.root_frame
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self._build_sidebar(root)
        G = theme.GAP
        self.content = ctk.CTkFrame(root, corner_radius=theme.PANEL_RADIUS, fg_color=theme.c("main"),
                                    border_width=1, border_color=theme.c("hover"))
        self.content.grid(row=0, column=1, sticky="nsew", padx=(G // 2, G), pady=G)
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self._build_banner()
        # Das Dashboard wird erst beim ersten Anzeigen gebaut (spart beim Neuaufbau nach Einstellungen Zeit).

    def _build_sidebar(self, root):
        G = theme.GAP
        self.sidebar = ctk.CTkFrame(root, width=235, corner_radius=theme.PANEL_RADIUS, fg_color=theme.c("sidebar"),
                                    border_width=1, border_color=theme.c("hover"))
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(G, G // 2), pady=G)
        self.sidebar.grid_propagate(False)
        self.logo = self._logo_label(self.sidebar, 195)
        self.logo.pack(padx=20, pady=(24, 14), anchor="w")
        self.move_btn = ctk.CTkButton(self.sidebar, text="⇅  " + tr("Move modules"), height=28, corner_radius=8, fg_color=theme.c("hover"),
                                      hover_color=theme.c("inset"), text_color=theme.TEXT, command=self.open_layout_editor)
        self.move_btn.pack(fill="x", padx=12, pady=(0, 6))
        # Der untere Block wird VOR den Menüpunkten gepackt: wird das Fenster niedrig, bleiben Notaus, Einstellungen,
        # Abmelden und Version sichtbar und die Menüpunkte rücken zusammen.
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(0, 10))
        self._build_ad_box(bottom)           # unten links
        self.user_label = ctk.CTkLabel(bottom, text="", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.user_label.pack(fill="x", padx=20, pady=(8, 2))
        ctk.CTkButton(bottom, text="↻  " + tr("Restart launcher"), height=30, corner_radius=8, fg_color=theme.c("hover"),
                      hover_color=theme.c("inset"), text_color=theme.TEXT, command=self.restart).pack(fill="x", padx=12, pady=(2, 2))
        ctk.CTkButton(bottom, text="▫  " + tr("Mini mode"), height=30, corner_radius=8, fg_color=theme.c("hover"),
                      hover_color=theme.c("inset"), text_color=theme.TEXT, command=self.enter_mini).pack(fill="x", padx=12, pady=(2, 2))
        ctk.CTkButton(bottom, text="■  " + tr("Emergency stop"), height=30, corner_radius=8, fg_color="#b91c1c",
                      hover_color="#7f1d1d", text_color="white", command=self.panic).pack(fill="x", padx=12, pady=(2, 4))
        self._add_nav("settings", "⚙  " + tr("Settings"), parent=bottom)
        self._add_nav("assistant", "💬  " + tr("Help assistant"), parent=bottom)
        self._add_nav("contact", "✉  " + tr("Contact"), parent=bottom)          # direkt unter dem Hilfe-Assistenten
        ctk.CTkButton(bottom, text="🚩  " + tr("Report"), anchor="w", height=36, corner_radius=8, fg_color="transparent",
                      text_color=theme.TEXT, hover_color=theme.c("hover"), command=self.open_report).pack(fill="x", padx=12, pady=2)
        ctk.CTkButton(bottom, text="⎋  " + tr("Sign out"), anchor="w", height=36, corner_radius=8, fg_color="transparent",
                      text_color=theme.TEXT, hover_color=theme.c("hover"), command=self.logout).pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(bottom, text=f"v{APP_VERSION}", text_color=theme.MUTED).pack(pady=(4, 0))
        # Die Menüpunkte liegen in einem scrollbaren Bereich: bei einem kleinen Fenster (nicht Vollbild) sind trotzdem alle Module erreichbar.
        self.nav_area = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0, width=200)
        self.nav_area.pack(fill="both", expand=True, padx=(0, 2))
        self._add_nav("dashboard", "⌂  " + tr("Dashboard"), parent=self.nav_area)
        for pid, label in self.nav_entries():
            if pid not in ("assistant", "contact"):      # stehen fest unten: Einstellungen, Hilfe-Assistent, Kontakt, Abmelden
                self._add_nav(pid, label, parent=self.nav_area)
        self.refresh_user_labels()
        self._compact = None
        self._fit_sidebar()

    def _rebuild_sidebar(self):
        """Nur die Seitenleiste neu aufbauen (Symbole, Reihenfolge, Kartoffel-Modus): die Seiten bleiben unberührt."""
        try:
            self.sidebar.destroy()
        except Exception:
            pass
        self.nav = {}
        self._build_sidebar(self.root_frame)
        self._highlight()

    def _rebuild_banner(self):
        if getattr(self, "banner", None) is not None:
            try:
                self.banner.destroy()
            except Exception:
                pass
        self._build_banner()

    # ---------- Seitenleiste passt sich der Fensterhöhe an
    COMPACT_LEVELS = ((780, 0), (680, 1), (0, 2))        # (ab Fensterhöhe, Stufe)

    def _sidebar_level(self) -> int:
        h = self.winfo_height()
        if not isinstance(h, int) or h <= 1:      # Fenster noch nicht angezeigt
            return 0
        return next(level for limit, level in self.COMPACT_LEVELS if h >= limit)

    def _fit_sidebar(self, _e=None):
        """Stufe 0: alles. Stufe 1: ohne Werbefeld. Stufe 2: zusätzlich ohne Logo und mit flacheren Knöpfen."""
        try:
            if not self.sidebar.winfo_exists():
                return
            level = self._sidebar_level()
            if level == self._compact:
                return
            self._compact = level
            btn_h = (40, 36, 30)[level]
            for b in self.nav.values():
                b.configure(height=btn_h)
            if level >= 1:
                self.ad_box.pack_forget()
            else:
                self.ad_box.pack(before=self.user_label, padx=14, pady=(0, 4))
            if level >= 2:
                self.logo.pack_forget()
            elif not self.logo.winfo_manager():
                self.logo.pack(padx=20, pady=(24, 14), anchor="w", before=self.move_btn)
        except Exception:
            traceback.print_exc()

    def _on_resize(self, e):
        if e.widget is not self:
            return
        size = (e.width, e.height)
        if size == getattr(self, "_last_size", None):          # nur verschoben, nicht in der Größe geändert
            return
        self._last_size = size
        self._last_input = time.monotonic()
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        # Während des Ziehens die (teure) Seite ausblenden, danach einmal neu anordnen: flüssiges Vergrößern/Verkleinern
        if self.settings.get("resize_freeze", True) and self.current in self.pages and not self._frozen:
            try:
                self.pages[self.current].grid_remove()
                self._frozen = True
            except Exception:
                pass
        self._resize_job = self.after(160, self._after_resize)

    def _after_resize(self):
        self._resize_job = None
        self._fit_sidebar()
        if self._frozen:
            self._frozen = False
            page = self.pages.get(self.current)
            if page is not None:
                try:
                    page.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
                except Exception:
                    pass

    # ---------- Anordnung (Reihenfolge, Sichtbarkeit, Hintergrundbild)
    def layout_items(self) -> list[tuple[str, str]]:
        """Alle verschiebbaren Einträge (Modul-ID, Anzeigename) in der gespeicherten Reihenfolge."""
        names = {p.id: f"{p.icon}  {tr(p.name)}" for p in self.plugins if getattr(p, "nav", True) and (self.is_admin or not getattr(p, "admin_only", False))}
        return [(i, names[i]) for i in layout.normalize_order(list(names), self.settings.get("nav_order"))]

    def nav_entries(self) -> list[tuple[str, str]]:
        hidden = set(self.settings.get("nav_hidden") or [])
        return [(i, label) for i, label in self.layout_items() if i not in hidden]

    def visible_plugins(self):
        shown = {i for i, _ in self.nav_entries()}
        return [p for p in self.plugins if p.id in shown]

    def set_layout(self, order=None, hidden=None):
        if order is not None:
            self.settings["nav_order"] = list(order)
        if hidden is not None:
            self.settings["nav_hidden"] = list(hidden)
        self.save_settings()
        self._soft_scopes = self._soft_scopes | {"sidebar"}
        if self._soft_job is None:
            self._soft_job = self.after(120, self._soft_rebuild)

    def _build_banner(self):
        """Eigenes Hintergrundbild als Banner über dem Seiteninhalt (Tk kennt keine durchsichtigen Widgets)."""
        self.banner = None
        path = self.settings.get("bg_image") or ""
        if not path or self.settings.get("potato_mode"):
            return
        try:
            h = layout.HEIGHTS.get(self.settings.get("bg_height"), layout.HEIGHTS["Medium"])
            img = background.render(path, 1920, h, layout.clamp_dim(self.settings.get("bg_dim")))
            self._bg_img = ctk.CTkImage(light_image=img, dark_image=img, size=(1920, h))
            box = ctk.CTkFrame(self.content, height=h, corner_radius=theme.CARD_RADIUS, fg_color=theme.c("main"))
            box.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
            box.pack_propagate(False)
            lab = ctk.CTkLabel(box, text="", image=self._bg_img)
            lab.place(relx=0.5, rely=0.5, anchor="center")
            self.banner = box
        except Exception:
            traceback.print_exc()
            self.banner = None

    def _logo_label(self, parent, width):
        """Logo als Bild; fällt auf den Namen als Text zurück, falls das Bild nicht geladen werden kann."""
        try:
            img = appicon.logo_image()
            h = round(img.height * width / img.width)
            self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(width, h))
            return ctk.CTkLabel(parent, text="", image=self._logo_img)
        except Exception:
            traceback.print_exc()
            return ctk.CTkLabel(parent, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold"))

    def _build_ad_box(self, parent):
        """Werbefenster (Platzhalter). Siehe core/ads.py: Es wird nichts geladen, solange keine Ad Unit ID gesetzt ist."""
        prov = ads.provider()
        box = ctk.CTkFrame(parent, width=200, height=84, corner_radius=10, fg_color=theme.c("inset"), border_width=1,
                           border_color=theme.c("hover"))
        box.pack(padx=14, pady=(0, 4))
        box.pack_propagate(False)
        ctk.CTkLabel(box, text=tr("Advertisement"), font=ctk.CTkFont(size=10), text_color=theme.MUTED).pack(anchor="w", padx=8, pady=(4, 0))
        ctk.CTkLabel(box, text=tr("Ad space (placeholder)") if not prov.available() else tr("Loading …"),
                     text_color=theme.MUTED, wraplength=180).pack(expand=True)
        self.ad_box = box

    def _add_nav(self, pid: str, label: str, parent=None):
        icon, text = None, label
        col = theme.icon_color(pid) if self.settings.get("colored_icons", True) and not self.settings.get("potato_mode") else None
        if col and "  " in label:
            icon, text = label.split("  ", 1)
        btn = ctk.CTkButton(parent or self.sidebar, text=("\u2003" * 3 + " " + text) if icon else label, anchor="w", height=40, corner_radius=12,
                            fg_color="transparent", text_color=theme.TEXT, hover=False, command=lambda: self.show(pid))
        btn.pack(fill="x", padx=12, pady=1)
        self.nav[pid] = btn
        lab = None
        if icon:
            lab = ctk.CTkLabel(btn, text=icon, text_color=col, width=22, fg_color="transparent")
            lab.place(x=12, rely=0.5, anchor="w")
            lab.bind("<Button-1>", lambda e: self.show(pid))
            btn._icon_label = lab

        def paint(inside: bool):
            if pid == self.current or not self.settings.get("hover_effect", True):
                return
            colour = theme.hover_tint() if inside else "transparent"
            btn.configure(fg_color=colour)
            if lab is not None:
                lab.configure(fg_color=colour)
        hover_area(btn, paint, extra=(lab,) if lab is not None else ())

    def refresh_user_labels(self):
        if self.user and getattr(self, "user_label", None) is not None and self.user_label.winfo_exists():
            self.user_label.configure(text=f"👤  {self.user['display_name']}")
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self.dashboard.welcome.configure(text=tr("Welcome, {name}!", name=self.user["display_name"]) + " 👋")

    def show(self, pid: str):
        self._last_input = time.monotonic()
        if self.current in self.pages:
            self.pages[self.current].grid_forget()
        if pid not in self.pages:
            try:
                if pid == "dashboard":
                    self.dashboard = DashboardPage(self.content, self)
                    self.pages[pid] = self.dashboard
                elif pid in self.plugin_by_id:
                    self.pages[pid] = self.plugin_by_id[pid].create_page(self.content)
                else:
                    self.pages[pid] = self._builtin[pid](self.content, self)
            except Exception:
                traceback.print_exc()
                box = ctk.CTkFrame(self.content, fg_color=theme.c("main"))
                ctk.CTkLabel(box, text=tr("This page could not be loaded:") + "\n\n" + traceback.format_exc()[-900:],
                             text_color=theme.DANGER, justify="left", wraplength=620).pack(padx=24, pady=24, anchor="w")
                self.pages[pid] = box
        self.pages[pid].grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        if self.current != pid:
            self.previous = self.current
            self.trail = (self.trail + [pid])[-8:]
        self.current = pid
        if pid == "assistant" and hasattr(self.pages[pid], "show_chips"):
            self.pages[pid].show_chips()
        self._schedule_prewarm()
        self._highlight()

    def _highlight(self):
        pid = self.current
        for k, b in self.nav.items():
            active = k == pid
            b.configure(fg_color=theme.accent() if active else "transparent",
                        text_color=theme.contrast_text(theme.accent()) if active else theme.TEXT)
            lab = getattr(b, "_icon_label", None)
            if lab is not None:
                try:
                    lab.configure(fg_color=theme.accent() if active else "transparent")
                except Exception:
                    pass

    # ---------- Einstellungen
    def save_settings(self):
        """Lokal speichern und (bei Cloud-Konto) verschlüsselt in die Datenbank spiegeln (entprellt)."""
        self._save_job_schedule()
        if self.user is None or getattr(self.identity, "backend", "") != "cloud":
            return
        if self._push_job is not None:
            self.after_cancel(self._push_job)
        self._push_job = self.after(1500, lambda: self.identity.push_settings(self.user, self.settings))

    def _save_job_schedule(self):
        """Die Datei wird höchstens alle 0,4 s geschrieben (Schieberegler, Farbwahl): weniger Festplattenzugriffe, kein Ruckeln."""
        self._dirty = True
        if getattr(self, "_save_job", None) is None:
            self._save_job = self.after(400, self.flush_settings)

    def flush_settings(self):
        self._save_job = None
        if getattr(self, "_dirty", False):
            self._dirty = False
            try:
                config.save_settings(self.settings)
            except OSError:
                traceback.print_exc()

    # Welche Einstellung braucht welchen Neuaufbau? Nur Farben/Größe/Sprache erzeugen alle Widgets neu.
    SOFT_SCOPES = {"colored_icons": "sidebar", "potato_mode": "both", "bg_image": "banner", "bg_dim": "banner", "bg_height": "banner",
                   "hover_effect": "none"}

    def apply_look(self, changes: dict):
        self.settings.update(changes)
        self.save_settings()
        theme.apply(self.settings)
        scopes = {self.SOFT_SCOPES.get(k, "full") for k in changes} or {"full"}
        scopes.discard("none")                      # z. B. Hover-Effekt: wirkt sofort, braucht keinen Neuaufbau
        if not scopes:
            return
        if "full" in scopes:
            self._schedule_rebuild()
            return
        self._soft_scopes = self._soft_scopes | scopes
        if self._soft_job is None:
            self._soft_job = self.after(120, self._soft_rebuild)

    def _soft_rebuild(self):
        self._soft_job = None
        scopes, self._soft_scopes = self._soft_scopes, set()
        if self.user is None or getattr(self, "content", None) is None:
            return
        if scopes & {"sidebar", "both"}:
            self._rebuild_sidebar()
        if scopes & {"banner", "both"}:
            self._rebuild_banner()

    def set_language(self, code: str):
        self.settings["language"] = code
        self.save_settings()
        i18n.set_language(code)
        self.update_text = tr("Update status: not checked yet")
        self._schedule_rebuild()

    def _schedule_rebuild(self):
        """Mehrere Änderungen kurz hintereinander (Schieberegler, mehrere Schalter) bauen die Oberfläche nur einmal neu auf."""
        if self._rebuild_job is not None:
            self.after_cancel(self._rebuild_job)
        self._rebuild_job = self.after(150, self._rebuild_keep_page)

    # Seiten im Leerlauf vorbereiten, damit der erste Wechsel in ein Modul nicht lange lädt
    PREWARM = ("autoclicker", "gamemacros", "macros", "productivity", "clicktools", "gamer")

    def _schedule_prewarm(self):
        if self._prewarm_job is None and not self.settings.get("potato_mode"):
            self._prewarm_job = self.after(2500, self._prewarm_step)

    def _prewarm_step(self):
        self._prewarm_job = None
        try:
            if time.monotonic() - self._last_input < 3.0 or self.settings.get("potato_mode"):
                self._schedule_prewarm()           # nur im Leerlauf vorbauen, nie während man bedient
                return
            if self.user is None or not self.winfo_exists() or getattr(self, "content", None) is None:
                return
            shown = {i for i, _ in self.nav_entries()}
            for pid in self.PREWARM:
                if pid in shown and pid not in self.pages and pid in self.plugin_by_id:
                    self.pages[pid] = self.plugin_by_id[pid].create_page(self.content)     # gebaut, aber nicht angezeigt
                    self._prewarm_job = self.after(600, self._prewarm_step)
                    return
        except Exception:
            traceback.print_exc()

    def _rebuild_keep_page(self):
        self._rebuild_job = None
        if self._prewarm_job is not None:
            self.after_cancel(self._prewarm_job)
            self._prewarm_job = None
        page = self.current or "dashboard"
        self.configure(fg_color=theme.c("backdrop"))
        self.build_main()
        self.show(page)

    def apply_limits(self) -> list[str]:
        s = self.settings
        return system_limits.apply(s["cpu_priority"], int(s["cpu_cores"]), int(s["ram_limit_mb"]))

    # ---------- Fehler, KI-Hilfe und Meldungen (Update 1.9.0)
    def record_error(self, code: str, text: str, kind: str = "error", trace: str = "") -> None:
        """Automatische Meldung mit Fehlercode (nur wenn "Diagnose senden" an ist und ein Cloud-Konto angemeldet ist)."""
        self.telemetry.report(kind, text, trace, code)

    def show_error(self, title: str, message: str, code: str | None = None, parent=None) -> None:
        from core import error_dialog
        error_dialog.show_error(self, title, message, code, parent)

    def open_report(self, code: str | None = None, text: str = "", category: str = "bug") -> None:
        from core import error_dialog
        error_dialog.open_report(self, code, text, category)

    def ask_help(self, text: str) -> bool:
        """Stellt eine Bedienfrage dem Hilfe-Assistenten (kennt das Programm, antwortet auch offline)."""
        self.show("assistant")
        page = self.pages.get("assistant")
        if page is not None and hasattr(page, "ask"):
            page.ask(text)
            return True
        return False

    def ask_ai(self, text: str, preset: str = "Free chat") -> bool:
        """Öffnet das Modul "AI Chat" und schickt `text` ab (z. B. vom Dashboard oder "Ask AI" im Fehlerfenster)."""
        if "aichat" in self.plugin_by_id:
            self.show("aichat")
            page = self.pages.get("aichat")
            if page is not None and hasattr(page, "ask_external"):
                page.ask_external(text, preset)
                return True
        self.show("assistant")
        page = self.pages.get("assistant")
        if page is not None and hasattr(page, "ask"):
            page.ask(text)
        return False

    # ---------- Thread-sichere UI-Aufrufe
    def call_soon(self, fn, *args, **kwargs):
        self._ui_q.put((fn, args, kwargs))

    def _drain(self):
        try:
            while True:
                fn, args, kwargs = self._ui_q.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(TICK_MS, self._drain)

    # ---------- Updates
    def check_updates(self, manual: bool = False):
        def work():
            try:
                info, err = updater.check(), None
            except Exception as exc:
                info, err = None, (exc if isinstance(exc, updater.NoReleaseYet) else str(exc))
            try:                                   # bei jeder Prüfung auch nach einer neuen Arena schauen (nur wenn sie installiert ist)
                from modules.arena import plugin as arena_plugin
                arena = arena_plugin.update_info()
            except Exception:
                arena = None
            self.call_soon(self._on_update_result, info, err, manual, arena)

        threading.Thread(target=work, daemon=True).start()

    def _set_update_text(self, text):
        self.update_text = text
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self.dashboard.set_update_text(text)

    def _on_update_result(self, info, err, manual, arena=None):
        if self.user is None:
            return
        if isinstance(err, updater.NoReleaseYet):
            self._set_update_text(str(err))
        elif err:
            self._set_update_text(tr("Update check failed: {e}", e=err) + " [E-UPD-001]")
            self.record_error("E-UPD-001", str(err), "update")
        elif info:
            self._set_update_text(tr("New version {v} available", v=info.version))
            UpdateDialog(self, info, arena)
            return
        else:
            self._set_update_text(tr("You have the latest version."))
        if arena:
            self._set_update_text(self.update_text + "  ·  " + tr("New Recoil Arena version {v}", v=arena["available"]))
            ArenaUpdateDialog(self, arena)

    # ---------- Beenden
    def report_callback_exception(self, exc, val, tb):
        """Fehler in Tk-Rückrufen: wie gewohnt ausgeben und zusätzlich (anonym) melden."""
        traceback.print_exception(exc, val, tb)
        self.telemetry.report_exc("ui", exc, val, tb)

    def close(self):
        for step in (self.telemetry.stop, self.flush_settings, self._shutdown_plugins):
            try:
                step()                       # ein Fehler hier darf das Beenden (und damit den Neustart) nicht abbrechen
            except Exception:
                traceback.print_exc()
        try:
            self.destroy()
        except Exception:
            traceback.print_exc()
