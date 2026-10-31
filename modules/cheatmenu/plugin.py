"""Modul "Cheat-Menü": Einzelspieler-Cheats für Minecraft (Befehle) und GTA 5 Enhanced (offizielle Cheat-Codes).

Minecraft-Cheats laufen über das Modul "My macros" (gleicher Ausführer, Notaus und F7 gelten auch hier).
GTA-Cheats tippt gta_input.py über Scan-Codes in die Cheat-Konsole des Spiels.
Jeder Cheat bekommt einen Eintrag in Einstellungen > Hotkeys (Gruppe "Cheat menu"), standardmäßig ohne Taste.
"""
import threading
import traceback

from core.i18n import tr
from core.plugin_api import BasePlugin

GROUP = "Cheat menu"
DEFAULTS = {"delay": 3, "chat_key": "t", "console": "auto", "recoil_best": {}, "recoil3d_best": {}, "recoil_history": [], "trainer_prefs": {}}


class Plugin(BasePlugin):
    id = "cheatmenu"
    name = "Cheat menu"
    icon = "🕹️"
    version = "1.0.0"
    order = 65
    description = "Single-player cheats for Minecraft and GTA 5 Enhanced, plus a recoil trainer."

    def on_load(self):
        from . import cheats
        self.status = ""
        self.on_status = None              # die Seite setzt hier eine Funktion für Statusmeldungen
        self._stop = threading.Event()
        try:
            from core.hotkey_registry import Entry
            reg = self.app.hotkeys
            for c in cheats.ALL.values():
                label = ("GTA: " if cheats.is_gta(c.id) else "Minecraft: ") + c.title
                reg.register(Entry(f"cm.{c.id}", label, GROUP, "", action=lambda cid=c.id: self.run(cid, hotkey=True)))
        except Exception:                  # ohne Hotkey-Verwaltung läuft das Menü trotzdem
            traceback.print_exc()

    # ---- Einstellungen ----
    def cfg(self) -> dict:
        saved = self.app.settings.get("cheatmenu")
        out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
        if isinstance(saved, dict):
            out.update({k: v for k, v in saved.items() if k in DEFAULTS})
        return out

    def set_cfg(self, **kw) -> None:
        store = self.app.settings.setdefault("cheatmenu", {})
        store.update({k: v for k, v in kw.items() if k in DEFAULTS})
        self.app.save_settings()

    def _say(self, text: str, ok: bool = True) -> None:
        self.status = text
        cb = self.on_status
        if cb is None:
            return
        try:
            self.app.after(0, lambda: cb(text, ok))
        except Exception:
            pass

    # ---- Ausführen ----
    def run(self, cheat_id: str, hotkey: bool = False, custom: str = "") -> str:
        """Startet einen Cheat. Über einen Hotkey ohne Wartezeit, über die Seite mit Start-Verzögerung."""
        from . import cheats
        cfg = self.cfg()
        try:
            delay = 0 if hotkey else max(0, min(30, float(cfg["delay"])))
        except (TypeError, ValueError):
            delay = 3
        if cheat_id == "mc_custom":
            commands = (custom,)
            title = "Eigener Befehl"
        else:
            c = cheats.ALL.get(cheat_id)
            if c is None:
                return "Unbekannter Cheat."
            commands, title = c.commands, c.title
        if cheats.is_gta(cheat_id):
            return self._run_gta(title, commands, cfg["console"], delay)
        return self._run_minecraft(title, commands, cfg["chat_key"], delay)

    def _run_minecraft(self, title, commands, chat_key, delay) -> str:
        from . import cheats
        macros = self.app.plugin_by_id.get("macros")
        if macros is None:
            return "Das Modul „My macros“ fehlt – es wird für die Minecraft-Cheats gebraucht."
        try:
            script = cheats.minecraft_script(commands, delay, chat_key)
        except ValueError as exc:
            return tr(str(exc))
        if macros.state == "running":
            macros.stop()
        err = macros.run(script)
        if not err:
            self._say(f"Minecraft: {title}" + (f" – in {delay:g} s ins Spiel wechseln!" if delay else ""))
        return err

    def _run_gta(self, title, codes, console, delay) -> str:
        from . import gta_input
        if not gta_input.available():
            return "Die GTA-Cheats gehen nur unter Windows."
        self._stop.clear()

        def work():
            err = gta_input.send_codes(codes, console, delay, self._stop)
            self._say(err or f"GTA: {title} eingegeben.", ok=not err)

        threading.Thread(target=work, daemon=True, name="cheatmenu-gta").start()
        self._say(f"GTA: {title}" + (f" – in {delay:g} s ins Spiel wechseln!" if delay else ""))
        return ""

    def stop(self) -> None:
        self._stop.set()
        macros = self.app.plugin_by_id.get("macros")
        if macros is not None and macros.state == "running":
            macros.stop()

    def on_shutdown(self):
        self._stop.set()

    def dashboard_summary(self) -> str:
        return "Single-player cheats for Minecraft and GTA 5 Enhanced, plus a recoil trainer."

    def create_page(self, parent):
        from .page import CheatMenuPage
        return CheatMenuPage(parent, self)
