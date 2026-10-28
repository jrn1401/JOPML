"""Zeitplaner: startet gespeicherte Makros zu einer Uhrzeit oder in festen Abständen (nur solange der Launcher läuft)."""
import datetime
import re
import threading
from dataclasses import dataclass

from core.i18n import tr

MODES = ("daily", "interval")
MAX_ENTRIES = 30
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


@dataclass
class Entry:
    name: str
    macro: str
    mode: str = "daily"          # daily: täglich um `at`; interval: alle `minutes` Minuten
    at: str = "12:00"
    minutes: int = 30
    enabled: bool = True

    def validate(self) -> "Entry":
        self.name = (self.name or "").strip()[:40] or self.macro
        if not self.macro:
            raise ValueError(tr("Choose a saved macro."))
        if self.mode not in MODES:
            raise ValueError(tr("Unknown mode."))
        if self.mode == "daily" and not _TIME.match(self.at or ""):
            raise ValueError(tr("Time must look like 18:30."))
        if self.mode == "interval":
            self.minutes = int(self.minutes)
            if not 1 <= self.minutes <= 1440:
                raise ValueError(tr("The interval must be 1–1440 minutes."))
        return self

    def to_dict(self):
        return dict(self.__dict__)


def parse_entries(data) -> list[Entry]:
    out = []
    for d in (data if isinstance(data, list) else [])[:MAX_ENTRIES]:
        try:
            out.append(Entry(**{k: d[k] for k in ("name", "macro", "mode", "at", "minutes", "enabled") if k in d}).validate())
        except (TypeError, ValueError, KeyError):
            continue
    return out


def due(e: Entry, now: datetime.datetime, last_run: datetime.datetime | None) -> bool:
    """Ist der Eintrag jetzt fällig? (genau einmal pro Termin)"""
    if not e.enabled:
        return False
    if e.mode == "interval":
        return last_run is None or (now - last_run).total_seconds() >= e.minutes * 60
    h, m = (int(x) for x in e.at.split(":"))
    slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return now >= slot and (last_run is None or last_run < slot)


class Scheduler:
    """Prüft alle paar Sekunden. run(macro_name) -> '' oder Fehlertext. log: Liste von (Zeit, Text), neueste zuletzt."""

    def __init__(self, get_entries, run, tick=5.0, clock=datetime.datetime.now):
        self.get_entries, self.run, self.tick, self.clock = get_entries, run, tick, clock
        self.last: dict[str, datetime.datetime] = {}
        self.log: list[tuple[str, str]] = []
        self._stop = threading.Event()
        self._t = None

    def start(self):
        if self._t and self._t.is_alive():
            return
        self._stop.clear()
        started = self.clock()
        for e in self.get_entries():                      # Intervalle zählen ab Start; verpasste Tagestermine werden nicht nachgeholt
            self.last.setdefault(e.name, started)
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def check_once(self):
        now = self.clock()
        for e in self.get_entries():
            if due(e, now, self.last.get(e.name)):
                self.last[e.name] = now
                err = self.run(e.macro)
                self._log(f"{e.name}: " + (err or tr("started")))

    def _log(self, text):
        self.log.append((self.clock().strftime("%d.%m. %H:%M:%S"), text))
        del self.log[:-50]

    def _loop(self):
        while not self._stop.wait(self.tick):
            try:
                self.check_once()
            except Exception as exc:
                self._log(f"{type(exc).__name__}: {exc}")
