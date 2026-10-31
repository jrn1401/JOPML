"""Maus einfangen wie in einem Spiel: Zeiger verstecken, in der Fensterbildmitte halten und nur die Bewegung lesen.
Unter Windows über die Win32-Funktionen (zuverlässig, auch mit ClipCursor); sonst über Tk. Es wird nur der Zeiger dieses einen Fensters bewegt."""
import sys
import threading
import time

WIN = sys.platform.startswith("win")
if WIN:
    import ctypes
    from ctypes import wintypes
    _u = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)         # Pixelkoordinaten stimmen sonst bei skalierten Bildschirmen nicht
    except Exception:
        pass


class Poller:
    """Fragt die Mausposition mehrere hundert Mal pro Sekunde ab (unabhängig von der Bildrate), summiert die Bewegung und stellt den Zeiger
    jedes Mal zurück in die Mitte. Dadurch geht bei schnellen Bewegungen oder niedriger Bildrate nichts verloren und die Steuerung fühlt sich direkt an."""

    def __init__(self, get_pos, set_pos, center, hz=500):
        self.get_pos, self.set_pos, self.c, self.period = get_pos, set_pos, center, 1.0 / hz
        self.lock = threading.Lock()
        self.dx = self.dy = 0
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.set_pos(*self.c)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            try:
                x, y = self.get_pos()
                dx, dy = x - self.c[0], y - self.c[1]
                if dx or dy:
                    self.set_pos(*self.c)
                    with self.lock:
                        self.dx += dx
                        self.dy += dy
            except Exception:
                pass
            time.sleep(self.period)

    def take(self):
        with self.lock:
            d = (self.dx, self.dy)
            self.dx = self.dy = 0
        return d

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(0.3)
        self.thread = None


class Grab:
    def __init__(self, widget):
        self.w = widget
        self.on = False
        self.c = (0, 0)
        self.poller = None

    def _pos(self):
        if WIN:
            p = wintypes.POINT()
            _u.GetCursorPos(ctypes.byref(p))
            return p.x, p.y
        return self.w.winfo_pointerxy()

    def _set(self, x, y):
        if WIN:
            _u.SetCursorPos(int(x), int(y))
        else:
            rx, ry = self.w.winfo_rootx(), self.w.winfo_rooty()
            self.w.event_generate("<Motion>", warp=True, x=int(x - rx), y=int(y - ry))

    def start(self):
        w = self.w
        w.update_idletasks()
        x, y, ww, hh = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
        self.c = (x + ww // 2, y + hh // 2)
        if WIN:
            r = wintypes.RECT(x, y, x + ww, y + hh)
            _u.ClipCursor(ctypes.byref(r))
        try:
            w.configure(cursor="none")
        except Exception:
            pass
        self._set(*self.c)
        self.on = True
        if WIN:
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)          # genaue Wartezeiten (sonst nur ~64 Abfragen pro Sekunde)
            except Exception:
                pass
            self.poller = Poller(self._pos, self._set, self.c)
            self.poller.start()

    def delta(self):
        if not self.on:
            return 0, 0
        if self.poller is not None:
            return self.poller.take()
        x, y = self._pos()
        dx, dy = x - self.c[0], y - self.c[1]
        if dx or dy:
            self._set(*self.c)
        return dx, dy

    def stop(self):
        if self.poller is not None:
            self.poller.stop()
            self.poller = None
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
        if WIN:
            try:
                _u.ClipCursor(None)
            except Exception:
                pass
        try:
            self.w.configure(cursor="arrow")
        except Exception:
            pass
        self.on = False
