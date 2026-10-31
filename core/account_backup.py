"""Verschlüsselte Sicherung eines LOKALEN Kontos (Datei mit Passphrase). Kein GUI-Import.

Zweck: Konto (Passwort-Prüfwert, Anzeigename, optional 2FA) auf einen anderen PC mitnehmen oder nach einer Neuinstallation wiederherstellen.
Wichtig: Das Passwort selbst wird NICHT gespeichert und kann daraus nicht abgelesen werden. Wer das Passwort vergisst, bekommt es auch
mit der Sicherung nicht zurück (Sicherheitsregel: es gibt kein "Passwort vergessen").
Verschlüsselung: AES-256-GCM, Schlüssel aus der Passphrase per scrypt (zufälliges Salz je Datei).
"""
import base64
import json
import os
import time

from core import accounts
from core.i18n import tr

FORMAT = "jopml-account-backup"
MIN_PASSPHRASE = 10
_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}


class BackupError(ValueError):
    pass


class BackupExists(BackupError):
    """Das Konto gibt es auf diesem Computer schon (nur mit overwrite=True ersetzen)."""


def _key(passphrase: str, salt: bytes, params: dict) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return Scrypt(salt=salt, length=32, n=params["n"], r=params["r"], p=params["p"]).derive(passphrase.encode("utf-8"))


def export_account(store: "accounts.AccountStore", username: str, password: str, passphrase: str) -> str:
    """Gibt den Dateiinhalt (JSON-Text) zurück. Verlangt das Kontopasswort, damit nicht jeder an der offenen Sitzung ein Backup ziehen kann."""
    u = store._user(username)
    if not u["pw"] or not accounts._check_password(password or "", u["pw"]):
        raise BackupError(tr("The password is wrong."))
    if len(passphrase or "") < MIN_PASSPHRASE:
        raise BackupError(tr("The backup passphrase needs at least {n} characters.", n=MIN_PASSPHRASE))
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, nonce = os.urandom(16), os.urandom(12)
    record = {k: u[k] for k in ("username", "display_name", "email", "pw", "totp_secret", "totp_enabled", "created")}
    plain = json.dumps({"saved": int(time.time()), "user": record}, ensure_ascii=False).encode("utf-8")
    blob = AESGCM(_key(passphrase, salt, _SCRYPT)).encrypt(nonce, plain, FORMAT.encode())
    b = lambda x: base64.b64encode(x).decode()  # noqa: E731
    return json.dumps({"format": FORMAT, "version": 1, "kdf": "scrypt", **_SCRYPT, "salt": b(salt), "nonce": b(nonce), "data": b(blob)})


def _read(text: str, passphrase: str) -> dict:
    try:
        d = json.loads(text)
        if d.get("format") != FORMAT or d.get("kdf") != "scrypt":
            raise ValueError
        params = {"n": int(d["n"]), "r": int(d["r"]), "p": int(d["p"])}
        if not (2 ** 14 <= params["n"] <= 2 ** 20 and 1 <= params["r"] <= 16 and 1 <= params["p"] <= 4):
            raise ValueError
        salt, nonce, blob = (base64.b64decode(d[k]) for k in ("salt", "nonce", "data"))
    except (ValueError, KeyError, TypeError):
        raise BackupError(tr("This is not a JOPML account backup."))
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        plain = AESGCM(_key(passphrase or "", salt, params)).decrypt(nonce, blob, FORMAT.encode())
        user = json.loads(plain.decode("utf-8"))["user"]
    except (InvalidTag, ValueError, KeyError):
        raise BackupError(tr("Wrong passphrase or damaged file."))
    need = {"username", "display_name", "email", "pw", "totp_secret", "totp_enabled", "created"}
    if not isinstance(user, dict) or not need <= set(user) or not accounts.USERNAME_RE.match(str(user["username"])) \
            or not isinstance(user["pw"], dict) or not {"salt", "hash", "iter"} <= set(user["pw"]):
        raise BackupError(tr("This is not a JOPML account backup."))
    return user


def restore_account(store: "accounts.AccountStore", text: str, passphrase: str, overwrite: bool = False) -> str:
    """Stellt das Konto wieder her. Gibt den Benutzernamen zurück. Existiert er schon, wird er nur mit overwrite=True ersetzt."""
    user = _read(text, passphrase)
    name = accounts._norm_user(user["username"])
    if name in store.users and not overwrite:
        raise BackupExists(tr("An account with this username already exists on this computer."))
    if not isinstance(user["pw"]["iter"], int) or not 1000 <= user["pw"]["iter"] <= 5_000_000:
        raise BackupError(tr("This is not a JOPML account backup."))
    email = str(user["email"] or "")
    if email and store._email_taken(email, except_user=name):
        email = ""                                            # E-Mail gehört schon einem anderen Konto
    rec = store._new_record(name, str(user["display_name"])[:40] or name, email, user["pw"])
    rec["totp_secret"] = user["totp_secret"] if user["totp_enabled"] else None
    rec["totp_enabled"] = bool(user["totp_enabled"] and user["totp_secret"])
    rec["created"] = int(user["created"]) if isinstance(user["created"], (int, float)) else rec["created"]
    store.users[name] = rec
    store._save()
    return name
