"""Anonyme Diagnose für Cloud-Konten: ein Lebenszeichen pro Minute (wer ist online) und Fehlerberichte für das Admin-Modul.
Es werden nur Version, Betriebssystem, aktuelle Seite, Fehlercode und Fehlertexte gesendet – keine Eingaben, Makros oder Nachrichten.
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
        self._seen: set = set()

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

    def context(self, force: bool = False) -> str | None:
        """Optionaler, kurzer Kontext: aktuelle Seite und die letzten besuchten Seiten (nur Seitennamen, keine Eingaben).
        Nur wenn der Nutzer "Kontext mitsenden" eingeschaltet hat (oder er es für eine Meldung ausdrücklich ankreuzt)."""
        if not force and not (self.enabled() and self.app.settings.get("diagnostics_context", False)):
            return None
        trail = [str(x) for x in list(getattr(self.app, "trail", []))[-6:]]
        return scrub(f"page={getattr(self.app, 'current', '') or '-'}; trail={'>'.join(trail) or '-'}")[:300]

    def report(self, kind: str, message: str, trace: str = "", code: str | None = None) -> None:
        """Automatische Meldung (mit Fehlercode). Gleiche Meldungen werden pro Programmstart nur einmal gesendet; der Server fasst sie zusätzlich zusammen."""
        if not self.enabled():
            return
        msg = scrub(message)[:500]
        key = (code, kind, re.sub(r"\d+", "#", msg)[:120])
        if key in self._seen or len(self._seen) >= 200:
            return
        self._seen.add(key)
        try:
            self._q.put_nowait((kind, msg, scrub(trace)[:4000], code, self.context()))
        except queue.Full:
            pass

    def report_user(self, category: str, message: str, code: str | None = None, with_context: bool = False) -> None:
        """Meldung eines Nutzers (Knopf "Report"): sofort, blockierend, unabhängig vom Diagnose-Schalter, weil der Nutzer sie selbst abschickt.
        Wirft eine Exception mit verständlichem Text, wenn das Senden scheitert."""
        text = scrub(message).strip()
        if len(text) < 5:
            raise ValueError("Please describe the problem in a few words.")
        self._call("jopml_user_report", {"p_category": category, "p_message": text[:2000], "p_code": code,
                                         "p_version": APP_VERSION, "p_os": self._os, "p_context": self.context(True) if with_context else None})

    def my_reports(self) -> list:
        """Eigene Meldungen mit Ticket-Status und Antworten des Betreibers (blockierend)."""
        res = self._call("jopml_my_reports", {})
        return res if isinstance(res, list) else []

    def reports_seen(self) -> None:
        self._call("jopml_my_reports_seen", {})

    def report_exc(self, kind, exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        self.report(kind, f"{getattr(exc_type, '__name__', 'Error')}: {exc}", text, "E-APP-001")

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
                kind, msg, trace, code, ctx = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                self._call("jopml_report_error", {"p_code": code, "p_kind": kind, "p_message": msg, "p_trace": trace,
                                                  "p_version": APP_VERSION, "p_os": self._os, "p_context": ctx})
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
