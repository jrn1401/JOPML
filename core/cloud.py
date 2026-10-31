"""Supabase-Client (nur Standardbibliothek): Konto, Google-Anmeldung, verschlüsseltes Profil, KI-Funktion.

Server-Gegenstück: supabase/migrations/*.sql (Tabellen + Funktionen) und supabase/functions/jopml-ai.
Der Client kennt nur die öffentliche Project-URL und den publishable key. Alles Sensible (Schlüssel für die
Verschlüsselung, Gemini-Key, Google-Client-Secret) liegt ausschließlich auf dem Server.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from core import oauth_loopback
from core import net
from core.version import (AI_FUNCTION, APP_ID, APP_VERSION, OAUTH_LOOPBACK_PORT, PSEUDO_EMAIL_TEMPLATE,
                          SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL)


CHAT_FUNCTION = "jopml-chat"


class CloudError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden. `code` ist ein kurzer Serverschlüssel (z. B. "limit_tokens"), falls vorhanden."""

    def __init__(self, msg="", code=None):
        super().__init__(msg)
        self.code = code


# Admin-Meldungen (nur im Modul "Publish" sichtbar, deshalb nur Deutsch)
ADMIN_MSG_FORBIDDEN = "Upload nicht erlaubt: Dieses Konto ist kein Admin-Konto."


def json_bytes(obj) -> bytes:
    return json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class CloudClient:
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_PUBLISHABLE_KEY):
        self.url = (url or "").rstrip("/")
        self.key = key or ""
        self.session: dict | None = None      # access_token, refresh_token, expires_at
        self.on_session = None                # Rückruf nach jeder neuen Sitzung/Token-Erneuerung (speichert den rotierten Token)

    @property
    def configured(self) -> bool:
        return self.url.startswith("https://") or self.url.startswith("http://127.0.0.1")

    # ---------- HTTP ----------
    def _request(self, method: str, path: str, body=None, token: str | None = None, timeout: float = 20):
        headers = {"apikey": self.key, "Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        headers["Authorization"] = f"Bearer {token or self.key}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with net.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(2_000_000).decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode("utf-8"))
            except Exception:
                err = {}
            msg = err.get("error_description") or err.get("msg") or err.get("message") or err.get("error") or ""
            code = err.get("code") if isinstance(err.get("code"), str) else None
            raise CloudError(self._friendly(str(msg), exc.code), code) from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise CloudError("Unexpected answer from the server.") from None

    @staticmethod
    def _friendly(msg: str, status: int) -> str:
        low = msg.lower()
        if "invalid login" in low or "invalid_grant" in low or "invalid credentials" in low:
            return "Wrong username or password."
        if "already registered" in low or "already been registered" in low or "user_already_exists" in low:
            return "This username is already taken."
        if "username_taken" in low or "handle_taken" in low:
            return "This username is already taken."
        if "name_not_allowed" in low:
            return "This name is not allowed. Please choose another one."
        if "password" in low and ("short" in low or "least" in low or "weak" in low):
            return "The password is too short or too weak."
        if status == 429 or "rate limit" in low:
            return "Too many attempts. Please wait a moment."
        return msg or f"Server error ({status})."

    # ---------- Sitzung ----------
    def _set_session(self, data: dict) -> dict:
        if not isinstance(data, dict) or not data.get("access_token"):
            raise CloudError("The server did not return a session. Is 'Confirm email' still enabled in the Supabase "
                             "Auth settings? It must be turned off (see supabase/config.toml).")
        expires = data.get("expires_at") or (int(time.time()) + int(data.get("expires_in", 3600)))
        self.session = {"access_token": data["access_token"], "refresh_token": data.get("refresh_token", ""),
                        "expires_at": int(expires)}
        if self.on_session:
            try:
                self.on_session(self.session)
            except Exception:
                pass
        return self.session

    def token(self) -> str:
        if not self.session:
            raise CloudError("Not signed in.")
        if self.session["expires_at"] - time.time() < 60 and self.session.get("refresh_token"):
            self.refresh(self.session["refresh_token"])
        return self.session["access_token"]

    def refresh(self, refresh_token: str) -> dict:
        data = self._request("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token})
        return self._set_session(data)

    def sign_out(self) -> None:
        if self.session:
            try:
                self._request("POST", "/auth/v1/logout", {}, token=self.session["access_token"], timeout=8)
            except CloudError:
                pass
        self.session = None

    # ---------- Anmelden / Registrieren ----------
    @staticmethod
    def pseudo_email(username: str) -> str:
        return PSEUDO_EMAIL_TEMPLATE.format(u=username.strip().lower())

    def sign_up(self, username: str, password: str) -> dict:
        data = self._request("POST", "/auth/v1/signup", {"email": self.pseudo_email(username), "password": password})
        return self._set_session(data)

    def sign_in(self, username: str, password: str) -> dict:
        data = self._request("POST", "/auth/v1/token?grant_type=password",
                             {"email": self.pseudo_email(username), "password": password})
        return self._set_session(data)

    def sign_in_google(self, cancel: threading.Event | None = None) -> dict:
        """Google über Supabase Auth (PKCE). Der Browser öffnet Supabase -> Google -> zurück auf 127.0.0.1."""
        verifier = secrets.token_urlsafe(64)
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())

        def build(redirect: str) -> str:
            return f"{self.url}/auth/v1/authorize?" + urllib.parse.urlencode({
                "provider": "google", "redirect_to": redirect,
                "code_challenge": challenge, "code_challenge_method": "s256"})

        try:
            got = oauth_loopback.capture_redirect(build, port=OAUTH_LOOPBACK_PORT, cancel=cancel)
        except oauth_loopback.LoopbackError as exc:
            raise CloudError(str(exc)) from None
        if "error" in got:
            raise CloudError("Sign-in cancelled." if got.get("error") == "access_denied"
                             else f"Google sign-in failed: {got.get('error_description', got['error'])}")
        data = self._request("POST", "/auth/v1/token?grant_type=pkce",
                             {"auth_code": got["code"], "code_verifier": verifier})
        return self._set_session(data)

    # ---------- Profil (verschlüsselt in der Datenbank, nur über RPC) ----------
    def rpc(self, name: str, args: dict | None = None):
        return self._request("POST", f"/rest/v1/rpc/{name}", args or {}, token=self.token())

    def ensure_profile(self, username: str | None, display_name: str | None) -> dict:
        prof = self.rpc("jopml_ensure_profile", {"p_username": username, "p_display_name": display_name})
        if not isinstance(prof, dict):
            raise CloudError("Profile could not be created.")
        return prof

    def get_profile(self) -> dict | None:
        return self.rpc("jopml_get_profile")

    def save_profile(self, display_name: str | None = None, email: str | None = None, settings: dict | None = None) -> dict:
        """Sendet nur die übergebenen Felder; der Server mischt sie in das verschlüsselte Profil."""
        p = {k: v for k, v in (("display_name", display_name), ("email", email), ("settings", settings)) if v is not None}
        return self.rpc("jopml_save_profile", {"p": p})

    def delete_account(self) -> None:
        self.rpc("jopml_delete_account")
        self.session = None

    # ---------- Veröffentlichen (nur Admin; der Server prüft das über Storage-Regeln) ----------
    def is_admin(self) -> bool:
        try:
            return self.rpc("jopml_is_admin") is True
        except CloudError:
            return False

    def public_release_url(self, name: str) -> str:
        return f"{self.url}/storage/v1/object/public/releases/{urllib.parse.quote(name)}"

    def read_manifest(self, name: str = "version.json") -> dict | None:
        try:
            req = urllib.request.Request(self.public_release_url(name), headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
            with net.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read(1_000_000).decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def upload_release(self, name: str, data: bytes, content_type: str, cache_seconds: int = 3600) -> None:
        """Lädt eine Datei in den Bucket 'releases' (ersetzt eine vorhandene gleichen Namens)."""
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.token()}", "Content-Type": content_type,
                   "x-upsert": "true", "cache-control": f"max-age={int(cache_seconds)}",
                   "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        req = urllib.request.Request(f"{self.url}/storage/v1/object/releases/{urllib.parse.quote(name)}",
                                     data=data, method="POST", headers=headers)
        try:
            with net.urlopen(req, timeout=600) as resp:
                resp.read(10_000)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                raise CloudError(ADMIN_MSG_FORBIDDEN) from None
            raise CloudError(f"Upload fehlgeschlagen (Status {exc.code}).") from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None

    def _storage(self, method: str, path: str, body=None, timeout: float = 30):
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.token()}", "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(f"{self.url}/storage/v1/{path}", data=data, method=method, headers=headers)
        try:
            with net.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read(5_000_000).decode("utf-8") or "null")
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                raise CloudError(ADMIN_MSG_FORBIDDEN) from None
            raise CloudError(f"Anfrage fehlgeschlagen (Status {exc.code}).") from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None

    def list_releases(self) -> list[dict]:
        """Alle Dateien im Bucket 'releases' (nur Admin)."""
        res = self._storage("POST", "object/list/releases", {"prefix": "", "limit": 500, "offset": 0,
                                                             "sortBy": {"column": "created_at", "order": "desc"}})
        return res if isinstance(res, list) else []

    def delete_release(self, name: str) -> None:
        self._storage("DELETE", "object/releases", {"prefixes": [name]})

    def release_sha256(self, name: str) -> str:
        """Prüfsumme einer hochgeladenen Datei (wird gestreamt, die Datei liegt nie ganz im Speicher)."""
        h = hashlib.sha256()
        req = urllib.request.Request(self.public_release_url(name) + f"?t={int(time.time())}", headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
        try:
            with net.urlopen(req, timeout=120) as resp:
                for chunk in iter(lambda: resp.read(1024 * 1024), b""):
                    h.update(chunk)
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"Datei konnte nicht gelesen werden: {exc}") from None
        return h.hexdigest()

    # ---------- KI (Supabase Edge Function -> Gemini) ----------
    def ai_stream(self, messages: list[dict], lang: str, on_text) -> str:
        """Hilfe-Antwort Stück für Stück (on_text(bisheriger_text) wird mehrfach aufgerufen). Gibt den ganzen Text zurück.
        Wirft CloudError; ein älterer Server ohne Streaming antwortet mit JSON, das hier ebenfalls verstanden wird."""
        import codecs
        from core import handbook
        body = {"kind": "help", "messages": messages[-10:], "lang": lang, "version": APP_VERSION, "handbook": handbook.text(), "stream": True}
        headers = {"apikey": self.key, "Content-Type": "application/json", "Authorization": f"Bearer {self.token()}",
                   "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        req = urllib.request.Request(f"{self.url}/functions/v1/{AI_FUNCTION}", data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
        try:
            with net.urlopen(req, timeout=60) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype:
                    data = json.loads(resp.read(1_000_000).decode("utf-8"))
                    reply = data.get("reply") if isinstance(data, dict) else None
                    if not isinstance(reply, str) or not reply.strip():
                        raise CloudError("Empty answer from the AI.")
                    on_text(reply.strip())
                    return reply.strip()
                dec, text = codecs.getincrementaldecoder("utf-8")("replace"), ""
                while True:
                    chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(512)
                    if not chunk:
                        break
                    text += dec.decode(chunk)
                    on_text(text)
                text += dec.decode(b"", final=True)
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode("utf-8")).get("error", "")
            except Exception:
                err = ""
            raise CloudError(self._friendly(str(err), exc.code)) from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None
        if not text.strip():
            raise CloudError("Empty answer from the AI.")
        return text.strip()

    def ai(self, kind: str, messages: list[dict], lang: str = "en") -> str:
        from core import handbook
        body = {"kind": kind, "messages": messages[-10:], "lang": lang, "version": APP_VERSION}
        if kind == "help":
            body["handbook"] = handbook.text()       # die KI kennt so immer genau die Version des Nutzers
        data = self._request("POST", f"/functions/v1/{AI_FUNCTION}", body, token=self.token(), timeout=60)
        reply = data.get("reply") if isinstance(data, dict) else None
        if not isinstance(reply, str) or not reply.strip():
            raise CloudError((data or {}).get("error", "Empty answer from the AI.") if isinstance(data, dict) else "Empty answer.")
        return reply.strip()

    # ---------- KI-Chat (Edge Function jopml-chat: Gemini und Groq) ----------
    def _chat_call(self, body: dict, timeout: float = 75) -> dict:
        data = self._request("POST", f"/functions/v1/{CHAT_FUNCTION}", body, token=self.token(), timeout=timeout)
        if not isinstance(data, dict):
            raise CloudError("Unexpected answer from the server.")
        return data

    def chat_status(self) -> dict:
        """{"providers": [...], "models": {anbieter: standardmodell}, "policy": {max_answer, daily_tokens, tokens_used, daily_requests}}"""
        return self._chat_call({"kind": "status"}, 25)

    def chat_models(self) -> dict:
        """{"providers": [...], "models": {anbieter: [modelle]}, "defaults": {...}}"""
        return self._chat_call({"kind": "models"}, 30)

    def chat(self, provider: str, messages: list[dict], lang: str, context: str = "", model: str | None = None) -> dict:
        body = {"provider": provider, "messages": messages, "lang": lang, "context": context}
        if model:
            body["model"] = model
        data = self._chat_call(body)
        if not isinstance(data.get("reply"), str) or not data["reply"].strip():
            raise CloudError(str(data.get("error") or "Empty answer from the AI."), data.get("code"))
        return data

    def analyze_errors(self, text: str, lang: str = "de", provider: str = "gemini") -> dict:
        """Nur Admins: lässt die KI zusammengefasste Fehlergruppen auswerten."""
        return self._chat_call({"kind": "analyze", "provider": provider, "lang": lang, "context": text[:12000],
                                "messages": [{"role": "user", "content": "Analyse the error groups."}]}, 90)

    def chat_stream(self, provider: str, messages: list[dict], lang: str, context: str = "", model: str | None = None,
                    on_text=None, cancel=None, on_start=None, fallback: bool = True) -> dict:
        """Chat-Antwort Stück für Stück. on_text(bisheriger_Text) wird mehrfach gerufen, `cancel` ist ein threading.Event (gesetzt = abbrechen),
        on_start(provider, model, fallback_from) kommt, sobald der Server antwortet. Ergebnis: {"reply", "provider", "model", "tokens",
        "fallback_from", "fallback_reason", "cancelled"}. Wirft CloudError (mit .code)."""
        import codecs
        body = {"provider": provider, "messages": messages, "lang": lang, "context": context, "stream": True, "fallback": bool(fallback)}
        if model:
            body["model"] = model
        headers = {"apikey": self.key, "Content-Type": "application/json", "Authorization": f"Bearer {self.token()}",
                   "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        req = urllib.request.Request(f"{self.url}/functions/v1/{CHAT_FUNCTION}", data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
        mark, text, cancelled = "\x1eMETA", "", False
        try:
            with net.urlopen(req, timeout=90) as resp:
                if on_start:
                    on_start(resp.headers.get("X-Provider") or provider, resp.headers.get("X-Model") or model or "", resp.headers.get("X-Fallback-From") or "")
                dec = codecs.getincrementaldecoder("utf-8")("replace")
                while True:
                    if cancel is not None and cancel.is_set():
                        cancelled = True
                        break
                    chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(512)
                    if not chunk:
                        break
                    text += dec.decode(chunk)
                    if on_text:
                        on_text(text.split(mark, 1)[0])
                if not cancelled:
                    text += dec.decode(b"", final=True)
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode("utf-8"))
            except Exception:
                err = {}
            raise CloudError(self._friendly(str(err.get("error", "")), exc.code), err.get("code") if isinstance(err.get("code"), str) else None) from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None
        reply, _, meta_raw = text.partition(mark)
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
        except ValueError:
            meta = {}
        reply = reply.strip()
        if not reply and not cancelled:
            raise CloudError("Empty answer from the AI.", "empty")
        return {"reply": reply, "provider": meta.get("provider") or provider, "model": meta.get("model") or model or "", "tokens": int(meta.get("tokens") or 0),
                "fallback_from": meta.get("fallback_from"), "fallback_reason": meta.get("fallback_reason"), "cancelled": cancelled}
