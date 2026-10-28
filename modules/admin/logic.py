"""Reine Hilfen für die Admin-Übersicht (ohne Oberfläche, gut testbar)."""
import datetime

# Grenzen des kostenlosen Supabase-Tarifs (Richtwerte; bei einem bezahlten Tarif sind sie höher)
FREE_DB_BYTES = 500 * 1024 * 1024


def fmt_bytes(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "–"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "–"


def parse_ts(value):
    """ISO-Zeitstempel des Servers -> aware datetime (oder None)."""
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_uptime(started, now=None) -> str:
    s, n = parse_ts(started), parse_ts(now) if now else datetime.datetime.now(datetime.timezone.utc)
    if not s or not n:
        return "–"
    secs = max(0, int((n - s).total_seconds()))
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d} d {h} h" if d else (f"{h} h {m} min" if h else f"{m} min")


def fmt_ago(ts, now=None) -> str:
    t, n = parse_ts(ts), parse_ts(now) if now else datetime.datetime.now(datetime.timezone.utc)
    if not t or not n:
        return "–"
    secs = max(0, int((n - t).total_seconds()))
    if secs < 90:
        return f"{secs} s"
    if secs < 5400:
        return f"{secs // 60} min"
    if secs < 172800:
        return f"{secs // 3600} h"
    return f"{secs // 86400} d"


def db_fill(db_bytes, limit=FREE_DB_BYTES) -> float:
    """Anteil der Datenbank am Richtwert (0–1)."""
    try:
        return max(0.0, min(1.0, float(db_bytes) / float(limit)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def health(o: dict) -> tuple[str, str]:
    """(Stufe, Text) – Stufe "ok" | "warn" | "bad". Nur aus dem, was die Datenbank selbst melden kann."""
    if not isinstance(o, dict) or not o:
        return "bad", "No answer from the server."
    conns, mx = int(o.get("connections") or 0), int(o.get("max_connections") or 0)
    if mx and conns / mx > 0.85:
        return "warn", "Almost all database connections are in use."
    if db_fill(o.get("db_bytes")) > 0.85:
        return "warn", "The database is almost full (free plan: 500 MB)."
    hit = o.get("cache_hit")
    if hit is not None and float(hit) < 90:
        return "warn", "Low cache hit rate – the server may be short on memory."
    return "ok", "Server is running normally."


def summarize(o: dict) -> list[tuple[str, str]]:
    """Beschriftung/Wert-Paare für die Übersichtskarten."""
    o = o if isinstance(o, dict) else {}
    return [
        ("Online now", str(o.get("online_now", "–"))),
        ("Active in 24 h", str(o.get("online_24h", "–"))),
        ("Registered accounts", str(o.get("registered", "–"))),
        ("New in 7 days", str(o.get("new_7d", "–"))),
        ("Errors in 24 h", str(o.get("errors_24h", "–"))),
        ("Errors in total", str(o.get("errors_total", "–"))),
        ("Database size", f"{fmt_bytes(o.get('db_bytes'))} ({db_fill(o.get('db_bytes')) * 100:.0f} % of 500 MB)"),
        ("Connections", f"{o.get('connections', '–')} / {o.get('max_connections', '–')}"),
        ("Server running for", fmt_uptime(o.get("started_at"), o.get("server_time"))),
        ("Cache hit rate", f"{o.get('cache_hit')} %" if o.get("cache_hit") is not None else "–"),
        ("PostgreSQL", str(o.get("pg_version", "–"))),
        ("Chat messages", str(o.get("messages", "–"))),
    ]
