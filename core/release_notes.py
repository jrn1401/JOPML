"""Release-Notes je Version: das Programm schreibt sie selbst (aus RELEASE_NOTES.txt bzw. dem Änderungsverlauf des Handbuchs plus dem Text, den der
Admin beim Hochladen einträgt) und trägt sie in Community > News ein (eine Ankündigung je Version, aufklappbar)."""
import re
from pathlib import Path

MAX_BODY = 5800


def _file_lines() -> dict[str, str]:
    try:
        text = (Path(__file__).resolve().parents[1] / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    except OSError:
        return {}
    out = {}
    for part in re.split(r"(?=Version \d+\.\d+\.\d+:)", text):
        m = re.match(r"Version (\d+\.\d+\.\d+):\s*(.*)", part.strip(), re.S)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def bullets(text: str) -> list[str]:
    """Teilt eine Zeile in Stichpunkte: an ';' und an Satzenden ('. ' + Großbuchstabe), aber nie innerhalb von Klammern oder Anführungszeichen."""
    items, depth, quote, cur = [], 0, False, ""
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "„":
            quote = True
        elif ch == "“":
            quote = False
        cur += ch
        free = depth == 0 and not quote
        nxt = text[i + 2] if i + 2 < len(text) else ""
        if free and ch == ";":
            items.append(cur[:-1])
            cur = ""
        elif free and ch == "." and text[i + 1:i + 2] == " " and nxt.isupper():
            items.append(cur)
            cur = ""
    items.append(cur)
    return [x.strip().rstrip(".").strip() for x in items if x.strip(" .")]


def known_versions() -> list[str]:
    """Alle Versionen, zu denen es Notizen gibt, älteste zuerst."""
    return sorted(_file_lines(), key=lambda v: tuple(int(x) for x in v.split(".")))


def compose(version: str, extra: str = "") -> tuple[str, str]:
    """(Titel, Text) für eine Version. Quelle: RELEASE_NOTES.txt; fehlt die Version dort, der Text des Admins."""
    line = _file_lines().get(version, "")
    parts = ["• " + b for b in bullets(line)] if line else []
    extra = (extra or "").strip()
    if extra:
        parts.append(("" if not parts else "\n") + extra)
    body = "\n".join(parts).strip() or "Neue Version."
    return f"Version {version}", body[:MAX_BODY]


def post(client, version: str, extra: str = "") -> None:
    """Trägt die Release-Note ein (aktualisiert sie, wenn es die Version schon gibt). Wirft bei Fehlern."""
    title, body = compose(version, extra)
    client.rpc("jopml_admin_release_note", {"p": {"version": version, "title": title, "body": body}})
