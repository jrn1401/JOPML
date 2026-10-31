"""Erfundene Waffen und Spielstile der Arena (reine Daten, ohne Oberfläche)."""

# Waffe: Schaden, Kopfschuss-Faktor, Schuss/s, Magazin, Nachladen (s), Automatik, Streuung stehend/laufend (Grad), Rückstoßmuster
# Rückstoß = (Seite, Höhe) in Grad je Schuss; nach dem Muster kommt ein zufälliges Wackeln. RECOVER = Grad/s, mit denen sich der Rückstoß ohne Feuer setzt.
WEAPONS = {
    "sidearm": {"name": "Sidearm P1", "damage": 22, "head": 2.5, "rate": 5.0, "mag": 12, "reload": 1.4, "auto": False,
                "spread_stand": 0.15, "spread_move": 2.2, "kick": [(0.0, 1.6)], "wobble": 0.3, "recover": 14.0,
                "zoom": 1.3, "look": "pistol"},
    "smg": {"name": "Vector SMG", "damage": 12, "head": 2.0, "rate": 14.0, "mag": 32, "reload": 1.9, "auto": True,
            "spread_stand": 0.35, "spread_move": 1.4, "recover": 16.0, "wobble": 0.35, "zoom": 1.5, "look": "smg",
            "kick": [(0.0, 0.9)] * 5 + [(0.35, 0.8)] * 8 + [(-0.4, 0.7)] * 8 + [(0.3, 0.6)] * 11},
    "rifle": {"name": "Ranger AR", "damage": 20, "head": 2.5, "rate": 10.0, "mag": 30, "reload": 2.3, "auto": True,
              "spread_stand": 0.25, "spread_move": 2.8, "recover": 12.0, "wobble": 0.3, "zoom": 1.7, "look": "rifle",
              "kick": [(0.0, 1.5)] * 8 + [(0.5, 1.1)] * 6 + [(-0.7, 0.9)] * 8 + [(0.6, 0.8)] * 8},
    "dmr": {"name": "Marksman DMR", "damage": 48, "head": 2.2, "rate": 3.0, "mag": 10, "reload": 2.6, "auto": False,
            "spread_stand": 0.05, "spread_move": 4.0, "kick": [(0.1, 2.6)], "wobble": 0.2, "recover": 9.0,
            "zoom": 3.0, "look": "dmr"},
    "lmg": {"name": "Bulwark LMG", "damage": 18, "head": 2.0, "rate": 11.0, "mag": 60, "reload": 4.0, "auto": True,
            "spread_stand": 0.45, "spread_move": 3.6, "recover": 10.0, "wobble": 0.5, "zoom": 1.6, "look": "lmg",
            "kick": [(0.0, 1.0)] * 10 + [(0.8, 1.3)] * 10 + [(-1.0, 1.1)] * 10 + [(0.7, 0.9)] * 10 + [(-0.6, 0.8)] * 20},
}

# Visieren (rechte Maustaste): ADS_SPREAD = Faktor auf die Streuung, ADS_MOVE = Laufgeschwindigkeit, ADS_KICK = Faktor auf den Rückstoß
ADS_SPREAD, ADS_MOVE, ADS_KICK, ADS_TIME = 0.45, 0.6, 0.8, 0.14

# Spielstile: wie streng Bewegung bestraft wird, wie stark der Rückstoß wirkt, Bot-Leben, Schaden der Bots
STYLES = {
    "Tactical – stand still to shoot": {"descr": "Moving ruins your aim: stop before you shoot. Medium recoil.", "move": 1.6, "recoil": 1.0, "bot_hp": 100, "bot_dmg": 8, "target_speed": 0.9},
    "Precision – one shot counts": {"descr": "Almost no recoil, but any movement makes shots very inaccurate.", "move": 2.4, "recoil": 0.5, "bot_hp": 100, "bot_dmg": 12, "target_speed": 0.0},
    "Arcade – run and gun": {"descr": "Movement hardly matters. Stronger recoil, tougher bots.", "move": 0.25, "recoil": 1.3, "bot_hp": 140, "bot_dmg": 6, "target_speed": 1.9},
}
DEFAULT_STYLE = "Tactical – stand still to shoot"

# Farbthemen: Wand-Grundfarben (4 Sorten), Decke, Boden, Bots (Team A/B), Kopf, Akzent (Leuchtstreifen, Leuchtspur, Fadenkreuz)
THEMES = {
    "Studio": {"walls": ["#6676a0", "#7586b0", "#56658a", "#8394bd"], "sky": "#222c44", "floor": "#27324c", "bot": "#ff5d73", "bot2": "#ffb347", "head": "#ffe0c2", "accent": "#4cc9f0"},
    "Classic": {"walls": ["#8c8f94", "#6e7f9c", "#9c6e6e", "#6e9c7d"], "sky": "#2a3140", "floor": "#3b3f46", "bot": "#e5484d", "bot2": "#e5a50a", "head": "#f3d7b6", "accent": "#ffd479"},
    "Neon": {"walls": ["#7c3aed", "#0ea5e9", "#ec4899", "#22c55e"], "sky": "#0a0612", "floor": "#150b26", "bot": "#fde047", "bot2": "#22d3ee", "head": "#fbcfe8", "accent": "#22d3ee"},
    "Desert": {"walls": ["#c9a46a", "#b58a52", "#d8b98a", "#a77b49"], "sky": "#8ec5e8", "floor": "#d9c08c", "bot": "#2563eb", "bot2": "#dc2626", "head": "#f1d5b0", "accent": "#ff8a3d"},
    "Mono": {"walls": ["#dddddd", "#aaaaaa", "#888888", "#cccccc"], "sky": "#111111", "floor": "#222222", "bot": "#ffffff", "bot2": "#999999", "head": "#ffffff", "accent": "#ffffff"},
}
DEFAULT_THEME = "Studio"

# Fadenkreuz-Farben und -Formen (wie in Zieltrainern frei wählbar)
CROSSHAIR_COLORS = {"White": "#ffffff", "Green": "#4ade80", "Cyan": "#22d3ee", "Pink": "#f472b6", "Yellow": "#fde047"}
CROSSHAIR_STYLES = ("Cross", "Dot", "Circle")


def accent(theme: dict) -> str:
    return theme.get("accent", "#ffd479")


def weapon_ids() -> list:
    return list(WEAPONS)


def kick_for(wid: str, shot_index: int) -> tuple:
    """Rückstoß-Muster der Waffe für den n-ten Schuss in Folge (nach dem Ende des Musters bleibt der letzte Wert)."""
    pat = WEAPONS[wid]["kick"]
    return pat[min(shot_index, len(pat) - 1)]
