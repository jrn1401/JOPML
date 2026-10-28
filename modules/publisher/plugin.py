"""Modul "Veröffentlichen": neue Versionen für alle Nutzer bereitstellen. Nur für Admin-Konten sichtbar."""
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "publisher"
    name = "Publish"
    icon = "⬆"
    version = "1.0.0"
    order = 90
    admin_only = True          # nur sichtbar, wenn der Server das Konto als Admin bestätigt hat
    description = "Upload new versions for all users (admin only)."

    def create_page(self, parent):
        from .page import PublisherPage
        return PublisherPage(parent, self)
