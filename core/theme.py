"""Design: Hell/Dunkel, Akzentfarbe und frei einstellbare Farben (Theme-Manager).

Alle Farben sind (hell, dunkel)-Paare; eigene Farben gelten in beiden Modi.
Absichtlich schlank: Es gibt keine Animationen und keine Hintergrund-Threads.
"""
import re

import customtkinter as ctk

DEFAULT_ACCENT = "#4f8cff"
ACCENTS = {
    "Blue": "#4f8cff", "Violet": "#8b5cf6", "Pink": "#e5589f", "Red": "#e5484d",
    "Orange": "#f08a24", "Green": "#2e9d5b", "Teal": "#14b8a6",
}
MODES = {"Dark": "dark", "Light": "light", "System": "system"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_PALETTE = {
    "sidebar": ("#f3f5fa", "#1b1e25"),          # Seitenleiste und Inhalt sind gleich gefärbte, abgerundete Flächen ...
    "main": ("#f3f5fa", "#1b1e25"),
    "backdrop": ("#c5cad8", "#08090c"),         # ... mit fast schwarzem Zwischenraum (Hintergrund des Fensters)
    "card": ("#ffffff", "#242831"),
    "inset": ("#e8ebf3", "#14161b"),
    "hover": ("#d3d9e8", "#262b36"),
    "bubble": ("#e8ebf3", "#2d323d"),
}
# Namen der frei einstellbaren Farben (Anzeigetext, Schlüssel)
COLOR_KEYS = [("Background", "main"), ("Sidebar", "sidebar"), ("Cards and menus", "card"),
              ("Input fields", "inset"), ("Hover", "hover"), ("Text", "text")]

PRESETS = {
    "Default": {"mode": "dark", "accent": DEFAULT_ACCENT, "colors": {}},
    "Light": {"mode": "light", "accent": DEFAULT_ACCENT, "colors": {}},
    "Graphite": {"mode": "dark", "accent": "#9aa4b2", "colors": {
        "main": "#202124", "sidebar": "#202124", "card": "#2b2c2f", "inset": "#161616", "hover": "#34363a", "text": "#e8eaed"}},
    "Ocean": {"mode": "dark", "accent": "#14b8a6", "colors": {
        "main": "#0f1e2b", "sidebar": "#0f1e2b", "card": "#16293a", "inset": "#0a1520", "hover": "#1d3549", "text": "#e6f1f7"}},
    "Forest": {"mode": "dark", "accent": "#2e9d5b", "colors": {
        "main": "#14201a", "sidebar": "#14201a", "card": "#1c2d24", "inset": "#0e1712", "hover": "#243a2f", "text": "#e8f3ec"}},
    "Sunset": {"mode": "dark", "accent": "#f97316", "colors": {
        "main": "#241a14", "sidebar": "#241a14", "card": "#33241b", "inset": "#1a110c", "hover": "#43301f", "text": "#fbeee3"}},
    "Contrast": {"mode": "dark", "accent": "#ffd400", "colors": {
        "main": "#000000", "sidebar": "#000000", "card": "#141414", "inset": "#000000", "hover": "#2a2a2a", "text": "#ffffff"}},
    "Rose": {"mode": "dark", "accent": "#e5589f", "colors": {
        "main": "#241821", "sidebar": "#241821", "card": "#31212d", "inset": "#1a1018", "hover": "#3d2938", "text": "#f6e9f1"}},
}

PALETTE = dict(DEFAULT_PALETTE)
MUTED = ("gray40", "gray60")
TEXT = ("gray10", "gray90")
DANGER = "#e5484d"
OK = "#2e9d5b"
_accent = DEFAULT_ACCENT


def c(name: str):
    return PALETTE[name]


PANEL_RADIUS = 20       # Seitenleiste und Inhaltsfläche
CARD_RADIUS = 16
GAP = 12                # Abstand zwischen den Flächen


def accent() -> str:
    return _accent


def is_hex(value) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


def shade(color: str, factor: float) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * factor))) for v in (r, g, b))


def mix(a: str, b: str, t: float) -> str:
    """Mischt zwei Hex-Farben: t=0 ergibt a, t=1 ergibt b."""
    ra = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    rb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def hover_tint():
    """Leicht hervorgehobener Hintergrund beim Darüberfahren: Farbe der Seitenleiste mit etwas Akzent (hell, dunkel)."""
    base = c("sidebar")
    base = base if isinstance(base, (tuple, list)) else (base, base)
    return tuple(mix(x, _accent, 0.18) if is_hex(x) else x for x in base[:2])


def contrast_text(bg: str) -> str:
    r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


_last_scale = None
_last_mode = None


def apply(settings: dict) -> None:
    """Setzt Modus, Akzent und eigene Farben. Wirkt auf danach erzeugte Widgets (die App baut ihre Oberfläche neu auf)."""
    global _accent, MUTED, TEXT
    mode = settings.get("appearance_mode", "dark")
    global _last_scale, _last_mode
    from core import perf
    perf.set_potato(settings.get("potato_mode", False))
    try:
        scale = max(80, min(150, int(settings.get("ui_scale", 100)))) / 100
        if scale != _last_scale:                 # nur bei Änderung: jeder Aufruf löst sonst ein Neuzeichnen aller Widgets aus
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            _last_scale = scale
    except (TypeError, ValueError, AttributeError):
        pass
    mode = mode if mode in ("dark", "light", "system") else "dark"
    if mode != _last_mode:
        ctk.set_appearance_mode(mode)
        _last_mode = mode
    acc = settings.get("accent", DEFAULT_ACCENT)
    _accent = acc if is_hex(acc) else DEFAULT_ACCENT

    PALETTE.clear()
    PALETTE.update(DEFAULT_PALETTE)
    custom = settings.get("colors") or {}
    for key in ("main", "sidebar", "card", "inset", "hover"):
        if is_hex(custom.get(key)):
            PALETTE[key] = (custom[key], custom[key])
    if is_hex(custom.get("main")) or is_hex(custom.get("sidebar")):
        base = custom.get("sidebar") if is_hex(custom.get("sidebar")) else custom["main"]
        PALETTE["backdrop"] = (shade(base, 0.8), shade(base, 0.4))
    if is_hex(custom.get("card")) and not is_hex(custom.get("bubble")):
        PALETTE["bubble"] = (shade(custom["card"], 1.15),) * 2
    if is_hex(custom.get("text")):
        TEXT = (custom["text"], custom["text"])
        MUTED = (shade(custom["text"], 0.65),) * 2
    else:
        TEXT, MUTED = ("gray10", "gray90"), ("gray40", "gray60")

    hover = shade(_accent, 0.82)
    on_accent = contrast_text(_accent)
    patches = {
        "CTkButton": {"fg_color": _accent, "hover_color": hover, "text_color": on_accent},
        "CTkOptionMenu": {"fg_color": _accent, "button_color": hover, "button_hover_color": shade(_accent, 0.7)},
        "CTkComboBox": {"button_color": _accent, "button_hover_color": hover},
        "CTkSwitch": {"progress_color": _accent},
        "CTkRadioButton": {"fg_color": _accent, "hover_color": hover},
        "CTkCheckBox": {"fg_color": _accent, "hover_color": hover},
        "CTkSegmentedButton": {"selected_color": _accent, "selected_hover_color": hover},
        "CTkProgressBar": {"progress_color": _accent},
        "CTkSlider": {"progress_color": _accent, "button_color": _accent, "button_hover_color": hover},
    }
    shapes = {"CTkButton": 10, "CTkOptionMenu": 10, "CTkEntry": 10, "CTkComboBox": 10, "CTkSegmentedButton": 10, "CTkTextbox": 10,
              "CTkScrollableFrame": 14}
    try:
        for widget, radius in shapes.items():
            if "corner_radius" in ctk.ThemeManager.theme.get(widget, {}):
                ctk.ThemeManager.theme[widget]["corner_radius"] = radius
        for widget, keys in patches.items():
            for key, value in keys.items():
                if key in ctk.ThemeManager.theme.get(widget, {}):
                    ctk.ThemeManager.theme[widget][key] = [value, value]
    except Exception as exc:     # Farbanpassung ist nur Kosmetik
        print("Theme konnte nicht angepasst werden:", exc)


# Farben der Menü-Symbole (abschaltbar unter Einstellungen > Aussehen)
ICON_COLORS = {
    "dashboard": "#4aa3ff", "autoclicker": "#ff6b6b", "gamemacros": "#a66bff", "macros": "#4cd1a0",
    "productivity": "#ffd23f", "clicktools": "#ff9f43", "gamer": "#6bff8e", "community": "#5ac8fa",
    "extensions": "#c58bff", "publisher": "#ff7ab8", "admin": "#ff5d5d", "recoil": "#ffb36b",
    "assistant": "#7ad7ff", "contact": "#ffc857", "settings": "#b0b8c4",
}


def icon_color(pid: str):
    return ICON_COLORS.get(pid)
