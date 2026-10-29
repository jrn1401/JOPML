"""Makro-Marktplatz, Ankündigungen und Bestenlisten (Client-Seite). Alle Aufrufe sind blockierend -> im Hintergrund-Thread nutzen."""
from core import chatfilter
from core.i18n import tr
from modules.macros import dsl

from .service import CommunityError

MAX_SCRIPT = 20000
KINDS = ("cps5", "reaction", "recoil_up", "recoil_right", "recoil_zigzag", "recoil_random")


def analyze(script: str) -> list[str]:
    """Sicherheits-/Qualitätshinweise zu einem Makro. Makros sind keine Programme (nur Klicks, Tasten, Text), trotzdem
    zeigen wir vor dem Import, was passieren wird. Wirft dsl.MacroError bei ungültigem Makro."""
    cmds = dsl.parse(script)
    notes: list[str] = []

    def walk(items, inside_forever=False, has_wait=False):
        nonlocal notes
        wait_here = any(c.op in ("wait", "hold") for c in items)
        for c in items:
            if c.op == "repeat":
                forever = not c.args[0]
                if forever and not (wait_here or any(x.op in ("wait", "hold") for x in c.body)):
                    notes.append(tr("A loop without a pause: it would click as fast as possible."))
                if forever:
                    notes.append(tr("Runs forever until you stop it (F7 or the emergency stop)."))
                walk(c.body, inside_forever or forever)
            elif c.op == "type":
                notes.append(tr("Types text: {t}", t=str(c.args[0])[:40]))
            elif c.op == "wait" and c.args[0] < 0.005 and not inside_forever:
                notes.append(tr("Very short pauses (under 5 ms)."))
    walk(cmds)
    if len(script) > MAX_SCRIPT:
        notes.append(tr("The macro is very long."))
    return list(dict.fromkeys(notes))


def check_for_publish(title: str, descr: str, script: str) -> str:
    """Gibt '' oder einen anzeigbaren Fehlertext zurück (gleiche Prüfungen wie der Server, damit Fehler früh kommen)."""
    t = (title or "").strip()
    if not 3 <= len(t) <= 60:
        return tr("The title needs 3–60 characters.")
    if len(descr or "") > 500:
        return tr("The description is too long (max. 500 characters).")
    if not (script or "").strip():
        return tr("There is no macro to share yet.")
    if len(script) > MAX_SCRIPT:
        return tr("The macro is very long.")
    try:
        dsl.parse(script)
    except dsl.MacroError as exc:
        return str(exc)
    for text in (t, descr or "", script):
        v = chatfilter.check(text)
        if not v.ok:
            return chatfilter.explain(v)
    return ""


class MarketService:
    def __init__(self, svc):
        self.svc = svc

    def _rpc(self, name, p=None):
        return self.svc._rpc(name, p)

    def publish(self, title: str, descr: str, script: str) -> int:
        err = check_for_publish(title, descr, script)
        if err:
            raise CommunityError(err)
        return int(self._rpc("jopml_m_publish", {"title": title.strip(), "descr": (descr or "").strip(), "script": script})["id"])

    def browse(self, q: str = "", sort: str = "new", offset: int = 0) -> list[dict]:
        return self._rpc("jopml_m_list", {"q": q, "sort": sort, "offset": offset, "limit": 30}) or []

    def get(self, macro_id: int) -> dict:
        d = self._rpc("jopml_m_get", {"id": macro_id})
        dsl.parse(d["script"])                    # auch vom Server kommende Makros werden geprüft, bevor wir sie anzeigen
        return d

    def rate(self, macro_id: int, stars: int) -> None:
        self._rpc("jopml_m_rate", {"id": macro_id, "stars": stars})

    def report(self, macro_id: int, reason: str) -> None:
        self._rpc("jopml_m_report", {"id": macro_id, "reason": reason})

    def delete(self, macro_id: int) -> None:
        self._rpc("jopml_m_delete", {"id": macro_id})

    # Ankündigungen
    def news(self) -> list[dict]:
        return self._rpc("jopml_news_list") or []

    def post_news(self, title: str, body: str) -> None:
        self._rpc("jopml_news_post", {"title": title, "body": body})

    def delete_news(self, news_id: int) -> None:
        self._rpc("jopml_news_delete", {"id": news_id})

    # Bestenlisten
    def submit_score(self, kind: str, value: float) -> float:
        return float(self._rpc("jopml_score_submit", {"kind": kind, "value": value})["best"])

    def top(self, kind: str) -> list[dict]:
        return self._rpc("jopml_score_top", {"kind": kind, "limit": 20}) or []
