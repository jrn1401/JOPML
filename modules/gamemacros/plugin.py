"""Modul "Game macros": fertige Makros für Spiele (Minecraft, Idle-Spiele, Inventar, Chat).

Die Makros laufen über das Modul "My macros" (gleicher Ausführer, F7 und Notaus gelten auch hier).
Jedes Makro kann einen eigenen Start-Hotkey (ohne Stopp-Taste schaltet er um) und optional einen eigenen Stopp-Hotkey haben;
beide lassen sich auf ein Programm beschränken. Die Tasten verwaltet die zentrale Hotkey-Verwaltung (Einstellungen > Hotkeys)."""
import time

from core.hotkey_registry import Entry
from core.i18n import tr
from core.plugin_api import BasePlugin

CHAT_COOLDOWN_S = 2.0        # Schutz vor Chat-Spam: zwei Chat-Makros nie dichter hintereinander


class Plugin(BasePlugin):
    id = "gamemacros"
    name = "Game macros"
    icon = "🎮"
    version = "1.1.0"
    order = 30
    description = "Ready-made macros for games (Minecraft, idle games, inventory, chat)."

    def on_load(self):
        from . import library
        self.status = ""
        self.running_id = ""
        self._last_chat = 0.0
        self.on_change = None            # Seite setzt hier eine Funktion, die nach Hotkey-Änderungen die Anzeige aktualisiert
        reg = self.app.hotkeys
        for pr in library.PRESETS:
            reg.register(Entry(f"gm.{pr.id}", pr.title, "Game macros", "", action=lambda pr=pr: self.toggle_preset(pr)))
        stored = self.app.settings.get("hotkeys") or {}
        for pr in library.PRESETS:
            if f"gm.stop.{pr.id}" in stored:
                self._register_stop(pr)

    # ---- Werte und Platzhalter ----
    def context(self) -> dict:
        gamer = self.app.plugin_by_id.get("gamer")
        rnd = getattr(getattr(gamer, "match", None), "rounds", None)
        name = (self.app.user or {}).get("display_name") or (self.app.user or {}).get("username") or ""
        return {"time": time.strftime("%H:%M"), "round": rnd if rnd is not None else "", "name": name}

    def params_for(self, preset) -> dict:
        saved = (self.app.settings.get("gm_params") or {}).get(preset.id)
        return dict(saved) if isinstance(saved, dict) else {}

    def remember(self, preset, raw: dict) -> None:
        store = self.app.settings.setdefault("gm_params", {})
        store[preset.id] = {k: str(v) for k, v in raw.items()}
        self.app.save_settings()

    # ---- Starten / Stoppen ----
    def run_preset(self, preset, raw: dict) -> str:
        """Gibt '' bei Erfolg oder einen Fehlertext zurück."""
        from . import library
        macros = self.app.plugin_by_id.get("macros")
        if macros is None:
            return tr("The macro module is not available.")
        if preset.category == "chat" and time.time() - self._last_chat < CHAT_COOLDOWN_S:
            return tr("Please wait a moment (protection against chat spam).")
        try:
            script = library.build(preset, raw, self.context())
        except ValueError as exc:
            return str(exc)
        if macros.state == "running":
            macros.stop()
        self.remember(preset, raw)
        err = macros.run(script)
        if not err:
            self.running_id = preset.id
            if preset.category == "chat":
                self._last_chat = time.time()
        return err

    def toggle_preset(self, preset) -> str:
        """Hotkey: läuft dieses Makro, wird es gestoppt, sonst mit den zuletzt benutzten Werten gestartet."""
        macros = self.app.plugin_by_id.get("macros")
        if macros is not None and macros.state == "running" and self.running_id == preset.id:
            self.stop()
            return ""
        return self.run_preset(preset, self.params_for(preset))

    def stop(self) -> None:
        macros = self.app.plugin_by_id.get("macros")
        if macros is not None:
            macros.stop()
        self.running_id = ""

    def save_preset(self, preset, raw: dict, name: str) -> str:
        from . import library
        macros = self.app.plugin_by_id.get("macros")
        try:
            script = library.build(preset, raw, self.context())
            macros.save(name, script)
        except (ValueError, OSError) as exc:
            return str(exc)
        return ""

    # ---- Hotkeys je Makro ----
    def hotkey_ids(self, preset) -> tuple[str, str]:
        return f"gm.{preset.id}", f"gm.stop.{preset.id}"

    def _register_stop(self, preset):
        self.app.hotkeys.register(Entry(f"gm.stop.{preset.id}", preset.title, "Game macros (stop key)", "",
                                        action=lambda: self.stop_if_running(preset)))

    def stop_if_running(self, preset) -> None:
        macros = self.app.plugin_by_id.get("macros")
        if macros is not None and macros.state == "running" and self.running_id == preset.id:
            self.stop()

    def set_start_key(self, preset, text: str, raw: dict | None = None) -> str:
        if raw is not None:
            self.remember(preset, raw)
        return self.app.hotkeys.set_key(f"gm.{preset.id}", text)

    def set_stop_key(self, preset, text: str) -> str:
        sid = f"gm.stop.{preset.id}"
        if not (text or "").strip():
            self.app.hotkeys.unregister(sid)
            self.app.settings.get("hotkeys", {}).pop(sid, None)
            self.app.save_settings()
            self.app.hotkeys.apply_soon()
            return ""
        if sid not in self.app.hotkeys.entries:
            self._register_stop(preset)
        err = self.app.hotkeys.set_key(sid, text)
        if err:
            self.app.hotkeys.unregister(sid)
        return err

    def create_page(self, parent):
        from .page import GameMacrosPage
        return GameMacrosPage(parent, self)
