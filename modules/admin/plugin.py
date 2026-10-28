"""Modul "Admin": Übersicht (Nutzer online, Server-Zustand), registrierte Konten, Fehlerberichte und das Veröffentlichen neuer Versionen.
Nur für Admin-Konten sichtbar; alle Abfragen prüft der Server noch einmal (jopml_is_admin)."""
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "admin"
    name = "Admin"
    icon = "🛡"
    version = "1.0.0"
    order = 90
    admin_only = True
    description = "Server overview, accounts, error reports and publishing (admin only)."

    def create_page(self, parent):
        from .page import AdminPage
        return AdminPage(parent, self)

    def rpc(self, name: str, args: dict | None = None):
        """Server-Aufruf (blockierend – nur aus einem Hintergrund-Thread aufrufen)."""
        client = getattr(self.app.identity, "client", None)
        if client is None or not getattr(client, "session", None):
            raise RuntimeError("Not signed in with a cloud account.")
        return client.rpc(name, args or {})
