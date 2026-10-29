"""Notaus: ein globaler Tastenkürzel (und ein Knopf) stoppt Autoclicker und Makros sofort."""
import traceback

from core import config

DEFAULT = "<ctrl>+<shift>+<f12>"


def stop_everything(app) -> list[str]:
    """Stoppt alle Module, die etwas tun. Gibt die IDs der Module zurück, bei denen etwas lief."""
    stopped = []
    for p in getattr(app, "plugins", []):
        try:
            if p.id == "autoclicker":
                if p.engine is not None and p.engine.running:
                    p.stop()
                    stopped.append(p.id)
            elif p.id == "clicktools":
                mk = getattr(p, "mk", None)
                if mk is not None and (mk.holding or mk.scrolling or mk.afk_running):
                    mk.stop_all()
                    stopped.append(p.id)
            elif p.id == "macros":
                if getattr(p, "state", "") == "running":
                    p.stop()
                    stopped.append(p.id)
        except Exception:
            traceback.print_exc()
    return stopped


class Panic:
    def __init__(self, app):
        self.app = app
        self._hk = None
        self.error = ""

    def start(self) -> str:
        """Gibt '' oder eine Fehlermeldung zurück (z. B. fehlende Rechte)."""
        self.stop()
        hk = (self.app.settings.get("panic_hotkey") or DEFAULT).strip()
        try:
            from core.hotkeys import global_hotkeys
            self._hk = global_hotkeys({hk: lambda: self.app.call_soon(self.app.panic)})
            self._hk.daemon = True
            self._hk.start()
            self.error = ""
        except Exception as exc:
            self._hk = None
            self.error = f"{type(exc).__name__}: {exc}"
        return self.error

    def stop(self):
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass
            self._hk = None
