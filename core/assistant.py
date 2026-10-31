"""Hilfe-Assistent: eingebaute FAQ (offline, mehrsprachig) + KI (Supabase-Funktion -> Gemini) + optionaler eigener Endpunkt.

Die Antworten sind englische Quelltexte und werden über tr() in die Sprache des Nutzers übersetzt.
Stichwörter sind deutsch UND englisch, damit Fragen in beiden Sprachen gefunden werden.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from core import ai_client
from core import net
from core.i18n import tr
from core.version import APP_ID, APP_VERSION

FAQ = [
    (("lag", "laggt", "langsam", "slow", "ruckelt", "potato", "kartoffel", "weak pc", "schwacher pc", "performance"),
     "If the program is slow or lags, switch on Potato mode in Settings > Performance (turns off background picture, coloured icons, "
     "pre-building of pages and slows polling). Also keep 'Hide the page while resizing the window' on and lower the interface size in Appearance."),
    (("admin", "online users", "wer ist online", "fehlermeldungen", "error reports", "server status"),
     "Admin accounts have the menu 'Admin' with Overview (users online, accounts, server and database status), Accounts, Errors and Publish."),
    (("farbwechsel", "color change", "colour change", "farbe ändert", "pixel"),
     "Autoclicker > Colour trigger: switch on 'Trigger on any colour change' to start the macro when the watched point changes colour at all."),
    (("hotkey", "f6", "tastenkombination", "global", "hintergrund", "background", "shortcut key"),
     "Set start/stop hotkeys in 'Jaron Op Makro' under 'Global hotkeys': click 'Record' and press the key or combination "
     "(e.g. F6 or Ctrl+Alt+P). If start and stop are the same, the key toggles. Hotkeys also work when the window is in the background."),
    (("intervall", "interval", "geschwindigkeit", "speed", "millisekunden", "milliseconds", "schnell", "fast", "cps"),
     "The click interval is made of minutes, seconds and milliseconds (minimum 1 ms). Very short intervals depend on the "
     "operating system and the target program. Some programs do not process every click."),
    (("taste", "key", "buchstabe", "leertaste", "space", "maus", "mouse", "ziel", "target"),
     "As the target you can choose the left, right or middle mouse button or any keyboard key. With 'Record key' you simply press the key yourself."),
    (("wiederholen", "repeat", "unendlich", "infinite", "timer", "laufzeit", "run time"),
     "Under 'Repeats & timer' choose 'Repeat forever' or 'X times'. With 'Limit run time' the clicker stops after exactly the set time."),
    (("profil", "profile", "speichern", "save", "laden", "load", "json"),
     "Save and load profiles at the top of 'Jaron Op Makro' with 'Save …' and 'Load …'. They are plain JSON files you can share."),
    (("makro", "macro", "skript", "script", "ki", "ai", "generieren", "generate", "beschreib", "describe"),
     "Open 'My macros'. Write commands such as 'click left 500 300', 'wait 50ms' and 'repeat forever … end', or describe the macro "
     "in the box on top (e.g. 'click every 50 ms at 500 300') and press 'Generate'. Simple sentences are understood offline; harder ones "
     "use the AI when you are signed in with a cloud account. Every macro is checked before it runs. F7 starts/stops."),
    (("extension", "erweiterung", "browser", "browsing", "links", "notiz", "notes", "suche", "search"),
     "Under 'Extensions' add ready-made extensions (Quick links, Web search, Notes) with one click, switch them on or off and configure them there."),
    (("update", "aktualisieren", "version", "neue version"),
     "On start the launcher checks for updates automatically. If there is one, a window with 'Update now' appears. You can also check manually on the dashboard."),
    (("smartscreen", "blockiert", "blocked", "virus", "antivirus", "defender", "startet nicht", "does not start"),
     "Windows warns about unknown programs: click 'More info', then 'Run anyway'. If the button is missing, tick 'Unblock' in the file properties. "
     "Some virus scanners wrongly flag auto-clickers."),
    (("passwort", "password", "kennwort", "ändern", "change", "vergessen", "forgot", "reset"),
     "A password cannot be changed after the account has been created (security rule), and there is no 'forgot password'. If you lose it, create a new account. "
     "Your display name and optional e-mail can be edited in Settings → Account."),
    (("2fa", "zwei", "two-factor", "faktor", "authenticator", "totp"),
     "Two-factor sign-in (local accounts) is set up under Settings → Account → 'Set up 2FA'. Enter the key in an authenticator app and confirm with the 6-digit code. "
     "Make sure your phone's clock is correct."),
    (("google", "gmail", "anmelden mit", "sign in with"),
     "'Sign in with Google' works through the cloud account system (Supabase). It needs a one-time setup by the operator of the app. If it is not active, use a JOPMakro account."),
    (("angemeldet bleiben", "stay signed in", "remember", "login", "anmelden", "abmelden", "logout", "konto", "account"),
     "When signing in you can choose how long to stay signed in: 24 hours, 1 week, 30 days or forever. Sign out at the bottom of the sidebar."),
    (("email", "e-mail", "anonym", "anonymous", "privat", "private", "daten", "data", "datenschutz", "privacy", "löschen", "delete"),
     "E-mail and real name are optional. In Settings → Account you can export your data and delete your account at any time."),
    (("farbe", "color", "colour", "design", "dunkel", "dark", "hell", "light", "akzent", "accent", "theme", "icon"),
     "Under Settings → Appearance you can pick Dark, Light or System, an accent colour, presets, your own colours (colour picker) and change the app icon background."),
    (("sprache", "language", "deutsch", "english", "español", "русский", "français", "中文"),
     "Change the language under Settings → Language. Available: English, Deutsch, Español, Русский, Français, 中文."),
    (("verknüpfung", "shortcut", "autostart", "startup", "desktop"),
     "Under Settings → System you can create a desktop shortcut and switch autostart on or off."),
    (("download", "drosseln", "throttle", "bandbreite", "bandwidth"),
     "Limit the download speed for updates under Settings → Performance in KB/s (0 = unlimited)."),
    (("ram", "cpu", "gpu", "prozessor", "arbeitsspeicher", "memory", "hardware", "leistung", "performance", "kerne", "cores"),
     "Under Settings → Performance you can limit priority, number of CPU cores and (Windows only) memory of this program. This affects only the launcher itself. "
     "There is no GPU limit because the program does not use the graphics card."),
    (("werbung", "ads", "advert", "banner"),
     "The ad box in the sidebar is a placeholder. No ads are loaded at the moment."),
    (("match", "sieg", "niederlage", "gewonnen", "verloren", "win", "loss", "victory", "defeat", "automatisch zählen", "auto detect"),
     "Under Gamer & Stream → Match counter you can let the program count wins and losses itself: choose the screen area around the 'Victory' / 'Defeat' text, "
     "teach it your victory and your defeat screen with the 'Learn' buttons, then switch on 'Count wins and losses automatically'. Only screen colours are compared; nothing is read from the game."),
    (("monitor", "zweiter bildschirm", "second screen", "mehrere monitore", "fenster verschieben", "fenster layout", "window layout"),
     "Under Productivity → Windows you can pick a target monitor, send the last used window to the next monitor (Ctrl+Alt+M) and save the open windows with their exact position and monitor "
     "as a layout. In a layout, 'discord:right@2' puts Discord on monitor 2 (counted from left to right)."),
    (("overlay bleibt", "overlays bleiben", "overlay nach neustart", "overlay after restart", "overlays stay"),
     "Overlays that were switched on when you closed the program come back automatically at the next start."),
    (("modul importieren", "module importieren", "import module", "eigenes modul", "own module", "plugin importieren", "modul hinzufügen"),
     "Under Settings → System → Import modules you can add your own module from a folder, a .zip file, a single .py file or by pasting code (it needs a plugin.py with a class Plugin). "
     "A module is program code with all rights of the program, so import only modules you trust. It is loaded at the next start, stays when the program is updated and can be removed in the same place."),
    (("ki chat", "ai chat", "chatgpt", "claude", "gemini", "groq", "chatten", "openai", "anthropic", "modell wählen", "choose model"),
     "Open the menu item 'AI Chat' (or type your wish into the big assistant on the Dashboard), pick Gemini or Groq and a model in the model menu, and write your message. "
     "You confirm a data notice for each AI once. Claude and ChatGPT are no longer offered. Answers are labelled AI-generated. Chats are saved on your PC only if you switch it on under 'Chats'."),
    (("vorlage", "template", "timer modul", "notizen modul", "mit ki beheben", "fix with ai", "modul reparieren", "repair module", "verlauf modul", "module history", "rückgängig", "undo module", "diff"),
     "In the AI Chat press 'Templates' for ready modules (Timer, Notes, Hotkey counter, Text snippets): add them or let the AI change them. For a module that does not work, open Modules, select it "
     "and press 'Fix with AI': you see exactly which lines change and accept with one click. 'History' in the same place brings back an older version."),
    (("chatverlauf", "chat history", "chats speichern", "save chats", "projekt chat", "streaming", "abbrechen", "stop button", "andere ki", "switch to the other ai", "limit erreicht gemini"),
     "Under 'Chats' in the AI Chat you can save chats on this PC (encrypted, off by default) and open or delete them; 'Project' keeps chats per module. 'Stop' cancels an answer. "
     "If your AI reaches its limit, the other one answers and you are told (only if you consented to both)."),
    (("meine meldungen", "my reports", "antwort auf meldung", "ticket", "status meldung"),
     "Press 'Report' in the sidebar, then 'My reports': you see whether your report was received, is being worked on or is fixed, and answers from the operator."),
    (("fehlercode", "error code", "e-net", "e-mod", "e-ai", "e-upd", "ki fragen", "ask ai", "melden", "report button"),
     "Every error shows a code like E-MOD-005 and a solution. All codes are listed under Help assistant > 'Error codes'. In the error window press 'Ask AI' for an explanation or 'Report' to tell the operator; you can also use the 'Report' button in the sidebar any time for problems and ideas."),
    (("modul anforderungen", "module requirements", "anforderungen", "welche dateien", "upload kriterien", "upload criteria", "modul regeln", "module rules"),
     "Open 'Modules' and press 'View module requirements': it shows the exact rules for modules, Lua scripts, shared modules and macros (file types, sizes, number of files, forbidden content) and can save them as a file. It always matches your program version."),
    (("kontakt", "contact", "feedback", "fehler melden", "bug", "idee", "idea", "vorschlag"),
     "Praise, ideas and questions go through 'Contact'. Something not working? Use 'Report' in the sidebar (you can follow it under 'My reports')."),
]

FALLBACK = ("I have no matching answer for that. Try other keywords (e.g. 'hotkey', 'profile', 'update') or write to us via 'Contact'.")


def _words(text: str) -> str:
    return re.sub(r"[^\w+ -]", " ", text.lower())


def answer_local(question: str) -> str:
    q = _words(question)
    best, best_score = None, 0
    for keys, answer in FAQ:
        score = sum(1 for k in keys if k in q)
        if score > best_score:
            best, best_score = answer, score
    return tr(best or FALLBACK)


def _check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    local = p.hostname in ("127.0.0.1", "localhost")
    if p.scheme != "https" and not (p.scheme == "http" and local):
        raise ValueError("The assistant address must start with https://")


def ask_remote(url: str, history: list[dict], timeout: float = 30) -> str:
    _check_url(url)
    payload = {"app": APP_ID, "version": APP_VERSION,
               "messages": [{"role": m["role"], "content": m["content"][:1000]} for m in history[-10:]]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": f"{APP_ID}/{APP_VERSION}"})
    with net.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read(200_000).decode("utf-8"))
    reply = data.get("reply") if isinstance(data, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("Empty answer from the assistant server.")
    return reply.strip()


def reply(app, question: str, history: list[dict], url: str = "", on_text=None) -> tuple[str, bool]:
    """Gibt (Antwort, kam_von_ki) zurück. Reihenfolge: Cloud-KI -> eigener Endpunkt -> FAQ."""
    hist = [{"role": m["role"], "content": m["content"][:1000]} for m in history[-10:]]
    if ai_client.available(app):
        try:
            if on_text is not None:
                return ai_client.ask_stream(app, hist, on_text), True
            return ai_client.ask(app, "help", hist), True
        except ai_client.AiUnavailable as exc:
            return answer_local(question) + "\n\n" + tr("(The AI is not reachable: {e}. This is the standard answer.)", e=str(exc)), False
    if url:
        try:
            return ask_remote(url, history), True
        except (ValueError, OSError, urllib.error.URLError):
            return answer_local(question) + "\n\n" + tr("(The AI assistant is not reachable right now, this is the standard answer.)"), False
    return answer_local(question), False
