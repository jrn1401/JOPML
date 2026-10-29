"""Tasteneingabe für die GTA-5-Cheat-Konsole.

GTA liest die Tastatur über Scan-Codes; normale Unicode-Eingaben (wie bei `type` im Makro-Modul) kommen dort oft nicht an.
Deshalb werden hier die Tasten über SendInput mit Scan-Codes gedrückt – passend zum aktuell eingestellten Tastaturlayout.
Nur Windows. Es wird nichts im Spiel verändert, nur getippt wie auf einer echten Tastatur.
"""
import sys
import threading
import time

VK_OEM_3 = 0xC0          # Taste, auf die GTA die Konsole legt: US-Layout "~", deutsches Layout "Ö"
SC_LEFT_OF_1 = 0x29      # Taste links neben der 1 ("^" auf deutscher Tastatur)
SC_ENTER = 0x1C
CONSOLE_KEYS = {"Automatisch (~ bzw. Ö)": "auto", "Taste links neben 1 (^)": "left_of_1"}

KEY_DOWN_S = 0.035
BETWEEN_S = 0.035

_lock = threading.Lock()


def available() -> bool:
    return sys.platform == "win32"


class _Win:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ct = ctypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.KEYBDINPUT, self.INPUT = KEYBDINPUT, INPUT
        self.SendInput = user32.SendInput
        self.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.SendInput.restype = wintypes.UINT
        self.VkKeyScanW = user32.VkKeyScanW
        self.VkKeyScanW.argtypes = (wintypes.WCHAR,)
        self.VkKeyScanW.restype = ctypes.c_short
        self.MapVirtualKeyW = user32.MapVirtualKeyW
        self.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
        self.MapVirtualKeyW.restype = wintypes.UINT

    def scan_for_char(self, ch: str) -> int:
        vk = self.VkKeyScanW(ch) & 0xFF
        if vk == 0xFF:
            raise ValueError(f"Zeichen {ch!r} gibt es auf dieser Tastatur nicht.")
        return self.MapVirtualKeyW(vk, 0)        # MAPVK_VK_TO_VSC

    def scan_for_vk(self, vk: int) -> int:
        return self.MapVirtualKeyW(vk, 0)

    def _send(self, scan: int, up: bool):
        flags = 0x0008 | (0x0002 if up else 0)     # KEYEVENTF_SCANCODE (| KEYEVENTF_KEYUP)
        inp = self.INPUT(type=1)                   # INPUT_KEYBOARD
        inp.u.ki = self.KEYBDINPUT(0, scan, flags, 0, 0)
        if self.SendInput(1, self.ct.byref(inp), self.ct.sizeof(inp)) != 1:
            raise OSError("Windows hat die Tasteneingabe abgelehnt (läuft das Spiel als Administrator?).")

    def tap(self, scan: int):
        self._send(scan, False)
        time.sleep(KEY_DOWN_S)
        self._send(scan, True)
        time.sleep(BETWEEN_S)


def plan(codes, console: str = "auto"):
    """Ablauf als Liste von Schritten (zum Testen ohne Windows): ("console",) / ("char", c) / ("enter",) / ("pause", s)."""
    steps = []
    for i, code in enumerate(codes):
        code = "".join(ch for ch in str(code).lower() if ch.isalnum())
        if not code:
            continue
        if i:
            steps.append(("pause", 0.6))
        steps += [("console",), ("pause", 0.35)] + [("char", ch) for ch in code] + [("enter",)]
    return steps


def send_codes(codes, console: str = "auto", delay_s: float = 0, stop: threading.Event | None = None) -> str:
    """Tippt Cheat-Codes in die GTA-Konsole. Gibt '' bei Erfolg oder einen Fehlertext zurück. Blockiert (im Thread aufrufen)."""
    if not available():
        return "Die GTA-Cheats gehen nur unter Windows."
    if not _lock.acquire(blocking=False):
        return "Es wird gerade schon ein Cheat eingegeben."
    try:
        w = _Win()
        con = SC_LEFT_OF_1 if console == "left_of_1" else (w.scan_for_vk(VK_OEM_3) or SC_LEFT_OF_1)
        end = time.time() + max(0.0, delay_s)
        while time.time() < end:
            if stop is not None and stop.is_set():
                return "Abgebrochen."
            time.sleep(0.05)
        for step in plan(codes, console):
            if stop is not None and stop.is_set():
                return "Abgebrochen."
            if step[0] == "pause":
                time.sleep(step[1])
            elif step[0] == "console":
                w.tap(con)
            elif step[0] == "enter":
                w.tap(SC_ENTER)
            else:
                w.tap(w.scan_for_char(step[1]))
        return ""
    except (OSError, ValueError) as exc:
        return str(exc)
    finally:
        _lock.release()
