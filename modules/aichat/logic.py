"""KI-Chat: Anbieter (Gemini, Groq), Modelle, Aufgaben-Vorlagen, Einwilligung und Anfrage (ohne Oberfläche, gut testbar).

Rechtlicher Rahmen (siehe Rechtstext): Der Chat ist ein KI-System im Sinne des EU-KI-Gesetzes (Art. 50: Nutzer müssen erkennen, dass sie mit einer KI sprechen
und dass Inhalte KI-erzeugt sind). Die Eingaben gehen über unseren Server an den gewählten Anbieter (Google Gemini oder Groq, beide USA); darum gibt es
vor der ersten Nutzung je Anbieter eine ausdrückliche Einwilligung. Der Verlauf wird nur lokal und verschlüsselt gespeichert, wenn der Nutzer das will
(Standard: aus, 1.10.0). Claude und ChatGPT gibt es hier nicht mehr (1.9.0).
"""
import json
import re
import time

from core import ai_context, config, errors, requirements_doc, secretstore
from core.cloud import CloudError
from core.i18n import get_language

PROVIDERS = {
    "gemini": ("Gemini", "Google · USA"),
    "groq": ("Groq", "Groq · USA"),
}
REAL = ("gemini", "groq")
DEFAULT_PROVIDER = "gemini"
MAX_TURNS = 12
# "Maximum" in der Verwaltung = diese Werte (Obergrenzen des Systems); -1 bedeutet "kein Limit"
MAX_ANSWER_TOKENS = 16384
MAX_DAILY_TOKENS = 100_000_000


class ChatUnavailable(Exception):
    """Text darf dem Nutzer angezeigt werden. `code` ist ein Fehlercode (core.errors)."""

    def __init__(self, msg="", code=None):
        super().__init__(msg)
        self.code = code or errors.classify(msg, "E-AI-001")


def presets() -> dict:
    """Aufgaben-Vorlagen: Name -> (Beschreibung, Hintergrundwissen für die KI). Das Hintergrundwissen kommt live aus dem Programm."""
    return {
        "Free chat": ("Ask anything.", lambda: ""),
        "Write a macro": ("Describe what should be clicked or typed; the answer uses the launcher's macro language.",
                          lambda: "Write macros ONLY in this language and answer with one code block:\n" + ai_context.MACRO_SPEC),
        "Write a module": ("Describe the module; the AI writes the code and the window, you can add it with one button.",
                           lambda: ai_context.MODULE_SPEC + "\nRequirements of this launcher:\n" + requirements_doc.modules_text("en")),
        "Fix a module": ("Pick one of your own modules; the AI proposes a fixed version and you see the changes before you accept.",
                         lambda: FIX_RULES + "\n" + ai_context.MODULE_SPEC),
        "Explain an error": ("Paste an error message or crash.log text.",
                             lambda: "Explain the error in simple steps and give the most likely fix. Codes look like E-NET-001; "
                                     "known codes: " + "; ".join(f"{k} = {v}" for k, v in errors.CODES.items())),
    }


FIX_RULES = ("You fix a module of this launcher. Answer with a short explanation of the cause (2-4 sentences) and then ONE complete python code block with "
             "the whole fixed plugin.py (not only the changed lines). Keep id, name and everything that works unchanged. Do not add network access, "
             "file deletion or code built at runtime.")
CODE_LIMIT = 9000


def preset_context(name: str, extra: str = "") -> str:
    p = presets().get(name)
    base = p[1]() if p else ""
    return (base + ("\n\n" + extra if extra else ""))[:14000]


def fix_prompt(name: str, code: str, problem: str = "", error_text: str = "") -> tuple[str, str]:
    """(Nachricht, Zusatz-Kontext) für 'Fehler beheben lassen'. Der Code kommt in den Kontext, damit die Nachricht kurz bleibt."""
    code = (code or "")[:CODE_LIMIT]
    msg = f"Please fix my module '{name}'."
    if problem.strip():
        msg += "\nProblem: " + problem.strip()[:600]
    if error_text.strip():
        msg += "\nError: " + error_text.strip()[:600]
    return msg, f"Current code of the module '{name}':\n```python\n{code}\n```"


# ---------------------------------------------------------------- Einstellungen (Anbieter und Modell je Anbieter merken)
def _prefs_path():
    return config.app_dir() / "ai_chat_prefs.json"


def prefs() -> dict:
    d = config.load_json(_prefs_path(), {}) or {}
    prov = d.get("provider") if d.get("provider") in REAL else DEFAULT_PROVIDER
    models = d.get("models") if isinstance(d.get("models"), dict) else {}
    return {"provider": prov, "models": {k: str(v) for k, v in models.items() if k in REAL and isinstance(v, str)}}


def save_prefs(provider: str, models: dict) -> None:
    config.save_json(_prefs_path(), {"provider": provider if provider in REAL else DEFAULT_PROVIDER,
                                     "models": {k: v for k, v in models.items() if k in REAL and v}})


# ---------------------------------------------------------------- Einwilligung je Anbieter
def _consent_path():
    return config.app_dir() / "ai_chat_consent.json"


def consented(provider: str) -> bool:
    return bool((config.load_json(_consent_path(), {}) or {}).get(provider))


def give_consent(provider: str) -> None:
    data = config.load_json(_consent_path(), {}) or {}
    data[provider] = True
    config.save_json(_consent_path(), data)


def missing_consent(provider: str) -> list[str]:
    return [provider] if provider in REAL and not consented(provider) else []


# ---------------------------------------------------------------- Anfrage
def client_of(app):
    ident = getattr(app, "identity", None)
    c = getattr(ident, "client", None)
    return c if c and c.configured and getattr(c, "session", None) else None


NEED_ACCOUNT = "The AI chat needs a cloud account (sign in with a JOPMakro account or Google)."


def _client(app):
    c = client_of(app)
    if c is None:
        raise ChatUnavailable(NEED_ACCOUNT, "E-NET-003")
    return c


def status(app) -> dict:
    """{"providers": [...], "models": {...}, "policy": {...}} – wirft ChatUnavailable."""
    try:
        return _client(app).chat_status()
    except CloudError as exc:
        raise ChatUnavailable(str(exc), errors.from_cloud(exc)) from None


def models(app) -> dict:
    try:
        return _client(app).chat_models()
    except CloudError as exc:
        raise ChatUnavailable(str(exc), errors.from_cloud(exc)) from None


def ask(app, provider: str, history: list[dict], preset: str = "Free chat", model: str | None = None) -> dict:
    """Blockierend (im Thread aufrufen). Gibt {"reply", "provider", "model", "tokens", ...} zurück oder wirft ChatUnavailable."""
    c = _client(app)
    if provider not in REAL:
        provider = DEFAULT_PROVIDER
    if missing_consent(provider):
        raise ChatUnavailable("Please confirm the data notice for this AI first.", "E-AI-006")
    try:
        return c.chat(provider, history[-MAX_TURNS:], get_language(), preset_context(preset), model)
    except CloudError as exc:
        raise ChatUnavailable(str(exc), errors.from_cloud(exc)) from None


# ---------------------------------------------------------------- Modul aus der KI-Antwort
_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S | re.I)


def extract_module_code(reply: str) -> str | None:
    """Der erste Code-Block der Antwort, der wie ein Modul aussieht (class Plugin ...), sonst None."""
    for m in _BLOCK.finditer(reply or ""):
        code = m.group(1).strip("\n")
        if re.search(r"class\s+Plugin\b", code) and "BasePlugin" in code:
            return code + "\n"
    return None


def module_name_of(code: str) -> str:
    """Modulname aus `id = "..."` im Code (bereinigt), sonst 'ki_modul'."""
    from core import module_import
    m = re.search(r"^\s*id\s*=\s*[\"']([^\"']+)[\"']", code or "", re.M)
    name = module_import.clean_name(m.group(1)) if m else ""
    return name or "ki_modul"


def guess_preset(text: str) -> str:
    """Vorlage passend zur ersten Nachricht (Dashboard): Modul, Makro, Fehler – sonst freier Chat."""
    t = (text or "").lower()
    if re.search(r"\b(modul|module|plugin)\b|mod ", t):
        return "Write a module"
    if re.search(r"makro|macro|autoclick|klick|click", t):
        return "Write a macro"
    if re.search(r"fehler|error|e-[a-z]{2,4}-\d{3}|traceback|crash", t):
        return "Explain an error"
    return "Free chat"


def ask_stream(app, provider, history, preset="Free chat", model=None, extra="", on_text=None, cancel=None, on_start=None, fallback=True) -> dict:
    """Wie ask(), aber Stück für Stück (CloudClient.chat_stream). Blockierend, im Thread aufrufen."""
    c = _client(app)
    if provider not in REAL:
        provider = DEFAULT_PROVIDER
    if missing_consent(provider):
        raise ChatUnavailable("Please confirm the data notice for this AI first.", "E-AI-006")
    try:
        return c.chat_stream(provider, history[-MAX_TURNS:], get_language(), preset_context(preset, extra), model,
                             on_text=on_text, cancel=cancel, on_start=on_start, fallback=fallback)
    except CloudError as exc:
        raise ChatUnavailable(str(exc), errors.from_cloud(exc)) from None


def fallback_note(res: dict) -> str:
    """Hinweis, wenn der Server wegen eines Limits oder einer Störung auf den anderen Anbieter gewechselt hat (leer = kein Wechsel)."""
    src = res.get("fallback_from")
    if not src or src == res.get("provider"):
        return ""
    return "{a} is not available right now ({r}). This answer comes from {b}."


# ---------------------------------------------------------------- Verlauf lokal (verschlüsselt, abschaltbar) und Chats pro Modul-Projekt
HISTORY_MAX_CHATS = 30
HISTORY_MAX_MESSAGES = 40
GENERAL = "General"


def _hist_path():
    return config.app_dir() / "ai_chat_history.dat"


def history_enabled() -> bool:
    return bool((config.load_json(_prefs_path(), {}) or {}).get("save_history"))


def set_history_enabled(on: bool) -> None:
    d = config.load_json(_prefs_path(), {}) or {}
    d["save_history"] = bool(on)
    config.save_json(_prefs_path(), d)
    if not on:
        delete_history()


def _read_store() -> dict:
    try:
        raw = _hist_path().read_text(encoding="ascii")
        data = json.loads(secretstore.unprotect(raw))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_store(data: dict) -> None:
    _hist_path().write_text(secretstore.protect(json.dumps(data, ensure_ascii=False)), encoding="ascii")


def delete_history() -> None:
    try:
        _hist_path().unlink(missing_ok=True)
    except OSError:
        pass


def projects() -> list[str]:
    """Namen aller Projekte mit gespeicherten Chats (immer inklusive 'General')."""
    return [GENERAL] + sorted(k for k in _read_store() if k != GENERAL)


def chats(project: str = GENERAL) -> list[dict]:
    """Gespeicherte Chats eines Projekts, neueste zuerst: [{id, title, time, messages}]."""
    lst = _read_store().get(project) or []
    return sorted([c for c in lst if isinstance(c, dict)], key=lambda c: c.get("time", 0), reverse=True)


def save_chat(project: str, chat_id: str | None, history: list[dict]) -> str | None:
    """Speichert (oder aktualisiert) einen Chat – nur wenn der Verlauf eingeschaltet ist. Gibt die Chat-ID zurück."""
    if not history_enabled() or not history:
        return chat_id
    data = _read_store()
    lst = [c for c in (data.get(project) or []) if isinstance(c, dict)]
    chat_id = chat_id or str(int(time.time() * 1000))
    first = next((m["content"] for m in history if m.get("role") == "user"), "")
    entry = {"id": chat_id, "title": first.strip().replace("\n", " ")[:60] or "Chat", "time": int(time.time()),
             "messages": [{"role": m["role"], "content": m["content"][:8000]} for m in history[-HISTORY_MAX_MESSAGES:]]}
    lst = [c for c in lst if c.get("id") != chat_id] + [entry]
    data[project] = sorted(lst, key=lambda c: c.get("time", 0), reverse=True)[:HISTORY_MAX_CHATS]
    _write_store(data)
    return chat_id


def delete_chat(project: str, chat_id: str) -> None:
    data = _read_store()
    data[project] = [c for c in (data.get(project) or []) if c.get("id") != chat_id]
    if not data[project] and project != GENERAL:
        data.pop(project, None)
    _write_store(data)


# ---------------------------------------------------------------- Dashboard-Weiche: wohin gehört eine Frage?
def guess_target(text: str) -> str:
    """'chat' (KI-Chat: schreiben, bauen, Fehler erklären) oder 'help' (Hilfe: wie bedient man das Programm). Eine Stelle, damit nichts doppelt ist."""
    t = (text or "").lower()
    if guess_preset(t) != "Free chat":
        return "chat"
    if re.search(r"wie |how |wo |where |was ist|what is|einstell|setting|hotkey|taste|update|konto|account|login|anmeld", t):
        return "help"
    return "chat"
