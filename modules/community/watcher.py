"""Community-Meldungen im Hintergrund: auch wenn die Community-Seite nicht geöffnet oder noch nicht entsperrt ist.

Alle 60 Sekunden werden Serverliste, Einladungen, Ankündigungen und neue Makros des Marktplatzes abgefragt (nur Metadaten, es wird nichts
entschlüsselt). Der erste Durchlauf merkt sich nur den Stand; gemeldet wird erst, was danach neu ist. Die Auswahl der Quellen und die
stummgeschalteten Server stehen in den Benachrichtigungs-Einstellungen. Solange die Chat-Ansicht selbst läuft, übernimmt sie die Meldungen."""
import threading

INTERVAL_S = 60


def unread_map(spaces: list[dict], is_unread, skip_channel: str = "") -> dict:
    """{Kanal-ID: (Art, Server-ID, Name)} für alle ungelesenen Kanäle. Art: "server" oder "dm"."""
    out = {}
    for sp in spaces or []:
        kind = sp.get("kind", "server")
        label = (sp.get("peer") or {}).get("display_name") if kind == "dm" else sp.get("name")
        for c in sp.get("channels", []):
            if c["id"] != skip_channel and is_unread(c):
                out[c["id"]] = (kind, sp.get("id", ""), label or c.get("name", ""))
    return out


def fresh_events(prev: dict | None, cur: dict, muted_servers=()) -> list[tuple[str, str, str]]:
    """Vergleicht den alten und den neuen Stand. Gibt (Ereignis, Titel, Text) zurück; prev=None ist der erste Durchlauf (nichts melden).
    Stand: {"unread": {...}, "invites": int, "news": int, "market": int}"""
    if prev is None:
        return []
    out: list[tuple[str, str, str]] = []
    muted = {str(m) for m in muted_servers}
    new = {cid: v for cid, v in cur["unread"].items() if cid not in prev["unread"] and v[1] not in muted}
    dms = sorted({v[2] for v in new.values() if v[0] == "dm"})
    chans = sorted({v[2] for v in new.values() if v[0] != "dm"})
    if dms:
        out.append(("dm", "New messages", ", ".join(dms[:3])))
    if chans:
        out.append(("chat", "New messages", ", ".join("#" + c for c in chans[:3])))
    if cur["invites"] > prev["invites"]:
        out.append(("invite", "New invitation", "You were invited to a server."))
    if cur["news"] > prev["news"]:
        out.append(("news", "New announcement", ""))
    if cur["market"] > prev["market"]:
        out.append(("market", "New macro in the marketplace", ""))
    return out


class Watcher:
    def __init__(self, plugin):
        self.plugin = plugin
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev: dict | None = None
        self.error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._prev = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(5 if self._prev is None else INTERVAL_S):
            try:
                self.poll()
            except Exception as exc:
                self.error = str(exc)[:200]

    def snapshot(self) -> dict | None:
        svc = self.plugin.service()
        if svc is None:
            return None
        spaces = svc.refresh()
        from modules.community.market import MarketService
        mk = MarketService(svc)
        news = max([int(r.get("id", 0)) for r in mk.news()] or [0])
        market = max([int(r.get("id", 0)) for r in mk.browse("", "new")] or [0])
        return {"unread": unread_map(spaces, self.plugin.is_unread), "invites": len(svc.my_invites()), "news": news, "market": market}

    def poll(self) -> list:
        if getattr(self.plugin, "chat_active", False):
            self._prev = None                       # die Chat-Ansicht läuft: danach neu aufsetzen, damit nichts doppelt gemeldet wird
            return []
        cur = self.snapshot()
        if cur is None:
            return []
        prefs = self.plugin.app.notifier.prefs()
        events = fresh_events(self._prev, cur, prefs.muted_servers)
        self._prev = cur
        from core.i18n import tr
        for ev, title, text in events:
            self.plugin.app.call_soon(self.plugin.app.notifier.notify, ev, tr(title), tr(text) if text.endswith(".") else text)
        return events
