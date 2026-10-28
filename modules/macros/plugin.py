"""Modul "My macros": eigene Makros schreiben, prüfen, speichern und ausführen; KI-Generator."""
import re
import threading
import time
import traceback
from pathlib import Path

from core.config import profiles_dir
from core.plugin_api import BasePlugin

from . import dsl

HOTKEY = "<f7>"      # Standard; einstellbar über settings["macros_hotkey"]


class Plugin(BasePlugin):
    id = "macros"
    name = "My macros"
    icon = "✎"
    version = "1.1.0"
    order = 40
    description = "Write your own macros or let the AI create them from a description. Start/stop with F7."

    def on_load(self):
        self.runner = None
        self.state = "idle"          # idle | running
        self.last = ""
        self.hotkey_error = ""
        self.current_text = ""
        self._listener = None
        self._register_hotkey()
        from core.hotkey_registry import Entry

        def set_key(key):
            if not key:
                return "Please enter a shortcut."
            self.app.settings["macros_hotkey"] = key
            self.app.save_settings()
            self._register_hotkey()
            return self.hotkey_error or None
        self.app.hotkeys.register(Entry("macros.toggle", "My macros: Start / Stop", "My macros", HOTKEY,
                                        get_key=lambda: self.app.settings.get("macros_hotkey") or HOTKEY, set_key=set_key))

    def on_shutdown(self):
        self.stop()
        if self._listener:
            self._listener.stop()
            self._listener = None

    def create_page(self, parent):
        from .page import MacroPage
        return MacroPage(parent, self)

    # ---- Dateien
    def folder(self) -> Path:
        return profiles_dir(self.id)

    @staticmethod
    def safe_name(name: str) -> str:
        n = re.sub(r"[^\w\- .]", "", name.strip(), flags=re.U).strip(" .")[:60]
        if not n:
            raise ValueError("Please enter a name.")
        return n

    def list_macros(self) -> list[str]:
        return sorted(p.stem for p in self.folder().glob("*.jopm"))

    def save(self, name: str, text: str) -> None:
        dsl.parse(text)                                     # nur gültige Makros speichern
        (self.folder() / f"{self.safe_name(name)}.jopm").write_text(text, encoding="utf-8")

    def load(self, name: str) -> str:
        return (self.folder() / f"{self.safe_name(name)}.jopm").read_text(encoding="utf-8")

    def delete(self, name: str) -> None:
        try:
            (self.folder() / f"{self.safe_name(name)}.jopm").unlink()
        except OSError:
            pass

    # ---- Export / Import (eine .jopm-Textdatei, überall lesbar)
    def export_to(self, name: str, path: str) -> None:
        Path(path).write_text(self.load(name), encoding="utf-8")

    def import_from(self, path: str, name: str | None = None) -> tuple[str, str]:
        """Liest eine Makro-Datei, prüft sie und speichert sie. Gibt (Name, Text) zurück. Wirft MacroError/ValueError/OSError."""
        p = Path(path)
        if p.stat().st_size > 200_000:
            raise ValueError("This file is too large for a macro.")
        text = p.read_text(encoding="utf-8")
        base = self.safe_name(name or p.stem)
        n, i = base, 2
        while (self.folder() / f"{n}.jopm").exists():       # nichts überschreiben
            n, i = f"{base} {i}", i + 1
        self.save(n, text)
        return n, text

    # ---- Ausführen
    def run(self, text: str, backend=None) -> str:
        """Gibt '' bei Erfolg oder eine Fehlermeldung zurück."""
        if self.state == "running":
            return ""
        try:
            cmds = dsl.parse(text)
            backend = backend or dsl.PynputBackend()
        except dsl.MacroError as exc:
            return str(exc)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        self.current_text = text
        self.runner = dsl.Runner(backend)
        self.state, self.last = "running", ""

        def work():
            t0 = time.perf_counter()
            try:
                self.last = self.runner.run(cmds)
                from core import stats
                stats.record_macro(time.perf_counter() - t0)
            except Exception as exc:
                traceback.print_exc()
                self.last = f"error: {exc}"
            finally:
                self.state = "idle"

        threading.Thread(target=work, daemon=True).start()
        return ""

    def stop(self):
        if self.runner:
            self.runner.stop()

    def toggle(self):
        if self.state == "running":
            self.stop()
        elif self.current_text:
            self.run(self.current_text)

    def _register_hotkey(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self.hotkey_error = ""
        try:
            from core.hotkeys import global_hotkeys
            self._listener = global_hotkeys({self.app.settings.get("macros_hotkey") or HOTKEY: lambda: self.app.call_soon(self.toggle)})
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            self.hotkey_error = str(exc)
