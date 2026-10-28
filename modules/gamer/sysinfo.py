"""System-Werte für das Overlay: CPU, RAM, GPU-Temperatur (nur NVIDIA, über nvidia-smi) und Ping. Alles optional."""
import os
import shutil
import socket
import subprocess
import time

PING_HOST = ("1.1.1.1", 443)


def cpu_ram() -> tuple[float | None, float | None]:
    try:
        import psutil
        return psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
    except Exception:
        pass
    try:                                              # Notlösung ohne psutil: Auslastung aus der Lastzahl schätzen
        load = os.getloadavg()[0] / (os.cpu_count() or 1) * 100
        return min(100.0, load), None
    except (OSError, AttributeError):
        return None, None


_gpu_cache = [0.0, None]


def gpu_temp() -> float | None:
    """Wird höchstens alle 5 Sekunden neu abgefragt (das Hilfsprogramm zu starten ist teuer)."""
    now = time.monotonic()
    if now - _gpu_cache[0] < 5:
        return _gpu_cache[1]
    _gpu_cache[0], _gpu_cache[1] = now, _gpu_temp_now()
    return _gpu_cache[1]


def _gpu_temp_now() -> float | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=2, creationflags=0x08000000 if os.name == "nt" else 0).stdout.strip().splitlines()
        return float(out[0]) if out else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class FpsMeter:
    """Bildrate über den Windows-Fenster-Compositor (DWM). Gemessen werden zwei Zähler:
    die DirectX-Präsentationen des Fensters im Vordergrund (das Spiel selbst) und, falls das nichts liefert,
    die vom Compositor ausgegebenen Bilder des Desktops. Grenzen: Fenster und randloses Vollbild; bei "Vollbild-Exklusiv"
    und auf macOS/Linux gibt es keinen Wert (None). Wer die genaue Zahl braucht, nutzt den Zähler im Spiel."""

    def __init__(self):
        self._last = None

    @staticmethod
    def _counters():
        """(Desktop-Bilder, DirectX-Präsentationen des Vordergrundfensters oder None) oder None."""
        if os.name != "nt":
            return None
        import ctypes

        class Ratio(ctypes.Structure):
            _fields_ = [("n", ctypes.c_uint32), ("d", ctypes.c_uint32)]

        u32, u64 = ctypes.c_uint32, ctypes.c_uint64

        class Info(ctypes.Structure):
            _fields_ = [("cbSize", u32), ("rateRefresh", Ratio), ("qpcRefreshPeriod", u64), ("rateCompose", Ratio), ("qpcVBlank", u64),
                        ("cRefresh", u64), ("cDXRefresh", u32), ("qpcCompose", u64), ("cFrame", u64), ("cDXPresent", u32),
                        ("cRefreshFrame", u64), ("cFrameSubmitted", u64), ("cDXPresentSubmitted", u32), ("cFrameConfirmed", u64),
                        ("cDXPresentConfirmed", u32), ("cRefreshConfirmed", u64), ("cDXRefreshConfirmed", u32), ("cFramesLate", u64),
                        ("cFramesOutstanding", u32), ("cFrameDisplayed", u64), ("qpcFrameDisplayed", u64), ("qpcRefreshFrameDisplayed", u64),
                        ("cFrameComplete", u64), ("qpcFrameComplete", u64), ("cFramePending", u64), ("qpcFramePending", u64),
                        ("cFramesDisplayed", u64), ("cFramesComplete", u64), ("cFramesPending", u64), ("cFramesAvailable", u64),
                        ("cFramesDropped", u64), ("cFramesMissed", u64), ("cRefreshNextDisplayed", u64), ("cRefreshNextPresented", u64),
                        ("cRefreshesDisplayed", u64), ("cRefreshesPresented", u64), ("cRefreshStarted", u64), ("cPixelsReceived", u64),
                        ("cPixelsDrawn", u64), ("cBuffersEmpty", u64)]

        def query(hwnd):
            info = Info()
            info.cbSize = ctypes.sizeof(info)
            ok = ctypes.windll.dwmapi.DwmGetCompositionTimingInfo(hwnd, ctypes.byref(info)) == 0
            return info if ok else None
        desk = query(None)
        if desk is None:
            return None
        fg = None
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            win = query(hwnd) if hwnd else None
            fg = int(win.cDXPresent) if win is not None else None
        except Exception:
            fg = None
        return int(desk.cFrame), fg

    def read(self) -> float | None:
        try:
            cur = self._counters()
        except Exception:
            return None
        now = time.monotonic()
        last, self._last = self._last, (cur, now)
        if cur is None or last is None or last[0] is None or now - last[1] < 0.2:
            return None
        dt = now - last[1]
        (frame, dx), (lframe, ldx) = cur, last[0]
        if dx is not None and ldx is not None and dx > ldx:
            return round((dx - ldx) / dt, 0)
        if frame > lframe:
            return round((frame - lframe) / dt, 0)
        return None


def ping_ms(host=PING_HOST, timeout=1.5) -> float | None:
    t0 = time.perf_counter()
    try:
        with socket.create_connection(host, timeout=timeout):
            pass
    except OSError:
        return None
    return round((time.perf_counter() - t0) * 1000, 0)


def format_stats(s: dict, show: dict | None = None) -> str:
    """Eine Zeile je Wert. s: cpu, ram, gpu, ping (None = nicht verfügbar)."""
    show = show or {"cpu": True, "ram": True, "gpu": True, "fps": True, "ping": True}
    rows = []
    if show.get("cpu"):
        rows.append("CPU  " + (f"{s['cpu']:.0f} %" if s.get("cpu") is not None else "–"))
    if show.get("ram"):
        rows.append("RAM  " + (f"{s['ram']:.0f} %" if s.get("ram") is not None else "–"))
    if show.get("gpu"):
        rows.append("GPU  " + (f"{s['gpu']:.0f} °C" if s.get("gpu") is not None else "–"))
    if show.get("fps"):
        rows.append("FPS  " + (f"{s['fps']:.0f}" if s.get("fps") is not None else "–"))
    if show.get("ping"):
        rows.append("Ping " + (f"{s['ping']:.0f} ms" if s.get("ping") is not None else "–"))
    return "\n".join(rows)


_ping_cache = [0.0, None]


def sample(with_gpu=True, with_ping=True, fps: "FpsMeter | None" = None) -> dict:
    cpu, ram = cpu_ram()
    ping = None
    if with_ping:
        if time.monotonic() - _ping_cache[0] >= 4:
            _ping_cache[0], _ping_cache[1] = time.monotonic(), ping_ms()
        ping = _ping_cache[1]
    return {"cpu": cpu, "ram": ram, "gpu": gpu_temp() if with_gpu else None, "ping": ping, "fps": fps.read() if fps else None}
