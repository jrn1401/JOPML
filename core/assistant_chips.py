"""Passende Schnellfragen für den Hilfe-Assistenten, je nachdem, von welcher Seite man kommt."""

# Modul-ID -> Fragen (Englisch = Quelltext, wird mit tr() übersetzt; jede unter 1000 Zeichen)
CHIPS = {
    "macros": ["How do I make a macro repeat forever?", "How do I click only when a pixel has a certain color?", "How do I test a macro step by step?"],
    "autoclicker": ["How do I set the click speed?", "How do I start and stop the autoclicker with a key?"],
    "clicktools": ["What can the click tools do?", "How do I hold a mouse button for a long time?"],
    "gamer": ["How do I show the ping on the screen?", "How do I move an overlay?", "How do I hide overlays while streaming?"],
    "luascripts": ["How do I add a Lua script?", "Which commands can a Lua script use?"],
    "cheatmenu": ["How does the recoil trainer score me?", "How do I get on the leaderboard?"],
    "community": ["How do I share a macro?", "How do I rate a shared macro?"],
    "modmanager": ["How do I add a module?", "How do I remove a module again?"],
    "settings": ["How do I back up my data?", "How do I change a hotkey?", "How do I change the language?"],
}
DEFAULT = ["What can this program do?", "How do I change a hotkey?", "How do I stop everything quickly?"]


def for_page(pid) -> list[str]:
    """Fragen für die Seite `pid` (zuvor geöffnet); ohne passende Seite die allgemeinen."""
    return list(CHIPS.get(pid or "", DEFAULT))
