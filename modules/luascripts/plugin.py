"""Modul "Lua scripts": eigene Lua-Skripte in einer Sandbox ausführen (Bibliothek lupa).

Skripte liegen als <name>.lua im Datenordner (lua_scripts). Hinzufügen: auf dieser Seite oder im Menüpunkt Modules.
Ein Skript darf rechnen, print(...), wait(ms) und macro("...") benutzen (Makro-Sprache des Launchers).
Notaus (Strg+Umschalt+F12) und der Stopp-Knopf beenden es.
"""
import traceback

from core.i18n import tr
from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "luascripts"
    name = "Lua scripts"
    icon = "🌙"
    version = "1.0.0"
    order = 70
    description = "Run your own Lua scripts safely: calculations, output and macro commands."

    def on_load(self):
        self.runner = None
        self.on_line = None              # die Seite setzt hier eine Funktion für Ausgaben

    def macros(self):
        return self.app.plugin_by_id.get("macros")

    def _emit(self, text, ok=True):
        cb = self.on_line
        if cb is not None:
            try:
                self.app.call_soon(cb, text, ok)
            except Exception:
                traceback.print_exc()

    @property
    def running(self) -> bool:
        return self.runner is not None and self.runner.running

    def run_script(self, name: str) -> str:
        """Gibt '' oder einen Fehlertext zurück."""
        from core import module_import
        from .runner import LuaRunner
        if self.running:
            return tr("A script is already running. Stop it first.")
        try:
            text = module_import.read_lua(name)
        except module_import.ImportErrorJOPML as exc:
            return str(exc)
        self.runner = LuaRunner(text, self._emit, macros=self.macros())
        err = self.runner.start()
        if not err:
            self._emit(tr("Started: {n}", n=name))
        return err

    def stop(self) -> None:
        if self.runner is not None:
            self.runner.stop()

    def on_shutdown(self):
        self.stop()

    def create_page(self, parent):
        from .page import LuaPage
        return LuaPage(parent, self)
