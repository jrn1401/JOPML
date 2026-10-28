"""CPS- und Reaktionstest (reine Logik)."""
import random
import time

DURATION = 5.0
MAX_HUMAN_CPS = 20.0            # derselbe Grenzwert wie auf dem Server


class CpsTest:
    """Der erste Klick startet die Uhr; danach zählt jeder Klick bis DURATION vorbei ist."""

    def __init__(self, duration: float = DURATION, clock=time.perf_counter):
        self.duration, self.clock = duration, clock
        self.t0: float | None = None
        self.clicks = 0

    def click(self) -> bool:
        """Gibt False zurück, wenn der Test schon vorbei ist."""
        now = self.clock()
        if self.t0 is None:
            self.t0 = now
        if now - self.t0 > self.duration:
            return False
        self.clicks += 1
        return True

    @property
    def finished(self) -> bool:
        return self.t0 is not None and self.clock() - self.t0 >= self.duration

    def remaining(self) -> float:
        return self.duration if self.t0 is None else max(0.0, self.duration - (self.clock() - self.t0))

    def cps(self) -> float:
        return round(self.clicks / self.duration, 2)

    def valid(self) -> bool:
        return 0 < self.cps() <= MAX_HUMAN_CPS


class ReactionTest:
    """Wartezeit zufällig 1–4 s; Klick davor = zu früh; sonst Reaktionszeit in ms."""

    def __init__(self, clock=time.perf_counter, rng=random.uniform):
        self.clock = clock
        self.delay = rng(1.0, 4.0)
        self.t0 = self.clock()
        self.result: float | None = None
        self.too_early = False

    def go_time(self) -> float:
        return self.t0 + self.delay

    def is_go(self) -> bool:
        return self.clock() >= self.go_time()

    def click(self) -> float | None:
        if self.result is not None or self.too_early:
            return self.result
        if not self.is_go():
            self.too_early = True
            return None
        self.result = round((self.clock() - self.go_time()) * 1000, 0)
        return self.result


def rating(ms: float) -> str:
    return "Lightning fast" if ms < 180 else "Very good" if ms < 250 else "Average" if ms < 350 else "Take your time"
