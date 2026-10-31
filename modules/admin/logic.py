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


AI_LIMIT_MAX = 100_000


def parse_limit(text):
    """Eingabefeld "KI-Limit pro Tag" -> (Zahl 0..100000, '') oder (None, Fehlertext). Leer = kein Wert."""
    t = str(text or "").strip()
    if not t.isdigit():
        return None, "Enter a whole number between 0 and 100000."
    n = int(t)
    if n > AI_LIMIT_MAX:
        return None, "Enter a whole number between 0 and 100000."
    return n, ""


# KI-Regeln (1.9.0): je Konto oder als Standard. None = Standard erben, -1 = kein Limit, "Maximum" = größter Wert, den das System zulässt
LIMIT_KINDS = {
    "requests": ("AI messages per day", 100_000),
    "answer": ("Answer length (tokens)", 16_384),
    "tokens": ("Token usage per day", 100_000_000),
}
UNLIMITED = -1


def fmt_limit(n, kind) -> str:
    """Anzeige eines Wertes: None -> 'default', -1 -> 'no limit', Maximum -> 'maximum', sonst die Zahl (Englisch, mit tr() anzeigen)."""
    if n is None:
        return "default"
    if n == UNLIMITED:
        return "no limit"
    if n >= LIMIT_KINDS[kind][1]:
        return "maximum"
    return f"{int(n):,}".replace(",", ".")


def parse_value(text, kind):
    """Eingabe -> (Zahl 1..Maximum, '') oder (None, Fehlertext). Das Wort "max"/"maximum" ergibt das Maximum, "none"/"unlimited" -1."""
    t = str(text or "").strip().lower().replace(".", "").replace(",", "").replace(" ", "")
    top = LIMIT_KINDS[kind][1]
    if t in ("max", "maximum"):
        return top, ""
    if t in ("none", "unlimited", "nolimit", "-1"):
        return UNLIMITED, ""
    if not t.isdigit() or not (0 <= int(t) <= top):
        return None, "Enter a whole number, 'maximum' or 'no limit'."
    return int(t), ""


def friendly_rpc_error(msg: str) -> str:
    """Server-Fehler der Berechtigungs-Funktionen -> verständlicher Text (Englisch, mit tr() anzeigen)."""
    m = str(msg)
    for key, text in (("cannot remove yourself", "You cannot remove your own admin rights."), ("last admin", "The last admin cannot be removed."),
                      ("not allowed", "Only admins can do this."), ("unknown user", "This account does not exist."), ("bad limit", "Enter a whole number between 0 and 100000.")):
        if key in m:
            return text
    return m


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


# ---- Fehlergruppen (1.9.0): komprimierte Auswertung
def top_counts(groups, field, n=3):
    """Häufigste Werte eines Zählfelds (versions/systems = {Wert: Anzahl}) über alle Gruppen -> [(Wert, Anzahl)]."""
    tot: dict = {}
    for g in groups or []:
        for k, v in (g.get(field) or {}).items():
            tot[k] = tot.get(k, 0) + int(v or 0)
    return sorted(tot.items(), key=lambda kv: -kv[1])[:n]


def summary_parts(groups):
    """(Anzahl Gruppen, Vorkommen, "Code ×n, …" der häufigsten, häufigste Version oder "") für die Kurzfassung (Text mit tr() zusammensetzen)."""
    groups = groups or []
    hits = sum(int(g.get("hits") or 0) for g in groups)
    codes: dict = {}
    for g in groups:
        c = g.get("code") or g.get("kind") or "?"
        codes[c] = codes.get(c, 0) + int(g.get("hits") or 0)
    top = ", ".join(f"{k} ×{v}" for k, v in sorted(codes.items(), key=lambda kv: -kv[1])[:3])
    ver = top_counts(groups, "versions", 1)
    return len(groups), hits, top, (ver[0][0] if ver else "")


def summarize_groups(groups) -> str:
    """Kurzfassung (Englisch) für Tests und Protokolle."""
    n, hits, top, ver = summary_parts(groups)
    return f"{n} groups · {hits} occurrences · top: {top}" + (f" · most affected version: {ver}" if ver else "") if n else ""


def groups_for_ai(groups, n=20, max_chars=9000) -> str:
    """Kompakter Text für die KI-Auswertung (bereits bereinigte Meldungen, kurze Stacktrace-Ausschnitte). Keine Konten, keine E-Mail-Adressen."""
    out = []
    for g in sorted(groups or [], key=lambda g: -int(g.get("hits") or 0))[:n]:
        trace = (g.get("sample_trace") or "").strip().splitlines()
        out.append(f"- code={g.get('code') or '-'} kind={g.get('kind')} hits={g.get('hits')} versions={g.get('versions')} "
                   f"message={str(g.get('message'))[:300]!r}" + (f" trace_end={trace[-1][:200]!r}" if trace else ""))
    return "\n".join(out)[:max_chars]


REPORT_CATEGORIES = {"bug": "Bug", "module": "Module problem", "idea": "Idea", "other": "Other"}


# ---------------------------------------------------------------- 1.10.0: KI-Kosten, Budget, Tickets
BUDGET_WARN = 0.8
TICKET_STATUS = {"new": "New", "in_progress": "In progress", "fixed": "Fixed"}
TICKET_NEXT = {"new": "in_progress", "in_progress": "fixed", "fixed": "new"}
PROVIDER_COLORS = {"gemini": "#4f8cff", "groq": "#f59e0b"}


def budget_state(used, budget) -> tuple[float, str]:
    """(Anteil 0..1+, 'ok'|'warn'|'full'|'none'). budget -1/None = kein Budget. Warnung ab 80 %."""
    if budget is None or int(budget) < 0:
        return 0.0, "none"
    if int(budget) == 0:
        return 1.0, "full"
    frac = int(used or 0) / int(budget)
    return frac, "full" if frac >= 1 else "warn" if frac >= BUDGET_WARN else "ok"


def budget_warning(b: dict, t=lambda s: s) -> str:
    """Warntext (Teile über t() übersetzt) oder '' – für Nachrichten und Tokens ab 80 %."""
    out = []
    for used_k, bud_k, name in (("requests_today", "requests_budget", "messages"), ("tokens_today", "tokens_budget", "tokens")):
        frac, st = budget_state(b.get(used_k), b.get(bud_k))
        if st in ("warn", "full"):
            out.append(f"{t(name)} {round(frac * 100)} %")
    return (t("AI budget") + ": " + ", ".join(out)) if out else ""


def chart_series(rows, days: int = 14, field: str = "tokens"):
    """Zeilen {day, provider, hits, tokens, fallbacks} -> (Tage[YYYY-MM-DD], {Anbieter: [Wert je Tag]}); fehlende Tage = 0, genau `days` Tage bis heute."""
    import datetime as dt
    today = dt.date.today()
    labels = [(today - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    series: dict = {}
    for r in rows or []:
        d, p = str(r.get("day"))[:10], str(r.get("provider") or "?")
        if d in labels:
            series.setdefault(p, [0] * days)[labels.index(d)] += int(r.get(field) or 0)
    return labels, series


def fallback_total(rows) -> int:
    return sum(int(r.get("fallbacks") or 0) for r in rows or [])


def ticket_counts(tickets) -> dict:
    c = {"new": 0, "in_progress": 0, "fixed": 0}
    for t in tickets or []:
        c[t.get("status") if t.get("status") in c else "new"] += 1
    return c


def ticket_title(group: dict) -> str:
    code = group.get("code") or ""
    msg = str(group.get("message") or "").strip().replace("\n", " ")
    return (f"{code}: " if code else "") + msg[:120]
