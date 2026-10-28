"""Globale Hotkeys: überall dieselbe Bedienung. macOS nutzt core/mackeys (Quartz), sonst pynput."""
import sys


def global_hotkeys(mapping: dict):
    """Gibt ein Objekt mit start(), stop() und daemon zurück. Fehler (z. B. fehlende Rechte) kommen als Exception bei start()."""
    if sys.platform == "darwin":
        from core import mackeys
        return mackeys.MacHotKeys(mapping)
    from pynput import keyboard
    return keyboard.GlobalHotKeys(mapping)
