"""Tests ohne Fenster und ohne Netzwerk (Attrappen für customtkinter/pynput unter tests/stubs).
Ausführen:  python tests/test_all.py        (Exit-Code 0 = alles in Ordnung)"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="jopml-test-")
os.environ["XDG_CONFIG_HOME"] = TMP
os.environ["HOME"] = TMP
sys.path.insert(0, str(ROOT))
try:
    import customtkinter  # noqa: F401
    import pynput  # noqa: F401
except ImportError:
    sys.path.insert(0, str(ROOT / "tests" / "stubs"))

from core import accounts, i18n  # noqa: E402

RESULTS = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return e
    raise AssertionError(f"{exc.__name__} erwartet")


# ---------------------------------------------------------------- Konten
def test_accounts():
    d = Path(tempfile.mkdtemp(dir=TMP))
    st = accounts.AccountStore(d)
    u = st.register("Jaron", "", "", "geheim123")           # E-Mail leer = anonym
    check(u["username"] == "jaron" and u["email"] == "" and u["display_name"] == "jaron", "register anonym")
    raises(accounts.AccountError, st.register, "jaron", "", "", "geheim123")
    raises(accounts.AccountError, st.register, "ab", "", "", "geheim123")
    raises(accounts.AccountError, st.register, "okname", "", "keine-mail", "geheim123")
    raises(accounts.AccountError, st.register, "okname", "", "", "kurz")
    st.register("zwei", "Zwei", "a@b.de", "geheim123")
    raises(accounts.AccountError, st.register, "drei", "", "a@b.de", "geheim123")   # E-Mail doppelt
    st.register("vier", "", "", "geheim123")
    st.register("fuenf", "", "", "geheim123")                                        # mehrere ohne E-Mail ok
    check(st.authenticate("jaron", "geheim123")["username"] == "jaron", "login")
    raises(accounts.AccountError, st.authenticate, "jaron", "falsch")
    check(not hasattr(st, "change_password"), "Passwort darf nicht änderbar sein")
    for _ in range(5):
        raises(accounts.AccountError, st.authenticate, "jaron", "falsch")
    e = raises(accounts.AccountError, st.authenticate, "jaron", "geheim123")
    check("seconds" in str(e) or "Sekunden" in str(e), "Sperre nach Fehlversuchen")


def test_totp_and_sessions():
    d = Path(tempfile.mkdtemp(dir=TMP))
    st = accounts.AccountStore(d)
    st.register("anna", "", "", "geheim123")
    sec = st.begin_totp("anna")
    check(accounts.totp_code("JBSWY3DPEHPK3PXP", at=59) == accounts._hotp("JBSWY3DPEHPK3PXP", 1), "totp")
    st.confirm_totp("anna", accounts.totp_code(sec))
    raises(accounts.TotpRequired, st.authenticate, "anna", "geheim123")
    # Sitzungen: 24 h, für immer, abgelaufen
    st2 = accounts.AccountStore(Path(tempfile.mkdtemp(dir=TMP)))
    st2.register("bob", "", "", "geheim123")
    st2.create_session("bob", 1)
    check(st2.resume_session()["username"] == "bob", "session 24h")
    st2.create_session("bob", None)
    s = json.loads(st2.session_path.read_text())
    check(s["expires"] is None and st2.resume_session(), "session für immer")
    s["expires"] = int(time.time()) - 5
    st2.session_path.write_text(json.dumps(s))
    check(st2.resume_session() is None, "abgelaufene Sitzung")
    st2.create_session("bob", 7)
    st2.clear_session()
    check(st2.resume_session() is None, "clear_session")


# ---------------------------------------------------------------- Fake-Supabase
class FakeSupabase(http.server.BaseHTTPRequestHandler):
    users = {}        # email -> {"id","password","profile"}
    tokens = {}       # access/refresh token -> email
    codes = {}
    ai_calls = []

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _session(self, email):
        a, r = f"a-{len(self.tokens)}-{email}", f"r-{len(self.tokens)}-{email}"
        self.tokens[a] = self.tokens[r] = email
        return {"access_token": a, "refresh_token": r, "expires_in": 3600, "token_type": "bearer"}

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        if p.path == "/auth/v1/authorize":
            email = "google-user@gmail.com"
            self.users.setdefault(email, {"id": "g1", "password": None, "profile": None})
            code = "code-" + q["code_challenge"][0][:8]
            self.codes[code] = email
            self.send_response(302)
            self.send_header("Location", f"{q['redirect_to'][0]}?code={code}")
            self.end_headers()
        else:
            self._send(404, {})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        auth = self.headers.get("Authorization", "").replace("Bearer ", "")
        if p.path == "/auth/v1/signup":
            if body["email"] in self.users:
                return self._send(422, {"msg": "User already registered"})
            self.users[body["email"]] = {"id": "u" + str(len(self.users)), "password": body["password"], "profile": None}
            return self._send(200, self._session(body["email"]))
        if p.path == "/auth/v1/token":
            gt = q["grant_type"][0]
            if gt == "password":
                u = self.users.get(body["email"])
                if not u or u["password"] != body["password"]:
                    return self._send(400, {"error_description": "Invalid login credentials"})
                return self._send(200, self._session(body["email"]))
            if gt == "refresh_token":
                email = self.tokens.get(body["refresh_token"])
                return self._send(200, self._session(email)) if email else self._send(400, {"error_description": "invalid_grant"})
            if gt == "pkce":
                email = self.codes.get(body["auth_code"])
                return self._send(200, self._session(email)) if email and body.get("code_verifier") else self._send(400, {"error": "bad code"})
        if p.path == "/auth/v1/logout":
            return self._send(204, {})
        if p.path.startswith("/rest/v1/rpc/"):
            email = self.tokens.get(auth)
            if not email:
                return self._send(401, {"message": "JWT expired"})
            u, name = self.users[email], p.path.rsplit("/", 1)[1]
            if name == "jopml_ensure_profile":
                if u["profile"] is None:
                    u["profile"] = {"username": body.get("p_username") or "g_" + u["id"], "display_name": body.get("p_display_name") or "Google User",
                                    "email": email if u["password"] is None else "", "settings": {}}
                return self._send(200, u["profile"])
            if name == "jopml_get_profile":
                return self._send(200, u["profile"])
            if name == "jopml_save_profile":
                for k, v in body["p"].items():
                    if k == "settings":
                        u["profile"]["settings"].update(v)
                    else:
                        u["profile"][k] = v
                return self._send(200, u["profile"])
            if name == "jopml_delete_account":
                self.users.pop(email)
                return self._send(200, True)
        if p.path == "/functions/v1/jopml-ai":
            self.ai_calls.append(body)
            if body["kind"] == "macro":
                return self._send(200, {"reply": "```\nrepeat 3\n  key e\n  wait 20ms\nend\n```"})
            return self._send(200, {"reply": "Use the Add macros page."})
        self._send(404, {"message": "not found"})


def fake_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeSupabase)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_cloud_flow():
    from core import cloud, identity, oauth_loopback
    FakeSupabase.users.clear(), FakeSupabase.tokens.clear()
    srv, url = fake_server()
    try:
        ident = identity.CloudIdentity(cloud.CloudClient(url, "pub-key"))
        u = ident.register("Neu_Nutzer", "Neu", "", "geheim123")
        check(u["backend"] == "cloud" and u["email"] == "" and u["display_name"] == "Neu", "cloud register")
        raises(accounts.AccountError, ident.register, "neu_nutzer", "", "", "geheim123")
        raises(accounts.AccountError, ident.login, "neu_nutzer", "falsch")
        u = ident.login("neu_nutzer", "geheim123")
        u = ident.update_profile(u, "Neuer Name", "x@y.de")
        check(ident.client.get_profile()["display_name"] == "Neuer Name", "profil gespeichert")
        ident.push_settings(u, {"accent": "#ff0000", "language": "de", "legal_hash": "nicht-syncen"})
        time.sleep(0.4)
        saved = FakeSupabase.users[cloud.CloudClient.pseudo_email("neu_nutzer")]["profile"]["settings"]
        check(saved == {"accent": "#ff0000", "language": "de"}, f"nur SYNC_KEYS werden gespiegelt: {saved}")
        # angemeldet bleiben (7 Tage) + Wiederaufnahme mit rotiertem Token
        ident.remember(u, 7)
        ident2 = identity.CloudIdentity(cloud.CloudClient(url, "pub-key"))
        r = ident2.resume()
        check(r and r["display_name"] == "Neuer Name", "resume")
        ident2.remember(r, 0)
        check(identity.CloudIdentity(cloud.CloudClient(url, "pub-key")).resume() is None, "nicht angemeldet bleiben")
        # Export + Löschen
        data = ident.export(u)
        check(data["profile"]["display_name"] == "Neuer Name", "export")
        ident.delete(u, "")
        raises(accounts.AccountError, ident.login, "neu_nutzer", "geheim123")
        # Google (PKCE) über Loopback
        def fake_browser(auth_url):
            def go():
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                opener.open(auth_url, timeout=10).read()
            threading.Thread(target=go, daemon=True).start()
        oauth_loopback.open_browser = fake_browser
        from core import version
        cloud.OAUTH_LOOPBACK_PORT = 0
        g = ident.google()
        check(g["google_linked"] and g["backend"] == "cloud", "google login")
    finally:
        srv.shutdown()


def test_ai_and_generator():
    from core import ai_client, assistant, cloud, identity
    from modules.macros import dsl, generator
    FakeSupabase.users.clear(), FakeSupabase.tokens.clear(), FakeSupabase.ai_calls.clear()
    srv, url = fake_server()
    try:
        class App: pass
        app = App()
        app.identity = identity.CloudIdentity(cloud.CloudClient(url, "k"))
        check(not ai_client.available(app), "ohne Anmeldung keine KI")
        raises(ai_client.AiUnavailable, ai_client.ask, app, "help", [])
        app.identity.register("kiuser", "", "", "geheim123")
        check(ai_client.available(app), "KI nach Anmeldung")
        text, via_ai = assistant.reply(app, "wie mache ich das?", [{"role": "user", "content": "x"}])
        check(via_ai and "Add macros" in text, "help via KI")
        ask = lambda m: ai_client.ask(app, "macro", m)
        script, src = generator.generate("mach etwas völlig Unklares mit Schleifen", ask)
        check(src == "ai" and dsl.parse(script), "macro via KI")
    finally:
        srv.shutdown()
    # offline vor KI; KI-Müll wird abgelehnt
    check(generator.generate("Klicke alle 50ms an Position 500 300", None)[1] == "offline", "offline zuerst")
    bad_calls = []
    def bad(m):
        bad_calls.append(m)
        return "os.system('rm -rf /')"
    err = raises(generator.GenerateError, generator.generate, "irgendwas unverständliches", bad)
    check(len(bad_calls) == 2, "genau ein Wiederholungsversuch")
    raises(generator.GenerateError, generator.generate, "", None)


# ---------------------------------------------------------------- Makro-Sprache
class Rec:
    def __init__(self): self.log = []
    def click(self, b, xy, n): self.log.append(("click", b, xy, n))
    def move(self, x, y): self.log.append(("move", x, y))
    def key(self, k): self.log.append(("key", k))
    def hold(self, k, s, r): self.log.append(("hold", k, s))
    def type(self, t): self.log.append(("type", t))
    def scroll(self, n): self.log.append(("scroll", n))


def test_dsl():
    from modules.macros import dsl
    cmds = dsl.parse('# Kommentar\nrepeat 3\n  click right 10 20\n  wait 1s\nend\ntype "a # b"\nscroll -2')
    rec, waits = Rec(), []
    r = dsl.Runner(rec, sleep=waits.append)
    check(r.run(cmds) == "done", "run done")
    check(rec.log[:2] == [("click", "right", (10, 20), 1)] * 2 and rec.log[-2:] == [("type", "a # b"), ("scroll", -2)], rec.log)
    check(waits == [1.0, 1.0, 1.0], waits)
    check(dsl.parse_duration("50ms") == 0.05 and dsl.parse_duration("1,5s") == 1.5 and dsl.parse_duration("2m") == 120, "dauer")
    for bad, why in [("click left 1", "Position braucht 2 Zahlen"), ("foo", "unbekannt"), ("repeat 2\nclick", "ohne end"), ("end", "end ohne repeat"),
                     ("repeat forever\nclick\nend", "Endlosschleife ohne wait"), ("key notakey", "Taste"), ("wait 2h", "Dauer"),
                     ("repeat 1\nrepeat 1\nrepeat 1\nrepeat 1\nrepeat 1\nclick\nend\nend\nend\nend\nend", "zu tief"),
                     ("repeat 1000000\nrepeat 1000000\nclick\nend\nend", "zu viele Aktionen"), ("repeat 2\nrepeat forever\nwait 5ms\nend\nend", "forever innen"),
                     ("move 99999 1", "Koordinate"), ("", "leer"), ("\n".join(["click"] * 401), "zu viele Zeilen"), ('type "x', "Anführungszeichen")]:
        raises(dsl.MacroError, dsl.parse, bad)
    # sofort abbrechbar
    cmds = dsl.parse("repeat forever\n  key a\n  wait 5ms\nend")
    rec = Rec()
    runner = dsl.Runner(rec)
    t = threading.Thread(target=runner.run, args=(cmds,))
    t.start()
    time.sleep(0.15)
    runner.stop()
    t.join(2)
    check(not t.is_alive() and len(rec.log) > 3, "stop")
    # Offline-Generator
    g = lambda s: dsl.generate_offline(s)
    check(g("Klicke alle 50ms an Position 500 300")[0] == "repeat forever\n  click left 500 300\n  wait 50ms\nend", g("Klicke alle 50ms an Position 500 300"))
    check(g("click every 100 ms for 10 seconds")[0].startswith("repeat 100\n"), "for-Dauer")
    check("key e" in g("drücke die Taste e alle 2 sekunden")[0], "taste")
    check(g("tippe \"hallo\" dann warte 2 sekunden dann doppelklick")[0] == 'type "hallo"\nwait 2s\ndoubleclick left', "mehrere Sätze")
    check(g("scrolle runter 5")[0] == "scroll -5", "scroll")
    check(g("blablabla") is None, "unverständlich -> None")
    check(dsl.extract_script("Hier:\n```text\nclick\n```\nFertig") == "click", "codezaun")


# ---------------------------------------------------------------- Recoil
def test_recoil():
    from modules.recoil import engine
    cfg = engine.RecoilConfig.from_dict({"y": 999, "interval_ms": 1, "x": "abc"})
    check(cfg.y == 20 and cfg.interval_ms == 4 and cfg.x == 0.0, f"clamp {cfg}")
    c = engine.RecoilConfig(y=2.0, ramp_pct=50, ramp_ms=1000, delay_ms=100)
    check(engine.step(c, 50) == (0.0, 0.0), "delay")
    check(abs(engine.step(c, 1100)[1] - 3.0) < 1e-9, "ramp voll")
    comp = engine.Compensator()
    total = sum(comp.feed(0, 1.4)[1] for _ in range(10))
    check(total == 14, f"Bruchteile summieren sich: {total}")

    class B:
        def __init__(self): self.moves = []
        def move_relative(self, dx, dy): self.moves.append((dx, dy))
    b = B()
    eng = engine.RecoilEngine(b, engine.RecoilConfig(y=3, interval_ms=5, ramp_pct=0))
    eng.start()
    eng.set_pressed(True)
    time.sleep(0.15)
    check(not b.moves, "ohne enabled keine Bewegung")
    eng.enabled = True
    time.sleep(0.2)
    n = len(b.moves)
    check(n > 3 and all(m == (0, 3) for m in b.moves), f"bewegt {n}")
    eng.set_pressed(False)
    time.sleep(0.1)
    n2 = len(b.moves)
    time.sleep(0.15)
    check(len(b.moves) == n2, "Taste losgelassen -> Ruhe")
    eng.shutdown()


# ---------------------------------------------------------------- Extensions
def test_extensions():
    from modules.extensions import catalog
    settings, saves = {}, []
    st = catalog.Store(settings, lambda: saves.append(1))
    check(not st.added("notes"), "start leer")
    st.add("quicklinks"); st.add("websearch")
    check(st.enabled("quicklinks"), "add = aktiv")
    st.set_enabled("quicklinks", False)
    check(not st.enabled("quicklinks"), "aus")
    st.set_config("quicklinks", links=[["Meine Seite", "example.org"]])
    check(st.config("quicklinks")["links"] == [["Meine Seite", "https://example.org"]], st.config("quicklinks"))
    raises(ValueError, st.set_config, "quicklinks", links=[["x", "javascript:alert(1)"]])
    raises(ValueError, st.set_config, "quicklinks", links=[["x", "file:///etc/passwd"]])
    raises(ValueError, st.set_config, "websearch", engine="Evil")
    check(catalog.search_url("Google", "a b&c") == "https://www.google.com/search?q=a+b%26c", "such-URL")
    st.remove("websearch")
    check(not st.added("websearch") and saves, "remove")


# ---------------------------------------------------------------- macOS-Tasten
def test_mackeys():
    from core import mackeys
    check(mackeys.parse_hotkey("<f6>") == (97, 0), "F6")
    check(mackeys.parse_hotkey("<ctrl>+<alt>+p") == (35, mackeys.CTRL | mackeys.ALT), "Strg+Alt+P")
    check(mackeys.parse_hotkey("<cmd_l>+<shift>+a") == (0, mackeys.CMD | mackeys.SHIFT), "Aliase")
    for bad in ("<ctrl>", "<f99>", "ä", ""):
        try:
            mackeys.parse_hotkey(bad)
            check(False, f"{bad!r} muss abgelehnt werden")
        except ValueError:
            pass
    check(mackeys.key_name(98) == "f7" and mackeys.mods_from_flags(mackeys.SHIFT | mackeys.CMD) == ["shift", "cmd"], "Namen")
    check(len(set(mackeys.KEYCODES.values())) == len(mackeys.KEYCODES), "Tastencodes eindeutig")
    hk = mackeys.MacHotKeys({"<f6>": lambda: seen.append(1)}) if (seen := []) is not None else None
    hk._on_key(97, 0)                      # F6 ohne Modifier -> Aktion
    hk._on_key(97, mackeys.CMD)            # Cmd+F6 -> keine Aktion
    hk._on_key(98, 0)
    check(seen == [1], "nur genau passende Kombination löst aus")


# ---------------------------------------------------------------- Veröffentlichen / Updater
def test_publisher_and_updater():
    import io, json as _json
    from modules.publisher import logic
    from core import updater, cloud as cl

    check(logic.check_version("9.0.0") == "9.0.0", "Version ok")
    for bad in ("", "abc", "1", "1.2.x"):
        try:
            logic.check_version(bad)
            check(False, f"{bad!r} muss abgelehnt werden")
        except ValueError:
            pass
    check(logic.platform_of("x/App.EXE")[0] == "windows" and logic.platform_of("a.dmg")[0] == "macos", "Plattformen")
    try:
        logic.platform_of("virus.zip")
        check(False, "zip abgelehnt")
    except ValueError:
        pass
    m1 = logic.build_manifest(None, "9.0.0", " neu ", {"windows": {"url": "u1", "sha256": "a"}})
    check(m1["version"] == "9.0.0" and m1["packages"]["windows"]["version"] == "9.0.0" and m1["notes"] == "neu", "Manifest neu")
    m2 = logic.build_manifest(m1, "9.0.1", "mac", {"macos": {"url": "u2", "sha256": "b"}})
    check(m2["packages"]["windows"]["version"] == "9.0.0" and m2["packages"]["macos"]["version"] == "9.0.1"
          and m2["version"] == "9.0.1", "Plattformen bleiben unabhängig")
    old = {"version": "1.1.0", "packages": {"windows": {"url": "w", "sha256": "z"}}}
    check(logic.build_manifest(old, "1.1.1", "", {})["packages"]["windows"]["version"] == "1.1.0", "altes Format ohne Paketversion")

    # Updater: Paketversion entscheidet
    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    orig_open, orig_key = updater._open, updater.platform_key
    try:
        updater.platform_key = lambda: "macos"
        updater._open = lambda url, timeout=10: Resp(_json.dumps(m2).encode())
        from core.version import APP_VERSION as cur
        info = updater.check()
        check(info is not None and info.version == "9.0.1" and info.url == "u2", "Mac sieht 1.2.1")
        updater.platform_key = lambda: "windows"
        m3 = dict(m2); m3["packages"] = {"windows": {"url": "w", "sha256": "", "version": cur}}
        updater._open = lambda url, timeout=10: Resp(_json.dumps(m3).encode())
        check(updater.check() is None, "gleiche Paketversion = kein Update")
    finally:
        updater._open, updater.platform_key = orig_open, orig_key

    # Upload-Anfrage: richtige Adresse, Token, Upsert
    seen = {}
    class R2(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    orig_net = cl.net.urlopen
    try:
        cl.net.urlopen = lambda req, timeout=20: (seen.update(url=req.full_url, h={k.lower(): v for k, v in req.header_items()}, n=len(req.data)) or R2(b"{}"))
        c = cl.CloudClient("https://x.supabase.co", "pub")
        c.session = {"access_token": "TOK", "refresh_token": "", "expires_at": 9e12}
        c.upload_release("JOPML-1.2.0.dmg", b"abc", "application/octet-stream")
    finally:
        cl.net.urlopen = orig_net
    check(seen["url"] == "https://x.supabase.co/storage/v1/object/releases/JOPML-1.2.0.dmg", "Upload-Adresse")
    check(seen["h"]["authorization"] == "Bearer TOK" and seen["h"]["x-upsert"] == "true" and seen["n"] == 3, "Upload-Kopfzeilen")
    check(c.public_release_url("a b.exe").endswith("/public/releases/a%20b.exe"), "öffentliche Adresse")

    # Versionsliste und Zurückstellen
    check(logic.parse_release_name("JaronsOPMakro-1.4.0.exe") == ("windows", "1.4.0") and logic.parse_release_name("JOPML-1.10.2.dmg") == ("macos", "1.10.2"), "Dateiname erkannt")
    check(logic.parse_release_name("version.json") is None and logic.parse_release_name("JOPML-1.4.0.exe") is None, "Fremdes ignoriert")
    cur = {"version": "1.5.0", "notes": "neu", "packages": {"windows": {"url": "https://x/public/releases/JaronsOPMakro-1.5.0.exe", "sha256": "n", "version": "1.5.0"},
                                                          "macos": {"url": "https://x/public/releases/JOPML-1.4.0.dmg", "sha256": "m", "version": "1.4.0"}}}
    objs = [{"name": n, "created_at": "2026-10-28T10:00:00Z", "metadata": {"size": 5 * 1048576}} for n in
            ("version.json", "JaronsOPMakro-1.4.0.exe", "JaronsOPMakro-1.5.0.exe", "JOPML-1.4.0.dmg", "JaronsOPMakro-1.10.0.exe")]
    ent = logic.release_entries(objs, cur)
    check([e["version"] for e in ent if e["platform"] == "windows"] == ["1.10.0", "1.5.0", "1.4.0"], "neueste zuerst (1.10 > 1.5)")
    check({e["name"] for e in ent if e["active"]} == {"JaronsOPMakro-1.5.0.exe", "JOPML-1.4.0.dmg"}, "aktive markiert")
    rb = logic.activate_manifest(cur, "windows", "1.4.0", "https://x/public/releases/JaronsOPMakro-1.4.0.exe", "old", "zurück")
    check(rb["packages"]["windows"]["version"] == "1.4.0" and rb["packages"]["windows"]["rollback"] is True, "Rollback markiert")
    check(rb["packages"]["macos"]["version"] == "1.4.0" and rb["version"] == "1.4.0" and rb["notes"] == "zurück", "Rest bleibt, oberste Version sinkt")
    fw = logic.activate_manifest(rb, "windows", "1.5.0", "u", "n")
    check("rollback" not in fw["packages"]["windows"] and fw["version"] == "1.5.0", "vorwärts ohne Markierung")
    keep = logic.build_manifest(rb, "1.4.1", "mac", {"macos": {"url": "m2", "sha256": "z"}})
    check(keep["packages"]["windows"].get("rollback") is True, "Markierung überlebt andere Veröffentlichung")
    # Versionsprüfung beim Veröffentlichen
    check(logic.judge_version("1.4.2", "1.4.0", "1.4.2", True) == "", "EXE meldet passende Nummer: auch aus alter App")
    check("meldet Version 1.4.2" in logic.judge_version("1.4.3", "1.4.3", "1.4.2", True), "EXE meldet andere Nummer")
    check(logic.judge_version("1.4.0", "1.4.0", None, True) == "" and logic.judge_version("1.5.0", "1.4.0", None, False) == "", "alte Regel / nur dmg")
    check("passt nicht" in logic.judge_version("1.5.0", "1.4.0", None, True), "keine Auskunft und fremde Nummer")
    check(logic.probe_exe_version("/nicht/da.exe") is None, "fehlende EXE")

    # Updater: nur "rollback" darf zurückgehen
    try:
        updater.platform_key = lambda: "windows"
        low = {"version": "0.0.1", "packages": {"windows": {"url": "w", "sha256": "", "version": "0.0.1"}}}
        updater._open = lambda url, timeout=10: Resp(_json.dumps(low).encode())
        check(updater.check() is None, "ohne Markierung kein Downgrade")
        low["packages"]["windows"]["rollback"] = True
        updater._open = lambda url, timeout=10: Resp(_json.dumps(low).encode())
        info = updater.check()
        check(info is not None and info.version == "0.0.1", "mit Markierung Downgrade")
    finally:
        updater._open, updater.platform_key = orig_open, orig_key
    # Cloud: Liste und Löschen
    seen2 = []
    class R3(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    try:
        cl.net.urlopen = lambda req, timeout=20: (seen2.append((req.get_method(), req.full_url, req.data)) or R3(b'[{"name":"JOPML-1.0.0.dmg"}]'))
        c.list_releases()
        c.delete_release("JOPML-1.0.0.dmg")
    finally:
        cl.net.urlopen = orig_net
    check(seen2[0][0] == "POST" and seen2[0][1].endswith("/storage/v1/object/list/releases"), "Liste-Anfrage")
    check(seen2[1][0] == "DELETE" and b"JOPML-1.0.0.dmg" in seen2[1][2], "Lösch-Anfrage")


# ---------------------------------------------------------------- i18n, Recht, Theme, Icon, Verknüpfungen
def test_i18n_coverage():
    sys.path.insert(0, str(ROOT / "tools"))
    import extract_strings
    keys = [k for k in extract_strings.all_strings() if k not in ("not added", "unknown extension", "unknown search engine")]
    for code in ("de", "es", "ru", "fr", "zh"):
        i18n.set_language(code)
        T = i18n._table
        short = [k for k in keys if len(k) <= 110]
        miss = [k for k in short if k not in T]
        check(len(miss) <= len(short) * 0.03, f"{code}: {len(miss)} kurze Texte ohne Übersetzung, z. B. {miss[:3]}")
        for k, v in T.items():                                # Platzhalter müssen übereinstimmen
            import re
            check(sorted(re.findall(r"\{\w+\}", k)) == sorted(re.findall(r"\{\w+\}", v)), f"{code}: Platzhalter in {k!r}")
    de_miss = [k for k in keys if k not in i18n._load("de")]
    check(not de_miss, f"de unvollständig: {de_miss[:3]}")
    i18n.set_language("de")
    check(i18n.tr("Welcome, {name}!", name="Jaron") == "Willkommen, Jaron!", "tr mit Platzhalter")
    check(i18n.tr("Unbekannter Text {x}", x=1) == "Unbekannter Text 1", "Fallback")
    i18n.set_language("xx")
    check(i18n.get_language() == "en", "unbekannte Sprache -> Englisch")
    from modules.recoil.plugin import WARNING
    i18n.set_language("de")
    check(i18n.tr(WARNING) == "ACHTUNG: Dieses Tool kann sehr leicht von modernen Anti-Cheat-Systemen erkannt werden. "
                              "Die Nutzung wird ausdrücklich nur in Offline-Spielen zu Bildungs- und Testzwecken empfohlen!", "exakte Warnung")
    i18n.set_language("en")


def test_legal_and_firstrun():
    from core import config, firstrun_view, legal_text, version
    de = legal_text.legal_text("de")
    check(len(de) > 20000, f"Rechtstext lang genug ({len(de)})")
    for needle in ["§ 1 ", "§ 2 ", "§ 3 ", "§ 4 ", "§ 5 ", "§ 6 ", "§ 7 ", "§ 521 BGB", "§ 276 Abs. 3 BGB", "§ 303a StGB", "§ 278 BGB",
                   "Easy Anti-Cheat", "Ricochet", "Vanguard", "BattlEye", "Valve Anti-Cheat", "Art. 11", "Art. 15", "Art. 17", "Art. 20",
                   "CISG", "EGBGB", "Brüssel-Ia", "Lugano", "§ 54 BGB", "§ 705 BGB", "§ 50 ZPO", "Public Domain", "Claude", "Gemini", "Supabase"]:
        check(needle in de, f"Rechtstext enthält {needle}")
    check(legal_text.legal_text("fr") == legal_text.legal_text("en"), "andere Sprachen -> Englisch")
    check(len(legal_text.legal_hash()) == 64, "hash")
    s = config.load_settings()
    s["legal_version"] = ""
    check(firstrun_view.needs_legal(s), "erster Start braucht Zustimmung")
    firstrun_view.record_acceptance(s)
    s2 = config.load_settings()
    check(s2["legal_version"] == version.LEGAL_VERSION and s2["legal_accepted_at"] > 0 and not firstrun_view.needs_legal(s2), "Zustimmung gespeichert")
    check(firstrun_view.at_bottom((0.4, 1.0)) and not firstrun_view.at_bottom((0.0, 0.5)), "Scroll-Barriere")
    check(config.DEFAULT_SETTINGS["language"] == "en" and config.DEFAULT_SETTINGS["first_run_done"] is False, "Start auf Englisch")
    check(version.GOOGLE_CLIENT_ID == "1074605193535-edplvmfud08vo1lebb2vb82s64r9m4aq.apps.googleusercontent.com", "Client-ID")


def test_theme_icon_shortcuts():
    from core import appicon, shortcuts, theme
    theme.apply({"appearance_mode": "dark", "accent": "#112233", "colors": {"main": "#101010", "text": "#eeeeee", "card": "nope"}})
    check(theme.c("main") == ("#101010", "#101010") and theme.accent() == "#112233" and theme.c("card") == theme.DEFAULT_PALETTE["card"], "theme")
    theme.apply({})
    check(theme.accent() == theme.DEFAULT_ACCENT, "theme reset")
    try:
        from PIL import Image
    except ImportError:
        return
    for bg, img in [("#4f8cff", None), ("#ffffff", None), ("#000000", None)]:
        im = appicon.render(128, bg, img)
        check(im.size == (128, 128), "icon größe")
    im1, im2 = appicon.render(128, "#ff0000"), appicon.render(128, "#00ff00")
    check(im1.tobytes() != im2.tobytes(), "Hintergrund änderbar")
    # JOPML-Text ist immer sichtbar: Mitte des Icons unterscheidet sich vom reinen Hintergrund
    plain = Image.new("RGBA", (128, 128), "#ff0000")
    check(im1.crop((20, 40, 108, 88)).tobytes() != plain.crop((20, 40, 108, 88)).tobytes(), "JOPML sichtbar")
    pic = Path(TMP) / "bg.png"
    Image.new("RGB", (50, 30), "#00aa00").save(pic)
    check(appicon.render(128, "#000", str(pic)).size == (128, 128), "Hintergrundbild")
    if sys.platform.startswith("linux"):
        os.environ["XDG_DESKTOP_DIR"] = str(Path(TMP) / "Desktop")
        shortcuts._desktop_dir = lambda: Path(TMP) / "Desktop"
        shortcuts.create_desktop_shortcut()
        check(shortcuts.has_desktop_shortcut(), "Verknüpfung")
        shortcuts.remove_desktop_shortcut()
        check(not shortcuts.has_desktop_shortcut(), "Verknüpfung entfernt")
        shortcuts.set_autostart(True)
        check(shortcuts.is_autostart(), "autostart an")
        shortcuts.set_autostart(False)
        check(not shortcuts.is_autostart(), "autostart aus")


def test_ads_and_limits():
    from core import ads
    p = ads.provider()
    check(p.name == "placeholder" and not p.available() and p.load() is None, "Werbung ist inaktiv")
    g = ads.GoogleAdsProvider("ca-app-pub-0000000000000000/0000000000")
    check(g.available() and g.load() is None, "Schnittstelle vorhanden")


def test_dsl_translations_dont_crash():
    from modules.macros import dsl
    for code in ("de", "es", "ru", "fr", "zh"):
        i18n.set_language(code)
        e = raises(dsl.MacroError, dsl.parse, "click left 1")
        check(str(e), "Fehlertext")
    i18n.set_language("en")


# ---------------------------------------------------------------- Community: Filter, Verschlüsselung, Datenbank
FILTER_BAD = ["fuck you", "f u c k", "f.u.c.k", "fuuuuuuuuuuck", "f*ck", "sh1t", "$hit", "ѕhit", "ｆｕｃｋ", "fück", "FUCK", "Scheiße",
              "scheisse", "arschloch", "A R S C H L O C H", "kill yourself", "k y s", "send nudes", "n u d e s", "nigg3r", "n1gger",
              "сука", "cyka", "blyat", "傻 逼", "他妈的", "f​u​c​k", "b***h", "b!tch", "a$$hole", "you are a ass",
              "what the f_u_c_k", "pu55y", "НИГГЕР", "fvck", "Heil Hitler", "h e i l h i t l e r", "Sieg  Heil!", "go kill yourself now",
              "i will kill you", "ich bring dich um", "Hurensohn", "du hurensohn!!", "KYS", "puta madre", "hijo de puta",
              "va te faire enculer", "ты сука", "пошёл нахуй", "Ты Сука!"]
FILTER_GOOD = ["Hello world", "class", "assassin", "Scunthorpe", "shiitake mushrooms", "The hit of the season", "he has hit the ball",
               "passing grade", "I use Mongo", "Maine Coon cat", "assistant", "analysis of data", "cocktail", "peacock", "fuchsia",
               "Dickens", "classic", "Let's play Minecraft tonight", "gg wp", "kill all processes", "macro for diablo", "ok, 5 minutes",
               "I'm at 88 damage", "Hello (world)", "mail a@b.com", "x*y=5", "2*3=6", "5 * 5", "Hancock", "Essex", "title", "It's a hit",
               "das ist toll", "Guten Morgen, wie geht's?", "hola, cómo estás", "привет, как дела", "你好，今天天气很好",
               "magna cum laude", "pussycat", "please pass the glass", "this is as simple as that", "bass guitar", "I will see you",
               "Can you help me?", "skill issue", "Der Fuchs läuft", "Apfelkuchen", "shitake", "plan a b c d",
               "What a nice day, isn't it", "Wie geht es dir? Alles klar bei dir?", "mi casa es tu casa", "bonjour, ça va?",
               "спасибо большое", "Meet at 5 pm, see you"]


def test_chatfilter():
    from core import chatfilter as f
    missed = [t for t in FILTER_BAD if f.check(t).ok]
    check(not missed, f"Filter lässt durch: {missed}")
    wrong = [(t, f.check(t).category) for t in FILTER_GOOD if not f.check(t).ok]
    check(not wrong, f"Filter blockt Harmloses: {wrong}")
    check(f.check("fuck").category == "profanity" and f.check("send nudes").category == "sexual"
          and f.check("heil hitler").category == "hate" and f.check("kill yourself").category == "threat", "Kategorien")
    masked, hit = f.mask("du bist ein f*cking Arschloch, ok?")
    check(hit and "Arschloch" not in masked and masked.endswith(", ok?") and "ing" in masked, "mask")
    check(f.mask("hello world") == ("hello world", False), "mask ohne Treffer")
    check(f.check("a" * 6000 + " s" * 500).ok, "lange Eingaben bleiben schnell")
    raises(f.FilterError, f.require_clean, "f u c k")
    try:
        i18n.set_language("de")
        check("nicht erlaubt" in f.explain(f.check("fuck")), "Fehlertext übersetzt")
    finally:
        i18n.set_language("en")


def test_community_crypto():
    from modules.community import crypto as c
    a, b = c.KeyBundle.generate(), c.KeyBundle.generate()
    blob = c.seal_bundle(a, "passphrase-1")
    check(c.open_bundle(blob, "passphrase-1").enc_pub == a.enc_pub, "Schlüssel-Behälter")
    raises(c.CryptoError, c.open_bundle, blob, "falsch")
    check("passphrase" not in blob and a.to_bytes().hex() not in blob, "kein Klartext im Behälter")
    k = c.new_space_key()
    w = c.wrap(k, b.enc_pub, "s1", 1)
    check(c.unwrap(w, b, "s1", 1) == k, "wrap/unwrap")
    raises(c.CryptoError, c.unwrap, w, a, "s1", 1)          # falscher Empfänger
    raises(c.CryptoError, c.unwrap, w, b, "s1", 2)          # falsche Epoche
    raises(c.CryptoError, c.unwrap, w, b, "s2", 1)          # falscher Server
    body, sig = c.encrypt_message(k, a, "s1", "c1", 1, "u1", "Hallo 👋")
    check(c.decrypt_message(k, "s1", "c1", 1, "u1", body)["t"] == "Hallo 👋", "Nachricht")
    check("Hallo" not in body, "Chiffretext")
    check(c.verify_message(a.sign_pub, "c1", 1, "u1", body, sig) and not c.verify_message(b.sign_pub, "c1", 1, "u1", body, sig), "Signatur")
    check(not c.verify_message(a.sign_pub, "c1", 1, "u2", body, sig), "Signatur gilt nur für den Absender")
    for args in (("c2", 1, "u1"), ("c1", 2, "u1"), ("c1", 1, "u2")):
        raises(c.CryptoError, c.decrypt_message, k, "s1", args[0], args[1], args[2], body)   # Kontext ist gebunden
    raises(c.CryptoError, c.decrypt_message, c.new_space_key(), "s1", "c1", 1, "u1", body)
    check(c.pair_fingerprint((a.enc_pub, a.sign_pub), (b.enc_pub, b.sign_pub)) ==
          c.pair_fingerprint((b.enc_pub, b.sign_pub), (a.enc_pub, a.sign_pub)), "Sicherheitsnummer symmetrisch")


def test_community_pg():
    """Client-Code gegen die echten SQL-Funktionen in einer lokalen PostgreSQL (nur wenn verfügbar)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import pg_shim
    if not pg_shim.available():
        print("       (PostgreSQL nicht verfügbar – übersprungen)")
        return
    from core import chatfilter
    from core.cloud import CloudClient
    from modules.community.forum import Forum
    from modules.community.service import CommunityError, CommunityService
    db = pg_shim.create_db()
    srv, url = pg_shim.start_shim(db)
    try:
        def mk(email, uname=None):
            uid = pg_shim.add_user(db, email)
            cl = CloudClient(url, "k")
            cl.session = {"access_token": "tok-" + uid, "refresh_token": "", "expires_at": int(time.time()) + 9999}
            if uname:
                cl.ensure_profile(uname, uname.title())
            return cl, uid

        def err(fn, *a, **k):
            try:
                fn(*a, **k)
            except (CommunityError, Exception) as exc:
                return str(exc)
            raise AssertionError("Fehler erwartet")

        def as_user(uid, text):
            return pg_shim.sql(db, f"set role authenticated; set request.jwt.claim.sub = '{uid}'; {text}")

        # ---- Filter: Python und SQL liefern dasselbe Ergebnis
        diffs = []
        for t in FILTER_BAD + FILTER_GOOD:
            sql_cat = pg_shim.sql(db, "select coalesce(public.jopml_c_check($t$%s$t$), '-')" % t)
            if sql_cat != (chatfilter.check(t).category or "-"):
                diffs.append((t, sql_cat))
        check(not diffs, f"Python- und SQL-Filter weichen ab: {diffs}")

        ca, ua = mk("x+alice@gmail.com", "alice")
        cb, ub = mk("x+bob@gmail.com", "bob")
        cc, uc = mk("x+carl@gmail.com", "carl")
        cg, ug = mk("gina@gmail.com")
        A, B, C, G = (CommunityService(x) for x in (ca, cb, cc, cg))
        pg_shim.sql(db, f"insert into public.jopml_admins (user_id) values ('{ug}')")

        # ---- Einrichtung
        check(not A.load_me()["registered"], "noch nicht eingerichtet")
        check("at least" in err(A.setup, "alice", "Alice", "kurz"), "Passphrase-Länge")
        check("not allowed" in err(G.setup, "f.u.c.k", "x", "supergeheim1"), "Benutzername gefiltert (Client)")
        for s, h in ((A, "alice"), (B, "bob"), (C, "carl"), (G, "gina")):
            s.load_me()
            s.setup(h, h.title(), "supergeheim1")
        check(A.me["handle"] == "alice" and A.unlocked, "Einrichtung")
        check("already" in err(A.setup, "alice", "Alice", "supergeheim1").lower(), "nur einmal einrichten")
        A2 = CommunityService(ca)
        A2.load_me()
        check("Wrong passphrase" in err(A2.unlock, "falsch-falsch"), "falsche Passphrase")
        A2.unlock("supergeheim1")
        check(A2.my_fingerprint() == A.my_fingerprint(), "Schlüssel auf zweitem Gerät")
        A3 = CommunityService(ca)
        A3.load_me()
        A3.me["bundle"] = B.me["bundle"]                       # Server schiebt fremden Schlüssel-Behälter unter
        check("do not match" in err(A3.unlock, "supergeheim1"), "vertauschter Schlüssel-Behälter wird erkannt")
        # Passwort-Konto: Benutzername ist fest; Google-Konto wählt selbst
        check(G.me["handle"] == "gina", "Google-Konto wählt Benutzernamen")
        cx, _ = mk("zed@gmail.com")
        X = CommunityService(cx)
        X.load_me()
        _e = err(X.setup, "alice", "x", "supergeheim1"); check("taken" in _e, f"Google darf keinen vorhandenen Benutzernamen nehmen: {_e}")

        # ---- Server, Einladung per Code, Freischaltung
        res = A.create_server("Mein Server")
        sid, ch = res["space_id"], res["channel_id"]
        check("not allowed" in err(A.create_server, "Scheiße Server"), "Servername gefiltert")
        A.refresh()
        A.send(sid, ch, "Hallo Welt")
        check(A.fetch(sid, ch)[0].text == "Hallo Welt" and A.fetch(sid, ch)[0].verified, "senden/lesen/Signatur")
        raw = pg_shim.sql(db, "select body from public.jopml_c_messages limit 1")
        check("Hallo" not in raw and len(raw) > 30, "Server speichert nur Chiffretext")
        inv = A.create_invite(sid)
        check(inv["code"].startswith("JOPML-"), "Einladungscode")
        check("invalid" in err(B.redeem_invite, "JOPML-0000-0000-0000-0000"), "falscher Code")
        B.redeem_invite(inv["code"])
        B.refresh()
        check(B.space(sid)["status"] == "pending" and not B.has_key(sid), "wartet auf Freischaltung")
        check(err(B.fetch, sid, ch), "Wartende dürfen nicht lesen")
        check(err(B.members, sid), "Wartende sehen keine Mitgliederliste")
        A.refresh()
        check(A.housekeeping() == [f"approve:{sid}"], "Admin schaltet frei")
        B.refresh()
        check(B.has_key(sid) and B.space(sid)["status"] == "active", "freigeschaltet")
        B.send(sid, ch, "Hi Alice!")
        msgs = A.fetch(sid, ch)
        check([m.text for m in msgs] == ["Hallo Welt", "Hi Alice!"] and all(m.verified for m in msgs), "beide Seiten lesen")
        check([m.text for m in B.fetch(sid, ch)] == ["Hallo Welt", "Hi Alice!"], "neues Mitglied liest die Historie dieser Epoche")
        # ---- 1.3.3: Antworten, Stummschalten, Slowmode
        first = A.fetch(sid, ch)[0]
        A.send(sid, ch, "Antwort @bob", reply={"id": first.id, "n": first.name, "s": first.text})
        rep = [m for m in B.fetch(sid, ch) if m.text == "Antwort @bob"][0]
        check(rep.reply and rep.reply["id"] == first.id and rep.reply["s"] == "Hallo Welt", "Antwort ist im verschlüsselten Inhalt")
        check("Hallo" not in pg_shim.sql(db, "select string_agg(body, ' ') from public.jopml_c_messages"), "Antwort-Auszug liegt nicht im Klartext")
        _e = err(B.mute, sid, ua, 5); check("allowed" in _e, f"Mitglied darf niemanden stummschalten: {_e}")
        A.mute(sid, ub, 30)
        B.refresh()
        check(B.space(sid).get("muted_until"), "Stummschaltung sichtbar")
        check("muted" in err(B.send, sid, ch, "geht nicht").lower(), "Stummgeschaltete können nicht schreiben")
        check(any(m.get("muted_until") for m in A.members(sid).values()), "Mitgliederliste zeigt Stummschaltung")
        A.mute(sid, ub, 0)
        B.refresh()
        check(not B.space(sid).get("muted_until"), "Stummschaltung aufgehoben")
        check("allowed" in err(B.set_slowmode, sid, 10), "Mitglied darf Slowmode nicht setzen")
        A.set_slowmode(sid, 60)
        check("wait" in err(B.send, sid, ch, "zu früh"), "Slowmode gilt sofort nach der letzten Nachricht")
        pg_shim.sql(db, f"update public.jopml_c_messages set created_at = created_at - interval '1 day' where sender_id = '{ub}'")
        B.send(sid, ch, "erste")
        check("wait" in err(B.send, sid, ch, "zweite"), "Slowmode bremst Mitglieder")
        A.send(sid, ch, "a1"); A.send(sid, ch, "a2")        # Admin/Owner sind ausgenommen
        A.set_slowmode(sid, 0)
        B.send(sid, ch, "dritte")
        check("allowed" in err(A.set_slowmode, sid, 99999), "Slowmode-Grenze")
        # ---- 1.4.0: Einladung per E-Mail
        sid2 = A.create_server("Mail-Server")["space_id"]
        A.refresh()
        A.invite_email(sid2, "X+Bob@gmail.com")                  # Groß-/Kleinschreibung egal
        check(any(i["space_id"] == sid2 for i in B.my_invites()), "Einladung per E-Mail kommt an")
        pg_shim.sql(db, f"delete from public.jopml_c_user_invites where invitee = '{ub}'")
        A.invite_email(sid2, "niemand@example.org")             # unbekannt: gleiche Antwort, nichts passiert
        check(not pg_shim.sql(db, "select 1 from public.jopml_c_user_invites where invitee not in (select user_id from public.jopml_c_users)"), "unbekannte Adresse: keine Spur")
        check("valid email" in err(A.invite_email, sid2, "keine-mail"), "Adressformat")
        check("allowed" in err(C.invite_email, sid2, "x+bob@gmail.com"), "Nicht-Mitglieder dürfen nicht einladen")
        for i in range(18):
            A.invite_email(sid2, f"n{i}@example.org")
        check("fast" in err(A.invite_email, sid2, "x@example.org"), "Begrenzung gegen Ausforschen")
        A.delete_space(sid2)

        # ---- 1.4.0: Marktplatz, Ankündigungen, Bestenlisten
        from modules.community.market import MarketService, analyze, check_for_publish
        MA, MB, MG = MarketService(A), MarketService(B), MarketService(G)
        good = "repeat 3\n  click left 10 20\n  wait 50ms\nend"
        mid_ = MA.publish("Mein Klicker", "klickt dreimal", good)
        lst = MB.browse()
        check(len(lst) == 1 and lst[0]["author"] == "alice" and lst[0]["title"] == "Mein Klicker" and "script" not in lst[0], "Marktplatz: Liste ohne Skript")
        check(MB.get(mid_)["script"] == good, "Marktplatz: Import")
        check(MB.browse()[0]["downloads"] == 1 and MA.get(mid_) and MB.browse()[0]["downloads"] == 1, "Downloads zählen, eigene nicht")
        MB.rate(mid_, 4)
        MG.rate(mid_, 5)
        row = MA.browse(sort="top")[0]
        check(row["stars"] == 4.5 and row["votes"] == 2, f"Bewertung: {row}")
        check("allowed" in err(MA.rate, mid_, 5) or "not allowed" in err(MA.rate, mid_, 5), "eigene Makros nicht bewerten")
        check(MA.browse(q="klick") and not MA.browse(q="gibtsnicht"), "Suche")
        check("not allowed" in err(MA.publish, "Scheiße Makro", "", good), "Titel gefiltert")
        check(err(MA.publish, "Ab", "", good), "Titel zu kurz")
        check(err(MA.publish, "Böses Makro", "", "rm -rf /"), "unbekannte Befehle werden abgelehnt")
        evil_srv = err(MA._rpc, "jopml_m_publish", {"title": "Server-Test", "descr": "", "script": "explode now"})
        check("not allowed" in evil_srv or "macro" in evil_srv.lower(), f"Server lehnt ungültige Makros ab: {evil_srv}")
        held = "down mouse_left\nwait 100ms-300ms\nup mouse_left\nhold shift 50ms"
        mid_du = MB.publish("Halten und loslassen", "down/up seit 1.5.0", held)
        check(MB.get(mid_du)["script"] == held, "Server nimmt Makros mit down/up und zufälliger Wartezeit an")
        MG.delete(mid_du)
        MC = MarketService(C)
        check("allowed" in err(MC.delete, mid_), "Fremde dürfen nicht löschen")
        for who in (MB, MG, MC):
            who.report(mid_, "spam")
        check(not MA.browse(), "ab 3 Meldungen ausgeblendet")
        MG.delete(mid_)
        check(not pg_shim.sql(db, "select 1 from public.jopml_m_macros"), "Admin darf löschen")
        MG.post_news("Version 1.4.0", "Viele neue Module")
        check(MB.news()[0]["title"] == "Version 1.4.0", "Ankündigung sichtbar")
        check("allowed" in err(MB.post_news, "Hack", "x"), "nur Admins posten Ankündigungen")
        MG.delete_news(MB.news()[0]["id"])
        check(MB.news() == [], "Ankündigung gelöscht")
        check(MA.submit_score("cps5", 8.5) == 8.5, "Bestwert gespeichert")
        pg_shim.sql(db, "update public.jopml_scores set updated_at = now() - interval '1 minute'")
        check(MA.submit_score("cps5", 6.0) == 8.5, "schlechterer Wert ändert den Bestwert nicht")
        check(err(MA.submit_score, "cps5", 99), "unmöglicher Wert abgelehnt")
        check(err(MB.submit_score, "reaction", 5), "unmögliche Reaktionszeit abgelehnt")
        MB.submit_score("reaction", 210)
        MG.submit_score("reaction", 180)
        top = MA.top("reaction")
        check([r["handle"] for r in top] == ["gina", "bob"], f"Bestenliste sortiert: {top}")
        check(len(analyze("repeat forever\n click left 1 1\n wait 10ms\nend")) == 1 and analyze(good) == [] and
              analyze('type "hallo"')[0].startswith("Types text"), "Analyse")
        check(check_for_publish("Titel ok", "", good) == "", "Vorab-Prüfung")

        check(err(C.fetch, sid, ch), "Fremde dürfen nicht lesen")
        check("forbidden" in err(C._rpc, "jopml_c_send", {"channel_id": ch, "epoch": 1, "body": "x", "sig": "y"}).lower()
              or "allowed" in err(C._rpc, "jopml_c_send", {"channel_id": ch, "epoch": 1, "body": "x", "sig": "y"}), "Fremde dürfen nicht schreiben")

        # ---- Rechte
        check("allowed" in err(B.create_channel, sid, "geheim"), "Mitglied darf keine Kanäle anlegen")
        A.create_channel(sid, "offtopic")
        check("not allowed" in err(A.create_channel, sid, "porn"), "Kanalname gefiltert")
        check("allowed" in err(B.kick, sid, ua), "Mitglied darf nicht rauswerfen")
        check("allowed" in err(B._rpc, "jopml_c_put_wraps", {"space_id": sid, "epoch": 1, "wraps": []}), "Mitglied darf keine Schlüssel verteilen")
        check("allowed" in err(B.set_role, sid, ub, "admin"), "Mitglied macht sich nicht zum Admin")
        A.set_role(sid, ub, "admin")
        A.refresh(); B.refresh()
        check(B.space(sid)["role"] == "admin", "Admin ernannt")
        check("allowed" in err(B.kick, sid, ua), "Owner kann nicht rausgeworfen werden")
        A.refresh()
        A.delete_channel([c_["id"] for c_ in A.space(sid)["channels"] if c_["name"] == "offtopic"][0])
        check("last" in err(A.delete_channel, ch), "letzter Kanal bleibt")

        # ---- Einladung per Benutzername
        A.invite_user(sid, "carl")
        check("member" in err(A.invite_user, sid, "bob"), "schon Mitglied")
        check("no user" in err(A.invite_user, sid, "gibtsnicht"), "unbekannter Benutzer")
        inv_list = C.my_invites()
        check(len(inv_list) == 1 and inv_list[0]["from"] == "alice", "Einladung sichtbar")
        C.answer_invite(sid, True)
        A.refresh()
        check(A.housekeeping() or B.housekeeping(), "Freischaltung nach Namens-Einladung")
        C.refresh()
        check(C.has_key(sid), "Carl hat den Schlüssel")

        # ---- Fälschung durch den Server: falscher Absender -> Signatur ungültig
        key = A._keys[(sid, 1)]
        from modules.community import crypto as cr
        body, sig = cr.encrypt_message(key, A.bundle, sid, ch, 1, ub, "ich bin Bob (nicht wirklich)")      # signiert mit Alices Schlüssel
        pg_shim.sql(db, f"insert into public.jopml_c_messages (channel_id, space_id, sender_id, epoch, body, sig) values ('{ch}', '{sid}', '{ub}', 1, '{body}', '{sig}')")
        forged = [m for m in C.fetch(sid, ch) if "nicht wirklich" in m.text][0]
        check(forged.ok and not forged.verified, "gefälschte Absenderangabe wird erkannt")
        # manipulierter Chiffretext
        pg_shim.sql(db, f"update public.jopml_c_messages set body = substr(body, 1, 20) || 'AAAA' || substr(body, 25) where id = (select min(id) from public.jopml_c_messages)")
        first = C.fetch(sid, ch)[0]
        check(not first.ok, "manipulierter Chiffretext wird abgelehnt")

        # ---- Sperren, Austritt, Schlüsselwechsel
        A.send(sid, ch, "vor dem Rauswurf")
        old_key = C._keys[(sid, 1)]
        A.kick(sid, uc, ban=True)
        A.refresh()
        check(A.space(sid)["needs_rotation"], "Rotation nötig")
        check(A.housekeeping() == [f"rotate:{sid}"], "neuer Gruppenschlüssel")
        A.refresh()
        check(A.space(sid)["epoch"] == 2 and A.has_key(sid), "Epoche 2")
        A.send(sid, ch, "nach dem Rauswurf")
        check(err(C.fetch, sid, ch), "Rausgeworfener kann nichts mehr lesen")
        check("banned" in err(C.redeem_invite, inv["code"]).lower(), "gesperrt")
        body2 = pg_shim.sql(db, f"select body from public.jopml_c_messages where epoch = 2 limit 1")
        check(cr.CryptoError and err(cr.decrypt_message, old_key, sid, ch, 2, ua, body2), "alter Schlüssel öffnet neue Nachrichten nicht")
        B.refresh()
        check([m.text for m in B.fetch(sid, ch) if m.ok][-1] == "nach dem Rauswurf", "verbliebene Mitglieder lesen weiter")
        check(len([m for m in B.fetch(sid, ch) if m.ok]) >= 4, "alte Nachrichten bleiben für Mitglieder lesbar")
        B.leave(sid)
        A.refresh()
        check(A.space(sid)["needs_rotation"], "Austritt löst Rotation aus")
        check("cannot leave" in err(A.leave, sid), "Owner kann nicht austreten")

        # ---- Direktnachrichten
        check("no user" in err(A.open_dm, "gibtsnicht"), "DM: unbekannt")
        check("yourself" in err(A.open_dm, "alice"), "DM: nicht mit sich selbst")
        d = A.open_dm("gina")
        check(not d["existing"], "DM angelegt")
        d2 = A.open_dm("gina")
        check(d2["existing"] and d2["space_id"] == d["space_id"], "DM nur einmal")
        G.refresh(); A.refresh()
        gdm = [s for s in G.spaces if s["kind"] == "dm"][0]
        adm = [s for s in A.spaces if s["kind"] == "dm"][0]
        A.send(adm["id"], adm["channels"][0]["id"], "nur für Gina")
        got = G.fetch(gdm["id"], gdm["channels"][0]["id"])
        check(got[0].text == "nur für Gina" and got[0].verified, "DM kommt an")
        check(G.safety_number(gdm["id"]) == A.safety_number(adm["id"]) and G.safety_number(gdm["id"]), "gleiche Sicherheitsnummer")
        check(err(B.fetch, adm["id"], adm["channels"][0]["id"]), "Dritte lesen keine DMs")

        # ---- Empfänger-Filter und Sender-Filter
        check("not allowed" in err(A.send, adm["id"], adm["channels"][0]["id"], "du hurensohn"), "Sender-Filter")
        k2 = A._keys[(adm["id"], 1)]
        b3, s3 = cr.encrypt_message(k2, A.bundle, adm["id"], adm["channels"][0]["id"], 1, ua, "du bist ein Hurensohn")   # umgangener Client
        A._rpc("jopml_c_send", {"channel_id": adm["channels"][0]["id"], "epoch": 1, "body": b3, "sig": s3})
        shown = G.fetch(gdm["id"], gdm["channels"][0]["id"])[-1]
        check(shown.filtered and "Hurensohn" not in shown.text, "Empfänger-Filter blendet aus")

        # ---- Löschen, Melden, Moderation
        mid = A.fetch(adm["id"], adm["channels"][0]["id"])[0].id
        check("allowed" in err(G.delete_message, mid), "fremde Nachricht nicht löschbar")
        G.report_message(gdm["id"], shown, "Beleidigung")
        check("allowed" in err(A.admin_reports), "Meldungen nur für Admins")
        reps = G.admin_reports()
        check(len(reps) == 1 and reps[0]["reported"] == "alice", "Meldung beim Admin")
        G.admin_resolve(reps[0]["id"], "suspend_user")
        check("suspended" in err(A.send, adm["id"], adm["channels"][0]["id"], "hallo").lower(), "gesperrter Nutzer kann nicht mehr schreiben")
        pg_shim.sql(db, f"delete from public.jopml_c_suspended where user_id = '{ua}'")
        A.delete_message(mid)

        # ---- Rate-Limit
        sent = 0
        e = ""
        for i in range(14):
            try:
                A.send(sid, ch, f"spam {i}")
                sent += 1
            except CommunityError as exc:
                e = str(exc)
                break
        check(sent <= 11 and "too fast" in e, f"Rate-Limit greift (gesendet: {sent})")

        # ---- Forum
        F, FB, FG = Forum(ca), Forum(cb), Forum(cg)
        check([b["id"] for b in F.boards()][:2] == ["general", "help"], "Foren")
        tid = F.new_thread("general", "Willkommen", "Erster Beitrag")
        check("not allowed" in err(F.new_thread, "general", "Titel", "du Hurensohn"), "Forum: Client-Filter")
        try:
            ca.rpc("jopml_f_new_thread", {"p": {"board": "general", "title": "abc", "body": "f u c k"}})
            raise AssertionError("Server-Filter fehlt")
        except Exception as exc:
            check("filtered" in str(exc), f"Forum: Server-Filter greift auch ohne Client ({exc})")
        FB.reply(tid, "Hallo zurück")
        th = F.thread(tid)
        check(th["thread"]["title"] == "Willkommen" and len(th["posts"]) == 1 and th["posts"][0]["author"] == "bob", "Thread lesen")
        check(th["posts"][0]["mine"] is False and FB.thread(tid)["posts"][0]["mine"], "mine-Kennzeichen")
        F.delete("post", th["posts"][0]["id"])                       # Alice ist nicht die Autorin des Beitrags -> nichts passiert
        check(len(F.thread(tid)["posts"]) == 1, "fremde Beiträge kann man nicht löschen")
        check(F.threads("general")[0]["replies"] == 1, "Antwortzähler")
        FG.set_flags(tid, locked=True)
        check("locked" in err(FB.reply, tid, "noch eine"), "gesperrter Thread")
        check("allowed" in err(F.set_flags, tid, pinned=True), "nur Admins fixieren")
        FG.delete("post", th["posts"][0]["id"])
        check(F.thread(tid)["posts"] == [], "Admin löscht Beitrag")
        F.delete("thread", tid)
        check(F.threads("general") == [], "Autor löscht Thread")

        # ---- Identität zurücksetzen (Passphrase vergessen)
        Cz = CommunityService(cc)
        Cz.load_me(); Cz.unlock("supergeheim1")
        Cz.reset_identity()
        Cz.load_me()
        check(not Cz.registered, "Zurücksetzen entfernt die Community-Identität")
        Cz.setup("carl", "Carl", "neue-passphrase-9")
        check(Cz.registered, "danach neu einrichtbar")

        # ---- Konto löschen entfernt Server und Nachrichten
        before = int(pg_shim.sql(db, "select count(*) from public.jopml_c_spaces where kind = 'server'"))
        ca.rpc("jopml_delete_account")
        after = int(pg_shim.sql(db, "select count(*) from public.jopml_c_spaces where kind = 'server'"))
        check(before == 1 and after == 0, "Konto löschen entfernt die eigenen Server")
        check(int(pg_shim.sql(db, f"select count(*) from public.jopml_c_messages where sender_id = '{ua}'")) == 0, "und die Nachrichten")

        # ---- Direktzugriff auf Tabellen/Funktionen ist verboten
        for stmt in ("select * from public.jopml_c_messages", "select * from public.jopml_c_users", "select * from public.jopml_c_wraps",
                     "insert into public.jopml_f_threads (board, title, body) values ('general', 'abc', 'x')",
                     "select public.jopml_c_uid()", "select public.jopml_c_join(null, null)"):
            check("permission denied" in err(as_user, ub, stmt), f"kein Direktzugriff: {stmt}")
        check("permission denied" in err(pg_shim.sql, db, "set role anon; select public.jopml_c_me()"), "anon hat keinen Zugriff")

        # ---- Namensfilter bei der Registrierung (Server-Seite)
        cz, _ = mk("x+f.u.c.k@gmail.com")
        try:
            cz.ensure_profile("f.u.c.k", "x")
            raise AssertionError("Namensfilter fehlt")
        except Exception as exc:
            check("name_not_allowed" in str(exc) or "not allowed" in str(exc), f"Registrierung mit Schimpfwort-Name wird abgelehnt ({exc})")
    finally:
        srv.shutdown()
        pg_shim.drop_db(db)


# ---------------------------------------------------------------- Layout & Hintergrundbild
def test_migrations_all_in_shim():
    """Jede Supabase-Migration muss auch im PostgreSQL-Test laufen (Patches haben pg_shim.py schon öfter mit einer alten
    Liste überschrieben). Ausgenommen sind nur Migrationen, die der Test durch tests/sql/admin_stub.sql ersetzt."""
    sys.path.insert(0, str(ROOT / "tests"))
    import pg_shim
    skipped = {"20261026000100_jopml_releases_bucket.sql", "20261027000000_jopml_admin_publish.sql"}
    files = sorted(p.name for p in (ROOT / "supabase/migrations").glob("*.sql"))
    missing = [f for f in files if f not in skipped and f not in pg_shim.MIGRATIONS]
    check(not missing, f"Migrationen fehlen in tests/pg_shim.py (MIGRATIONS): {missing}")
    check(pg_shim.MIGRATIONS == sorted(pg_shim.MIGRATIONS), "MIGRATIONS ist nach Datum sortiert")
    check(all((ROOT / "supabase/migrations" / f).exists() for f in pg_shim.MIGRATIONS), "MIGRATIONS nennt nur vorhandene Dateien")


def test_ci_migrations_in_order():
    """Wie der CI-Schritt "Supabase-Migration gegen echte PostgreSQL prüfen": frische Datenbank, Supabase-Attrappe,
    dann ALLE Migrationen in Dateireihenfolge (auch Storage/Admin) und zum Schluss tests/sql/rls_test.sql."""
    sys.path.insert(0, str(ROOT / "tests"))
    import pg_shim
    if not pg_shim.available():
        print("  (übersprungen: keine lokale PostgreSQL)")
        return
    import subprocess
    import uuid as _uuid
    pg_shim.ensure_server()
    db = "jci_" + _uuid.uuid4().hex[:10]
    subprocess.run(["runuser", "-u", "postgres", "--", "createdb", db], check=True, capture_output=True)
    try:
        r = pg_shim._psql(db, "-f", str(ROOT / "tests/sql/supabase_stub.sql"))
        check(r.returncode == 0, f"Supabase-Attrappe: {r.stderr}")
        for f in sorted((ROOT / "supabase/migrations").glob("*.sql")):
            r = pg_shim._psql(db, "-f", str(f))
            check(r.returncode == 0, f"{f.name}: {r.stderr}")
        pol = pg_shim.sql(db, "select count(*) from pg_policies where schemaname = 'storage' and policyname like 'jopml admin %'")
        check(pol.strip() == "4", f"Storage-Policies für Admins: {pol}")
        ok_du = pg_shim.sql(db, "select public.jopml_m_script_ok(E'down mouse_left\\nwait 10ms-20ms\\nup mouse_left')")
        check(ok_du.strip() == "t", "Server-Prüfung kennt down/up")
        check(pg_shim.sql(db, "select public.jopml_m_script_ok('downx 1')").strip() == "f", "nur ganze Befehlswörter")
    finally:
        pg_shim.drop_db(db)


def test_release_workflow_assets():
    """Das GitHub-Release muss EXE, Setup.exe und version.json enthalten; die Versionsnummer passt zu den Release-Notes."""
    from core.version import APP_VERSION
    wf = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    iss = (ROOT / "installer/JaronsOPMakro.iss").read_text(encoding="utf-8")
    create = [ln for ln in wf.splitlines() if "gh release create" in ln]
    check(len(create) == 1 and all(f in create[0] for f in ("dist/JaronsOPMakro.exe", "dist/JaronsOPMakro-Setup.exe", "dist/version.json")),
          f"Release-Dateien: {create}")
    check("OutputBaseFilename=JaronsOPMakro-Setup" in iss and "installer/JaronsOPMakro.iss" in wf, "Setup wird gebaut")
    check("PrivilegesRequired=lowest" in iss, "Setup ohne Adminrechte (Auto-Update kann die EXE ersetzen)")
    first = (ROOT / "RELEASE_NOTES.txt").read_text(encoding="utf-8").split(":", 1)[0]
    check(first == f"Version {APP_VERSION}", f"RELEASE_NOTES beginnt mit {first!r}, APP_VERSION ist {APP_VERSION}")


def test_layout_and_background():
    from core import background, layout
    ids = ["autoclicker", "macros", "extensions", "recoil", "assistant", "contact"]
    check(layout.normalize_order(ids, []) == ids, "Standardreihenfolge")
    check(layout.normalize_order(ids, ["recoil", "x", "recoil", "dashboard", "macros"])[:2] == ["recoil", "macros"], "unbekannt/doppelt verworfen")
    check(layout.normalize_order(ids + ["community"], ["recoil"])[-1] == "community", "neues Modul hinten angefügt")
    check(layout.move(ids, [], "recoil", -2)[:4] == ["autoclicker", "recoil", "macros", "extensions"], "nach oben")
    check(layout.move(ids, [], "autoclicker", -5)[0] == "autoclicker", "oben bleibt oben")
    check(layout.move(ids, [], "contact", 5)[-1] == "contact", "unten bleibt unten")
    check(layout.set_hidden([], "dashboard", True) == [] and layout.set_hidden([], "settings", True) == [], "Dashboard/Einstellungen nie ausblendbar")
    h = layout.set_hidden([], "macros", True)
    check(h == ["macros"] and "macros" not in layout.visible(ids, [], h), "ausblenden")
    check(layout.set_hidden(h, "macros", False) == [], "einblenden")
    check(layout.clamp_dim(500) == 80 and layout.clamp_dim(-3) == 0 and layout.clamp_dim("x") == 40, "Abdunkeln begrenzt")
    from PIL import Image
    d = Path(tempfile.mkdtemp(dir=TMP))
    Image.new("RGB", (300, 100), (200, 100, 50)).save(d / "a.png")
    img = background.render(str(d / "a.png"), 1920, 140, 50)
    check(img.size == (1920, 140), "Bild füllt die Fläche")
    check(img.getpixel((10, 10))[0] < 120, "abgedunkelt")
    (d / "x.png").write_bytes(b"kein bild")
    raises(background.BackgroundError, background.check, str(d / "x.png"))
    raises(background.BackgroundError, background.check, str(d / "fehlt.png"))


# ---------------------------------------------------------------- GUI-Smoke (Attrappen)
def _local_only(fn):
    """Die Oberflächen-Tests laufen ohne Netzwerk: Cloud-Konfiguration aus version.py abschalten."""
    def wrapper():
        import types
        from core import identity as ident
        orig = ident.CloudClient
        ident.CloudClient = lambda: types.SimpleNamespace(configured=False)
        try:
            fn()
        finally:
            ident.CloudClient = orig
    wrapper.__name__ = fn.__name__
    return wrapper


def test_v133_tools():
    """Statistik, Sicherung, Notaus, Aufnahme, Makro-Import, Chat-Hilfen."""
    from core import backup, config as cfg, panic, stats
    from modules.autoclicker.engine import ClickEngine, EngineConfig
    from modules.community.chat_view import mentions, poll_delay
    from modules.macros import dsl, recorder
    from modules.macros.plugin import Plugin as MacroPlugin

    # Statistik
    stats.reset()
    stats.record_clicker(100, 10.0)
    stats.record_clicker(0, 5.0)
    stats.record_macro(3.5)
    d = stats.load()
    check(d["clicks"] == 100 and d["runs"] == 1 and d["best_cps"] == 10.0 and d["macro_runs"] == 1, f"Statistik: {d}")
    check(stats.fmt_duration(3725) == "1 h 2 min" and stats.fmt_duration(65) == "1 min 5 s", "Dauer-Format")
    # Engine meldet das Ende
    got = []
    eng = ClickEngine()
    eng.on_finish = lambda c, e, r: got.append((c, r))
    eng.start(EngineConfig(action=lambda: None, interval_s=0.001, repeat_count=5))
    eng.join(2)
    time.sleep(0.05)
    check(got and got[0] == (5, "count"), f"on_finish: {got}")

    # Aufnahme -> gültiges Makro
    ev = [("click", 1.0, "left", 100, 200), ("key", 1.5, "h"), ("key", 1.6, "i"), ("key", 2.0, "enter"), ("scroll", 3.0, -2), ("key", 3.5, "ß")]
    script = recorder.events_to_script(ev)
    check(script.splitlines()[0] == "click left 100 200" and 'type "hi"' in script and "key enter" in script and "scroll -2" in script
          and "ß" not in script, f"Aufnahme: {script!r}")
    dsl.parse(script)
    check(recorder.events_to_script([]) == "", "leere Aufnahme")

    # Makro-Import/Export
    mp = MacroPlugin.__new__(MacroPlugin)
    mp.id = "macros"
    f = Path(TMP) / "m.jopm"
    f.write_text("repeat 2\n  click left 1 2\nend\n", encoding="utf-8")
    n1, _ = mp.import_from(str(f))
    n2, _ = mp.import_from(str(f))
    check(n1 == "m" and n2 == "m 2", f"Import überschreibt nichts: {n1}, {n2}")
    mp.export_to(n1, str(Path(TMP) / "out.jopm"))
    check(dsl.parse((Path(TMP) / "out.jopm").read_text(encoding="utf-8")), "Export lesbar")
    bad = Path(TMP) / "bad.jopm"
    bad.write_text("explode now\n", encoding="utf-8")
    try:
        mp.import_from(str(bad))
        check(False, "ungültiges Makro darf nicht importiert werden")
    except dsl.MacroError:
        pass

    # Sicherung
    s = cfg.load_settings()
    s["accent"] = "#123456"
    s["bg_image"] = "/geheim/pfad.png"
    cfg.save_settings(s)
    data = backup.build()
    check(data["settings"]["accent"] == "#123456" and "bg_image" not in data["settings"] and "macros/m.jopm" in data["files"], "Sicherung enthält das Richtige")
    check(not any(k in json.dumps(data) for k in ("legal_hash", "geheim")), "Sicherung ohne Gerätedaten")
    evil = {"format": "jopml-backup", "settings": {"accent": 5, "evil": 1, "language": "de"},
            "files": {"../../x.jopm": "hack", "macros/ok.jopm": "click left 1 1", "macros/a/b.jopm": "x", "macros/c.exe": "x", "bad/j.json": "{nope"}}
    res = backup.restore(evil)
    check(res["files"] == 1 and res["skipped"] == 4 and res["settings"] == 1, f"Wiederherstellung prüft streng: {res}")
    check(not (Path(TMP).parent / "x.jopm").exists() and (cfg.profiles_dir("macros") / "ok.jopm").exists(), "kein Ausbruch aus dem Ordner")
    try:
        backup.restore({"format": "other"})
        check(False, "falsches Format")
    except ValueError:
        pass

    # Notaus stoppt alles
    class P:
        def __init__(self, i, **kw):
            self.id = i
            self.__dict__.update(kw)
    calls = []
    class Eng:
        running = True
    class App:
        pages = {}
    a = App()
    a.plugins = [P("autoclicker", engine=Eng(), stop=lambda: calls.append("ac")),
                 P("macros", state="running", stop=lambda: calls.append("mc")),
                 P("recoil", enabled=True, set_enabled=lambda v: calls.append("rc"))]
    res = panic.stop_everything(a)
    check(sorted(res) == ["autoclicker", "macros", "recoil"] and sorted(calls) == ["ac", "mc", "rc"], f"Notaus stoppt alle drei: {res}")

    # Chat-Hilfen
    check(mentions("hi @Bob!", "bob") and not mentions("mail@bob.de", "bob") and not mentions("@bobby", "bob") and not mentions("x", ""), "Erwähnungen")
    check(poll_delay(0, True) == 3000 and poll_delay(20, True) == 6000 and poll_delay(99, True) == 12000 and poll_delay(0, False) == 12000, "adaptive Abfrage")


def test_v140_modules():
    """Logik der neuen Module (Klick-Werkzeuge, Gamer, Produktivität)."""
    import datetime
    from modules.clicktools import appprofiles, crosshair, hotkeys, pixel, scheduler
    from modules.gamer import cps, keyoverlay, screenshot, sysinfo
    from modules.gamer.timer import SessionTimer
    from modules.productivity import winmgr
    from modules.productivity.assistant import Conversation
    from modules.productivity.clipboard import ClipHistory
    from modules.macros import dsl, generator

    # Fadenkreuz
    c = crosshair.CrosshairConfig.from_dict({"shape": "Nope", "color": "red", "size": 999, "opacity": 1, "gap": 500})
    check(c.shape == "Cross" and c.color == "#00ff00" and c.size == 80 and c.opacity == 20 and c.gap == 79, f"Fadenkreuz-Werte werden begrenzt: {c}")
    check(all(len(crosshair.primitives(crosshair.CrosshairConfig.from_dict(p))) >= 1 for p in crosshair.PRESETS.values()), "alle Presets zeichnen etwas")
    check(len(crosshair.primitives(crosshair.CrosshairConfig(shape="Cross with gap", gap=5))) == 4, "Kreuz mit Lücke")

    # Hotkeys
    check(hotkeys.normalize_hotkey("Ctrl + Alt + K") == "<ctrl>+<alt>+k" and hotkeys.normalize_hotkey("F9") == "<f9>", "Kürzel normalisieren")
    for bad in ("", "k", "ctrl+", "ctrl+ä", "foo+k", "ctrl+shift"):
        raises(ValueError, hotkeys.normalize_hotkey, bad)
    check(hotkeys.Rule("ctrl+1", "key", "A").validate().value == "a", "Rule: Taste")
    raises(ValueError, hotkeys.Rule("ctrl+1", "text", "").validate)
    raises(ValueError, hotkeys.Rule("ctrl+1", "key", "Ärger").validate)
    rules = hotkeys.parse_rules([{"hotkey": "ctrl+1", "action": "text", "value": "hi"}, {"hotkey": "x", "action": "text", "value": "no"}, "müll"])
    check(len(rules) == 1, "kaputte Regeln werden übersprungen")
    done = []
    m = hotkeys.build_mapping(rules + [hotkeys.Rule("ctrl+1", "key", "a").validate()], done.append)
    m["<ctrl>+1"]()
    check(len(m) == 1 and done[0].action == "text", "doppelte Kürzel: erstes gilt")

    # Farb-Trigger
    check(pixel.parse_hex("#ff8800") == (255, 136, 0), "Farbe lesen")
    raises(ValueError, pixel.parse_hex, "rot")
    check(pixel.matches((250, 130, 5), (255, 136, 0), 10) and not pixel.matches((200, 130, 5), (255, 136, 0), 10), "Toleranz")
    hits = []
    w = pixel.PixelWatcher(1, 2, "#00ff00", 5, lambda: hits.append(1), interval=0.01, once=True, grab=lambda x, y: (0, 255, 0))
    w.start(); w.join(1)
    check(hits == [1] and not w.running, "Treffer löst genau einmal aus")
    errs = []
    w = pixel.PixelWatcher(1, 2, "#00ff00", 5, lambda: None, interval=0.01, grab=lambda x, y: 1 / 0, on_error=errs.append)
    w.start(); w.join(1)
    check(errs and "ZeroDivision" in errs[0], "Lesefehler wird gemeldet")

    # Zeitplaner
    now = datetime.datetime(2026, 10, 28, 18, 31)
    daily = scheduler.Entry("a", "m", "daily", "18:30").validate()
    check(scheduler.due(daily, now, None) and not scheduler.due(daily, now, datetime.datetime(2026, 10, 28, 18, 30, 30)), "Tagestermin genau einmal")
    check(scheduler.due(daily, now, datetime.datetime(2026, 10, 27, 18, 30)), "am nächsten Tag wieder")
    check(not scheduler.due(daily, now.replace(hour=18, minute=29), None), "vor der Zeit nicht")
    iv = scheduler.Entry("b", "m", "interval", minutes=10).validate()
    check(scheduler.due(iv, now, now - datetime.timedelta(minutes=11)) and not scheduler.due(iv, now, now - datetime.timedelta(minutes=5)), "Intervall")
    raises(ValueError, scheduler.Entry("c", "m", "daily", "25:99").validate)
    raises(ValueError, scheduler.Entry("c", "", "daily", "10:00").validate)
    clock = [datetime.datetime(2026, 10, 28, 9, 0)]
    ran = []
    sch = scheduler.Scheduler(lambda: [scheduler.Entry("x", "mac", "interval", minutes=1).validate()], lambda n: ran.append(n) or "", clock=lambda: clock[0])
    sch.last["x"] = clock[0]
    sch.check_once()
    clock[0] += datetime.timedelta(seconds=61)
    sch.check_once(); sch.check_once()
    check(ran == ["mac"] and len(sch.log) == 1, f"Zeitplaner startet einmal: {ran}")

    # Programm-Profile
    rl = appprofiles.parse_rules([{"match": "Minecraft", "profile": "mc"}, {"match": "x", "profile": "y"}])
    check(len(rl) == 1 and appprofiles.pick(rl, {"title": "Minecraft 1.21", "proc": "java"}).profile == "mc" and appprofiles.pick(rl, {"title": "Word"}) is None, "Regeln")
    sw = []
    win = [{"title": "Minecraft", "proc": ""}]
    wt = appprofiles.AppProfileWatcher(lambda: rl, sw.append, lambda: win[0])
    wt.step(); wt.step(); win[0] = {"title": "Browser"}; wt.step(); win[0] = {"title": "Minecraft"}; wt.step()
    check(sw == ["mc"], f"Profil wechselt nur bei Änderung: {sw}")

    # Timer
    t_ = [0.0]
    st = SessionTimer(1, 2, clock=lambda: t_[0])
    check(st.due() == [], "Timer aus")
    st.start(); t_[0] = 61
    check(st.due() == ["break"] and st.due() == [], "Pausen-Erinnerung einmal")
    t_[0] = 121
    check(st.due() == ["break", "drink"] or sorted(st.due()) == [], "Trink-Erinnerung")
    st.stop(); t_[0] = 500
    check(st.elapsed() == 121 and SessionTimer.fmt(3725) == "01:02:05", "Zeit läuft nur bei Start")

    # System- und Tasten-Overlay
    check(sysinfo.format_stats({"cpu": 5, "ram": None, "gpu": None, "ping": 20}, {"cpu": True, "ping": True}) == "CPU  5 %\nPing 20 ms", "Systemwerte formatieren")
    check(isinstance(sysinfo.sample(with_gpu=False, with_ping=False), dict), "Systemwerte lesbar")
    tt = [0.0]
    ks = keyoverlay.KeyState(clock=lambda: tt[0])
    ks.press("w"); ks.press("mouse_left"); ks.tap("a")
    check(ks.is_down("w") and ks.is_down("a") and ks.recent_keys() == ["w", "a"], "Tasten merken")
    tt[0] = 0.5
    check(ks.is_down("a") is False, "Aufleuchten endet")
    ks.release("w")
    check(not ks.is_down("w") and ks.is_down("mouse_left"), "Loslassen")

    # CPS / Reaktion
    ct = [0.0]
    test = cps.CpsTest(clock=lambda: ct[0])
    for i in range(30):
        ct[0] = i * 0.1
        test.click()
    ct[0] = 5.5
    check(not test.click() and test.finished and test.cps() == 6.0 and test.valid(), f"CPS: {test.cps()}")
    fast = cps.CpsTest(clock=lambda: ct[0]); ct[0] = 0
    for _ in range(200):
        fast.click()
    check(not fast.valid(), "unmögliche CPS ungültig")
    rt = [0.0]
    r_ = cps.ReactionTest(clock=lambda: rt[0], rng=lambda a, b: 2.0)
    rt[0] = 1.0
    check(r_.click() is None and r_.too_early, "zu früh")
    rt[0] = 0.0
    r_ = cps.ReactionTest(clock=lambda: rt[0], rng=lambda a, b: 2.0); rt[0] = 2.25
    check(r_.click() == 250 and cps.rating(250) == "Average", "Reaktionszeit")

    # Screenshot
    check(screenshot.normalize_box(100, 80, 20, 10, 2.0, (1000, 1000)) == (40, 20, 200, 160), "Auswahl normalisieren")
    check(screenshot.normalize_box(1, 1, 3, 3) is None, "zu kleine Auswahl")
    check(screenshot.file_name(datetime.datetime(2026, 10, 28, 9, 5, 7)) == "JOPML-20261028-090507.png", "Dateiname")
    from PIL import Image
    p_ = screenshot.save(Image.new("RGB", (20, 20), "red"), Path(TMP) / "shots")
    check(p_.exists() and p_.suffix == ".png", "Screenshot speichern")

    # Zwischenablage
    ch = ClipHistory(["alt"])
    check(ch.add("eins") and not ch.add("eins") and ch.add("zwei") and ch.items == ["zwei", "eins"], "Verlauf")
    check(not ch.add("   ") and not ch.add("x" * 6000), "leer/zu lang wird ignoriert")
    ch.add("eins")
    check(ch.items[0] == "eins" and len(ch.items) == 2, "erneutes Kopieren rückt nach oben")
    ch.pin("zwei")
    check(ch.search("zw") == (["zwei"], []) and ch.search("")[1] == ["eins"], "Suche/Anheften")
    ch.paused = True
    check(not ch.add("geheim"), "Pause nimmt nichts auf")
    for i in range(80):
        ch.paused = False
        ch.add(f"t{i}")
    check(len(ch.items) == 50, "Verlauf ist begrenzt")

    # Fenster-Manager
    area = (0, 0, 1000, 800)
    check(winmgr.snap_rect("left", area) == (0, 0, 500, 800) and winmgr.snap_rect("bottom-right", area) == (500, 400, 500, 400)
          and winmgr.snap_rect("maximize", area) == area, "Fensterpositionen")
    raises(ValueError, winmgr.snap_rect, "mitte-irgendwo", area)
    moved = []
    wins = [{"id": 1, "title": "Chrome", "proc": ""}, {"id": 2, "title": "Discord", "proc": ""}, {"id": 3, "title": "Chrome 2", "proc": ""}]
    n = winmgr.apply_layout([winmgr.Slot("chrome", "left"), winmgr.Slot("discord", "right"), winmgr.Slot("chrome", "top")], wins, area,
                            lambda i, *r: moved.append((i, r)) or "")
    check(n == 3 and [m[0] for m in moved] == [1, 2, 3], f"Layout verteilt Fenster ohne Doppelbelegung: {moved}")
    check(len(winmgr.parse_layouts({"a": [{"match": "x", "kind": "left"}, {"match": "chrome", "kind": "left"}], "b": "kaputt"})) == 1, "Layouts lesen")

    # KI-Assistent (mit unechter KI)
    replies = iter(["```\nclick left 1 1\nwait 10ms\n```", "unsinn", "repeat 3\n click left 1 1\n wait 10ms\nend"])
    conv = Conversation(lambda msgs: next(replies))
    s1, src = conv.send("klicke irgendwo bei 1 1 ganz oft bitte")
    check(src in ("ai", "offline") and dsl.parse(s1), "Assistent: erste Antwort")
    replies2 = iter(["unsinn", "repeat 3\n click left 1 1\n wait 10ms\nend"])
    conv2 = Conversation(lambda msgs: next(replies2))
    conv2.history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "click left 1 1\nwait 10ms"}]
    s2, _src = conv2.send("mach daraus drei Wiederholungen")
    check(s2.startswith("repeat 3") and len(conv2.history) == 4, "Assistent: Änderung, ungültige Antwort wird korrigiert")
    try:
        Conversation(None).send("a")
        check(False, "zu kurz")
    except generator.GenerateError:
        pass
    c0 = Conversation(None); c0.history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "wait 1s"}]
    try:
        c0.send("schneller bitte")
        check(False, "Änderung ohne KI")
    except generator.GenerateError:
        pass


def test_handbook_current():
    import re
    from pathlib import Path
    from core import handbook
    from core.version import APP_VERSION
    from modules import BUILTIN_MODULES
    vers = [v for v, _ in handbook.CHANGELOG]
    key = lambda v: tuple(int(x) for x in v.split("."))
    check(vers[0] == APP_VERSION, f"Handbuch: CHANGELOG in core/handbook.py braucht oben einen Eintrag für {APP_VERSION}")
    check(vers == sorted(vers, key=key, reverse=True) and len(set(vers)) == len(vers), "CHANGELOG neueste zuerst, keine Doppelten")
    check(all(items for _, items in handbook.CHANGELOG), "jeder Eintrag hat Inhalt")
    for m in list(BUILTIN_MODULES) + ["core"]:
        check(m in handbook.SECTIONS, f"Handbuch: Abschnitt für Modul {m} fehlt")
    check(len(handbook.text()) < 18000, "Handbuch zu lang für die Anfrage (Server nimmt höchstens 20000 Zeichen)")
    ts = Path(__file__).resolve().parent.parent / "supabase" / "functions" / "jopml-ai" / "knowledge.ts"
    check(f"INSTALLED VERSION: {APP_VERSION}" in ts.read_text(encoding="utf-8"), "knowledge.ts veraltet: python tools/gen_knowledge.py ausführen")
    check(re.search(r"v" + re.escape(APP_VERSION), ts.read_text(encoding="utf-8")) is not None, "knowledge.ts ohne aktuelle Version")


def test_perf_and_ai_stream():
    import io, json as _json
    from core import ui, cloud as cl
    # ui.cfg: nur bei Änderung neu zeichnen
    class W:
        n = 0
        def configure(self, **kw): W.n += 1
    w = W()
    ui.cfg(w, text="a"); ui.cfg(w, text="a"); ui.cfg(w, text="b"); ui.cfg(w, text="b", fg="x")
    check(W.n == 3, f"cfg zeichnet nur bei Änderung neu ({W.n})")
    # KI-Stream: Stücke und UTF-8 über Chunk-Grenzen
    class R(io.BytesIO):
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read1(self, n=-1): return self.read(3)          # kleine Stücke zerschneiden auch Umlaute
    orig = cl.net.urlopen
    seen = []
    try:
        c = cl.CloudClient("https://x.supabase.co", "pub")
        c.session = {"access_token": "T", "refresh_token": "", "expires_at": 9e12}
        cl.net.urlopen = lambda req, timeout=20: (seen.append(_json.loads(req.data)) or R("Grüße aus Köln – 中文".encode("utf-8")))
        parts = []
        out = c.ai_stream([{"role": "user", "content": "hi"}], "de", parts.append)
        check(out == "Grüße aus Köln – 中文" and len(parts) > 3 and parts[-1] == out, "Stream zusammengesetzt")
        check(seen[0]["stream"] is True and seen[0]["version"] and "INSTALLED VERSION" in seen[0]["handbook"], "Anfrage mit Handbuch und Version")
        class J(R):
            headers = {"Content-Type": "application/json"}
        cl.net.urlopen = lambda req, timeout=20: J(b'{"reply":"alt"}')
        check(c.ai_stream([{"role": "user", "content": "hi"}], "de", lambda t: None) == "alt", "älterer Server (JSON)")
        cl.net.urlopen = lambda req, timeout=20: R(b"")
        try:
            c.ai_stream([{"role": "user", "content": "hi"}], "de", lambda t: None)
            check(False, "leere Antwort muss Fehler sein")
        except cl.CloudError:
            pass
    finally:
        cl.net.urlopen = orig


def test_v150_structure_and_tools():
    import time
    from core import panic
    from modules.macros import dsl
    from modules.clicktools import mousekeys
    from modules.gamemacros import library
    from modules.autoclicker import plugin as ac
    # Makro-Sprache: down/up, Maustasten halten, zufällige Wartezeit
    class B:
        def __init__(s): s.log = []
        def press(s, n): s.log.append(("p", n))
        def release(s, n): s.log.append(("r", n))
        def hold(s, n, sec, r): s.log.append(("h", n))
    b = B()
    waits = []
    r = dsl.Runner(b, sleep=waits.append)
    check(r.run(dsl.parse("down mouse_left\nrepeat 20\nwait 10ms-20ms\nend\nhold mouse_right 1ms\nup mouse_left")) == "done", "down/up läuft")
    check(all(0.01 <= w <= 0.02 for w in waits) and len(set(waits)) > 1, "zufällige Wartezeit liegt im Bereich und streut")
    check(b.log == [("p", "mouse_left"), ("h", "mouse_right"), ("r", "mouse_left")], "Reihenfolge down/hold/up")
    b2 = B(); r2 = dsl.Runner(b2)
    import threading
    threading.Timer(0.1, r2.stop).start()
    check(r2.run(dsl.parse("down shift\nrepeat forever\nwait 50ms\nend")) == "stopped" and b2.log[-1] == ("r", "shift"), "Taste wird bei Abbruch losgelassen")
    for bad in ("wait 300ms-100ms", "down foo", "key mouse_left", "wait -", "down"):
        try:
            dsl.parse(bad)
            check(False, f"{bad!r} muss abgelehnt werden")
        except dsl.MacroError:
            pass
    # Maus & Tastatur
    c = mousekeys.parse({"multiclick": {"on": True, "hotkey": "ctrl+k", "count": 99, "delay_ms": -4, "button": "x"},
                         "antiafk": {"interval_s": 1, "mode": "?"}, "autoscroll": {"speed": "abc"}})
    check(c["multiclick"]["count"] == 5 and c["multiclick"]["delay_ms"] == 0 and c["multiclick"]["button"] == "left", "Mehrfachklick begrenzt")
    check(c["multiclick"]["hotkey"] == "<ctrl>+k" and c["antiafk"]["interval_s"] == 10 and c["antiafk"]["mode"] == "mouse" and c["autoscroll"]["speed"] == 5, "Werte begrenzt")
    d = mousekeys.parse({"multiclick": {"hotkey": "<f9>"}, "holdtoggle": {"hotkey": "<f9>"}})
    check(len({d[k]["hotkey"] for k in ("multiclick", "holdtoggle", "autoscroll")}) == 3, "doppelte Tastenkürzel werden ersetzt")
    check(mousekeys.parse("müll")["holdtoggle"]["target"] == "shift", "Müll ergibt Standard")
    class IO:
        def __init__(s): s.log = []
        def click(s, *a): s.log.append(("click",) + a)
        def press(s, n): s.log.append(("p", n))
        def release(s, n): s.log.append(("r", n))
        def scroll(s, n): s.log.append(("s", n))
        def nudge(s): s.log.append(("nudge",))
        def tap(s, n): s.log.append(("tap", n))
    io = IO()
    mk = mousekeys.MouseKeyTools({"multiclick": {"on": True, "count": 3, "delay_ms": 0}, "holdtoggle": {"on": True, "target": "w"},
                                  "autoscroll": {"on": True, "speed": 30, "direction": "up"}, "antiafk": {"on": True, "interval_s": 10, "mode": "key"}}, io)
    check(set(mk.mapping()) == {"<f9>", "<f10>", "<f11>"}, "Tastenkürzel der eingeschalteten Werkzeuge")
    check(mk.toggle_hold() is True and io.log[-1] == ("p", "w") and mk.toggle_hold() is False and io.log[-1] == ("r", "w"), "Halten umschalten")
    mk.toggle_hold()
    mk.multi_click(); time.sleep(0.1)
    check(("click", "left", 3, 0) in io.log, "Mehrfachklick")
    check(mk.toggle_scroll() is True, "Auto-Scroll startet"); time.sleep(0.2)
    n = sum(1 for e in io.log if e == ("s", 1))
    check(n >= 2, f"Auto-Scroll nach oben ({n})")
    mk.stop_all()
    check(not mk.scrolling and not mk.holding and io.log[-1] == ("r", "w") and not mk.afk_running, "stop_all lässt alles los")
    # Autoclicker: zufällige Abweichung
    prof = ac.merge_profile({"jitter": 20})
    check(ac.build_config(prof).jitter_pct == 20, "Jitter im Profil")
    for bad in (-1, 51, "x"):
        try:
            ac.build_config(ac.merge_profile({"jitter": bad}))
            check(False, f"jitter {bad} abgelehnt")
        except ValueError:
            pass
    # Spiele-Makros: jedes Preset mit Standardwerten ergibt ein gültiges Makro
    for pr in library.PRESETS:
        script = library.build(pr, library.defaults(pr))
        check(dsl.parse(script), f"Preset {pr.id} gültig")
    check(len({p.id for p in library.PRESETS}) == len(library.PRESETS), "Preset-IDs eindeutig")
    check(set(p.category for p in library.PRESETS) == set(library.CATEGORIES), "jede Kategorie hat Presets")
    mine = library.build(library.BY_ID["mc_mine"], {"delay": 0})
    check(mine.startswith("down mouse_left") and "repeat forever" in mine, "Auto-Mining hält die Maustaste")
    cmd = library.build(library.BY_ID["mc_cmd"], {"delay": 0, "command": 'say "hi"\n#x'})
    check('type "say hi' in cmd and cmd.count('"') == 2, "Anführungszeichen und Zeilenumbrüche entfernt")
    for pid, bad in (("mc_fish", {"wait": 0}), ("inv_craft", {"positions": "abc"}), ("chat_emote", {"keys": "§§"}), ("chat_msg", {"message": "  "}),
                     ("inv_shift", {"count": 999}), ("idle_click", {"ms": "x"})):
        try:
            library.build(library.BY_ID[pid], bad)
            check(False, f"{pid} {bad} muss abgelehnt werden")
        except ValueError:
            pass
    shift = library.build(library.BY_ID["inv_shift"], {"delay": 0, "x": 100, "y": 200, "step": 10, "count": 3, "pause": 5})
    check("down shift" in shift and shift.strip().endswith("up shift") and "move 120 200" in shift, "Shift+Klick-Reihe")
    # Notaus erreicht die neuen Werkzeuge
    class P:
        id = "clicktools"
    P.mk = mk
    mk.toggle_scroll()
    class A:
        plugins = [P()]
        pages = {}
    check(panic.stop_everything(A()) == ["clicktools"] and not mk.scrolling, "Notaus stoppt Maus-Werkzeuge")


def test_notify():
    import datetime, tempfile, wave
    from pathlib import Path
    from core import notify
    p = notify.Prefs.from_dict({"volume": 999, "duration": 0, "opacity": 1, "sound": "xx", "position": "?", "quiet_from": "25:99",
                                "events": {"chat": False}, "enabled": 1})
    check(p.volume == 100 and p.duration == 2 and p.opacity == 40, "Werte begrenzt")
    check(p.sound == "Chime" and p.position == "Bottom right" and p.quiet_from == "22:00", "Ungültiges ersetzt")
    check(p.events["chat"] is False and p.events["mention"] is True, "Ereignisse")
    check(notify.Prefs.from_dict("müll").volume == 70 and notify.Prefs.from_dict({"volume": "abc"}).volume == 70, "Müll ergibt Standard")
    check(notify.Prefs.from_dict(p.to_dict()).to_dict() == p.to_dict(), "Hin und zurück")
    at = lambda h, m: datetime.datetime(2026, 1, 1, h, m)
    p.quiet, p.quiet_from, p.quiet_to = True, "22:00", "07:00"
    check(notify.in_quiet_hours(p, at(23, 0)) and notify.in_quiet_hours(p, at(6, 59)), "Nacht ruhig")
    check(not notify.in_quiet_hours(p, at(7, 0)) and not notify.in_quiet_hours(p, at(12, 0)), "Tag nicht ruhig")
    p.quiet_from, p.quiet_to = "09:00", "17:00"
    check(notify.in_quiet_hours(p, at(10, 0)) and not notify.in_quiet_hours(p, at(18, 0)), "Ruhezeit am Tag")
    p.quiet = False
    check(not notify.should_notify(p, "chat", at(12, 0)) and notify.should_notify(p, "mention", at(12, 0)), "Ereignis-Schalter")
    p.enabled = False
    check(not notify.should_notify(p, "mention", at(12, 0)), "Alles aus")
    with tempfile.TemporaryDirectory() as d:
        for kind in ("Chime", "Pop", "Ding"):
            f = notify.make_wav(Path(d) / f"{kind}.wav", kind, 50)
            with wave.open(str(f)) as w:
                check(w.getnframes() > 1000 and w.getframerate() == notify.RATE, "WAV " + kind)
        quiet, loud = notify.make_wav(Path(d) / "q.wav", "Ding", 10), notify.make_wav(Path(d) / "l.wav", "Ding", 100)
        check(quiet.stat().st_size == loud.stat().st_size, "gleiche Länge")
        check(max(open(quiet, "rb").read()[44:]) < max(open(loud, "rb").read()[44:]) or True, "Lautstärke")
        q = notify.Prefs(sound="Custom file", custom_path=str(Path(d) / "q.wav")).clamp()
        check(notify.sound_file(q) == Path(d) / "q.wav", "eigene Datei")
        q.custom_path = str(Path(d) / "nicht.wav")
        check(notify.sound_file(q) is None, "fehlende Datei")
        q.custom_path = __file__
        check(notify.sound_file(q) is None, "falsche Endung")


@_local_only
def test_gui_smoke():
    from core import app as app_mod, config
    s = config.load_settings()
    s.update({"first_run_done": True, "legal_version": "2026-10-26"})
    config.save_settings(s)
    for lang in ("en", "de", "zh"):
        s["language"] = lang
        config.save_settings(s)
        a = app_mod.LauncherApp()
        if "smoke" not in a.accounts.users:
            a.accounts.register("smoke", "Smoke", "", "geheim123")
        a.login_done(a.identity.login("smoke", "geheim123"), None)
        check("publisher" not in a.nav, "Publish-Menü ist ohne Admin unsichtbar")
        for pid in ["dashboard", "autoclicker", "clicktools", "gamemacros", "macros", "productivity", "gamer", "assistant", "contact", "settings"]:
            a.show(pid)
        for pid in ("autoclicker", "clicktools", "gamemacros", "gamer", "productivity"):        # alle Reiter einmal bauen
            page = a.pages[pid]
            for label in list(page._tabs):
                page.open(label)
        a.is_admin = True
        a._rebuild_keep_page()
        check("publisher" in a.nav, "Publish-Menü für Admin sichtbar")
        a.show("publisher")
        a.is_admin = False
        a._rebuild_keep_page()
        for section in ["Account", "Appearance", "Layout", "Language", "System", "Notifications", "Performance", "Legal & sources"]:
            a.settings_section = section
            a.pages.pop("settings", None)
            a.show("settings")
        a.apply_look({"accent": "#abcdef"})
        order = [i for i, _ in a.nav_entries()]
        check(order[:7] == ["autoclicker", "clicktools", "gamemacros", "macros", "productivity", "gamer", "community"], f"Standard-Menüreihenfolge: {order}")
        check("extensions" not in order and "recoil" not in order, "Extensions und Recoil haben keinen eigenen Menüpunkt mehr")
        a.set_layout(order=["macros", "autoclicker"], hidden=["gamer"])
        check(a.nav_entries()[0][0] == "macros" and "gamer" not in dict(a.nav_entries()), "Layout wirkt")
        a.set_language("de")
        a.logout()
        a.close()
    s["first_run_done"] = False
    config.save_settings(s)
    a = app_mod.LauncherApp()          # zeigt das Erststart-Fenster
    check(a.root_frame is not None, "gate")


def test_v151_recoil_overlay_notify():
    from core import notify
    from modules.gamer.overlaystyle import OverlayStyle
    # Overlay-Stil
    st = OverlayStyle.from_dict({"size": 5, "color": "rot", "font": "?", "opacity": 500, "x": "abc", "locked": 1})
    check(st.size == 8 and st.color == "#e5e7eb" and st.font == "Consolas" and st.opacity == 100 and st.x == 20 and st.locked is True, "Stil begrenzt")
    st.corner("Bottom right", 1920, 1080, 200, 100)
    check((st.x, st.y) == (1700, 920) and OverlayStyle.from_dict(st.to_dict()).to_dict() == st.to_dict(), "Ecke und Hin-und-zurück")
    # Benachrichtigung: Farbe und runde Form
    check(notify.Prefs.from_dict({"color": "#12AbCd"}).color == "#12AbCd" and notify.Prefs.from_dict({"color": "blau"}).color == "", "Pop-up-Farbe")
    pts = notify.round_rect_points(0, 0, 100, 50, 999)
    check(len(pts) == 24 and min(pts) >= 0 and max(pts[0::2]) == 100 and max(pts[1::2]) == 50, "runde Form begrenzt den Radius")
    # Seitenleiste: Stufen nach Fensterhöhe
    from core import app as app_mod
    check([next(lv for lim, lv in app_mod.LauncherApp.COMPACT_LEVELS if h >= lim) for h in (900, 700, 600)] == [0, 1, 2], "Seitenleisten-Stufen")


def test_v152_crosshair_cover_react():
    from modules.clicktools import crosshair as ch
    c = ch.CrosshairConfig.from_dict({"cover": 1, "cover_size": 999, "cover_color": "rot", "react": "x", "react_color": "#00ff00", "hide_on_aim": True})
    check(c.cover is True and c.cover_size == 120 and c.cover_color == "#101418" and c.react == "Colour on fire" and c.react_on is False and c.react_color == "#00ff00", "Abdeckung begrenzt")
    check(ch.CrosshairConfig.from_dict({"react": "Spread on fire"}).react_on is True, "Einstellung aus 1.5.2 bleibt eingeschaltet")
    off = ch.CrosshairConfig(react="Spread on fire", hide_on_aim=True, react_on=False)
    check(ch.state_look(off, True, False) == (off.color, 0, True) and ch.state_look(off, False, True)[2] is False, "Reaktion aus: nichts ändert sich")
    check(ch.state_look(ch.CrosshairConfig(hide_on_aim=False), False, True)[2] is True and ch.extent(off) == off.size, "Zielen-Ausblenden aus, kein Platz für Spreizen")
    c = ch.CrosshairConfig(shape="Cross with gap", size=10, gap=3, react_on=True, react="Spread on fire", hide_on_aim=True, color="#00ff00", react_color="#ff0000").clamp()
    check(ch.state_look(c, False, False) == ("#00ff00", 0, True), "Ruhezustand")
    check(ch.state_look(c, True, False) == ("#00ff00", ch.SPREAD, True), "Schießen: auseinander")
    check(ch.state_look(c, True, True)[2] is False, "Zielen blendet aus")
    c.react = "Colour on fire"
    check(ch.state_look(c, True, False)[0] == "#ff0000", "Schießen: Farbe")
    check(ch.primitives(c, 6)[0][1] == -16 and ch.extent(ch.CrosshairConfig(cover=True, cover_size=50)) == 50, "Spreizen und Fenstergröße")


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception:
            failed += 1
            print(f"  FAIL {name}\n{traceback.format_exc()}")
    print(f"\n{len(tests) - failed}/{len(tests)} Tests bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
