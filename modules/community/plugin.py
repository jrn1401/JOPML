"""Modul "Community": Server, Kanäle und Direktnachrichten (Ende-zu-Ende-verschlüsselt) sowie ein öffentliches Forum.
Braucht ein Cloud-Konto (Supabase). Mit lokalen Konten zeigt die Seite nur einen Hinweis."""
import threading

from core import config
from core.plugin_api import BasePlugin

SEEN_FILE = "community_seen.json"


class Plugin(BasePlugin):
    id = "community"
    name = "Community"
    icon = "👥"
    version = "1.0.0"
    order = 70
    description = "Chat servers, direct messages (end-to-end encrypted) and a public forum for all users."

    def on_load(self):
        self._svc = None
        self._forum = None
        self._lock = threading.Lock()
        seen = config.load_json(config.app_dir() / SEEN_FILE, {})
        self.seen: dict = seen if isinstance(seen, dict) else {}
        self.chat_active = False                  # True, solange die Chat-Ansicht läuft (sie meldet dann selbst)
        from .watcher import Watcher
        self.watcher = Watcher(self)
        self.apply_background()

    def apply_background(self) -> None:
        """Startet oder stoppt die Hintergrund-Abfrage je nach Einstellung (Einstellungen > Benachrichtigungen)."""
        if self.app.notifier.prefs().community_background:
            self.watcher.start()
        else:
            self.watcher.stop()

    # ---- Zugriff auf Dienste (nur mit Cloud-Konto)
    def client(self):
        ident = self.app.identity
        c = getattr(ident, "client", None)
        return c if getattr(ident, "backend", "") == "cloud" and c is not None and getattr(c, "session", None) else None

    def service(self):
        from .service import CommunityService
        with self._lock:
            c = self.client()
            if c is None:
                return None
            if self._svc is None or self._svc.client is not c:
                self._svc = CommunityService(c)
                self._svc.on_spaces = lambda sp: self.app.call_soon(self.cache_spaces, sp)
            return self._svc

    def forum(self):
        from .forum import Forum
        with self._lock:
            c = self.client()
            if c is None:
                return None
            if self._forum is None or self._forum.client is not c:
                self._forum = Forum(c)
            return self._forum

    # ---- Angemeldet bleiben (Passphrase lokal gemerkt, siehe core/secretstore.py)
    def stay_enabled(self) -> bool:
        return bool(self.app.settings.get("community_stay"))

    def _stay_key(self) -> str:
        return str((self.app.user or {}).get("username") or (self.app.user or {}).get("id") or "user")

    def _stay_file(self):
        return config.app_dir() / "community_stay.json"

    def remember_passphrase(self, passphrase: str) -> None:
        from core import secretstore
        d = config.load_json(self._stay_file(), {})
        d = d if isinstance(d, dict) else {}
        d[self._stay_key()] = secretstore.protect(passphrase)
        config.save_json(self._stay_file(), d)

    def stored_passphrase(self) -> str:
        from core import secretstore
        d = config.load_json(self._stay_file(), {})
        tok = d.get(self._stay_key()) if isinstance(d, dict) else None
        if not tok:
            return ""
        try:
            return secretstore.unprotect(tok)
        except Exception:
            return ""

    def forget_passphrase(self, everyone: bool = False) -> None:
        d = config.load_json(self._stay_file(), {})
        if isinstance(d, dict):
            d = {} if everyone else {k: v for k, v in d.items() if k != self._stay_key()}
            config.save_json(self._stay_file(), d)

    def set_stay(self, on: bool) -> None:
        self.app.settings["community_stay"] = bool(on)
        if not on:
            self.forget_passphrase(everyone=True)
        self.app.save_settings()

    def cache_spaces(self, spaces: list) -> None:
        names = [{"id": s.get("id"), "name": s.get("name", "")} for s in spaces if s.get("kind") == "server"]
        if names != self.app.settings.get("community_cache"):
            self.app.settings["community_cache"] = names
            self.app.save_settings()

    # ---- "gelesen"-Markierungen (nur lokal)
    def is_unread(self, channel: dict) -> bool:
        last = channel.get("last_id")
        return bool(last) and int(last) > int(self.seen.get(channel["id"], 0))

    def mark_seen(self, channel_id: str, last_id) -> None:
        if last_id and int(last_id) > int(self.seen.get(channel_id, 0)):
            self.seen[channel_id] = int(last_id)

    def on_shutdown(self):
        self.watcher.stop()
        try:
            config.save_json(config.app_dir() / SEEN_FILE, dict(list(self.seen.items())[-500:]))
        except Exception:
            pass
        if getattr(self, "_svc", None) is not None:
            self._svc.lock()                      # Schlüssel verlassen den Speicher beim Abmelden/Beenden
        self._svc = self._forum = None

    def create_page(self, parent):
        from .page import CommunityPage
        return CommunityPage(parent, self)
