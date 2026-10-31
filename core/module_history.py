"""Versionsverlauf für eigene Module: vor jeder Änderung durch die KI (oder beim Ersetzen) wird die alte plugin.py gesichert,
damit man mit einem Klick zurückgehen kann. Ablage: <Datenordner>/module_history/<name>/<Zeitstempel>.py (höchstens 15 Stände je Modul)."""
import difflib
import time

from core import config, module_import

KEEP = 15


def _dir(name: str):
    return config.app_dir() / "module_history" / module_import.clean_name(name)


def current_path(name: str, root=None):
    return (root or module_import.user_dir()) / name / "plugin.py"


def current_code(name: str, root=None) -> str | None:
    p = current_path(name, root)
    try:
        return p.read_text(encoding="utf-8") if p.is_file() else None
    except OSError:
        return None


def save_version(name: str, code: str | None = None, root=None, note: str = "") -> str | None:
    """Sichert `code` (Standard: die aktuelle plugin.py). Gibt den Stand-Namen zurück oder None, wenn nichts zu sichern ist / sich nichts änderte."""
    code = current_code(name, root) if code is None else code
    if not code or not code.strip():
        return None
    versions = list_versions(name)
    if versions and read_version(name, versions[0][0]) == code:
        return None
    d = _dir(name)
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    n = 0
    while (d / f"{stamp}{'-%d' % n if n else ''}.py").exists():
        n += 1
    fn = f"{stamp}{'-%d' % n if n else ''}.py"
    (d / fn).write_text(code, encoding="utf-8")
    for old in sorted(d.glob("*.py"))[:-KEEP]:
        old.unlink(missing_ok=True)
    return fn


def list_versions(name: str) -> list[tuple[str, str]]:
    """[(Stand-Name, lesbares Datum)] neueste zuerst."""
    d = _dir(name)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.py"), reverse=True):
        st = f.stem
        try:
            nice = time.strftime("%d.%m.%Y %H:%M:%S", time.strptime(st[:15], "%Y%m%d-%H%M%S"))
        except ValueError:
            nice = st
        out.append((f.name, nice))
    return out


def read_version(name: str, version: str) -> str | None:
    f = _dir(name) / version
    if f.parent != _dir(name) or not f.is_file():          # kein Ausbrechen aus dem Ordner
        return None
    return f.read_text(encoding="utf-8")


def diff(old: str, new: str, context: int = 3, limit: int = 600) -> list[str]:
    """Zeilen im Unified-Diff-Format ('+', '-', '@@'); höchstens `limit` Zeilen."""
    lines = list(difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), "current", "proposed", n=context, lineterm=""))
    return lines[:limit] + ([f"… ({len(lines) - limit} more lines)"] if len(lines) > limit else [])


def stats(old: str, new: str) -> tuple[int, int]:
    """(hinzugefügte, entfernte Zeilen)."""
    add = rem = 0
    for ln in difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), lineterm="", n=0):
        if ln.startswith("+") and not ln.startswith("+++"):
            add += 1
        elif ln.startswith("-") and not ln.startswith("---"):
            rem += 1
    return add, rem


def apply_code(name: str, code: str, builtin=None, root=None) -> str:
    """Legt/ersetzt das Modul mit `code` (alle Prüfungen wie beim Import) und sichert vorher den alten Stand. Gibt den Modulnamen zurück."""
    existed = current_code(name, root) is not None
    if existed:
        save_version(name, None, root)
    return module_import.import_module_code(code, name, replace=existed, root=root, builtin=builtin)


def restore(name: str, version: str, builtin=None, root=None) -> str:
    """Stellt einen alten Stand wieder her; der aktuelle wird vorher ebenfalls gesichert (Rückgängig ist so selbst rückgängig machbar)."""
    code = read_version(name, version)
    if code is None:
        raise module_import.ImportErrorJOPML("This version does not exist any more.")
    return apply_code(name, code, builtin, root)
