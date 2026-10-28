"""Anonyme Diagnose für Cloud-Konten: ein Lebenszeichen pro Minute (wer ist online) und Fehlerberichte für das Admin-Modul.
Es werden nur Version, Betriebssystem, aktuelle Seite und Fehlertexte gesendet – keine Eingaben, Makros oder Nachrichten.
Abschaltbar unter Einstellungen > System (diagnostics)."""
import os
import platform
import queue
import re
import sys
import threading
import traceback

from core.version import APP_VERSION

HEARTBEAT_S = 60
_HOME = re.compile(re.escape(os.path.expanduser("~")), re.I) if os.path.expanduser("~") not in ("", "~") else None


def scrub(text: str) -> str:
    """Entfernt den Benutzerordner aus Pfaden (Datenschutz)."""
    text = str(text or "")
    if _HOME is not None:
        text = _HOME.sub("~", text)
    return re.sub(r"[A-Za-z]:\\Users\\[^\\]+", r"C:\\Users\\~", text)


class Telemetry:
    _hooked = False

    def __init__(self, app, send=None):
        self.app = app
        self._send = send                      # austauschbar (Tests): send(name, args)
        self._q: queue.Queue = queue.Queue(maxsize=50)
        self._stop = threading.Event()
        self._t = None
        self._os = f"{platform.system()} {platform.release()}"[:40]

    # ---- Aufrufe
    def enabled(self) -> bool:
        return bool(self.app.settings.get("diagnostics", True))

    def start(self):
        if self._t is not None and self._t.is_alive():
            return
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def report(self, kind: str, message: str, trace: str = "") -> None:
        if not self.enabled():
            return
        try:
            self._q.put_nowait((kind, scrub(message)[:500], scrub(trace)[:4000]))
        except queue.Full:
            pass

    def report_exc(self, kind, exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        self.report(kind, f"{getattr(exc_type, '__name__', 'Error')}: {exc}", text)

    def install_hooks(self):
        if Telemetry._hooked:                     # nur einmal einhängen (sonst verketten sich die Hooks)
            return
        Telemetry._hooked = True
        old = sys.excepthook

        def hook(t, v, tb):
            self.report_exc("crash", t, v, tb)
            old(t, v, tb)
        sys.excepthook = hook
        old_t = getattr(threading, "excepthook", None)

        def thook(args):
            if args.exc_type is not SystemExit:
                self.report_exc("thread", args.exc_type, args.exc_value, args.exc_traceback)
            if old_t:
                old_t(args)
        threading.excepthook = thook

    # ---- Hintergrund
    def _client(self):
        ident = getattr(self.app, "identity", None)
        c = getattr(ident, "client", None)
        return c if c is not None and getattr(c, "session", None) else None

    def _call(self, name, args):
        if self._send is not None:
            return self._send(name, args)
        c = self._client()
        if c is not None:
            return c.rpc(name, args)

    def flush(self):
        """Sendet wartende Fehlerberichte (blockierend; im Hintergrund-Thread)."""
        while True:
            try:
                kind, msg, trace = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                self._call("jopml_log_error", {"p_kind": kind, "p_message": msg, "p_trace": trace,
                                               "p_version": APP_VERSION, "p_os": self._os})
            except Exception:
                return

    def beat(self):
        if not self.enabled():
            return
        self._call("jopml_heartbeat", {"p_version": APP_VERSION, "p_os": self._os,
                                       "p_page": str(getattr(self.app, "current", "") or "")})

    def _loop(self):
        while not self._stop.is_set():
            try:
                if self.app.user is not None and (self._client() is not None or self._send is not None):
                    self.beat()
                    self.flush()
            except Exception:
                pass
            if self._stop.wait(HEARTBEAT_S):
                return
