"""Profile pro Programm: wechselt das Autoclicker-Profil automatisch, wenn ein bestimmtes Fenster im Vordergrund ist."""
import threading
from dataclasses import dataclass

from core.i18n import tr


@dataclass
class AppRule:
    match: str       # Teil des Fenstertitels oder Programmnamens (Groß-/Kleinschreibung egal)
    profile: str     # Name einer gespeicherten Autoclicker-Profildatei (ohne .json)

    def validate(self) -> "AppRule":
        self.match = (self.match or "").strip()
        self.profile = (self.profile or "").strip()
        if len(self.match) < 2:
            raise ValueError(tr("Enter at least 2 characters of the window or program name."))
        if not self.profile:
            raise ValueError(tr("Choose a profile."))
        return self


def parse_rules(data) -> list[AppRule]:
    out = []
    for d in (data if isinstance(data, list) else [])[:30]:
        try:
            out.append(AppRule(d["match"], d["profile"]).validate())
        except (KeyError, TypeError, ValueError):
            continue
    return out


def pick(rules: list[AppRule], win: dict | None) -> AppRule | None:
    if not win:
        return None
    hay = f"{win.get('title', '')} {win.get('proc', '')}".lower()
    return next((r for r in rules if r.match.lower() in hay), None)


class AppProfileWatcher:
    """Fragt das aktive Fenster ab; ruft switch(profilname) nur bei einem Wechsel auf."""

    def __init__(self, get_rules, switch, get_window, interval=1.5):
        self.get_rules, self.switch, self.get_window, self.interval = get_rules, switch, get_window, interval
        self._last = None
        self._stop = threading.Event()
        self._t = None
        self.current = ""

    def start(self):
        if self._t and self._t.is_alive():
            return
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def step(self):
        r = pick(self.get_rules(), self.get_window())
        name = r.profile if r else None
        if name and name != self._last:
            self.switch(name)
            self.current = name
        if name is not None or self._last is None:
            self._last = name
        # Wechselt der Nutzer in ein Fenster ohne Regel, bleibt das zuletzt gewählte Profil aktiv.

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.step()
            except Exception:
                pass
