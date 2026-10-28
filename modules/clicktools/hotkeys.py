"""Hotkey-Manager: eigene Tastenkürzel, die eine Taste drücken, Text eintippen oder ein gespeichertes Makro starten."""
import re
from dataclasses import dataclass

from core.i18n import tr

ACTIONS = ("text", "key", "macro")
MAX_RULES = 30
MAX_TEXT = 500
_MODS = {"ctrl", "alt", "shift", "cmd"}
_OK_KEY = re.compile(r"^([a-z0-9]|f([1-9]|1[0-2])|space|enter|tab|esc|backspace|delete|home|end|page_up|page_down|up|down|left|right|insert)$")


def normalize_hotkey(text: str) -> str:
    """'ctrl + alt + K' -> '<ctrl>+<alt>+k'. Wirft ValueError mit anzeigbarem Text."""
    parts = [p.strip().strip("<>").lower() for p in (text or "").replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError(tr("Please enter a shortcut."))
    mods = [p for p in parts[:-1]]
    key = parts[-1]
    if any(m not in _MODS for m in mods) or key in _MODS or not _OK_KEY.match(key):
        raise ValueError(tr("Unknown key in hotkey: {t}", t=text))
    if not mods and not re.match(r"^f([1-9]|1[0-2])$", key):
        raise ValueError(tr("Use Ctrl, Alt or Shift together with a key (or an F key alone)."))
    fmt = lambda k: f"<{k}>" if len(k) > 1 else k
    return "+".join(fmt(x) for x in mods + [key])


@dataclass
class Rule:
    hotkey: str
    action: str            # text | key | macro
    value: str
    name: str = ""

    def validate(self) -> "Rule":
        self.hotkey = normalize_hotkey(self.hotkey)
        if self.action not in ACTIONS:
            raise ValueError(tr("Unknown action."))
        self.value = (self.value or "").strip() if self.action != "text" else (self.value or "")
        if not self.value:
            raise ValueError(tr("Please fill in what the shortcut should do."))
        if self.action == "text" and len(self.value) > MAX_TEXT:
            raise ValueError(tr("The text is too long (max. {n} characters).", n=MAX_TEXT))
        if self.action == "key":
            self.value = self.value.lower()
            if not _OK_KEY.match(self.value):
                raise ValueError(tr("Unknown key: {t}", t=self.value))
        return self

    def to_dict(self):
        return {"hotkey": self.hotkey, "action": self.action, "value": self.value, "name": self.name}


def parse_rules(data) -> list[Rule]:
    out: list[Rule] = []
    for d in (data if isinstance(data, list) else [])[:MAX_RULES]:
        try:
            out.append(Rule(d["hotkey"], d["action"], d["value"], str(d.get("name", ""))[:40]).validate())
        except (KeyError, TypeError, ValueError):
            continue
    return out


def build_mapping(rules: list[Rule], do) -> dict:
    """pynput-Mapping {Kürzel: Funktion}; do(rule) führt eine Regel aus. Doppelte Kürzel: die erste gilt."""
    m: dict = {}
    for r in rules:
        m.setdefault(r.hotkey, (lambda rr=r: do(rr)))
    return m
