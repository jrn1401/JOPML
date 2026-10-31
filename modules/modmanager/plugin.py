"""Modul "Modules": Verwaltung der importierten Module und Lua-Skripte (hinzufügen, auswählen, entfernen)."""
from core.i18n import tr
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "modmanager"
    name = "Modules"
    icon = "🧩"
    version = "1.0.0"
    order = 85
    description = "Add your own modules and Lua scripts, see all added ones in a list and remove them."

    def on_load(self):
        pass

    def user_plugins(self) -> dict:
        """{Ordnername: Plugin} der geladenen importierten Module."""
        out = {}
        for p in self.app.plugins:
            if getattr(p, "user_module", False):
                out[type(p).__module__.split(".")[1] if "." in type(p).__module__ else p.id] = p
        return out

    def failed(self) -> dict:
        return {n: e for n, e in list(self.app.failed) + list(self.app.load_failed)}

    def dashboard_summary(self):
        from core import module_import
        n = len(module_import.installed())
        return tr("{n} added modules", n=n) if n else None

    def create_page(self, parent):
        from .page import ModulesPage
        return ModulesPage(parent, self)
