"""Modul "AI Chat": mit Gemini oder Groq chatten, Modell wählen, Makros und komplette Module (Code + Oberfläche) schreiben lassen. Die Schlüssel liegen nur auf dem Server."""
from core.i18n import tr
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "aichat"
    name = "AI Chat"
    icon = "🤖"
    version = "2.0.0"
    order = 44
    description = "Chat with Gemini or Groq, pick the model, and let the AI build macros and complete modules."

    def dashboard_summary(self):
        return tr("Chat with Gemini or Groq, pick the model, and let the AI build macros and complete modules.")

    def create_page(self, parent):
        from .page import ChatPage
        return ChatPage(parent, self)
