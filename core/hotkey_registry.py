"""Zentrale Hotkey-Verwaltung: alle Tastenkürzel der App an einer Stelle.

Module melden ihre Kürzel mit `app.hotkeys.register(Entry(...))` an. Der Nutzer kann sie in den Einstellungen umlegen, einzeln
ein- und ausschalten, auf ein Programm (Fenstertitel) beschränken, auf Standard zurücksetzen und als Profil speichern.

Zwei Arten von Einträgen:
- eigene (action gesetzt): die Verwaltung bindet sie selbst an EINEN gemeinsamen Listener;
- fremde (get_key/set_key gesetzt): das Modul bindet seine Tasten weiter selbst (Notaus, Autoclicker, Makros); die Verwaltung zeigt und ändert sie nur.
"""
import re
import threading
from dataclasses import dataclass
from typing import Callable

from core.i18n import tr

_MODS = {"ctrl", "alt", "shift", "cmd"}
_OK_KEY = re.compile(r"^([a-z0-9]|f([1-9]|1[0-9]|2[0-4])|space|enter|tab|esc|backspace|delete|home|end|page_up|page_down|up|down|left|right|insert)$")


def normalize(text: str) -> str:
    """'ctrl + alt + K' -> '<ctrl>+<alt>+k'. Wirft ValueError mit anzeigbarem Text. Leer = ohne Taste."""
    raw = (text or "").strip()
    if not raw:
        return ""
    parts = [p.strip().strip("<>").lower() for p in raw.replace(" ", "").split("+") if p.strip()]
    mods, key = parts[:-1], parts[-1]
    if any(m not in _MODS for m in mods) or key in _MODS or not _OK_KEY.match(key):
        raise ValueError(tr("Unknown key in hotkey: {t}", t=text))
    if not mods and not re.match(r"^f([1-9]|1[0-9]|2[0-4])$", key):
        raise ValueError(tr("Use Ctrl, Alt or Shift together with a key (or an F key alone)."))
    order = {"ctrl": 0, "alt": 1, "shift": 2, "cmd": 3}
    mods = sorted(set(mods), key=order.get)
    fmt = lambda k: f"<{k}>" if len(k) > 1 else k
    return "+".join(fmt(x) for x in mods + [key])


def pretty(hk: str) -> str:
    return " + ".join(p.strip("<>").upper() for p in hk.split("+")) if hk else "–"


@dataclass
class Entry:
    id: str
    label: str                              # englischer Quelltext (tr())
    group: str                              # Modulname, z. B. "Game macros"
    default: str = ""
    action: Callable | None = None          # eigene Einträge: wird im Hauptthread aufgerufen
    get_key: Callable[[], str] | None = None   # fremde Einträge: aktuelle Taste
    set_key: Callable[[str], str | None] | None = None   # fremde Einträge: neue Taste setzen (Rückgabe: Fehlertext oder None)
    windowed: bool = True                   # darf auf ein Programm beschränkt werden

    @property
    def external(self) -> bool:
        return self.get_key is not None


class Registry:
    def __init__(self, app, window_title: Callable[[], str] | None = None):
        self.app = app
        self.entries: dict[str, Entry] = {}
        self._hk = None
        self.error = ""
        self._lock = threading.Lock()
        self._window_title = window_title or _active_title
        self._job = None

    # ---- Speicher ----
    def _store(self) -> dict:
        st = self.app.settings.get("hotkeys")
        if not isinstance(st, dict):
            st = self.app.settings["hotkeys"] = {}
        return st

    def register(self, entry: Entry) -> None:
        self.entries[entry.id] = entry

    def unregister(self, entry_id: str) -> None:
        self.entries.pop(entry_id, None)

    def key_of(self, entry_id: str) -> str:
        e = self.entries[entry_id]
        if e.external:
            try:
                return e.get_key() or ""
            except Exception:
                return ""
        saved = self._store().get(entry_id, {})
        return saved["key"] if isinstance(saved, dict) and isinstance(saved.get("key"), str) else e.default

    def enabled(self, entry_id: str) -> bool:
        if self.entries[entry_id].external:
            return True
        saved = self._store().get(entry_id, {})
        return bool(saved.get("enabled", True)) if isinstance(saved, dict) else True

    def window_of(self, entry_id: str) -> str:
        saved = self._store().get(entry_id, {})
        w = saved.get("window", "") if isinstance(saved, dict) else ""
        return w if isinstance(w, str) else ""

    # ---- Ändern ----
    def set_key(self, entry_id: str, text: str) -> str:
        """Gibt '' oder einen Fehlertext zurück."""
        e = self.entries[entry_id]
        try:
            key = normalize(text)
        except ValueError as exc:
            return str(exc)
        if e.external:
            err = e.set_key(key) if e.set_key else tr("This shortcut is changed in its module.")
            return err or ""
        self._store().setdefault(entry_id, {})["key"] = key
        self._changed()
        return ""

    def set_enabled(self, entry_id: str, value: bool) -> None:
        if not self.entries[entry_id].external:
            self._store().setdefault(entry_id, {})["enabled"] = bool(value)
            self._changed()

    def set_window(self, entry_id: str, text: str) -> None:
        if self.entries[entry_id].windowed and not self.entries[entry_id].external:
            self._store().setdefault(entry_id, {})["window"] = (text or "").strip()[:80]
            self._changed()

    def reset(self, entry_id: str | None = None) -> None:
        if entry_id is None:
            for e in list(self.entries.values()):
                if e.external and e.set_key and e.default:
                    e.set_key(e.default)
            self._store().clear()
        else:
            e = self.entries[entry_id]
            if e.external:
                if e.set_key and e.default:
                    e.set_key(e.default)
            else:
                self._store().pop(entry_id, None)
        self._changed()

    def _changed(self) -> None:
        self.app.save_settings()
        self.apply()

    # ---- Doppelte Belegung ----
    def conflicts(self) -> dict[str, list[str]]:
        """{Taste: [IDs]} für Tasten, die mehrfach belegt sind (nur eingeschaltete Einträge; dieselbe Taste für verschiedene Programme oder global + ein Programm ist erlaubt)."""
        seen: dict[tuple[str, str], list[str]] = {}
        for i in self.entries:
            k = self.key_of(i)
            if k and self.enabled(i):
                seen.setdefault((k, self.window_of(i).lower()), []).append(i)
        out: dict[str, list[str]] = {}
        for (k, _w), ids in seen.items():
            if len(ids) > 1:
                out.setdefault(k, []).extend(ids)
        return out

    # ---- Profile (Export/Import) ----
    def snapshot(self) -> dict:
        snap = {}
        for i, e in self.entries.items():
            snap[i] = {"key": self.key_of(i), "enabled": self.enabled(i), "window": self.window_of(i)}
        return snap

    def load_snapshot(self, data) -> int:
        """Übernimmt Werte aus einem Profil; unbekannte IDs und ungültige Tasten werden übersprungen. Gibt die Anzahl übernommener Einträge zurück."""
        if not isinstance(data, dict):
            return 0
        n = 0
        for i, v in data.items():
            if i not in self.entries or not isinstance(v, dict):
                continue
            e = self.entries[i]
            try:
                key = normalize(v.get("key", ""))
            except ValueError:
                continue
            if e.external:
                if e.set_key and key:
                    e.set_key(key)
            else:
                self._store()[i] = {"key": key, "enabled": bool(v.get("enabled", True)),
                                    "window": str(v.get("window", ""))[:80] if e.windowed else ""}
            n += 1
        self._changed()
        return n

    def save_profile(self, name: str) -> str:
        name = (name or "").strip()[:40]
        if not name:
            return tr("Please enter a name.")
        profiles = self.app.settings.setdefault("hotkey_profiles", {})
        if len(profiles) >= 30 and name not in profiles:
            return tr("At most 30 profiles.")
        profiles[name] = self.snapshot()
        self.app.save_settings()
        return ""

    def load_profile(self, name: str) -> int:
        return self.load_snapshot(self.app.settings.get("hotkey_profiles", {}).get(name))

    def delete_profile(self, name: str) -> None:
        self.app.settings.get("hotkey_profiles", {}).pop(name, None)
        self.app.save_settings()

    # ---- Listener ----
    def apply_soon(self) -> None:
        """Mehrere Änderungen hintereinander binden die Tasten nur einmal neu."""
        try:
            if self._job is not None:
                self.app.after_cancel(self._job)
            self._job = self.app.after(200, self.apply)
        except Exception:
            self.apply()

    def apply(self) -> str:
        self._job = None
        with self._lock:
            self._stop_listener()
            mapping: dict = {}
            for i, e in self.entries.items():
                if e.external or e.action is None or not self.enabled(i):
                    continue
                k = self.key_of(i)
                if not k or k in mapping:
                    continue
                mapping[k] = self._make_trigger(i)
            self.error = ""
            if not mapping:
                return ""
            try:
                from core.hotkeys import global_hotkeys
                self._hk = global_hotkeys(mapping)
                self._hk.daemon = True
                self._hk.start()
            except Exception as exc:
                self._hk = None
                self.error = f"{type(exc).__name__}: {exc}"
            return self.error

    def _make_trigger(self, entry_id: str):
        # Mehrere Einträge mit derselben Taste in verschiedenen Programmen: der mit passendem Fenster gewinnt.
        key = self.key_of(entry_id)

        def fire():
            mine = [(i, e) for i, e in self.entries.items()
                    if not e.external and e.action is not None and self.enabled(i) and self.key_of(i) == key]
            mine.sort(key=lambda ie: self.window_of(ie[0]) == "")        # Einträge für ein bestimmtes Programm zuerst
            for i, e in mine:
                w = self.window_of(i).lower()
                if w and not self._window_matches(w):
                    continue
                self.app.call_soon(e.action)
                return
        return fire

    def _window_matches(self, needle: str) -> bool:
        try:
            return needle in (self._window_title() or "").lower()
        except Exception:
            return False

    def _stop_listener(self) -> None:
        if self._hk is not None:
            try:
                self._hk.stop()
            except Exception:
                pass
            self._hk = None

    def shutdown(self) -> None:
        with self._lock:
            self._stop_listener()


def _active_title() -> str:
    from core import winutil
    w = winutil.active_window() or {}
    return f"{w.get('title', '')} {w.get('proc', '')}"
