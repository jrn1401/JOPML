"""Fehlercodes für das ganze Programm.

Jeder Fehler, den Nutzer sehen oder den das Programm selbst bemerkt, bekommt einen Code (E-<Bereich>-<Nr>). Der Code steht in der Meldung,
hilft bei Support und KI-Hilfe und gruppiert die automatischen Berichte im Admin-Bereich. Texte sind Englisch (mit tr() anzeigen).
`classify(text)` rät den Code aus einem Fehlertext, wenn der Aufrufer keinen kennt.
"""
import re

CODES: dict[str, str] = {
    # Programm
    "E-APP-001": "Unexpected program error.",
    "E-APP-002": "A module could not be loaded.",
    "E-APP-003": "A page could not be opened.",
    "E-APP-004": "The launcher could not restart.",
    "E-APP-005": "A file could not be read or written.",
    # Netz / Konto
    "E-NET-001": "No connection to the server.",
    "E-NET-002": "The server returned an error.",
    "E-NET-003": "You are not signed in.",
    "E-ACC-001": "Sign-in failed.",
    "E-ACC-002": "The account backup failed.",
    # KI
    "E-AI-001": "The AI is not set up or not available.",
    "E-AI-002": "The daily AI request limit is reached.",
    "E-AI-003": "The daily AI token limit is reached.",
    "E-AI-004": "The AI service did not answer.",
    "E-AI-005": "The AI sent an empty answer.",
    "E-AI-006": "The AI data notice was not confirmed.",
    "E-AI-007": "The daily AI budget of the whole service is used up.",
    # Module
    "E-MOD-001": "The module name is not valid or already used.",
    "E-MOD-002": "The module ZIP file is not valid.",
    "E-MOD-003": "A module file is too large or not allowed.",
    "E-MOD-004": "The module code did not pass the check.",
    "E-MOD-005": "The module upload failed.",
    "E-MOD-006": "The module download failed.",
    "E-MOD-007": "The module import failed.",
    "E-MOD-008": "The AI module could not be built.",
    # Updates
    "E-UPD-001": "The update check failed.",
    "E-UPD-002": "The update download failed.",
    "E-UPD-003": "The update file did not match its checksum.",
    # Arena / Spiele / Makros
    "E-ARN-001": "The Recoil Arena could not be started.",
    "E-MAC-001": "A macro could not be run.",
    "E-MAC-002": "A profile could not be loaded.",
    # Berichte
    "E-REP-001": "The report could not be sent.",
}

# Lösungsvorschläge je Code (Englisch, mit tr() anzeigen): kurze Schritte, die ein Nutzer selbst versuchen kann
SOLUTIONS: dict[str, str] = {
    "E-APP-001": "Restart the launcher (sidebar: Restart launcher). If it happens again, press Report and describe what you did right before.",
    "E-APP-002": "Open Modules and check the state of the module. Remove it or press 'Fix with AI' if it is your own module; then restart.",
    "E-APP-003": "Go to another page and back. If it stays broken, restart the launcher and press Report.",
    "E-APP-004": "Close the launcher completely and start it again from the shortcut. Check that the program file is not blocked by a virus scanner.",
    "E-APP-005": "Check that the file or folder exists, is not open in another program and that you may write there (try another folder).",
    "E-NET-001": "Check your internet connection, then try again. A firewall or VPN can block the server; the app needs https access.",
    "E-NET-002": "The server had a problem. Wait a minute and try again. If it keeps happening, press Report.",
    "E-NET-003": "Sign in again (sidebar: Sign out, then sign in with your cloud account). Local accounts cannot use cloud features.",
    "E-ACC-001": "Check username and password (the password cannot be recovered). With Google sign-in, use the same Google account as before.",
    "E-ACC-002": "Check the passphrase and that the backup file is a .jopmacc file from this program.",
    "E-AI-001": "The AI is not set up on the server (missing key) or you have no cloud account. Operators: add GEMINI_API_KEY / GROQ_API_KEY in Supabase secrets.",
    "E-AI-002": "You used up today's AI messages. Try again tomorrow or ask an admin for a higher limit.",
    "E-AI-003": "You used up today's AI tokens. Shorter questions use fewer tokens. Try again tomorrow or ask an admin.",
    "E-AI-004": "Both AI services did not answer. Wait a minute and try again, or pick the other AI in the chat.",
    "E-AI-005": "Ask again with other words, or pick another model in the model menu.",
    "E-AI-006": "Confirm the data notice for the AI, or choose the other AI.",
    "E-AI-007": "Many people used the AI today. Try again tomorrow; the operator can raise the budget in Admin > AI.",
    "E-MOD-001": "Use only lowercase letters, digits and _ (2-31 characters, starting with a letter) and a name no built-in module uses.",
    "E-MOD-002": "Check that the ZIP is not damaged and contains plugin.py on the top level (or inside one folder).",
    "E-MOD-003": "Only allowed file types, at most the limits shown in 'View module requirements'. Remove large or unknown files.",
    "E-MOD-004": "plugin.py must be readable Python with a class Plugin(BasePlugin). Press 'Fix with AI' to let the AI repair it.",
    "E-MOD-005": "Check your connection and that the module meets the upload criteria ('View module requirements'). Try again later.",
    "E-MOD-006": "Check your connection and try the download again. The module may have been removed.",
    "E-MOD-007": "Read the message for the reason (name, file type, size). 'View module requirements' lists all rules.",
    "E-MOD-008": "The AI code could not be added. Ask the AI to send the COMPLETE plugin.py again, or press 'Fix with AI'.",
    "E-UPD-001": "Check your connection and press 'Check for updates' again later.",
    "E-UPD-002": "Check your connection and free disk space, then update again. You can also download the setup file from the official source.",
    "E-UPD-003": "The download was damaged or changed. Try again; if it repeats, download only from the official source and press Report.",
    "E-ARN-001": "Update the Recoil Arena (Update check) and start it again. The Arena needs numpy and a graphics-capable system.",
    "E-MAC-001": "Check the macro in the editor (red line = error). Test with a harmless target first.",
    "E-MAC-002": "Check that the file is a profile JSON exported from this program.",
    "E-REP-001": "Check your connection and that you are signed in with a cloud account. You can also use 'Contact'.",
}


def solution(code: str | None) -> str:
    return SOLUTIONS.get(code or "", SOLUTIONS["E-APP-001"])


def catalog() -> list[tuple[str, str, str]]:
    """[(Code, Bedeutung, Lösung)] sortiert nach Code – für die Seite "Error codes" in der Hilfe."""
    return [(c, CODES[c], solution(c)) for c in sorted(CODES)]


_RULES = [  # (Muster im Fehlertext, Code) – die erste Übereinstimmung gilt
    (r"checksum|sha-?256|prüfsumme", "E-UPD-003"),
    (r"update", "E-UPD-001"),
    (r"not a valid zip|bad.?zip|zip file", "E-MOD-002"),
    (r"too large|not allowed|not permitted|zu groß", "E-MOD-003"),
    (r"module name|already imported|name is not|reserved", "E-MOD-001"),
    (r"module.*(check|syntax)|plugin\.py|could not be read for the check", "E-MOD-004"),
    (r"upload", "E-MOD-005"),
    (r"budget of the day", "E-AI-007"),
    (r"token limit", "E-AI-003"),
    (r"daily ai limit|limit reached", "E-AI-002"),
    (r"empty answer", "E-AI-005"),
    (r"not set up|not configured|no provider|nicht verbunden", "E-AI-001"),
    (r"no connection|timed out|timeout|name resolution|urlopen|connection", "E-NET-001"),
    (r"not signed in|session", "E-NET-003"),
    (r"wrong username|invalid login|sign.?in", "E-ACC-001"),
    (r"server error|status 5\d\d|unexpected answer", "E-NET-002"),
    (r"permission|errno|oserror|no such file|ioerror", "E-APP-005"),
]


def known(code: str | None) -> bool:
    return bool(code) and code in CODES


def classify(text: str, default: str = "E-APP-001") -> str:
    low = str(text or "").lower()
    for pat, code in _RULES:
        if re.search(pat, low):
            return code
    return default


def from_cloud(exc) -> str:
    """Code für einen Cloud-/KI-Fehler: erst der Serverschlüssel (exc.code), dann der Text."""
    return {"limit_requests": "E-AI-002", "limit_tokens": "E-AI-003", "not_configured": "E-AI-001", "provider_missing": "E-AI-001",
            "provider_down": "E-AI-004", "limit_global": "E-AI-007", "empty": "E-AI-005", "not_signed_in": "E-NET-003", "forbidden": "E-NET-002"}.get(getattr(exc, "code", None) or "") or classify(str(exc))


def describe(code: str) -> str:
    return CODES.get(code, CODES["E-APP-001"])


def tag(text: str, code: str) -> str:
    """Hängt den Code an einen Meldungstext an (einmal)."""
    text = str(text or "").rstrip()
    return text if f"[{code}]" in text else f"{text} [{code}]"


_CODE_RE = re.compile(r"\[(E-[A-Z]{2,4}-\d{3})\]")


def extract(text: str) -> str | None:
    m = _CODE_RE.search(str(text or ""))
    return m.group(1) if m else None


def explain_prompt(code: str | None, text: str) -> str:
    """Frage an die KI ("Ask AI") für einen Fehler. Enthält nur Code und Meldungstext (Pfade werden vorher bereinigt)."""
    from core.telemetry import scrub
    head = f"Error code {code} ({describe(code)})\n" if code else ""
    return f"{head}Message: {scrub(text)[:600]}\nExplain in simple steps what this means and how I can fix it."
