"""Session-Timer mit Pausen- und Trink-Erinnerung (reine Logik, Uhr austauschbar)."""
import time


class SessionTimer:
    def __init__(self, break_min: int = 60, drink_min: int = 30, clock=time.monotonic):
        self.clock = clock
        self.break_min, self.drink_min = int(break_min), int(drink_min)
        self.started: float | None = None
        self._last = {"break": 0.0, "drink": 0.0}
        self.total_before = 0.0

    @property
    def running(self) -> bool:
        return self.started is not None

    def start(self):
        if self.running:
            return
        now = self.clock()
        self.started = now
        self._last = {"break": now, "drink": now}

    def stop(self):
        if self.running:
            self.total_before += self.clock() - self.started
            self.started = None

    def reset(self):
        self.started, self.total_before = None, 0.0

    def elapsed(self) -> float:
        return self.total_before + (self.clock() - self.started if self.running else 0.0)

    def due(self) -> list[str]:
        """Fällige Erinnerungen ('break', 'drink'); jede wird danach neu gestartet. 0 Minuten = aus."""
        if not self.running:
            return []
        now, out = self.clock(), []
        for kind, minutes in (("break", self.break_min), ("drink", self.drink_min)):
            if minutes > 0 and now - self._last[kind] >= minutes * 60:
                self._last[kind] = now
                out.append(kind)
        return out

    @staticmethod
    def fmt(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"
