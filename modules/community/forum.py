"""Öffentliches Forum für alle Launcher-Nutzer. Anders als die Chats ist es NICHT verschlüsselt (öffentlich = für alle lesbar);
dafür filtert auch der Server alle Beiträge (Datenbankfunktion jopml_c_check) – der Filter im Client gibt nur eine frühe Rückmeldung."""
from core import chatfilter
from core.cloud import CloudError

from .service import CommunityError, friendly

BOARDS = {                      # Anzeigename der Foren (Reihenfolge kommt vom Server)
    "general": "General",
    "help": "Help & questions",
    "macros": "Macros & scripts",
    "ideas": "Ideas & feedback",
    "offtopic": "Off-topic",
}


class Forum:
    def __init__(self, client):
        self.client = client

    def _rpc(self, name, p=None):
        try:
            return self.client.rpc(name, {"p": p} if p is not None else {})
        except CloudError as exc:
            raise CommunityError(friendly(exc)) from None

    @staticmethod
    def _clean(*texts):
        for t in texts:
            try:
                chatfilter.require_clean(t)
            except chatfilter.FilterError as exc:
                raise CommunityError(str(exc)) from None

    def boards(self) -> list[dict]:
        return self._rpc("jopml_f_boards") or []

    def threads(self, board: str, offset: int = 0) -> list[dict]:
        return self._rpc("jopml_f_threads", {"board": board, "offset": offset}) or []

    def thread(self, thread_id: int) -> dict:
        return self._rpc("jopml_f_thread", {"id": thread_id})

    def new_thread(self, board: str, title: str, body: str) -> int:
        self._clean(title, body)
        return self._rpc("jopml_f_new_thread", {"board": board, "title": title, "body": body})["id"]

    def reply(self, thread_id: int, body: str) -> int:
        self._clean(body)
        return self._rpc("jopml_f_reply", {"thread_id": thread_id, "body": body})["id"]

    def delete(self, kind: str, item_id: int) -> None:
        self._rpc("jopml_f_delete", {"kind": kind, "id": item_id})

    def set_flags(self, thread_id: int, locked=None, pinned=None) -> None:
        self._rpc("jopml_f_set_flags", {"id": thread_id, "locked": locked, "pinned": pinned})

    def report(self, kind: str, item_id: int, author: str, reason: str, text: str = "") -> None:
        self._rpc("jopml_c_report", {"kind": kind, "ref_id": str(item_id), "handle": author, "reason": reason, "evidence": text})
