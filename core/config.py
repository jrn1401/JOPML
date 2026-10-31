"""Pfade und persistente Launcher-Einstellungen."""
import json
import os
import sys
from pathlib import Path

from core.version import APP_ID

DEFAULT_SETTINGS = {
    "auto_backup_days": 0,         # 0 = aus, sonst alle N Tage eine Sicherung im Ordner "backups"
    "auto_backup_last": "",        # Datum (JJJJ-MM-TT) der letzten automatischen Sicherung
    "appearance_mode": "dark",     # dark | light | system
    "accent": "#4f8cff",
    "dl_limit_kbps": 0,            # 0 = unbegrenzt
    "cpu_priority": "normal",      # normal | low
    "cpu_cores": 0,                # 0 = alle
    "ram_limit_mb": 0,             # 0 = kein Limit (nur Windows)
    "assistant_url": "",
    "contact_endpoint": "",
    # --- v1.1 ---
    "language": "en",              # en | de | es | ru | fr | zh
    "colors": {},                  # eigene Farben: main, sidebar, card, inset, hover, text
    "icon_bg": "#4f8cff",          # Hintergrundfarbe des App-Icons
    "icon_image": "",              # optionales Hintergrundbild des App-Icons
    "remember": "30",              # Standard für "Angemeldet bleiben": 0 | 1 | 7 | 30 | forever
    "first_run_done": False,       # Sprache/Verknüpfung/Autostart-Angebot gezeigt
    "legal_version": "",           # Fassung der Bedingungen, der zugestimmt wurde
    "legal_hash": "",
    "legal_accepted_at": 0,
    "extensions": {},              # {id: {"enabled": bool, "config": {...}}}
    # --- v1.3 ---
    "nav_order": [],               # Reihenfolge der Module in der Seitenleiste (leer = Standard)
    "nav_hidden": [],              # ausgeblendete Module
    "diagnostics": True,           # anonyme Diagnose (Lebenszeichen + Fehler) an den Entwickler
    "community_stay": False,       # in der Community angemeldet bleiben (Passphrase lokal merken)
    "community_cache": [],         # zuletzt bekannte Server (für die Einstellungen ohne Anmeldung)
    "potato_mode": False,          # Kartoffel-Modus: alles Rechenintensive aus
    "resize_freeze": True,         # Seite beim Fensterziehen ausblenden (flüssiger)
    "hover_effect": True,          # Module in Menü und Dashboard werden beim Darüberfahren leicht hervorgehoben
    "colored_icons": True,         # bunte Symbole in Menü und Overlay
    "bg_image": "",                # eigenes Hintergrundbild (Pfad, nur lokal)
    "bg_dim": 40,                  # Abdunkeln des Bildes in Prozent
    "bg_height": "Medium",         # Small | Medium | Large
    # --- v1.3.3 ---
    "ui_scale": 100,               # Größe der Oberfläche in Prozent (80–150)
    "nav_version": 0,              # 2 = neue Menüstruktur (1.5.0); ältere Reihenfolgen werden einmal zurückgesetzt
    "notify": {},                  # Benachrichtigungen (siehe core/notify.py); leer = Standardwerte
    "panic_hotkey": "<ctrl>+<shift>+<f12>",   # Notaus: stoppt alles
    # --- v1.6.0 ---
    "hotkeys": {},                 # {id: {"key": "...", "enabled": bool, "window": "Teil des Fenstertitels"}} (siehe core/hotkey_registry.py)
    "hotkey_profiles": {},         # {Name: {id: {...}}} gespeicherte Tastenbelegungen (z. B. je Spiel)
    "macros_hotkey": "<f7>",       # Start/Stopp der Makros
    "macro_favorites": [],         # Namen gespeicherter Makros, die auf dem Dashboard stehen (1.8.1)
    "temp_session": False,         # kurze Sitzung nur für einen Neustart (Update/Modulwechsel), wird beim Wiederanmelden entfernt
    "mini_pos": [],                # letzte Position des Mini-Fensters [x, y]
    "gm_params": {},               # zuletzt benutzte Werte der Spiele-Makros {preset_id: {...}}
}


def app_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir(module_id: str) -> Path:
    d = app_dir() / "profiles" / module_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    """Atomar schreiben: erst Temp-Datei, dann ersetzen (kein halb geschriebenes JSON bei Absturz)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_settings() -> dict:
    data = load_json(app_dir() / "settings.json", {}) or {}
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    return merged


def save_settings(data: dict) -> None:
    save_json(app_dir() / "settings.json", {k: data[k] for k in DEFAULT_SETTINGS if k in data})
