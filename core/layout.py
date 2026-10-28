"""Anordnung der Seitenleiste: Reihenfolge und Sichtbarkeit der Module (reine Logik, ohne Oberfläche).

"dashboard" steht immer ganz oben, "settings" immer unten – beide lassen sich weder verschieben noch ausblenden,
damit man sich nie aus dem Programm aussperren kann.
"""
FIXED = ("dashboard", "settings")
MAX_DIM = 80
HEIGHTS = {"Small": 90, "Medium": 140, "Large": 220}


def normalize_order(ids: list[str], order) -> list[str]:
    """Gespeicherte Reihenfolge übernehmen, Unbekanntes verwerfen, neue Module hinten anfügen."""
    ids = [i for i in ids if i not in FIXED]
    saved = [i for i in (order if isinstance(order, list) else []) if isinstance(i, str)]
    out, seen = [], set()
    for i in saved:
        if i in ids and i not in seen:
            out.append(i)
            seen.add(i)
    out.extend(i for i in ids if i not in seen)
    return out


def visible(ids: list[str], order, hidden) -> list[str]:
    hid = set(hidden) if isinstance(hidden, list) else set()
    return [i for i in normalize_order(ids, order) if i not in hid]


def move(ids: list[str], order, pid: str, delta: int) -> list[str]:
    """Verschiebt `pid` um `delta` Plätze (negativ = nach oben). Gibt die neue vollständige Reihenfolge zurück."""
    cur = normalize_order(ids, order)
    if pid not in cur:
        return cur
    i = cur.index(pid)
    j = max(0, min(len(cur) - 1, i + delta))
    cur.insert(j, cur.pop(i))
    return cur


def set_hidden(hidden, pid: str, hide: bool) -> list[str]:
    out = [i for i in (hidden if isinstance(hidden, list) else []) if isinstance(i, str) and i != pid]
    if hide and pid not in FIXED:
        out.append(pid)
    return out


def clamp_dim(value) -> int:
    try:
        return max(0, min(MAX_DIM, int(value)))
    except (TypeError, ValueError):
        return 40
