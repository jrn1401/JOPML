"""Modul "Recoil Arena": startet das eigenständige Übungsspiel (eigenes Programm) oder installiert es aus einer ZIP-Datei."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from core import config, net
from core.version import APP_ID, APP_VERSION, SUPABASE_URL
from core.i18n import tr
from core.plugin_api import BasePlugin

APP_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_URL = SUPABASE_URL.rstrip("/") + "/storage/v1/object/public/releases/arena.json"
MAX_ZIP = 120 * 1024 * 1024
EXE_NAMES = ("JOPML-Arena.exe", "JOPML-Arena", "JOPML-Arena.app")


def builtin() -> bool:
    """True, wenn die Arena in der gebauten EXE steckt (Start mit 'JaronsOPMakro.exe --arena'). Dann ist kein Download nötig."""
    if not getattr(sys, "frozen", False):
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("arena.ui") is not None
    except Exception:
        return False


def install_dir() -> Path:
    return config.app_dir() / "arena_app"


def find_install(extra: list | None = None) -> tuple | None:
    """Sucht die Arena: ("exe", Datei) oder ("source", Ordner, der das Paket 'arena' enthält). Zuerst die selbst installierte."""
    if builtin():
        return ("builtin", Path(sys.executable))
    roots = [install_dir()] + list(extra or []) + [APP_ROOT]
    for r in roots:
        r = Path(r)
        for n in EXE_NAMES:
            if (r / n).is_file():
                return ("exe", r / n)
    for r in roots:
        r = Path(r)
        if (r / "arena" / "__main__.py").is_file():
            return ("source", r)
    return None


def python_command() -> list | None:
    """Ein Python mit tkinter, um die Arena aus dem Quellcode zu starten. In der gebauten EXE gibt es keins mitgeliefertes."""
    if not getattr(sys, "frozen", False):
        return [sys.executable]
    for name in ("py", "python3", "python"):
        p = shutil.which(name)
        if p:
            return [p] + (["-3"] if name == "py" else [])
    return None


def bundled_version() -> str:
    """Version der Arena, die in diesem Programm mitgeliefert wird (Quellcode-Betrieb), sonst ''."""
    if getattr(sys, "frozen", False):
        try:
            import arena
            return str(arena.VERSION) if builtin() else ""
        except Exception:
            return ""
    try:
        text = (APP_ROOT / "arena" / "__init__.py").read_text(encoding="utf-8")
        import re
        m = re.search(r'VERSION\s*=\s*"([\d.]+)"', text)
        return m.group(1) if m else ""
    except OSError:
        return ""


def installed_version() -> str:
    try:
        return json.loads((install_dir() / "INSTALLED.json").read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        return ""


def fetch_manifest(timeout: float = 12) -> dict:
    """arena.json aus dem Bereich 'releases'. Fehler: urllib.error.URLError / ValueError."""
    req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
    with net.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read(100_000).decode("utf-8"))
    if not isinstance(d, dict) or not str(d.get("url", "")).startswith("https://"):
        raise ValueError("invalid manifest")
    return d


def download_zip(url: str, sha256: str, progress=None) -> str:
    """Lädt das ZIP in eine Temp-Datei, prüft Größe und SHA-256. Gibt den Pfad zurück."""
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
    tmp = Path(tempfile.mkdtemp(prefix="jopml_arena_")) / "arena.zip"
    h, done = hashlib.sha256(), 0
    with net.urlopen(req, timeout=30) as r, open(tmp, "wb") as fh:
        total = int(r.headers.get("Content-Length") or 0)
        while chunk := r.read(64 * 1024):
            done += len(chunk)
            if done > MAX_ZIP:
                raise ValueError(tr("The archive is too large."))
            fh.write(chunk)
            h.update(chunk)
            if progress and total:
                progress(done / total)
    if sha256 and h.hexdigest().lower() != sha256.lower():
        raise ValueError(tr("Checksum mismatch – update cancelled."))
    return str(tmp)


def numpy_ready() -> bool:
    py = python_command()
    if py is None:
        return True            # gebaute EXE bringt alles mit
    try:
        return subprocess.run(py + ["-c", "import numpy, tkinter"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def safe_extract(zip_path: str, dest: Path) -> int:
    """Entpackt nur Dateien innerhalb von dest (kein ../, keine absoluten Pfade). Gibt die Zahl der Dateien zurück."""
    dest = dest.resolve()
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        names = [i for i in zf.infolist() if not i.is_dir()]
        for info in names:
            target = (dest / info.filename).resolve()
            if dest != target and dest not in target.parents:
                raise ValueError(tr("Unsafe path in the archive: {n}", n=info.filename))
        if not any(i.filename.replace("\\", "/").split("/")[-2:] == ["arena", "__main__.py"] or i.filename in EXE_NAMES for i in names):
            raise ValueError(tr("This ZIP does not contain the Arena."))
        if sum(i.file_size for i in names) > 300 * 1024 * 1024:
            raise ValueError(tr("The archive is too large."))
        staging = dest.with_name(dest.name + "_new")
        backup = dest.with_name(dest.name + "_old")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            for info in names:
                t = staging / info.filename
                t.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(t, "wb") as out:
                    shutil.copyfileobj(src, out)
                n += 1
            # Erst die fertig entpackte Fassung austauschen: schlägt etwas fehl (z. B. läuft die Arena noch), bleibt die alte Fassung heil.
            shutil.rmtree(backup, ignore_errors=True)
            if dest.exists():
                dest.rename(backup)
            try:
                staging.rename(dest)
            except OSError:
                if backup.exists() and not dest.exists():
                    backup.rename(dest)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return n


def version_in(root: Path) -> str:
    try:
        import re
        m = re.search(r'VERSION\s*=\s*"([\d.]+)"', (root / "arena" / "__init__.py").read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def mark_installed(version: str) -> None:
    try:
        (install_dir() / "INSTALLED.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    except OSError:
        pass


def own_install() -> bool:
    """True, wenn die Arena über den Launcher installiert wurde (nicht nur als Quellcode neben dem Programm liegt)."""
    if builtin():
        return False
    d = install_dir()
    return (d / "arena" / "__main__.py").is_file() or any((d / n).is_file() for n in EXE_NAMES)


def _newer(a: str, b: str) -> bool:
    from core.updater import parse_version
    try:
        return bool(a) and parse_version(a) > parse_version(b or "0")
    except Exception:
        return False


def update_info(timeout: float = 8) -> dict | None:
    """Prüft, ob es für die selbst installierte Arena eine neuere Fassung auf dem Server gibt.
    Gibt {"installed", "available", "manifest"} zurück, sonst None (nichts installiert, aktuell oder Server nicht erreichbar)."""
    if not own_install():
        return None
    try:
        m = fetch_manifest(timeout)
    except (urllib.error.URLError, ValueError, OSError):
        return None
    cur, new = installed_version(), str(m.get("version", ""))
    return {"installed": cur, "available": new, "manifest": m} if _newer(new, cur) else None


def sync(install_if_missing: bool = False, use_server: bool = True, progress=None) -> tuple:
    """Bringt die Arena auf den neuesten Stand. Gibt (Zustand, Text) zurück; Zustand: "none", "installed", "updated" oder "error".
    Zuerst der Server (releases/arena.json), sonst die mit dem Programm mitgelieferte Fassung. Eine laufende Installation bleibt bei Fehlern unverändert."""
    if builtin():
        return ("none", bundled_version())              # steckt in der EXE: wird mit dem Launcher-Update mitgeliefert
    own = own_install()
    if not own and not install_if_missing:
        return ("none", "")
    cur = installed_version() if own else ""
    try:
        if use_server:
            try:
                m = fetch_manifest()
                if _newer(str(m.get("version", "")), cur):
                    path = download_zip(m["url"], str(m.get("sha256", "")), progress)
                    safe_extract(path, install_dir())
                    v = version_in(install_dir()) or str(m.get("version", ""))
                    mark_installed(v)
                    return ("updated" if own else "installed", v)
            except (urllib.error.URLError, ValueError, OSError, KeyError):
                pass        # Server leer oder nicht erreichbar: weiter mit der mitgelieferten Fassung
        bv = bundled_version()
        src = APP_ROOT / "arena"
        if bv and (src / "__main__.py").is_file() and _newer(bv, cur):
            tmp = install_dir().with_name("arena_app_new")
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(src, tmp / "arena", ignore=shutil.ignore_patterns("__pycache__"))
            old = install_dir().with_name("arena_app_old")
            shutil.rmtree(old, ignore_errors=True)
            if install_dir().exists():
                install_dir().rename(old)
            tmp.rename(install_dir())
            shutil.rmtree(old, ignore_errors=True)
            mark_installed(bv)
            return ("updated" if own else "installed", bv)
    except Exception as exc:
        return ("error", f"{type(exc).__name__}: {str(exc)[:160]}")
    return ("none", cur)


class Plugin(BasePlugin):
    id = "arena"
    name = "Recoil Arena"
    icon = "🎯"
    version = "1.2.0"
    order = 45
    description = "A separate practice game with invented weapons, bots, colors and different play styles."

    def on_load(self):
        self.proc = None

    def status(self) -> str:
        f = find_install()
        if f is None:
            return tr("Not installed. Install the Arena ZIP below.")
        if f[0] == "builtin":
            return tr("Built into the launcher (version {v}).", v=bundled_version())
        return tr("Found: {p}", p=str(f[1]))

    def launch(self) -> str:
        """Startet die Arena als eigenen Prozess. Gibt '' oder eine Fehlermeldung zurück."""
        f = find_install()
        if f is None:
            return tr("The Arena is not installed yet.")
        try:
            if f[0] == "builtin":
                from core import relaunch
                self.proc = subprocess.Popen([sys.executable, "--arena"], env=relaunch.clean_env())
            elif f[0] == "exe":
                self.proc = subprocess.Popen([str(f[1])], cwd=str(f[1].parent))
            else:
                py = python_command()
                if py is None:
                    return tr("Python with tkinter is needed to start the Arena from source (or use the built JOPML-Arena.exe).")
                self.proc = subprocess.Popen(py + ["-m", "arena"], cwd=str(f[1]))
        except OSError as exc:
            return f"{type(exc).__name__}: {exc}"
        return ""

    def install(self, zip_path: str) -> int:
        n = safe_extract(zip_path, install_dir())
        mark_installed(version_in(install_dir()))
        return n

    def download_game(self, progress=None) -> str:
        """Lädt die Arena vom Server (releases/arena.json) und installiert sie. Fehlt sie dort, wird die mitgelieferte Fassung kopiert.
        Gibt einen Text mit dem Ergebnis zurück; Fehler als Exception."""
        if builtin():
            return tr("Built into the launcher (version {v}).", v=bundled_version())
        try:
            m = fetch_manifest()
            path = download_zip(m["url"], str(m.get("sha256", "")), progress)
            self.install(path)
            return tr("Downloaded and installed (version {v}).", v=str(m.get("version", "")))
        except (urllib.error.URLError, ValueError, OSError, KeyError) as exc:
            src = APP_ROOT / "arena"
            if not (src / "__main__.py").is_file():
                raise ValueError(tr("The game is not available for download yet ({e}).", e=str(exc)[:120])) from None
            dest = install_dir()
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(src, dest / "arena", ignore=shutil.ignore_patterns("__pycache__"))
            mark_installed(bundled_version())
            return tr("Installed the version that comes with this program ({v}).", v=bundled_version())

    def install_numpy(self) -> str:
        """pip install numpy für das Python, das die Arena startet (nur im Quellcode-Betrieb nötig)."""
        py = python_command()
        if py is None:
            return tr("Python was not found.")
        r = subprocess.run(py + ["-m", "pip", "install", "--user", "numpy"], capture_output=True, text=True, timeout=600)
        return "" if r.returncode == 0 else (r.stderr or r.stdout)[-300:]

    def export_zip(self, dest: str) -> int:
        """Packt die mitgelieferte Arena (Quellcode) als ZIP zum Weitergeben."""
        src = APP_ROOT / "arena"
        if not (src / "__main__.py").is_file():
            raise ValueError(tr("The Arena sources are not part of this program version."))
        n = 0
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(src.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    zf.write(p, "arena/" + str(p.relative_to(src)).replace("\\", "/"))
                    n += 1
            dist = APP_ROOT / "tools" / "arena_dist"
            if dist.is_dir():
                for p in sorted(dist.iterdir()):
                    if p.is_file():
                        zf.write(p, p.name)
        return n

    def dashboard_summary(self):
        return tr("A separate practice game with bots, weapons and colors.")

    def create_page(self, parent):
        from .page import ArenaPage
        return ArenaPage(parent, self)
