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

    # ---- "gelesen"-Markierungen (nur lokal)
    def is_unread(self, channel: dict) -> bool:
        last = channel.get("last_id")
        return bool(last) and int(last) > int(self.seen.get(channel["id"], 0))

    def mark_seen(self, channel_id: str, last_id) -> None:
        if last_id and int(last_id) > int(self.seen.get(channel_id, 0)):
            self.seen[channel_id] = int(last_id)

    def on_shutdown(self):
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
