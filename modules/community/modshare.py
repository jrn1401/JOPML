"""Module teilen (Client-Seite): eigene importierte Module hochladen, fremde ansehen und installieren, melden, prüfen (Admin).

Ein Modul ist Python-Code und läuft mit allen Rechten des Programms. Darum gilt hier:
- Geteilt werden nur Textdateien (.py .json .txt .md .csv), höchstens 40 Dateien und 300 KB.
- Der Server zeigt ein Modul anderen erst, wenn ein Admin es freigegeben hat (Admin-Konten teilen sofort).
- Vor jeder Installation sieht man den vollständigen Code und eine Liste auffälliger Aufrufe. Diese Liste ist eine Hilfe zum
  Lesen, KEINE Garantie: harmlos aussehender Code kann trotzdem schaden, auffälliger Code kann harmlos sein.
- Installiert wird über dieselbe Importfunktion wie bei Dateien (core/module_import.py) und erst nach ausdrücklicher Bestätigung.
Alle Netzwerkaufrufe blockieren -> im Hintergrund-Thread nutzen.
"""
import ast
import re
import shutil
import tempfile
from pathlib import Path

from core import chatfilter, module_import
from core.i18n import tr

from .service import CommunityError

TEXT_EXT = {".py", ".json", ".txt", ".md", ".csv"}
MAX_FILES, MAX_TOTAL = 40, 300_000
PATH_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,80}$")

# Aufrufe/Importe, auf die man vor der Installation besonders achten sollte (Name -> Hinweis)
RISKY_IMPORTS = {
    "subprocess": "Starts other programs.", "socket": "Opens network connections.", "urllib": "Accesses the internet.",
    "requests": "Accesses the internet.", "http": "Accesses the internet.", "ftplib": "Accesses the internet.",
    "smtplib": "Sends e-mails.", "ctypes": "Calls low-level system functions.", "winreg": "Reads or changes the Windows registry.",
    "pickle": "Loads objects that can run code.", "marshal": "Loads objects that can run code.", "base64": "Decodes hidden data (often used to hide code).",
    "webbrowser": "Opens web pages.", "shutil": "Copies or deletes files and folders.", "pynput": "Can read the keyboard and mouse.",
    "keyboard": "Can read the keyboard.", "pyperclip": "Reads the clipboard.", "sqlite3": "Reads databases (browsers keep passwords in them).",
}
RISKY_CALLS = {
    "eval": "Runs text as code.", "exec": "Runs text as code.", "compile": "Builds code from text.", "__import__": "Loads modules by name (can hide what is used).",
    "system": "Runs a system command.", "popen": "Runs a system command.", "startfile": "Opens a file or program.",
    "remove": "Deletes files.", "unlink": "Deletes files.", "rmtree": "Deletes folders.", "rmdir": "Deletes folders.",
    "getpass": "Asks for passwords.", "urlopen": "Accesses the internet.", "getattr": "Looks up names by text (can hide what is called).",
}


def risk_notes(files: dict) -> list[str]:
    """Auffällige Stellen im Code als lesbare Hinweise (übersetzt). Leere Liste = nichts Auffälliges gefunden, aber keine Garantie."""
    found: dict[str, str] = {}
    for path, text in files.items():
        if not path.lower().endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            found[f"syntax:{path}"] = tr("The file {p} is not valid Python code.", p=path)
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in RISKY_IMPORTS:
                    found.setdefault(f"imp:{n}", f"import {n} – " + tr(RISKY_IMPORTS[n]))
            if isinstance(node, ast.Call):
                fn = node.func
                n = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                if n in RISKY_CALLS:
                    found.setdefault(f"call:{n}", f"{n}() – " + tr(RISKY_CALLS[n]))
                if n == "open" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and any(c in str(node.args[1].value) for c in "wax+"):
                    found.setdefault("call:open_w", "open(…, 'w') – " + tr("Writes files."))
        if re.search(r"https?://", text):
            found.setdefault("url", tr("Contains web addresses."))
        if re.search(r"[A-Za-z0-9+/]{200,}={0,2}", text):
            found.setdefault("blob", tr("Contains a long block of encoded text (may hide something)."))
    return list(found.values())


def collect_installed(name: str, root: Path | None = None) -> dict:
    """Liest ein importiertes Modul (user_modules/<name>/) als {Pfad: Text}. Wirft CommunityError, wenn es nicht teilbar ist."""
    root = root or module_import.user_dir()
    base = root / name
    if not module_import.NAME_RE.match(name or "") or not (base / "plugin.py").is_file():
        raise CommunityError(tr("This module cannot be found."))
    files: dict[str, str] = {}
    other: list[str] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(base).as_posix()
        if rel == "__init__.py" and p.stat().st_size == 0:
            continue                                         # leere Paketdatei legt der Import selbst an
        if p.suffix.lower() not in TEXT_EXT:
            other.append(rel)
            continue
        try:
            files[rel] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            other.append(rel)
    if other:
        raise CommunityError(tr("Only text files can be shared (.py .json .txt .md .csv). Not shareable: {f}", f=", ".join(other[:5])))
    return files


def check_files(files: dict) -> str:
    if not isinstance(files, dict) or "plugin.py" not in files:
        return tr("The module needs a plugin.py file at its top level.")
    if len(files) > MAX_FILES:
        return tr("Too many files in the module (at most {n}).", n=MAX_FILES)
    total = 0
    for path, text in files.items():
        p = Path(path)
        if not PATH_RE.match(path) or ".." in path or "//" in path or p.suffix.lower() not in TEXT_EXT:
            return tr("File type not allowed in a module: {p}", p=path)
        if not isinstance(text, str):
            return tr("The module is not valid.")
        total += len(text)
    if total > MAX_TOTAL:
        return tr("The module is too large.")
    return ""


def check_for_publish(name: str, title: str, descr: str, files: dict) -> str:
    """Gibt '' oder einen Fehlertext zurück (gleiche Prüfungen wie der Server)."""
    if not module_import.NAME_RE.match(name or ""):
        return tr("The module name must be 2-31 characters: lowercase letters, digits and _, starting with a letter.")
    t = (title or "").strip()
    if not 3 <= len(t) <= 60:
        return tr("The title needs 3–60 characters.")
    if len(descr or "") > 500:
        return tr("The description is too long (max. 500 characters).")
    err = check_files(files)
    if err:
        return err
    try:
        tree = ast.parse(files["plugin.py"])
    except (SyntaxError, ValueError) as exc:
        return tr("plugin.py cannot be read: {e}", e=f"{type(exc).__name__}: {exc}")
    if not any(isinstance(n, ast.ClassDef) and n.name == "Plugin" for n in tree.body):
        return tr("plugin.py must define a class named Plugin.")
    for text in (t, descr or ""):
        v = chatfilter.check(text)
        if not v.ok:
            return chatfilter.explain(v)
    return ""


def install(files: dict, name: str, replace: bool = False, root: Path | None = None, builtin: set | None = None) -> str:
    """Schreibt die Dateien in einen Zwischenordner und importiert sie wie jeden Ordner (alle Prüfungen von module_import)."""
    err = check_files(files)
    if err:
        raise module_import.ImportErrorJOPML(err)
    tmp = Path(tempfile.mkdtemp(prefix="jopml-share-"))
    try:
        src = tmp / name
        for rel, text in files.items():
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return module_import.import_module_files(src, name, replace=replace, root=root, builtin=builtin)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class ModShareService:
    def __init__(self, svc):
        self.svc = svc

    def _rpc(self, name, p=None):
        return self.svc._rpc(name, p)

    def publish(self, name: str, title: str, descr: str, files: dict, version: str = "1.0.0") -> dict:
        err = check_for_publish(name, title, descr, files)
        if err:
            raise CommunityError(err)
        return self._rpc("jopml_mod_publish", {"name": name, "title": title.strip(), "descr": (descr or "").strip(), "version": version or "1.0.0", "files": files})

    def browse(self, q: str = "", sort: str = "new", offset: int = 0) -> list[dict]:
        return self._rpc("jopml_mod_list", {"q": q, "sort": sort, "offset": offset, "limit": 30}) or []

    def get(self, mod_id: int) -> dict:
        d = self._rpc("jopml_mod_get", {"id": mod_id})
        err = check_files(d.get("files"))               # auch vom Server kommende Module werden geprüft, bevor wir sie anzeigen
        if err or not module_import.NAME_RE.match(d.get("name") or ""):
            raise CommunityError(err or tr("The module is not valid."))
        return d

    def report(self, mod_id: int, reason: str) -> None:
        self._rpc("jopml_mod_report", {"id": mod_id, "reason": reason})

    def delete(self, mod_id: int) -> None:
        self._rpc("jopml_mod_delete", {"id": mod_id})

    def pending(self) -> list[dict]:
        return self._rpc("jopml_mod_pending", {}) or []

    def review(self, mod_id: int, approve: bool, note: str = "") -> None:
        self._rpc("jopml_mod_review", {"id": mod_id, "approve": approve, "note": note})
