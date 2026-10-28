"""Ende-zu-Ende-Verschlüsselung für die Community (Bibliothek: `cryptography`).

Bausteine
  * Jeder Nutzer hat zwei Schlüsselpaare: X25519 (Schlüsselaustausch) und Ed25519 (Signatur). Die privaten Teile verlassen das
    Gerät nur passwortgeschützt (scrypt + AES-256-GCM) – der Server speichert diesen Behälter, kann ihn aber nicht öffnen.
  * Jeder Server / jede DM hat einen zufälligen 256-Bit-Gruppenschlüssel pro "Epoche". Er wird für jedes Mitglied einzeln mit
    dessen öffentlichem X25519-Schlüssel verpackt (ECIES: Ephemeral-DH + HKDF-SHA256 + AES-GCM).
  * Kanalschlüssel = HKDF(Gruppenschlüssel, Kanal-ID). Nachrichten: AES-256-GCM, zufällige Nonce, Kontext (Server, Kanal,
    Epoche, Absender) als zusätzliche authentifizierte Daten. Zusätzlich signiert der Absender (Ed25519), damit der Server
    keine Nachrichten unter fremdem Namen einschleusen kann.
  * Wechselt die Mitgliederliste durch Austritt/Rauswurf, wird ein neuer Gruppenschlüssel (neue Epoche) verteilt.

Grenzen (ehrlich): Der Server liefert die öffentlichen Schlüssel der Mitglieder. Wer ihn kontrolliert, könnte einen falschen
Schlüssel unterschieben (klassisches Problem). Dagegen hilft der Vergleich der Sicherheitsnummern (fingerprint) über einen
anderen Kanal. Metadaten (wer schreibt wann in welchen Kanal) sieht der Server.
"""
import base64
import hashlib
import json
import os
import time

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SCRYPT_N = 2 ** 15
NONCE = 12
RAW = serialization.Encoding.Raw
RAW_PUB = serialization.PublicFormat.Raw
RAW_PRIV = serialization.PrivateFormat.Raw
NO_ENC = serialization.NoEncryption()


class CryptoError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden."""


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def unb64(text: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(text.encode())
    except Exception:
        raise CryptoError("Damaged data.") from None


# ------------------------------------------------------------------ Schlüsselpaare
class KeyBundle:
    def __init__(self, enc: x25519.X25519PrivateKey, sign: ed25519.Ed25519PrivateKey):
        self.enc, self.sign = enc, sign

    @classmethod
    def generate(cls) -> "KeyBundle":
        return cls(x25519.X25519PrivateKey.generate(), ed25519.Ed25519PrivateKey.generate())

    @property
    def enc_pub(self) -> str:
        return b64(self.enc.public_key().public_bytes(RAW, RAW_PUB))

    @property
    def sign_pub(self) -> str:
        return b64(self.sign.public_key().public_bytes(RAW, RAW_PUB))

    def to_bytes(self) -> bytes:
        return self.enc.private_bytes(RAW, RAW_PRIV, NO_ENC) + self.sign.private_bytes(RAW, RAW_PRIV, NO_ENC)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "KeyBundle":
        if len(raw) != 64:
            raise CryptoError("Damaged data.")
        return cls(x25519.X25519PrivateKey.from_private_bytes(raw[:32]), ed25519.Ed25519PrivateKey.from_private_bytes(raw[32:]))


def seal_bundle(bundle: KeyBundle, passphrase: str) -> str:
    """Private Schlüssel mit Passphrase verschlüsseln (für die Ablage auf dem Server)."""
    salt, nonce = os.urandom(16), os.urandom(NONCE)
    key = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=8, p=1).derive(passphrase.encode("utf-8"))
    ct = AESGCM(key).encrypt(nonce, bundle.to_bytes(), b"jopml-keys-v1")
    return json.dumps({"v": 1, "n": SCRYPT_N, "salt": b64(salt), "nonce": b64(nonce), "ct": b64(ct)})


def open_bundle(blob: str, passphrase: str) -> KeyBundle:
    try:
        d = json.loads(blob)
        n = int(d["n"])
        if n > 2 ** 17 or n < 2 ** 12:               # kein Missbrauch als Speicher-/Rechenbombe
            raise ValueError
        key = Scrypt(salt=unb64(d["salt"]), length=32, n=n, r=8, p=1).derive(passphrase.encode("utf-8"))
        return KeyBundle.from_bytes(AESGCM(key).decrypt(unb64(d["nonce"]), unb64(d["ct"]), b"jopml-keys-v1"))
    except InvalidTag:
        raise CryptoError("Wrong passphrase.") from None
    except (KeyError, ValueError, TypeError):
        raise CryptoError("Damaged data.") from None


# ------------------------------------------------------------------ Gruppenschlüssel verpacken
def new_space_key() -> bytes:
    return os.urandom(32)


def _wrap_key(shared: bytes, eph_pub: bytes, rcpt_pub: bytes, ctx: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_pub + rcpt_pub, info=b"jopml-wrap-v1|" + ctx).derive(shared)


def wrap(space_key: bytes, recipient_enc_pub: str, space_id: str, epoch: int) -> str:
    rcpt = x25519.X25519PublicKey.from_public_bytes(unb64(recipient_enc_pub))
    eph = x25519.X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(RAW, RAW_PUB)
    ctx = f"{space_id}|{epoch}".encode()
    key = _wrap_key(eph.exchange(rcpt), eph_pub, unb64(recipient_enc_pub), ctx)
    nonce = os.urandom(NONCE)
    return b64(eph_pub + nonce + AESGCM(key).encrypt(nonce, space_key, ctx))


def unwrap(wrapped: str, bundle: KeyBundle, space_id: str, epoch: int) -> bytes:
    raw = unb64(wrapped)
    if len(raw) < 32 + NONCE + 16:
        raise CryptoError("Damaged data.")
    eph_pub, nonce, ct = raw[:32], raw[32:32 + NONCE], raw[32 + NONCE:]
    ctx = f"{space_id}|{epoch}".encode()
    try:
        shared = bundle.enc.exchange(x25519.X25519PublicKey.from_public_bytes(eph_pub))
        key = _wrap_key(shared, eph_pub, unb64(bundle.enc_pub), ctx)
        return AESGCM(key).decrypt(nonce, ct, ctx)
    except (InvalidTag, ValueError):
        raise CryptoError("This key was not meant for you.") from None


# ------------------------------------------------------------------ Nachrichten
def channel_key(space_key: bytes, channel_id: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"jopml-channel-v1|" + channel_id.encode()).derive(space_key)


def _aad(space_id, channel_id, epoch, sender_id) -> bytes:
    return f"{space_id}|{channel_id}|{epoch}|{sender_id}".encode()


def encrypt_message(space_key: bytes, bundle: KeyBundle, space_id: str, channel_id: str, epoch: int, sender_id: str,
                    text: str, ts: float | None = None, reply: dict | None = None) -> tuple[str, str]:
    """Gibt (body, signatur) zurück. body = base64(nonce + AES-GCM(JSON)). `reply` (id, Name, Auszug) ist Teil des verschlüsselten Inhalts."""
    data = {"t": text, "ts": int(ts if ts is not None else time.time())}
    if reply:
        data["r"] = {"id": int(reply["id"]), "n": str(reply.get("n", ""))[:40], "s": str(reply.get("s", ""))[:80]}
    plain = json.dumps(data, ensure_ascii=False).encode("utf-8")
    nonce = os.urandom(NONCE)
    ct = AESGCM(channel_key(space_key, channel_id)).encrypt(nonce, plain, _aad(space_id, channel_id, epoch, sender_id))
    body = b64(nonce + ct)
    sig = b64(bundle.sign.sign(f"{channel_id}|{epoch}|{sender_id}|".encode() + body.encode()))
    return body, sig


def decrypt_message(space_key: bytes, space_id: str, channel_id: str, epoch: int, sender_id: str, body: str) -> dict:
    raw = unb64(body)
    if len(raw) < NONCE + 16:
        raise CryptoError("Damaged data.")
    try:
        plain = AESGCM(channel_key(space_key, channel_id)).decrypt(raw[:NONCE], raw[NONCE:], _aad(space_id, channel_id, epoch, sender_id))
        d = json.loads(plain.decode("utf-8"))
        if not isinstance(d, dict) or not isinstance(d.get("t"), str):
            raise ValueError
        return d
    except (InvalidTag, ValueError):
        raise CryptoError("Message could not be decrypted.") from None


def verify_message(sign_pub: str, channel_id: str, epoch: int, sender_id: str, body: str, sig: str) -> bool:
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(unb64(sign_pub)).verify(
            unb64(sig), f"{channel_id}|{epoch}|{sender_id}|".encode() + body.encode())
        return True
    except (InvalidSignature, ValueError, CryptoError):
        return False


# ------------------------------------------------------------------ Sicherheitsnummer
def fingerprint(enc_pub: str, sign_pub: str) -> str:
    h = hashlib.sha256(unb64(enc_pub) + unb64(sign_pub)).hexdigest()[:40].upper()
    return " ".join(h[i:i + 5] for i in range(0, 40, 5))


def pair_fingerprint(a: tuple[str, str], b: tuple[str, str]) -> str:
    """Gemeinsame Sicherheitsnummer zweier Personen – beide sehen dieselbe Zahl."""
    x, y = sorted([fingerprint(*a), fingerprint(*b)])
    h = hashlib.sha256((x + "|" + y).encode()).hexdigest()[:30].upper()
    return " ".join(h[i:i + 5] for i in range(0, 30, 5))
