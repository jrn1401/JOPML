"""Kennwerte für die Waffenkarten im Menü (ohne Oberfläche, testbar)."""
from . import weapons


def stat_bars(wid: str) -> list:
    """Vier Kennwerte 0..1 (Schaden, Feuerrate, Rückstoß, Magazin)."""
    w = weapons.WEAPONS[wid]
    kick = sum(abs(k[1]) for k in w["kick"][:10]) / min(10, len(w["kick"]))
    return [("Damage", min(1, w["damage"] / 50)), ("Fire rate", min(1, w["rate"] / 15)), ("Recoil", min(1, kick / 1.8)), ("Magazine", min(1, w["mag"] / 60))]
