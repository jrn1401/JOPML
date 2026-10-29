"""Sammelt alle übersetzbaren Texte (tr(...) und Hilfsfunktionen) aus dem Quellcode.
Aufruf: python tools/extract_strings.py  -> gibt die Liste aus; Test: tests/test_i18n.py"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPERS = {"muted": (1,), "page_title": (1, 2), "card": (1,), "banner": (1,), "_card": (0,), "_field": (1,),
           "ask_text": (1, 2, 3), "show_text": (1,), "confirm": (0, 1), "info": (0, 1)}
ERRORS = {"AccountError", "CloudError", "AiUnavailable", "ValueError", "GenerateError", "LoopbackError", "RuntimeError", "SpreadError", "TotpRequired", "CommunityError", "FilterError", "BackgroundError", "NoReleaseYet"}
# publisher: nur für den Admin sichtbar, deshalb bewusst nur Deutsch (nicht übersetzt)
SKIP_DIRS = {"tests", "tools", "csharp", "supabase", ".github", "server_examples", "publisher"}


def _lit(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def from_calls() -> set[str]:
    found: set[str] = set()
    for path in ROOT.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts) or "lang" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name == "tr" and node.args and _lit(node.args[0]):
                found.add(_lit(node.args[0]))
            elif name in ERRORS and node.args and _lit(node.args[0]):
                found.add(_lit(node.args[0]))
            elif name in HELPERS and name != "card" or (name == "card" and isinstance(f, ast.Attribute)):
                for i in HELPERS.get(name, ()):
                    if i < len(node.args) and _lit(node.args[i]):
                        found.add(_lit(node.args[i]))
        if path.name == "cloud.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and _lit(node.value):
                    found.add(_lit(node.value))
    return found


def from_constants() -> set[str]:
    sys.path.insert(0, str(ROOT))
    out: set[str] = set()
    from core import assistant, credits, firstrun_view, identity, settings_view, theme
    from core import contact_view
    from modules.extensions import catalog
    from modules.macros import page as macro_page
    for keys, answer in assistant.FAQ:
        out.add(answer)
    out.add(assistant.FALLBACK)
    out.update(contact_view.CATEGORIES)
    out.update(label for label, _ in identity.REMEMBER_CHOICES)
    out.update(settings_view.SECTIONS)
    out.update(theme.MODES)
    out.update(theme.PRESETS)
    out.update(label for label, _ in theme.COLOR_KEYS)
    out.update(role for _, role, _, _ in credits.CREDITS)
    for e in catalog.CATALOG:
        out.update((e["name"], e["desc"]))
    out.update(["Left mouse button", "Right mouse button", "Middle mouse button"])
    from modules.autoclicker import keys as ak
    out.update(ak.MOUSE_BUTTONS.values())
    from core.assistant_view import GREETING
    out.add(GREETING)
    from core import chatfilter, layout
    from modules.community import forum as c_forum, manage as c_manage, page as c_page, service as c_service
    out.update(c_service.ERROR_TEXTS.values())
    out.update(c_forum.BOARDS.values())
    out.update(c_manage.ROLE_LABEL.values())
    out.update(chatfilter.LABELS.values())
    out.update(layout.HEIGHTS)
    out.add(c_page.RULES)
    # Texte, die nur über Variablen an tr() gehen
    out.update(["Chats", "Forum", "Moderation", "Invite", "Members", "Channels", "Security", "More", "Dismiss", "Suspend user",
                "Delete server", "Delete thread", "Delete post", "Community rules"])
    # 1.4.0: Reiter der Sammelseiten, Formen, Positionen, Sortierungen, Bewertungen
    from modules.clicktools import crosshair as ct_cross
    from modules.gamer import cps as g_cps
    from modules.productivity import winmgr
    from modules.community import market_view
    out.update(["Crosshair", "Hotkeys", "Colour trigger", "Scheduler", "Program profiles", "Session timer", "System overlay", "Key overlay",
                "Speed tests", "Screenshot", "Clipboard", "Windows", "AI macro assistant", "Marketplace", "News", "Text", "Macro",
                "Lightning fast", "Very good", "Average", "Take your time", "Click tools", "Gamer & Stream", "Productivity",
                "Crosshair, hotkeys, colour trigger, scheduler and per-program profiles.", "Timer, overlays, speed tests and screenshots.",
                "Clipboard history, window layouts and the AI macro assistant.", "Search …", "Search", "Share a macro", "Report", "Post",
                "Record", "Reset", "Start", "Unpin", "Pin"])
    out.update(ct_cross.SHAPES)
    out.update(ct_cross.PRESETS)
    out.update(k.replace("-", " ").title() for k in winmgr.KINDS)
    out.update(market_view.SORTS)
    from core import notify
    from modules.gamemacros import library as gm_library
    from modules.clicktools import mousekeys as ck_mousekeys
    out.update(gm_library.CATEGORIES.values())
    for pr in gm_library.PRESETS:
        out.update([pr.title, pr.desc])
        out.update(pa.label for pa in pr.params)
    out.update(notify.EVENTS.values())
    out.update(notify.SOUNDS)
    out.update(notify.POSITIONS)
    # 1.5.1: Overlay-Aussehen, Profile pro Programm
    from modules.gamer import overlaystyle
    out.update(overlaystyle.CORNERS)
    out.update(["Font", "Size", "Bold text", "Dark outline (readable on any background)", "Dark box behind the text", "Highlight colour",
                "Text colour"])
    from modules.macros import page as m_page
    out.add(m_page.GEN_HINT)
    for label, text in m_page.GEN_EXAMPLES:
        out.update([label, text])
    from modules.clicktools import crosshair as ct_cross2
    out.update(ct_cross2.REACTIONS)
    out.update(ct_cross2.COVER_SHAPES)
    out.update(["Cover size", "Cover line width (Cross)", "Spread when shooting (px)", "Opens in (ms)", "Closes in (ms)"])
    # 1.6.0: Hotkey-Verwaltung (Beschriftungen und Gruppen werden beim Anzeigen mit tr() übersetzt), Overlay-Schalter, Tabs
    out.update(["Emergency stop", "General", "Autoclicker", "My macros", "Gaming & Stream", "Game macros", "Game macros (stop key)", "Crosshair",
                "Crosshair: show / hide", "Crosshair: next profile", "Autoclicker: Start", "Autoclicker: Stop", "My macros: Start / Stop",
                "Screenshot of a region", "Match: count a win", "Match: count a loss", "Match: count a kill", "Match: count a death",
                "Match: next round", "Stop all timers", "Notes: next map", "Show / hide all overlays",
                "Show the match overlay", "Show the timer overlay", "Show the notes overlay", "Show the network overlay",
                "Match counter", "Timers", "Notes", "Network", "+ Win", "+ Loss", "+ Kill", "+ Death", "+ Round"])
    out.update(f"Start timer {i} (restarts it)" for i in range(1, 7))
    out.update(["New announcement", "New macro in the marketplace", "No pop-ups or sounds while a program is fullscreen (a summary follows afterwards)",
                "Show community messages even when the Community page is closed or locked"])
    import importlib
    for mod in ("autoclicker", "macros", "extensions", "luascripts", "community", "clicktools", "gamemacros", "gamer", "productivity"):
        p = importlib.import_module(f"modules.{mod}.plugin").Plugin
        out.update((p.name, p.description))
    # 1.7.0: Admin-Modul (Beschriftungen laufen über Variablen)
    from modules.admin import logic as a_logic
    out.update(["Admin", "Overview", "Accounts", "Errors", "Publish",
                "Server overview, accounts, error reports and publishing. Only visible for admin accounts.",
                "Server overview, accounts, error reports and publishing (admin only).",
                "Server is running normally.", "Almost all database connections are in use.",
                "The database is almost full (free plan: 500 MB).", "Low cache hit rate – the server may be short on memory.",
                "No answer from the server."])
    out.update(label for label, _ in a_logic.summarize({}))
    return out


def all_strings() -> list[str]:
    return sorted(from_calls() | from_constants())


if __name__ == "__main__":
    for s in all_strings():
        print(repr(s))
