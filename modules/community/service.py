"""Community-Dienst: Server, Kanäle, Direktnachrichten, Einladungen – mit Ende-zu-Ende-Verschlüsselung auf dem Gerät.

Der Server (Supabase) bekommt nur Chiffretext, öffentliche Schlüssel und passwortgeschützte Schlüssel-Behälter.
Alle Aufrufe hier sind blockierend (Netzwerk) und gehören in einen Hintergrund-Thread.
"""
import json
import threading
from dataclasses import dataclass

from core import chatfilter
from core.cloud import CloudError
from core.i18n import tr

from . import crypto

MAX_TEXT = 2000
MIN_PASSPHRASE = 8


class CommunityError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden (englisch, wird mit tr() übersetzt)."""


# Fehlercodes des Servers -> verständliche Texte
ERROR_TEXTS = {
    "not_authenticated": "Please sign in again.",
    "not_registered": "Set up the community first.",
    "suspended": "This account is suspended from the community.",
    "forbidden": "You are not allowed to do this.",
    "not_found": "Not found.",
    "invite_invalid": "This invitation is invalid, expired or used up.",
    "user_not_found": "There is no user with this name.",
    "handle_taken": "This username is already taken.",
    "invalid_handle": "The username may contain 3–24 letters, digits and . _ -",
    "invalid_name": "This name is not valid.",
    "name_not_allowed": "This name is not allowed. Please choose another one.",
    "name_taken": "This name is already used here.",
    "rate_limited": "You are doing this too fast. Please wait a moment.",
    "limit_servers": "You can own at most 5 servers.",
    "limit_channels": "A server can have at most 25 channels.",
    "limit_members": "This server is full.",
    "limit_memberships": "You have reached the maximum number of servers and chats.",
    "limit_invites": "Too many open invitations.",
    "limit_dms": "You have reached the maximum number of direct chats.",
    "banned": "You are banned from this server.",
    "already_member": "This person is already a member.",
    "already_registered": "The community is already set up for this account.",
    "stale_epoch": "The keys changed. Please try again in a moment.",
    "no_key": "You do not have the key for this chat yet. A server admin has to approve you first.",
    "last_channel": "The last channel cannot be deleted.",
    "owner_cannot_leave": "The owner cannot leave. Delete the server instead.",
    "thread_locked": "This thread is locked.",
    "invalid_target": "You cannot do this with yourself.",
    "invalid_email": "Please enter a valid email address.",
    "invalid_script": "This macro contains commands that are not allowed.",
    "invalid_payload": "This value is not accepted.",
    "muted": "You are muted on this server for now.",
    "slowmode": "Slow mode is on: please wait a bit before your next message.",
}


def friendly(exc: Exception) -> str:
    msg = str(exc)
    if msg.startswith("filtered"):
        cat = msg.split(":", 1)[1] if ":" in msg else ""
        return chatfilter.explain(chatfilter.Verdict(False, cat or "profanity"))
    return tr(ERROR_TEXTS.get(msg.strip(), msg))


@dataclass
class Message:
    id: int
    sender_id: str
    handle: str
    name: str
    text: str
    created_at: str
    mine: bool
    ok: bool = True            # entschlüsselt
    verified: bool = False     # Signatur stimmt
    filtered: bool = False     # beim Anzeigen wurden Wörter ausgeblendet
    epoch: int = 1
    reply: dict | None = None  # {"id", "n", "s"}: Antwort auf eine andere Nachricht
    body: str = ""
    sig: str = ""


class CommunityService:
    def __init__(self, client):
        self.client = client
        self.me: dict | None = None
        self.bundle: crypto.KeyBundle | None = None
        self.spaces: list[dict] = []
        self._keys: dict[tuple[str, int], bytes] = {}
        self._members: dict[str, dict] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------ Aufrufe
    def _rpc(self, name: str, p: dict | None = None):
        try:
            return self.client.rpc(name, {"p": p} if p is not None else {})
        except CloudError as exc:
            raise CommunityError(friendly(exc)) from None

    # ------------------------------------------------------------ Einrichtung
    def load_me(self) -> dict:
        self.me = self._rpc("jopml_c_me")
        return self.me

    @property
    def registered(self) -> bool:
        return bool(self.me and self.me.get("registered"))

    @property
    def unlocked(self) -> bool:
        return self.bundle is not None

    @property
    def my_id(self) -> str:
        return (self.me or {}).get("user_id", "")

    def setup(self, handle: str, display: str, passphrase: str) -> None:
        if len(passphrase) < MIN_PASSPHRASE:
            raise CommunityError(tr("The passphrase needs at least {n} characters.", n=MIN_PASSPHRASE))
        for text in (handle, display):
            try:
                chatfilter.require_clean(text)
            except chatfilter.FilterError as exc:
                raise CommunityError(str(exc)) from None
        bundle = crypto.KeyBundle.generate()
        self.me = self._rpc("jopml_c_setup", {"handle": handle, "display": display, "enc_pub": bundle.enc_pub,
                                              "sign_pub": bundle.sign_pub, "bundle": crypto.seal_bundle(bundle, passphrase)})
        self.bundle = bundle

    def unlock(self, passphrase: str) -> None:
        if not self.registered:
            raise CommunityError(ERROR_TEXTS["not_registered"])
        try:
            bundle = crypto.open_bundle(self.me["bundle"], passphrase)
        except crypto.CryptoError as exc:
            raise CommunityError(str(exc)) from None
        if bundle.enc_pub != self.me["enc_pub"] or bundle.sign_pub != self.me["sign_pub"]:
            raise CommunityError("The stored keys do not match. Do not continue – the server may have been tampered with.")
        self.bundle = bundle

    def lock(self) -> None:
        with self._lock:
            self.bundle, self._keys, self._members, self.spaces, self.me = None, {}, {}, [], None

    def reset_identity(self) -> None:
        """Passphrase vergessen: Schlüssel, eigene Server/Chats und Nachrichten löschen, damit man neu starten kann."""
        self._rpc("jopml_c_reset")
        self.lock()

    def set_display(self, name: str) -> None:
        try:
            chatfilter.require_clean(name)
        except chatfilter.FilterError as exc:
            raise CommunityError(str(exc)) from None
        self.me = self._rpc("jopml_c_set_display", {"display": name})

    # ------------------------------------------------------------ Server & Schlüssel
    def refresh(self) -> list[dict]:
        """Liste aller Server/Chats laden und die für mich verpackten Schlüssel auspacken."""
        spaces = self._rpc("jopml_c_spaces") or []
        with self._lock:
            self.spaces = spaces
            for s in spaces:
                for w in s.get("wraps", []):
                    k = (s["id"], int(w["epoch"]))
                    if k not in self._keys and self.bundle:
                        try:
                            self._keys[k] = crypto.unwrap(w["wrapped"], self.bundle, s["id"], int(w["epoch"]))
                        except crypto.CryptoError:
                            pass
        return spaces

    def space(self, space_id: str) -> dict | None:
        return next((s for s in self.spaces if s["id"] == space_id), None)

    def has_key(self, space_id: str, epoch: int | None = None) -> bool:
        s = self.space(space_id)
        return bool(s) and (space_id, int(epoch or s["epoch"])) in self._keys

    def _need_bundle(self) -> crypto.KeyBundle:
        if not self.bundle:
            raise CommunityError("Unlock the community with your passphrase first.")
        return self.bundle

    def create_server(self, name: str) -> dict:
        b = self._need_bundle()
        try:
            chatfilter.require_clean(name)
        except chatfilter.FilterError as exc:
            raise CommunityError(str(exc)) from None
        res = self._rpc("jopml_c_create_server", {"name": name})
        key = crypto.new_space_key()
        self._rpc("jopml_c_put_wraps", {"space_id": res["space_id"], "epoch": 1,
                                        "wraps": [{"user_id": self.my_id, "wrapped": crypto.wrap(key, b.enc_pub, res["space_id"], 1)}]})
        self._keys[(res["space_id"], 1)] = key
        return res

    def open_dm(self, handle: str) -> dict:
        b = self._need_bundle()
        peer = self._rpc("jopml_c_lookup", {"handle": handle})
        if not peer:
            raise CommunityError(ERROR_TEXTS["user_not_found"])
        if peer["user_id"] == self.my_id:
            raise CommunityError(ERROR_TEXTS["invalid_target"])
        key = crypto.new_space_key()
        sid = self._new_space_id()            # der Wrap ist an diese ID gebunden, darum wählt sie der Client
        res = self._rpc("jopml_c_open_dm", {"handle": peer["handle"], "space_id": sid, "wraps": {
            "me": crypto.wrap(key, b.enc_pub, sid, 1), "peer": crypto.wrap(key, peer["enc_pub"], sid, 1)}})
        if not res.get("existing"):
            self._keys[(res["space_id"], 1)] = key
        return res

    @staticmethod
    def _new_space_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def create_channel(self, space_id: str, name: str) -> dict:
        try:
            chatfilter.require_clean(name)
        except chatfilter.FilterError as exc:
            raise CommunityError(str(exc)) from None
        return self._rpc("jopml_c_create_channel", {"space_id": space_id, "name": name})

    def delete_channel(self, channel_id: str) -> None:
        self._rpc("jopml_c_delete_channel", {"channel_id": channel_id})

    def delete_space(self, space_id: str) -> None:
        self._rpc("jopml_c_delete_space", {"space_id": space_id})

    def leave(self, space_id: str) -> None:
        self._rpc("jopml_c_leave", {"space_id": space_id})

    # ------------------------------------------------------------ Einladungen
    def create_invite(self, space_id: str, hours: int = 24, max_uses: int = 10) -> dict:
        return self._rpc("jopml_c_create_invite", {"space_id": space_id, "hours": hours, "max_uses": max_uses})

    def redeem_invite(self, code: str) -> dict:
        return self._rpc("jopml_c_redeem_invite", {"code": code})

    def invite_user(self, space_id: str, handle: str) -> None:
        self._rpc("jopml_c_invite_user", {"space_id": space_id, "handle": handle})

    def invite_email(self, space_id: str, email: str) -> None:
        """Lädt das Konto mit dieser E-Mail-Adresse ein. Die Antwort ist immer 'ok' (auch ohne Treffer), damit niemand Adressen ausforschen kann."""
        email = (email or "").strip()
        if "@" not in email or len(email) > 254:
            raise CommunityError(ERROR_TEXTS["invalid_email"])
        self._rpc("jopml_c_invite_email", {"space_id": space_id, "email": email})

    def my_invites(self) -> list[dict]:
        return self._rpc("jopml_c_my_invites") or []

    def answer_invite(self, space_id: str, accept: bool) -> None:
        self._rpc("jopml_c_answer_invite", {"space_id": space_id, "accept": accept})

    # ------------------------------------------------------------ Mitglieder & Moderation
    def members(self, space_id: str, force: bool = True) -> dict[str, dict]:
        if force or space_id not in self._members:
            rows = self._rpc("jopml_c_members", {"space_id": space_id}) or []
            self._members[space_id] = {m["user_id"]: m for m in rows}
        return self._members[space_id]

    def set_role(self, space_id: str, user_id: str, role: str) -> None:
        self._rpc("jopml_c_set_role", {"space_id": space_id, "user_id": user_id, "role": role})

    def kick(self, space_id: str, user_id: str, ban: bool = False) -> None:
        self._rpc("jopml_c_kick", {"space_id": space_id, "user_id": user_id, "ban": ban})

    def housekeeping(self) -> list[str]:
        """Für Owner/Admins: wartende Mitglieder freischalten und nach Austritten den Schlüssel erneuern."""
        done: list[str] = []
        b = self.bundle
        if not b:
            return done
        for s in list(self.spaces):
            if s["kind"] != "server" or s["status"] != "active" or s["role"] not in ("owner", "admin"):
                continue
            sid, epoch = s["id"], int(s["epoch"])
            try:
                if s.get("needs_rotation"):
                    members = [m for m in self.members(sid).values() if m["status"] == "active"]
                    key = crypto.new_space_key()
                    wraps = [{"user_id": m["user_id"], "wrapped": crypto.wrap(key, m["enc_pub"], sid, epoch + 1)} for m in members]
                    self._rpc("jopml_c_rotate", {"space_id": sid, "epoch": epoch + 1, "wraps": wraps})
                    self._keys[(sid, epoch + 1)] = key
                    s["epoch"], s["needs_rotation"] = epoch + 1, False
                    done.append(f"rotate:{sid}")
                elif s.get("pending", 0) and (sid, epoch) in self._keys:
                    pend = [m for m in self.members(sid).values() if m["status"] == "pending"]
                    key = self._keys[(sid, epoch)]
                    wraps = [{"user_id": m["user_id"], "wrapped": crypto.wrap(key, m["enc_pub"], sid, epoch)} for m in pend]
                    if wraps:
                        self._rpc("jopml_c_put_wraps", {"space_id": sid, "epoch": epoch, "wraps": wraps})
                        done.append(f"approve:{sid}")
            except CommunityError:
                continue                # z. B. zwei Admins gleichzeitig -> beim nächsten Durchlauf erneut
        return done

    # ------------------------------------------------------------ Nachrichten
    def send(self, space_id: str, channel_id: str, text: str, reply: dict | None = None) -> dict:
        b = self._need_bundle()
        text = text.strip()
        if not text:
            raise CommunityError("Please type a message.")
        if len(text) > MAX_TEXT:
            raise CommunityError(tr("Messages can have at most {n} characters.", n=MAX_TEXT))
        try:
            chatfilter.require_clean(text)
        except chatfilter.FilterError as exc:
            raise CommunityError(str(exc)) from None
        s = self.space(space_id)
        if not s:
            raise CommunityError(ERROR_TEXTS["not_found"])
        epoch = int(s["epoch"])
        key = self._keys.get((space_id, epoch))
        if key is None:
            raise CommunityError(ERROR_TEXTS["no_key"])
        body, sig = crypto.encrypt_message(key, b, space_id, channel_id, epoch, self.my_id, text, reply=reply)
        return self._rpc("jopml_c_send", {"channel_id": channel_id, "epoch": epoch, "body": body, "sig": sig})

    def _sign_pub(self, space_id: str, user_id: str) -> str | None:
        if user_id == self.my_id:
            return self.me.get("sign_pub")
        s = self.space(space_id)
        if s and s.get("peer") and s["peer"]["user_id"] == user_id:
            return s["peer"]["sign_pub"]
        m = self._members.get(space_id, {}).get(user_id)
        if m is None:
            try:
                m = self.members(space_id).get(user_id)
            except CommunityError:
                m = None
        return m["sign_pub"] if m else None

    def fetch(self, space_id: str, channel_id: str, after: int | None = None, before: int | None = None, limit: int = 50) -> list[Message]:
        rows = self._rpc("jopml_c_fetch", {"channel_id": channel_id, "after": after, "before": before, "limit": limit}) or []
        out: list[Message] = []
        for r in rows:
            m = Message(id=int(r["id"]), sender_id=r.get("sender_id") or "", handle=r.get("handle") or "?",
                        name=r.get("display_name") or r.get("handle") or "?", text="", created_at=r.get("created_at", ""),
                        mine=r.get("sender_id") == self.my_id, epoch=int(r["epoch"]), body=r["body"], sig=r["sig"])
            key = self._keys.get((space_id, m.epoch))
            if key is None:
                m.ok, m.text = False, tr("[encrypted – you do not have the key for this period]")
            else:
                try:
                    d = crypto.decrypt_message(key, space_id, channel_id, m.epoch, m.sender_id, m.body)
                    m.text = d["t"]
                    r = d.get("r")
                    if isinstance(r, dict) and isinstance(r.get("id"), int):
                        m.reply = {"id": r["id"], "n": chatfilter.mask(str(r.get("n", "")))[0], "s": chatfilter.mask(str(r.get("s", "")))[0]}
                    pub = self._sign_pub(space_id, m.sender_id)
                    m.verified = bool(pub) and crypto.verify_message(pub, channel_id, m.epoch, m.sender_id, m.body, m.sig)
                    m.text, m.filtered = chatfilter.mask(m.text)       # Empfänger-Filter (falls der Absender ihn umgangen hat)
                except crypto.CryptoError:
                    m.ok, m.text = False, tr("[message could not be decrypted]")
            out.append(m)
        return out

    def set_slowmode(self, space_id: str, seconds: int) -> None:
        self._rpc("jopml_c_set_slowmode", {"space_id": space_id, "seconds": int(seconds)})

    def mute(self, space_id: str, user_id: str, minutes: int) -> None:
        """minutes = 0 hebt die Stummschaltung auf."""
        self._rpc("jopml_c_mute", {"space_id": space_id, "user_id": user_id, "minutes": int(minutes)})

    def delete_message(self, message_id: int) -> None:
        self._rpc("jopml_c_delete_message", {"message_id": message_id})

    def report_message(self, space_id: str, msg: Message, reason: str) -> None:
        """Meldung mit Klartext + Signatur als Beleg. Der Melder gibt den Inhalt damit freiwillig weiter."""
        evidence = json.dumps({"text": msg.text if not msg.filtered else "", "body": msg.body, "sig": msg.sig, "epoch": msg.epoch,
                               "sender": msg.sender_id}, ensure_ascii=False)
        self._rpc("jopml_c_report", {"kind": "message", "space_id": space_id, "ref_id": str(msg.id), "handle": msg.handle,
                                     "reason": reason, "evidence": evidence, "sig": msg.sig})

    def report_server(self, space_id: str, reason: str) -> None:
        self._rpc("jopml_c_report", {"kind": "server", "space_id": space_id, "reason": reason})

    # ------------------------------------------------------------ Sicherheitsnummer
    def safety_number(self, space_id: str) -> str | None:
        s = self.space(space_id)
        if not s or not s.get("peer") or not self.me:
            return None
        return crypto.pair_fingerprint((self.me["enc_pub"], self.me["sign_pub"]), (s["peer"]["enc_pub"], s["peer"]["sign_pub"]))

    def my_fingerprint(self) -> str:
        return crypto.fingerprint(self.me["enc_pub"], self.me["sign_pub"])

    # ------------------------------------------------------------ Admin
    def admin_reports(self) -> list[dict]:
        return self._rpc("jopml_c_admin_reports") or []

    def admin_resolve(self, report_id: int, action: str) -> None:
        self._rpc("jopml_c_admin_resolve", {"id": report_id, "action": action})
