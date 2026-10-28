"""Einfache Nutzungsstatistik – nur lokal in einer Datei, nichts wird gesendet."""
import datetime
import threading

from core import config

FILE = "stats.json"
KEEP_DAYS = 30
_lock = threading.Lock()


def _empty() -> dict:
    return {"clicks": 0, "seconds": 0.0, "runs": 0, "macro_runs": 0, "macro_seconds": 0.0, "best_cps": 0.0, "days": {}}


def load() -> dict:
    d = config.load_json(config.app_dir() / FILE, None)
    out = _empty()
    if isinstance(d, dict):
        for k in out:
            if isinstance(out[k], dict):
                if isinstance(d.get(k), dict):
                    out[k] = {str(a): int(b) for a, b in d[k].items() if isinstance(b, (int, float))}
            elif isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool):
                out[k] = d[k]
    return out


def _today() -> str:
    return datetime.date.today().isoformat()


def _save(d: dict) -> None:
    days = d.get("days", {})
    for k in sorted(days)[:-KEEP_DAYS]:
        days.pop(k, None)
    config.save_json(config.app_dir() / FILE, d)


def record_clicker(count: int, seconds: float) -> None:
    """Wird von der Klick-Engine am Ende eines Laufs aufgerufen (aus einem Hintergrund-Thread)."""
    if count <= 0:
        return
    with _lock:
        d = load()
        d["clicks"] += int(count)
        d["seconds"] += float(seconds)
        d["runs"] += 1
        if seconds >= 1:
            d["best_cps"] = max(float(d.get("best_cps", 0)), round(count / seconds, 1))
        d["days"][_today()] = int(d["days"].get(_today(), 0)) + int(count)
        _save(d)


def record_macro(seconds: float) -> None:
    with _lock:
        d = load()
        d["macro_runs"] += 1
        d["macro_seconds"] += float(seconds)
        _save(d)


def reset() -> None:
    with _lock:
        config.save_json(config.app_dir() / FILE, _empty())


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h} h {m} min" if h else (f"{m} min {sec} s" if m else f"{sec} s")
