"""Modul "Game macros": fertige Makros für Spiele (Minecraft, Idle-Spiele, Inventar, Chat) und Anti-Recoil.

Die Makros laufen über das Modul "My macros" (gleicher Ausführer, F7 und Notaus gelten auch hier)."""
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "gamemacros"
    name = "Game macros"
    icon = "🎮"
    version = "1.0.0"
    order = 30
    description = "Ready-made macros for games (Minecraft, idle games, inventory, chat) and anti-recoil."

    def on_load(self):
        self.status = ""

    def run_preset(self, preset, raw: dict) -> str:
        """Gibt '' bei Erfolg oder einen Fehlertext zurück."""
        from . import library
        macros = self.app.plugin_by_id.get("macros")
        if macros is None:
            return "The macro module is not available."
        try:
            script = library.build(preset, raw)
        except ValueError as exc:
            return str(exc)
        if macros.state == "running":
            macros.stop()
        return macros.run(script)

    def stop(self) -> None:
        macros = self.app.plugin_by_id.get("macros")
        if macros is not None:
            macros.stop()

    def save_preset(self, preset, raw: dict, name: str) -> str:
        from . import library
        macros = self.app.plugin_by_id.get("macros")
        try:
            script = library.build(preset, raw)
            macros.save(name, script)
        except (ValueError, OSError) as exc:
            return str(exc)
        return ""

    def create_page(self, parent):
        from .page import GameMacrosPage
        return GameMacrosPage(parent, self)
