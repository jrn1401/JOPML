"""Zeitleiste für Makros: Schritte (oberste Ebene, Blöcke wie repeat/if bleiben zusammen) verschieben, löschen und alle Pausen skalieren.
Reine Textfunktionen ohne Oberfläche; die Seite prüft das Ergebnis danach mit dsl.parse."""
import re

OPENERS = ("repeat", "if")
WAIT_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m)\b")
UNIT_MS = {"ms": 1.0, "s": 1000.0, "m": 60000.0}


def _word(line: str) -> str:
    s = line.strip().split(None, 1)
    return s[0].lower() if s else ""


def blocks(script: str) -> list[list[str]]:
    """Oberste Schritte; ein Block (repeat/if ... end) ist ein Schritt. Leere Zeilen fallen weg."""
    out, cur, depth = [], [], 0
    for line in script.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        w = _word(line)
        cur.append(line.rstrip())
        if w in OPENERS:
            depth += 1
        elif w == "end":
            depth = max(0, depth - 1)
        if depth == 0:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def join(bl: list[list[str]]) -> str:
    return "\n".join("\n".join(b) for b in bl) + ("\n" if bl else "")


def summary(block: list[str]) -> str:
    first = block[0].strip()
    return first if len(block) == 1 else f"{first}  (+{len(block) - 1})"


def move(script: str, i: int, d: int) -> str:
    bl = blocks(script)
    j = i + d
    if 0 <= i < len(bl) and 0 <= j < len(bl):
        bl[i], bl[j] = bl[j], bl[i]
    return join(bl)


def delete(script: str, i: int) -> str:
    bl = blocks(script)
    if 0 <= i < len(bl):
        del bl[i]
    return join(bl)


def duplicate(script: str, i: int) -> str:
    bl = blocks(script)
    if 0 <= i < len(bl):
        bl.insert(i + 1, list(bl[i]))
    return join(bl)


def _fmt(ms: float) -> str:
    ms = max(1.0, ms)
    if ms >= 60000 and ms % 60000 == 0:
        return f"{int(ms // 60000)}m"
    if ms >= 1000 and ms % 1000 == 0:
        return f"{int(ms // 1000)}s"
    return f"{int(round(ms))}ms"


def scale_waits(script: str, factor: float) -> str:
    """Alle Pausen (wait ...) mit factor multiplieren; Zufallsbereiche (100ms-300ms) werden beide skaliert. Faktor 0.1 bis 10."""
    factor = max(0.1, min(10.0, float(factor)))
    out = []
    for line in script.replace("\r\n", "\n").split("\n"):
        if _word(line) == "wait":
            line = WAIT_RE.sub(lambda m: _fmt(float(m.group(1)) * UNIT_MS[m.group(2)] * factor), line)
        out.append(line)
    return "\n".join(out)


def total_wait_ms(script: str) -> float:
    """Grobe Summe aller Pausen auf einmaligem Durchlauf (Wiederholungen ungezählt; Zufallsbereich = Mittelwert)."""
    total = 0.0
    for line in script.split("\n"):
        if _word(line) == "wait":
            vals = [float(m.group(1)) * UNIT_MS[m.group(2)] for m in WAIT_RE.finditer(line)]
            if vals:
                total += sum(vals) / len(vals)
    return total
