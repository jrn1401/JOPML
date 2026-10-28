"""Fertige Spiele-Makros (Bibliothek). Jedes Preset erzeugt aus einigen Einstellungen ein Makro in der Makro-Sprache.

Kein GUI-Import. Alle Presets sind für Einzelspieler-, Idle-Spiele und Server gedacht, auf denen so etwas erlaubt ist."""
import re
from dataclasses import dataclass, field
from typing import Callable

from core.i18n import tr

CATEGORIES = {"minecraft": "Minecraft", "idle": "Idle & clicker games", "inventory": "Inventory & crafting", "chat": "Chat & emotes"}
CHAT_KEYS = ["enter", "t", "y", "u"]


@dataclass
class Param:
    key: str
    label: str
    default: object
    kind: str = "int"          # int | float | text | choice
    lo: float = 0
    hi: float = 100000
    choices: list = field(default_factory=list)


@dataclass
class Preset:
    id: str
    category: str
    title: str
    desc: str
    params: list
    build: Callable[[dict], str]


def clean(text: str, limit: int = 300) -> str:
    """Text für `type "..."`: keine Anführungszeichen, keine Zeilenumbrüche."""
    return re.sub(r"[\"\r\n#]", "", str(text)).strip()[:limit]


PLACEHOLDERS = ("{zeit}", "{runde}", "{name}")      # auch englisch: {time}, {round}


def fill(text: str, ctx: dict | None) -> str:
    """Ersetzt {zeit}/{time}, {runde}/{round} und {name} im Text. Ohne Angaben bleiben die Platzhalter stehen."""
    ctx = ctx or {}
    for keys, val in ((("zeit", "time"), ctx.get("time")), (("runde", "round"), ctx.get("round")), (("name",), ctx.get("name"))):
        if val is None or val == "":
            continue
        for k in keys:
            text = text.replace("{" + k + "}", str(val))
    return text


def value(p: Param, raw):
    """Prüft einen Eingabewert. Wirft ValueError mit anzeigbarem Text."""
    if p.kind == "text":
        t = clean(raw)
        if not t:
            raise ValueError(tr("Please fill in: {f}", f=tr(p.label)))
        return t
    if p.kind == "choice":
        if raw not in p.choices:
            raise ValueError(tr("Please fill in: {f}", f=tr(p.label)))
        return raw
    try:
        v = float(str(raw).replace(",", "."))
    except ValueError:
        raise ValueError(tr("Please enter a number for: {f}", f=tr(p.label))) from None
    if not p.lo <= v <= p.hi:
        raise ValueError(tr("{f} must be between {lo} and {hi}.", f=tr(p.label), lo=p.lo, hi=p.hi))
    return v if p.kind == "float" else int(v)


def _head(v) -> str:
    return f"wait {v['delay']}s\n" if v.get("delay") else ""


_DELAY = Param("delay", "Start delay (s)", 3, "int", 0, 60)


def _mine(v):
    return _head(v) + "down mouse_left\nrepeat forever\n  wait 1s\nend\n"


def _fish(v):
    return (_head(v) + f"repeat forever\n  click right\n  wait 1500ms\n  click right\n  wait {v['wait']}s\nend\n")


def _cmd(v):
    return _head(v) + f'key t\nwait 300ms\ntype "{v["command"]}"\nwait 100ms\nkey enter\n'


def _fastclick(v):
    return _head(v) + f"repeat forever\n  click left\n  wait {v['ms']}ms\nend\n"


def _upgrade(v):
    return _head(v) + f"repeat forever\n  click left {v['x']} {v['y']}\n  wait {v['every']}s\nend\n"


def _shift_row(v):
    lines = [_head(v) + "down shift"]
    for i in range(v["count"]):
        lines.append(f"move {v['x'] + i * v['step']} {v['y']}")
        lines.append("click left")
        lines.append(f"wait {v['pause']}ms")
    lines.append("up shift")
    return "\n".join(lines) + "\n"


def parse_positions(text: str) -> list[tuple[int, int]]:
    out = []
    for part in re.split(r"[;\n]", str(text)):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d{1,5})\s*[, ]\s*(\d{1,5})", part)
        if not m:
            raise ValueError(tr("Positions must look like 100,200; 300,200"))
        out.append((int(m.group(1)), int(m.group(2))))
    if not 1 <= len(out) <= 12:
        raise ValueError(tr("Enter 1 to 12 positions like 100,200; 300,200"))
    return out


def _craft(v):
    body = "".join(f"  click left {x} {y}\n  wait {v['pause']}ms\n" for x, y in parse_positions(v["positions"]))
    return _head(v) + f"repeat {v['times']}\n{body}end\n"


CHANNELS = ["Chat key as set", "All chat (Shift + chat key)"]
GG_LANGS = ["English", "Deutsch", "Español", "All three"]
GG_TEXT = {"English": "gg, well played!", "Deutsch": "gg, gut gespielt!", "Español": "gg, bien jugado!"}


def _opener(chat_key: str, channel: str) -> str:
    if channel == CHANNELS[1]:
        return f"down shift\nkey {chat_key}\nup shift\n"
    return f"key {chat_key}\n"


def _send(chat_key: str, text: str, channel: str = "") -> str:
    """Eine Nachricht: Chat öffnen, kurz warten, tippen, Enter."""
    return _opener(chat_key, channel) + f'wait 150ms\ntype "{text}"\nwait 100ms\nkey enter\n'


def _chat(v):
    return _head(v) + _send(v["chat_key"], v["message"], v.get("channel", ""))


def _chat_multi(v):
    """Mehrere Nachrichten (getrennt durch |) nacheinander, mit Mindestabstand (Schutz vor Chat-Spam)."""
    msgs = [clean(m) for m in str(v["messages"]).split("|") if clean(m)]
    if not 1 <= len(msgs) <= 8:
        raise ValueError(tr("Enter 1 to 8 messages separated by |"))
    out = _head(v)
    for i, m in enumerate(msgs):
        if i:
            out += f"wait {v['gap']}s\n"
        out += _send(v["chat_key"], m, v.get("channel", ""))
    return out


def _gg_multi(v):
    langs = ["English", "Deutsch", "Español"] if v["language"] == "All three" else [v["language"]]
    out = _head(v)
    for i, lg in enumerate(langs):
        if i:
            out += f"wait {v['gap']}s\n"
        out += _send(v["chat_key"], GG_TEXT[lg], v.get("channel", ""))
    return out


def _emote(v):
    keys = [k.strip().lower() for k in str(v["keys"]).split(",") if k.strip()]
    if not 1 <= len(keys) <= 12:
        raise ValueError(tr("Enter 1 to 12 keys separated by commas, e.g. g, g, h"))
    body = "".join(f"  key {k}\n  wait {v['pause']}ms\n" for k in keys)
    return _head(v) + f"repeat {v['times']}\n{body}end\n"


PRESETS = [
    Preset("mc_mine", "minecraft", "Auto-mining (hold the left mouse button)",
           "Holds the left mouse button down so your tool keeps breaking blocks. Stop releases it.", [_DELAY], _mine),
    Preset("mc_fish", "minecraft", "Auto-fishing (reel in and cast again)",
           "Right-clicks to reel in and cast again after the waiting time. It does not see bites – set the time to how long a bite usually takes.",
           [_DELAY, Param("wait", "Wait for a bite (s)", 25, "int", 3, 120)], _fish),
    Preset("mc_cmd", "minecraft", "Run a command",
           "Opens the chat, types your command and sends it – e.g. /time set day or /tp. Only works where you may use commands (single player, own server).",
           [_DELAY, Param("command", "Command", "/time set day", "text")], _cmd),
    Preset("idle_click", "idle", "Fast auto-click (Cookie Clicker and similar)",
           "Clicks at the current mouse position very fast. Move the mouse over the big button first.",
           [_DELAY, Param("ms", "Pause between clicks (ms)", 10, "int", 1, 5000)], _fastclick),
    Preset("idle_upgrade", "idle", "Buy upgrades regularly",
           "Clicks one screen position again and again, e.g. the upgrade button. Find the coordinates with the colour trigger tab or your screen tools.",
           [_DELAY, Param("x", "X position", 500, "int", 0, 20000), Param("y", "Y position", 400, "int", 0, 20000),
            Param("every", "Every (s)", 5, "int", 1, 3600)], _upgrade),
    Preset("inv_shift", "inventory", "Move items quickly (Shift+click a row)",
           "Holds Shift and clicks a row of inventory slots one after another to move the items.",
           [_DELAY, Param("x", "First slot X", 400, "int", 0, 20000), Param("y", "Slot row Y", 500, "int", 0, 20000),
            Param("step", "Distance between slots (px)", 54, "int", 1, 500), Param("count", "Number of slots", 9, "int", 1, 36),
            Param("pause", "Pause per slot (ms)", 60, "int", 0, 2000)], _shift_row),
    Preset("inv_craft", "inventory", "Crafting sequence",
           "Clicks a list of positions in order and repeats it, e.g. pick ingredient, place, take result.",
           [_DELAY, Param("positions", "Positions (x,y; x,y; …)", "400,300; 500,300; 700,300", "text"),
            Param("times", "Repeat", 10, "int", 1, 1000), Param("pause", "Pause per click (ms)", 150, "int", 0, 5000)], _craft),
    Preset("chat_msg", "chat", "Send a prepared message",
           "Opens the chat with the chosen key, types your message and sends it. Placeholders: {zeit} time, {runde} round number, {name} your name.",
           [_DELAY, Param("chat_key", "Key that opens the chat", "enter", "choice", choices=CHAT_KEYS),
            Param("message", "Message", "Good game, well played!", "text"),
            Param("channel", "Channel", CHANNELS[0], "choice", choices=CHANNELS)], _chat),
    Preset("chat_multi", "chat", "Several messages in a row",
           "Sends up to 8 messages one after another, separated by |. The pause between them protects you from chat spam (at least 2 seconds). "
           "Placeholders: {zeit} time, {runde} round number, {name} your name.",
           [_DELAY, Param("chat_key", "Key that opens the chat", "enter", "choice", choices=CHAT_KEYS),
            Param("messages", "Messages (separated by |)", "gg | see you next round, {name}", "text"),
            Param("gap", "Pause between messages (s)", 3, "int", 2, 60),
            Param("channel", "Channel", CHANNELS[0], "choice", choices=CHANNELS)], _chat_multi),
    Preset("chat_gg_multi", "chat", "GG in several languages",
           "Says “gg” in English, German, Spanish or all three one after another.",
           [_DELAY, Param("chat_key", "Key that opens the chat", "enter", "choice", choices=CHAT_KEYS),
            Param("language", "Language", GG_LANGS[0], "choice", choices=GG_LANGS),
            Param("gap", "Pause between messages (s)", 3, "int", 2, 60),
            Param("channel", "Channel", CHANNELS[0], "choice", choices=CHANNELS)], _gg_multi),
    Preset("chat_gg", "chat", "Say GG",
           "A quick “gg” at the end of a round.",
           [_DELAY, Param("chat_key", "Key that opens the chat", "enter", "choice", choices=CHAT_KEYS), Param("message", "Message", "gg", "text")], _chat),
    Preset("chat_callout", "chat", "Callout for your team",
           "A short callout you can send with one click – change the text to your call.",
           [_DELAY, Param("chat_key", "Key that opens the chat", "y", "choice", choices=CHAT_KEYS), Param("message", "Message", "Need help here!", "text")], _chat),
    Preset("chat_emote", "chat", "Emote / dance combo",
           "Presses a row of keys one after another, e.g. for an emote or dance combo.",
           [_DELAY, Param("keys", "Keys (separated by commas)", "g, g, h", "text"), Param("times", "Repeat", 3, "int", 1, 100),
            Param("pause", "Pause between keys (ms)", 250, "int", 0, 5000)], _emote),
]
BY_ID = {p.id: p for p in PRESETS}


def build(preset: Preset, raw: dict, ctx: dict | None = None) -> str:
    """Erzeugt das Makro aus Roheingaben (Texte). Wirft ValueError mit anzeigbarem Text. Das Ergebnis wird zusätzlich vom Makro-Parser geprüft.
    ctx: Werte für die Platzhalter {zeit}, {runde}, {name} in Textfeldern."""
    vals = {p.key: value(p, raw.get(p.key, p.default)) for p in preset.params}
    for p in preset.params:
        if p.kind == "text" and isinstance(vals[p.key], str):
            vals[p.key] = clean(fill(vals[p.key], ctx))
    script = preset.build(vals)
    from modules.macros import dsl
    try:
        dsl.parse(script)
    except dsl.MacroError as exc:
        raise ValueError(str(exc)) from None
    return script


def defaults(preset: Preset) -> dict:
    return {p.key: p.default for p in preset.params}
