"""Neustart des Launchers: saubere Umgebung, Warten bis die alte Instanz beendet ist, Protokoll bei Fehlern."""
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

PYI_PREFIXES = ("_PYI_",)
PYI_NAMES = ("_MEIPASS2", "_PYI_APPLICATION_HOME_DIR")


def clean_env(env=None) -> dict:
    """Umgebung für die neue Instanz. Eine per PyInstaller gebaute EXE (Einzeldatei) gibt ihre Entpack-Variablen an Kindprozesse weiter;
    die neue Instanz würde dann auf den temporären Ordner der alten zeigen, der beim Beenden gelöscht wird (Fehlermeldung beim Start)."""
    env = dict(os.environ if env is None else env)
    meipass = getattr(sys, "_MEIPASS", "") or ""
    for k in list(env):
        if k in PYI_NAMES or k.startswith(PYI_PREFIXES):
            env.pop(k, None)
    for k in ("TCL_LIBRARY", "TK_LIBRARY", "TKPATH"):
        v = env.get(k, "")
        if v and (meipass and v.startswith(meipass) or "_MEI" in v):
            env.pop(k, None)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env["JOPML_RESTARTED"] = "1"
    return env


def windows_line(cmd: list, delay: int = 3) -> str:
    """Eine Zeile für cmd /c: kurz warten (ping statt timeout – timeout bricht ohne Konsole sofort ab), dann starten."""
    quoted = " ".join(f'"{a}"' for a in cmd)
    return f'ping -n {int(delay) + 1} 127.0.0.1 >nul & start "" {quoted}'


def log(text: str) -> None:
    try:
        from core.config import app_dir
        with open(app_dir() / "restart.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except Exception:
        pass


def spawn(cmd: list, delay: int = 3) -> None:
    """Startet cmd nach kurzer Wartezeit als eigenen, vom Launcher unabhängigen Prozess. Wirft bei Fehlern OSError."""
    env = clean_env()
    cwd = str(Path(cmd[0]).parent) if getattr(sys, "frozen", False) else None
    log(f"restart: {cmd} (delay {delay}s, frozen={getattr(sys, 'frozen', False)})")
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(["cmd", "/c", windows_line(cmd, delay)], creationflags=flags, close_fds=True, env=env, cwd=cwd,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["sh", "-c", f"sleep {int(delay)}; exec " + shlex.join(cmd)], start_new_session=True, close_fds=True, env=env, cwd=cwd,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
