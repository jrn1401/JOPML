"""Kartoffel-Modus: ein globaler Schalter, den rechenintensive Teile (Abfragen, Animationen, Hintergrund) befragen."""
POTATO = False
FACTOR = 3          # im Kartoffel-Modus werden Abfrageintervalle so viel länger


def set_potato(on: bool) -> None:
    global POTATO
    POTATO = bool(on)


def ms(base: int) -> int:
    """Intervall in ms, im Kartoffel-Modus länger."""
    return int(base) * FACTOR if POTATO else int(base)
