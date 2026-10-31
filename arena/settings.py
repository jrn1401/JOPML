"""Einstellungen der Arena (eine kleine JSON-Datei im Benutzerordner)."""
import json
import os
import sys
from pathlib import Path

from . import weapons

DEFAULTS = {"weapon": "rifle", "style": weapons.DEFAULT_STYLE, "theme": weapons.DEFAULT_THEME, "bots": 5, "bots_shoot": False, "sens": 1.0, "fullscreen": True,
            "quality": "Auto", "mode": "bots", "fov": 85, "ads_sens": 1.0, "ads_toggle": False, "invert_y": False,
            "crosshair": "Cross", "crosshair_color": "Cyan", "hitboxes": False}


def path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) if sys.platform.startswith("win") else Path.home()
    return base / (".jopml_arena.json" if not sys.platform.startswith("win") else "jopml_arena.json")


def clean(d) -> dict:
    """Gültige Werte übernehmen, alles andere durch Standardwerte ersetzen."""
    d = d if isinstance(d, dict) else {}
    out = dict(DEFAULTS)
    if d.get("weapon") in weapons.WEAPONS:
        out["weapon"] = d["weapon"]
    if d.get("style") in weapons.STYLES:
        out["style"] = d["style"]
    if d.get("theme") in weapons.THEMES:
        out["theme"] = d["theme"]
    if isinstance(d.get("bots"), int) and not isinstance(d.get("bots"), bool):
        out["bots"] = max(0, min(12, d["bots"]))
    out["bots_shoot"] = bool(d.get("bots_shoot", False))
    out["fullscreen"] = bool(d.get("fullscreen", True))
    if d.get("quality") in ("Auto", "Low", "Medium", "High"):
        out["quality"] = d["quality"]
    for key, lo, hi in (("sens", 0.2, 4.0), ("fov", 60, 110), ("ads_sens", 0.3, 2.0)):
        try:
            out[key] = max(lo, min(hi, float(d.get(key, DEFAULTS[key]))))
        except (TypeError, ValueError):
            pass
    out["fov"] = int(round(out["fov"]))
    if d.get("mode") in ("bots", "targets"):
        out["mode"] = d["mode"]
    if d.get("crosshair") in weapons.CROSSHAIR_STYLES:
        out["crosshair"] = d["crosshair"]
    if d.get("crosshair_color") in weapons.CROSSHAIR_COLORS:
        out["crosshair_color"] = d["crosshair_color"]
    for key in ("ads_toggle", "invert_y", "hitboxes"):
        out[key] = bool(d.get(key, DEFAULTS[key]))
    return out


def load() -> dict:
    try:
        return clean(json.loads(path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(d: dict) -> None:
    try:
        path().write_text(json.dumps(clean(d)), encoding="utf-8")
    except OSError:
        pass
