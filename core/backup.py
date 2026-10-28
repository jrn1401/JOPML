"""Datensicherung: Einstellungen, Makros und Profile in eine JSON-Datei exportieren und wieder einlesen."""
import json
import re
from pathlib import Path

from core import config
from core.version import APP_VERSION

FORMAT = "jopml-backup"
# Gerätespezifisches bleibt draußen (Pfade, Zustimmungen, Anmelde-Voreinstellung)
EXCLUDE = {"bg_image", "icon_image", "first_run_done", "legal_version", "legal_hash", "legal_accepted_at", "remember", "recoil_ack",
           "assistant_url", "contact_endpoint", "ui_scale"}
EXTS = {".json", ".jopm"}
MAX_FILES, MAX_BYTES = 300, 200_000
_SAFE = re.compile(r"^[\w\- .]{1,80}$", re.U)


def build() -> dict:
    s = config.load_settings()
    files = {}
    root = config.app_dir() / "profiles"
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in EXTS and p.stat().st_size <= MAX_BYTES and len(files) < MAX_FILES:
                try:
                    files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    pass
    return {"format": FORMAT, "version": APP_VERSION,
            "settings": {k: v for k, v in s.items() if k not in EXCLUDE},
            "files": files}


def _safe_rel(rel: str) -> Path | None:
    parts = rel.split("/")
    if len(parts) != 2 or not all(_SAFE.match(x) and x not in (".", "..") for x in parts):
        return None
    return Path(parts[0]) / parts[1] if Path(parts[1]).suffix in EXTS else None


def restore(data, apply_settings: bool = True) -> dict:
    """Spielt eine Sicherung ein. Gibt {"settings": n, "files": n, "skipped": n} zurück. Wirft ValueError bei falschem Format."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("This is not a JOPML backup file.")
    res = {"settings": 0, "files": 0, "skipped": 0}
    cur = config.load_settings()
    if apply_settings and isinstance(data.get("settings"), dict):
        for k, v in data["settings"].items():
            if k in config.DEFAULT_SETTINGS and k not in EXCLUDE and isinstance(v, type(config.DEFAULT_SETTINGS[k])):
                cur[k] = v
                res["settings"] += 1
        config.save_settings(cur)
    root = config.app_dir() / "profiles"
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    for rel, text in list(files.items())[:MAX_FILES]:
        target = _safe_rel(str(rel))
        if target is None or not isinstance(text, str) or len(text) > MAX_BYTES:
            res["skipped"] += 1
            continue
        if target.suffix == ".json":
            try:
                json.loads(text)
            except ValueError:
                res["skipped"] += 1
                continue
        (root / target.parent).mkdir(parents=True, exist_ok=True)
        (root / target).write_text(text, encoding="utf-8")
        res["files"] += 1
    return res
