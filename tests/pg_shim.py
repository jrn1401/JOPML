"""Mini-PostgREST für Tests: nimmt POST /rest/v1/rpc/<funktion> entgegen und führt die Funktion in einer ECHTEN lokalen
PostgreSQL-Datenbank aus (Rolle `authenticated`, Nutzer aus dem Token "tok-<uuid>"). So laufen Client-Code und
SQL-Funktionen der Community gemeinsam – ohne Supabase und ohne Netzwerk.

Voraussetzung: PostgreSQL 16 (Debian/Ubuntu-Paket) und root-Rechte (für `runuser -u postgres`). Sonst werden die Tests übersprungen.
"""
import http.server
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = [
    "20261026000000_jopml_init.sql", "20261026000200_jopml_pseudo_mail.sql", "20261028000000_jopml_layout_settings.sql",
    "20261028000100_jopml_filter.sql", "20261028000200_jopml_community.sql", "20261028000300_jopml_name_filter.sql",
    "20261028201220_jopml_admin_overview.sql",
    "20261029000000_jopml_modtools.sql", "20261030000000_jopml_market.sql", "20261030000100_jopml_email_invite.sql",
    "20261031000000_jopml_filter_world.sql", "20261031000100_jopml_module_share.sql",
    "20261031000200_jopml_recoil_scores.sql", "20261031000300_jopml_permissions.sql",
    "20261031000400_jopml_190_limits_reports.sql", "20261031000500_jopml_1100_tickets_budget.sql",
    "20261031000600_jopml_1100_release_notes.sql", "20261031000700_jopml_market_downup.sql",
]


def available() -> bool:
    return bool(shutil.which("psql") and shutil.which("runuser") and os.geteuid() == 0 and Path("/usr/lib/postgresql").exists())


def _psql(db: str, *args: str, sql: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["runuser", "-u", "postgres", "--", "psql", "-q", "-At", "-X", "-v", "ON_ERROR_STOP=1", "-d", db, *args]
    return subprocess.run(cmd, input=sql, capture_output=True, text=True)


def ensure_server() -> None:
    if _psql("postgres", "-c", "select 1").returncode != 0:
        subprocess.run(["pg_ctlcluster", "16", "main", "start"], capture_output=True)
        for _ in range(30):
            if _psql("postgres", "-c", "select 1").returncode == 0:
                return
            import time
            time.sleep(0.5)
        raise RuntimeError("PostgreSQL startet nicht")


def create_db() -> str:
    ensure_server()
    db = "jt_" + uuid.uuid4().hex[:10]
    subprocess.run(["runuser", "-u", "postgres", "--", "createdb", db], check=True, capture_output=True)
    r = _psql(db, "-f", str(ROOT / "tests/sql/supabase_stub.sql"))
    if r.returncode:
        raise RuntimeError(r.stderr)
    # Admin-Ersatz vor der Community-Migration, Rest in Reihenfolge
    for f in MIGRATIONS:
        if f.startswith("20261028000200"):
            r = _psql(db, "-f", str(ROOT / "tests/sql/admin_stub.sql"))
            if r.returncode:
                raise RuntimeError(r.stderr)
        r = _psql(db, "-f", str(ROOT / "supabase/migrations" / f))
        if r.returncode:
            raise RuntimeError(f"{f}: {r.stderr}")
    return db


def drop_db(db: str) -> None:
    subprocess.run(["runuser", "-u", "postgres", "--", "dropdb", "--if-exists", db], capture_output=True)


def add_user(db: str, email: str) -> str:
    uid = str(uuid.uuid4())
    r = _psql(db, "-c", f"insert into auth.users (id, email) values ('{uid}', '{email}')")
    if r.returncode:
        raise RuntimeError(r.stderr)
    return uid


def sql(db: str, text: str) -> str:
    r = _psql(db, sql=text)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def _lit(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


class _Handler(http.server.BaseHTTPRequestHandler):
    db = ""

    def log_message(self, *a):
        pass

    def do_POST(self):
        m = re.match(r"^/rest/v1/rpc/([a-z_0-9]+)$", self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        if not m or not tok.startswith("tok-"):
            return self._send(401, {"message": "not_authenticated"})
        fn = m.group(1)
        if set(body) == {"p"}:
            args = _lit(body["p"])
        else:
            args = ", ".join(f"{k} => {_lit(v)}" for k, v in body.items())
        sqltext = (f"set role authenticated; set request.jwt.claim.sub = '{tok[4:]}'; "
                   f"select coalesce(public.{fn}({args})::text, 'null');")
        r = _psql(self.db, sql=sqltext)
        if r.returncode:
            msg = re.search(r"ERROR:\s+(.*)", r.stderr)
            return self._send(400, {"message": (msg.group(1) if msg else r.stderr).strip()})
        out = r.stdout.strip().splitlines()
        self._send(200, json.loads(out[-1]) if out else None)

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_shim(db: str):
    handler = type("H", (_Handler,), {"db": db})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
