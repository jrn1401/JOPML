"""Eigene Module aus Dateien importieren (Ordner, ZIP oder einzelne .py-Datei).

Importierte Module liegen unter <Programmordner>/user_modules/<name>/ und werden beim nächsten Start geladen (wie die eingebauten
Module: plugin.py mit einer Klasse `Plugin(BasePlugin)`). Ein Modul ist normaler Python-Code und läuft mit allen Rechten des
Programms - deshalb fragt die Oberfläche vor jedem Import ausdrücklich nach. Diese Prüfungen schützen vor Fehlbedienung
(kaputte Archive, Pfad-Tricks in ZIP-Dateien, Überschreiben eingebauter Module), NICHT vor bösartigem Code.
"""
import ast
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from core.i18n import tr

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
ALLOWED_EXT = {".py", ".json", ".txt", ".md", ".png", ".gif", ".ico", ".csv", ".lua"}
MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES = 200, 2 * 1024 * 1024, 8 * 1024 * 1024
RESERVED = {"core", "modules", "tests", "tools", "jopml_user"}


class ImportErrorJOPML(ValueError):
    """Verständlicher Fehlertext für die Oberfläche."""


def user_dir() -> Path:
    from core import config
    d = config.app_dir() / "user_modules"
    d.mkdir(parents=True, exist_ok=True)
    return d


def builtin_names() -> set[str]:
    import modules
    names = set(getattr(modules, "BUILTIN_MODULES", []))
    try:
        import pkgutil
        names |= {i.name for i in pkgutil.iter_modules(modules.__path__) if i.ispkg}
    except Exception:
        pass
    return names


def clean_name(text: str) -> str:
    """Aus einem Datei-/Ordnernamen einen gültigen Modulnamen machen (klein, a-z 0-9 _)."""
    n = re.sub(r"[^a-z0-9_]+", "_", Path(text).stem.lower()).strip("_")
    if n and not n[0].isalpha():
        n = "m_" + n
    return n[:31]


def check_name(name: str, builtin: set[str] | None = None) -> str:
    builtin = builtin_names() if builtin is None else builtin
    if not NAME_RE.match(name or ""):
        raise ImportErrorJOPML(tr("The module name must be 2-31 characters: lowercase letters, digits and _, starting with a letter."))
    if name in builtin or name in RESERVED:
        raise ImportErrorJOPML(tr("A built-in module already uses this name."))
    return name


def _check_files(files: list[tuple[str, int]]) -> None:
    """files = [(relativer Pfad, Größe)]. Prüft Anzahl, Größen, Endungen und Pfade."""
    if not files:
        raise ImportErrorJOPML(tr("The module is empty."))
    if len(files) > MAX_FILES:
        raise ImportErrorJOPML(tr("Too many files in the module (at most {n}).", n=MAX_FILES))
    total = 0
    for rel, size in files:
        p = Path(rel)
        if p.is_absolute() or ".." in p.parts or rel.startswith(("/", "\\")) or ":" in rel:
            raise ImportErrorJOPML(tr("Unsafe path in the module: {p}", p=rel))
        if p.suffix.lower() not in ALLOWED_EXT:
            raise ImportErrorJOPML(tr("File type not allowed in a module: {p}", p=rel))
        if size > MAX_FILE_BYTES:
            raise ImportErrorJOPML(tr("A file in the module is too large: {p}", p=rel))
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ImportErrorJOPML(tr("The module is too large."))
    if not any(Path(r).as_posix() == "plugin.py" for r, _ in files):
        raise ImportErrorJOPML(tr("The module needs a plugin.py file at its top level."))


def _check_plugin_source(path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        raise ImportErrorJOPML(tr("plugin.py cannot be read: {e}", e=f"{type(exc).__name__}: {exc}"))
    if not any(isinstance(n, ast.ClassDef) and n.name == "Plugin" for n in tree.body):
        raise ImportErrorJOPML(tr("plugin.py must define a class named Plugin."))


def _stage_folder(src: Path, stage: Path) -> None:
    files = [(p.relative_to(src).as_posix(), p.stat().st_size) for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    _check_files(files)
    for rel, _ in files:
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, target)


def _stage_zip(src: Path, stage: Path) -> None:
    try:
        z = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise ImportErrorJOPML(tr("This is not a valid ZIP file."))
    with z:
        infos = [i for i in z.infolist() if not i.is_dir() and "__pycache__" not in i.filename]
        names = [i.filename.replace("\\", "/") for i in infos]
        tops = {n.split("/", 1)[0] for n in names}
        strip = ""                                   # genau ein Ordner um alles herum: den Ordner weglassen
        if len(tops) == 1 and all("/" in n for n in names) and "plugin.py" not in names:
            strip = next(iter(tops)) + "/"
        rel = [(n[len(strip):], i.file_size) for n, i in zip(names, infos)]
        _check_files(rel)
        for (r, _), info in zip(rel, infos):
            target = stage / r
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as fin, open(target, "wb") as fout:
                shutil.copyfileobj(fin, fout, 65536)


def import_module_files(src, name: str | None = None, replace: bool = False, root: Path | None = None, builtin: set[str] | None = None) -> str:
    """Importiert `src` (Ordner mit plugin.py, ZIP oder einzelne .py-Datei) nach user_modules/<name>/. Gibt den Namen zurück.
    Fehler als ImportErrorJOPML mit verständlichem Text. Nichts wird halb installiert: erst in einen Zwischenordner, dann umbenennen."""
    src = Path(src)
    root = root or user_dir()
    if not src.exists():
        raise ImportErrorJOPML(tr("File not found."))
    default = src.name if src.is_dir() else src.stem
    name = check_name(name or clean_name(default), builtin)
    target = root / name
    if target.exists() and not replace:
        raise ImportErrorJOPML(tr("A module named {n} is already imported.", n=name))
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="jopml-mod-", dir=root))
    try:
        if src.is_dir():
            _stage_folder(src, stage)
        elif src.suffix.lower() == ".zip":
            _stage_zip(src, stage)
        elif src.suffix.lower() == ".py":
            if src.stat().st_size > MAX_FILE_BYTES:
                raise ImportErrorJOPML(tr("A file in the module is too large: {p}", p=src.name))
            shutil.copyfile(src, stage / "plugin.py")
        else:
            raise ImportErrorJOPML(tr("Choose a .zip file, a folder or a .py file."))
        _check_plugin_source(stage / "plugin.py")
        init = stage / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        stage.rename(target)
        return name
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


TEMPLATE = """from core.plugin_api import BasePlugin


class Plugin(BasePlugin):
    id = "mein_modul"          # eindeutig; darf keinem eingebauten Modul gehören
    name = "My module"
    icon = "🧩"
    version = "1.0.0"
    order = 200
    description = "What my module does."

    def on_load(self):
        pass                   # beim Programmstart

    def create_page(self, parent):
        import customtkinter as ctk
        page = ctk.CTkFrame(parent)
        ctk.CTkLabel(page, text="Hello from my module").pack(padx=20, pady=20)
        return page
"""


def import_module_code(code: str, name: str, replace: bool = False, root: Path | None = None, builtin: set[str] | None = None) -> str:
    """Legt ein Modul aus eingefügtem Quelltext an (wird zur plugin.py). Prüfungen wie beim Datei-Import."""
    code = (code or "").replace("\r\n", "\n")
    if not code.strip():
        raise ImportErrorJOPML(tr("The module is empty."))
    if len(code.encode("utf-8")) > MAX_FILE_BYTES:
        raise ImportErrorJOPML(tr("The module is too large."))
    name = check_name(name, builtin)
    with tempfile.TemporaryDirectory(prefix="jopml-code-") as tmp:
        src = Path(tmp) / f"{name}.py"
        src.write_text(code, encoding="utf-8")
        return import_module_files(src, name, replace=replace, root=root, builtin=builtin)


def installed(root: Path | None = None) -> list[str]:
    root = root or user_dir()
    return sorted(p.name for p in root.iterdir() if p.is_dir() and NAME_RE.match(p.name) and (p / "plugin.py").is_file()) if root.exists() else []


def remove_module(name: str, root: Path | None = None) -> bool:
    root = root or user_dir()
    if not NAME_RE.match(name or ""):
        return False
    target = root / name
    if target.is_dir() and target.parent == root:
        shutil.rmtree(target, ignore_errors=True)
        return True
    return False


# ---------------------------------------------------------------- Lua-Skripte (Modul "Lua scripts")
LUA_MAX_BYTES = 300_000


def lua_dir() -> Path:
    from core import config
    d = config.app_dir() / "lua_scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lua_scripts(root: Path | None = None) -> list[str]:
    root = root or lua_dir()
    return sorted(p.stem for p in root.glob("*.lua") if NAME_RE.match(p.stem)) if root.exists() else []


def check_lua_text(text: str) -> None:
    """Wirft ImportErrorJOPML, wenn das kein ladbarer Lua-Text ist (Größe, Binärdaten, Vorab-Bytecode)."""
    if not isinstance(text, str) or not text.strip():
        raise ImportErrorJOPML(tr("The script is empty."))
    if len(text.encode("utf-8")) > LUA_MAX_BYTES:
        raise ImportErrorJOPML(tr("The script is too large (at most 300 KB)."))
    if "\x00" in text or text.startswith("\x1bLua"):
        raise ImportErrorJOPML(tr("Only Lua source text can be added, not compiled Lua."))


def read_lua_file(path) -> str:
    p = Path(path)
    if p.suffix.lower() not in (".lua", ".txt"):
        raise ImportErrorJOPML(tr("Choose a .lua or .txt file."))
    if p.stat().st_size > LUA_MAX_BYTES:
        raise ImportErrorJOPML(tr("The script is too large (at most 300 KB)."))
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ImportErrorJOPML(tr("Only Lua source text can be added, not compiled Lua."))
    check_lua_text(text)
    return text


def import_lua_script(text: str, name: str, replace: bool = False, root: Path | None = None) -> str:
    """Speichert ein Lua-Skript als <name>.lua. Gibt den Namen zurück."""
    if not NAME_RE.match(name or ""):
        raise ImportErrorJOPML(tr("The module name must be 2-31 characters: lowercase letters, digits and _, starting with a letter."))
    check_lua_text(text)
    root = root or lua_dir()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{name}.lua"
    if target.exists() and not replace:
        raise ImportErrorJOPML(tr("A script with this name already exists."))
    target.write_text(text, encoding="utf-8")
    return name


def read_lua(name: str, root: Path | None = None) -> str:
    root = root or lua_dir()
    if not NAME_RE.match(name or "") or not (root / f"{name}.lua").is_file():
        raise ImportErrorJOPML(tr("This script cannot be found."))
    return (root / f"{name}.lua").read_text(encoding="utf-8")


def remove_lua(name: str, root: Path | None = None) -> bool:
    root = root or lua_dir()
    if not NAME_RE.match(name or ""):
        return False
    p = root / f"{name}.lua"
    if p.is_file():
        p.unlink()
        return True
    return False
