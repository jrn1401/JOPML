"""Kleine lokale Ablage für ein Geheimnis (z. B. die Community-Passphrase), damit man "angemeldet bleiben" kann.
Windows: mit DPAPI an das Windows-Konto gebunden. Andere Systeme: nur mit einem lokalen Zufallsschlüssel verschleiert
(Dateirechte 600) – das schützt nicht vor jemandem, der Zugriff auf dein Benutzerkonto hat."""
import base64
import ctypes
import os
import sys

from core import config

_KEYFILE = "secret.key"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inb = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    args = (ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(out)) if protect else \
        (ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(out))
    if not fn(*args):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _local_key() -> bytes:
    p = config.app_dir() / _KEYFILE
    if p.exists():
        return p.read_bytes()
    key = os.urandom(32)
    p.write_bytes(key)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return key


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def protect(text: str) -> str:
    raw = text.encode("utf-8")
    blob = _dpapi(raw, True) if sys.platform == "win32" else b"x" + _xor(raw, _local_key())
    return base64.b64encode(blob).decode("ascii")


def unprotect(token: str) -> str:
    blob = base64.b64decode(token.encode("ascii"))
    raw = _dpapi(blob, False) if sys.platform == "win32" else _xor(blob[1:], _local_key())
    return raw.decode("utf-8")
