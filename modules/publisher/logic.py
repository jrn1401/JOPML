"""Veröffentlichen: reine Logik (ohne Oberfläche, gut testbar).

Ablauf: Dateien (EXE/DMG) nach Supabase Storage hochladen, danach eine neue version.json schreiben.
Jedes Paket in der version.json hat eine eigene "version", damit Windows und Mac unabhängig aktualisiert werden können.
"""
import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

MAX_BYTES = 150 * 1024 * 1024          # Grenze des Buckets
PLATFORMS = {".exe": ("windows", "JaronsOPMakro-{v}.exe"), ".dmg": ("macos", "JOPML-{v}.dmg")}
VERSION_RE = re.compile(r"^\d+(\.\d+){1,3}$")


def parse_version(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def check_version(v: str) -> str:
    v = (v or "").strip()
    if not VERSION_RE.match(v):
        raise ValueError("Die Version muss wie 1.2.0 aussehen.")
    return v


def platform_of(path: str) -> tuple[str, str]:
    """Gibt (plattform, speicherort-vorlage) zurück oder wirft ValueError."""
    ext = Path(path).suffix.lower()
    if ext not in PLATFORMS:
        raise ValueError("Nur .exe (Windows) und .dmg (Mac) sind erlaubt.")
    return PLATFORMS[ext]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(current: dict | None, version: str, notes: str, packages: dict) -> dict:
    """packages: {plattform: {"url": ..., "sha256": ...}}. Fehlende Plattformen bleiben wie bisher."""
    version = check_version(version)
    old = (current or {}).get("packages", {}) if isinstance((current or {}).get("packages"), dict) else {}
    out = {}
    for plat, pkg in old.items():
        if isinstance(pkg, dict) and pkg.get("url"):
            out[plat] = {"url": pkg["url"], "sha256": pkg.get("sha256", ""),
                         "version": pkg.get("version") or (current or {}).get("version", "0")}
            if pkg.get("rollback"):
                out[plat]["rollback"] = True
    for plat, pkg in packages.items():
        out[plat] = {"url": pkg["url"], "sha256": pkg["sha256"], "version": version}
    top = max((p["version"] for p in out.values()), key=parse_version)
    return {"version": top, "notes": notes.strip(), "packages": out}


# ---------------------------------------------------------------- Versionsliste und Zurückstellen
def _name_regex(template: str) -> re.Pattern:
    return re.compile("^" + re.escape(template).replace(re.escape("{v}"), r"(\d+(?:\.\d+){1,3})") + "$")


_NAME_RES = {plat: _name_regex(tpl) for plat, tpl in PLATFORMS.values()}


def parse_release_name(name: str):
    """'JaronsOPMakro-1.4.0.exe' -> ('windows', '1.4.0'); alles andere (z. B. version.json) -> None."""
    for plat, rx in _NAME_RES.items():
        m = rx.match(name or "")
        if m:
            return plat, m.group(1)
    return None


def release_entries(objects, manifest) -> list[dict]:
    """Macht aus der Dateiliste des Buckets eine sortierte Liste (je Plattform neueste zuerst) und markiert, was gerade aktiv ist."""
    from urllib.parse import unquote
    pk = (manifest or {}).get("packages", {}) if isinstance((manifest or {}).get("packages"), dict) else {}
    out = []
    for o in objects or []:
        name = str(o.get("name", ""))
        parsed = parse_release_name(name)
        if not parsed:
            continue
        plat, ver = parsed
        url = unquote(str(pk.get(plat, {}).get("url", ""))) if isinstance(pk.get(plat), dict) else ""
        meta = o.get("metadata") or {}
        out.append({"name": name, "platform": plat, "version": ver, "size": int(meta.get("size") or 0),
                    "date": str(o.get("created_at") or o.get("updated_at") or "")[:10],
                    "active": bool(url) and url.endswith("/" + name)})
    out.sort(key=lambda e: (e["platform"], tuple(-x for x in parse_version(e["version"]))))
    return out


def activate_manifest(current: dict | None, platform: str, version: str, url: str, sha256: str, notes: str = "") -> dict:
    """Stellt für eine Plattform eine bereits hochgeladene Version als aktuelle ein (auch eine ältere = Zurückstellen).
    Ist sie älter als die bisherige, bekommt das Paket "rollback": true, damit Apps mit der neueren (fehlerhaften) Version
    die ältere ebenfalls angeboten bekommen."""
    version = check_version(version)
    out = build_manifest(current, version, notes or (current or {}).get("notes", ""), {})
    old = out["packages"].get(platform)
    older = bool(old) and parse_version(version) < parse_version(old["version"])
    pkg = {"url": url, "sha256": sha256, "version": version}
    if older:
        pkg["rollback"] = True
    out["packages"][platform] = pkg
    out["version"] = max((p["version"] for p in out["packages"].values()), key=parse_version)
    out["notes"] = notes.strip() or out["notes"]
    return out


def probe_exe_version(path: str, timeout: float = 90.0) -> str | None:
    """Fragt eine gebaute Windows-EXE nach ihrer Versionsnummer (`--version <Datei>`, ab Version 1.4.2 eingebaut).
    Gibt None zurück, wenn das nicht geht (anderes Betriebssystem, ältere EXE ohne die Funktion, Zeitüberschreitung).
    Eine ältere EXE ignoriert die Angabe und startet normal; sie wird nach Ablauf der Zeit beendet."""
    if not os.name == "nt":
        return None
    out = os.path.join(tempfile.mkdtemp(prefix="jopml-ver-"), "v.txt")
    try:
        proc = subprocess.Popen([path, "--version", out], creationflags=0x08000000,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return None
        v = open(out, encoding="utf-8").read().strip()
        return v if VERSION_RE.match(v) else None
    except (OSError, ValueError):
        return None


def judge_version(typed: str, app_version: str, exe_version: str | None, has_exe: bool) -> str:
    """Prüft die eingetragene Nummer. Gibt '' (in Ordnung) oder einen Fehlertext zurück.
    Maßgeblich ist die EXE selbst, weil sie ihre Nummer meldet. Ohne Auskunft der EXE gilt die alte Regel (Nummer des laufenden Programms)."""
    if exe_version is not None:
        if exe_version != typed:
            return (f"Die gewählte EXE meldet Version {exe_version}, eingetragen hast du {typed}. "
                    "Trage die Nummer ein, die die Datei meldet, sonst bietet jede Installation das Update endlos wieder an.")
        return ""
    if typed == app_version:
        return ""
    if has_exe:
        return (f"Die Versionsnummer ({typed}) passt nicht zu diesem Programm ({app_version}), und die gewählte EXE konnte nicht nach ihrer "
                "Version gefragt werden (sie ist älter als 1.4.2 oder wird auf diesem Gerät nicht unterstützt). Starte die frisch gebaute App "
                "und veröffentliche aus ihr, oder baue mit einer Version ab 1.4.2.")
    return ""        # nur .dmg: die Nummer lässt sich nicht prüfen, die Seite fragt vorher nach
