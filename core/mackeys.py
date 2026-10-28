"""macOS: Tastatur ohne pynput-Tastaturüberwachung.

Hintergrund: Unter neueren macOS-Versionen stürzt die Tastatur-Überwachung von pynput ab (Tastenübersetzung außerhalb des
Hauptthreads). Das Programm "schließt sich unerwartet", sobald irgendwo eine Taste gedrückt wird (z. B. Cmd+Tab).
Diese Datei liest die Tasten direkt über Quartz (Tastencode statt Zeichen) und braucht keine Übersetzung.
Nur die Tabellen und das Parsen sind plattformunabhängig und werden getestet; Quartz wird erst bei Gebrauch geladen.
Nachteil: Tastencodes sind die US-Positionen. Bei anderen Layouts (z. B. QWERTZ) liegen Buchstaben-Hotkeys an der US-Stelle.
Empfehlung: F-Tasten als Hotkeys (F6, F7, F8) – die sind überall gleich.
"""
import threading

from core.i18n import tr

KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14,
    "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27,
    "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "enter": 36, "l": 37, "j": 38, "'": 39,
    "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "tab": 48, "space": 49, "`": 50,
    "backspace": 51, "esc": 53, "delete": 117, "home": 115, "end": 119, "page_up": 116, "page_down": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
    "f11": 103, "f12": 111,
}
NAMES = {v: k for k, v in KEYCODES.items()}
# Modifier-Bits (CGEventFlags)
SHIFT, CTRL, ALT, CMD = 0x20000, 0x40000, 0x80000, 0x100000
MOD_BITS = {"shift": SHIFT, "ctrl": CTRL, "alt": ALT, "cmd": CMD}
MOD_ORDER = ["ctrl", "alt", "shift", "cmd"]
_ALIASES = {"ctrl_l": "ctrl", "ctrl_r": "ctrl", "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt", "shift_l": "shift",
            "shift_r": "shift", "cmd_l": "cmd", "cmd_r": "cmd", "escape": "esc", "return": "enter"}
ALL_MODS = SHIFT | CTRL | ALT | CMD


def parse_hotkey(hk: str) -> tuple[int, int]:
    """'<ctrl>+<alt>+p' -> (tastencode, modifier-maske). Wirft ValueError bei Unbekanntem."""
    mods, code = 0, None
    for raw in (hk or "").split("+"):
        part = raw.strip()
        name = part[1:-1] if part.startswith("<") and part.endswith(">") else part
        name = _ALIASES.get(name.lower(), name.lower())
        if name in MOD_BITS:
            mods |= MOD_BITS[name]
        elif name in KEYCODES and code is None:
            code = KEYCODES[name]
        else:
            raise ValueError(tr("Unknown key in hotkey: {t}", t=part))
    if code is None:
        raise ValueError(tr("The hotkey needs a key (not only Ctrl/Alt/Shift/Cmd)."))
    return code, mods


def key_name(code: int) -> str | None:
    return NAMES.get(code)


def mods_from_flags(flags: int) -> list[str]:
    return [m for m in MOD_ORDER if flags & MOD_BITS[m]]


class KeyTap(threading.Thread):
    """Hört auf Tastendrücke (keyDown) und ruft callback(tastencode, flags) im eigenen Thread auf."""

    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self.error = ""
        self._ready = threading.Event()
        self._loop = None
        self._tap = None

    def start(self):
        super().start()
        self._ready.wait(3)
        if self.error:
            raise RuntimeError(self.error)

    def run(self):
        try:
            import Quartz
        except Exception as exc:
            self.error = f"Quartz: {exc}"
            self._ready.set()
            return

        def cb(proxy, etype, event, refcon):
            try:
                if etype in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                    Quartz.CGEventTapEnable(self._tap, True)
                    return event
                code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                self.callback(int(code), int(Quartz.CGEventGetFlags(event)))
            except Exception:
                pass
            return event

        self._tap = Quartz.CGEventTapCreate(Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                                            Quartz.kCGEventTapOptionListenOnly,
                                            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown), cb, None)
        if self._tap is None:
            self.error = tr("No permission to monitor keys. Allow JOPML under System Settings → Privacy & Security → "
                            "Input Monitoring (and Accessibility), then restart the app.")
            self._ready.set()
            return
        src = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._loop, src, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        self._ready.set()
        Quartz.CFRunLoopRun()

    def stop(self):
        try:
            import Quartz
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, False)
            if self._loop is not None:
                Quartz.CFRunLoopStop(self._loop)
        except Exception:
            pass


class MacHotKeys:
    """Gleiche Bedienung wie pynput.keyboard.GlobalHotKeys({"<f6>": funktion})."""

    def __init__(self, mapping: dict):
        self._map = {}
        for hk, fn in mapping.items():
            self._map[parse_hotkey(hk)] = fn
        self.daemon = True
        self._tap = KeyTap(self._on_key)

    def _on_key(self, code, flags):
        fn = self._map.get((code, flags & ALL_MODS))
        if fn:
            fn()

    def start(self):
        self._tap.start()

    def stop(self):
        self._tap.stop()


def tap_key(name: str) -> None:
    """Drückt eine Taste (down/up) über Quartz. Wirft KeyError, wenn der Name nicht bekannt ist."""
    import Quartz
    code = KEYCODES[_ALIASES.get(name.lower(), name.lower())]
    for down in (True, False):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateKeyboardEvent(None, code, down))
