"""Multiplayer-Helfer ohne Oberfläche: Runden-/Match-Zähler, benannte Timer, Notizen je Karte, Ping-Verlauf.

Alles läuft von Hand (Tastendruck) oder aus eigenen Messungen. Es liest nichts aus Spielen aus."""
import time
from collections import deque

MAX_TIMERS = 6
MAX_NOTE = 1500


class MatchCounter:
    """Siege, Niederlagen, Kills, Tode und Runden für die aktuelle Sitzung; alles per Hotkey von Hand gezählt."""
    FIELDS = ("wins", "losses", "kills", "deaths", "rounds")

    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        for f in self.FIELDS:
            v = data.get(f, 0)
            setattr(self, f, v if isinstance(v, int) and 0 <= v < 100000 else 0)

    def add(self, field: str, n: int = 1) -> int:
        if field not in self.FIELDS:
            raise ValueError(field)
        v = max(0, min(99999, getattr(self, field) + n))
        setattr(self, field, v)
        return v

    def reset(self) -> None:
        for f in self.FIELDS:
            setattr(self, f, 0)

    def kd(self) -> float:
        return round(self.kills / self.deaths, 2) if self.deaths else float(self.kills)

    def winrate(self) -> int:
        games = self.wins + self.losses
        return round(100 * self.wins / games) if games else 0

    def lines(self, show=None) -> list[str]:
        """Zeilen für das Overlay (englische Beschriftungen, zum Übersetzen mit tr())."""
        out = [("Round", str(self.rounds)), ("Wins / Losses", f"{self.wins} / {self.losses}"),
               ("K / D", f"{self.kills} / {self.deaths}  ({self.kd()})")]
        return [f"{k}: {v}" for k, v in out]

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}

    def summary(self) -> str:
        return f"{self.wins}W {self.losses}L ({self.winrate()} %), K/D {self.kd()}, {self.rounds}"


SIG_W, SIG_H = 16, 8


def signature(img) -> list[int]:
    """Verkleinerter Farbabdruck eines Bildausschnitts (16 x 8 Felder, je R/G/B) zum Wiedererkennen von Sieg-/Niederlage-Bildschirmen."""
    small = img.convert("RGB").resize((SIG_W, SIG_H))
    return [int(v) for px in small.getdata() for v in px]


def distance(a, b) -> float:
    """Mittlerer Farbunterschied zweier Abdrücke (0 = gleich, 255 = völlig verschieden)."""
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _clean_sigs(v) -> list[list[int]]:
    out = []
    for sig in (v if isinstance(v, list) else [])[:3]:
        if isinstance(sig, list) and len(sig) == SIG_W * SIG_H * 3 and all(isinstance(x, int) and 0 <= x <= 255 for x in sig):
            out.append(sig)
    return out


class AutoOutcome:
    """Erkennt Sieg- und Niederlage-Bildschirme am Bildschirminhalt (nur Farben eines gewählten Bereichs, nichts aus dem Spiel gelesen).

    Einmal anlernen: Bereich wählen und bei sichtbarem Sieg- bzw. Niederlage-Bild "lernen". Danach zählt feed() jeden erkannten
    Bildschirm genau einmal: erst nach `need` Treffern hintereinander, dann gesperrt, bis das Bild `hold` Sekunden lang weg war,
    und höchstens alle `gap` Sekunden."""

    def __init__(self, data=None, clock=time.monotonic):
        d = data if isinstance(data, dict) else {}
        self.clock = clock
        self.on = bool(d.get("on", False))
        r = d.get("region")
        ok = isinstance(r, (list, tuple)) and len(r) == 4 and all(isinstance(x, int) and 0 <= x <= 20000 for x in r)
        self.region = tuple(r) if ok and r[2] > r[0] and r[3] > r[1] else None       # (links, oben, rechts, unten)
        self.win = _clean_sigs(d.get("win"))
        self.loss = _clean_sigs(d.get("loss"))
        t = d.get("tolerance", 22)
        self.tolerance = t if isinstance(t, int) and 5 <= t <= 60 else 22
        self.need, self.hold, self.gap = 2, 4.0, 20.0
        self._streak, self._streak_kind = 0, None
        self._locked, self._last_seen, self._last_count = False, 0.0, -1e9

    def ready(self) -> bool:
        return self.region is not None and bool(self.win or self.loss)

    def learn(self, kind: str, sig) -> int:
        """Merkt sich einen Abdruck (bis zu 3 je Art, der älteste fällt weg). Gibt die Zahl der gespeicherten zurück."""
        if kind not in ("win", "loss"):
            raise ValueError(kind)
        lst = getattr(self, kind)
        lst.append(list(sig))
        del lst[:-3]
        return len(lst)

    def forget(self, kind: str) -> None:
        getattr(self, kind).clear()

    def scores(self, sig) -> tuple[float, float]:
        """(kleinster Abstand zu Sieg-Abdrücken, zu Niederlage-Abdrücken); 255 wenn nichts gelernt."""
        return (min((distance(sig, w) for w in self.win), default=255.0), min((distance(sig, w) for w in self.loss), default=255.0))

    def classify(self, sig):
        """"wins", "losses" oder None."""
        w, l = self.scores(sig)
        best = min(w, l)
        if best >= self.tolerance:
            return None
        return "wins" if w <= l else "losses"

    def feed(self, sig):
        """Ein Bildschirmabdruck pro Messung. Gibt "wins"/"losses" zurück, wenn jetzt genau einmal gezählt werden soll."""
        now = self.clock()
        kind = self.classify(sig)
        if kind is None:
            self._streak, self._streak_kind = 0, None
            if self._locked and now - self._last_seen >= self.hold:
                self._locked = False
            return None
        self._last_seen = now
        if self._locked:
            return None
        self._streak = self._streak + 1 if kind == self._streak_kind else 1
        self._streak_kind = kind
        if self._streak >= self.need and now - self._last_count >= self.gap:
            self._locked, self._last_count = True, now
            return kind
        return None

    def to_dict(self) -> dict:
        return {"on": self.on, "region": list(self.region) if self.region else None, "win": self.win, "loss": self.loss, "tolerance": self.tolerance}


class NamedTimers:
    """Bis zu sechs Timer-Vorlagen (Name + Sekunden). Starten per Hotkey; jeder Timer läuft einzeln und meldet sich am Ende."""

    def __init__(self, slots=None, clock=time.monotonic):
        self.clock = clock
        self.slots: list[dict] = []
        for s in (slots if isinstance(slots, list) else [])[:MAX_TIMERS]:
            if isinstance(s, dict):
                self.slots.append(self._clean(s))
        while len(self.slots) < MAX_TIMERS:
            self.slots.append({"name": f"Timer {len(self.slots) + 1}", "seconds": 60, "sound": True})
        self.running: dict[int, float] = {}          # Slot -> Endzeit
        self.done: list[int] = []

    @staticmethod
    def _clean(s: dict) -> dict:
        try:
            sec = int(s.get("seconds", 60))
        except (TypeError, ValueError):
            sec = 60
        return {"name": str(s.get("name", "Timer"))[:24] or "Timer", "seconds": max(1, min(24 * 3600, sec)), "sound": bool(s.get("sound", True))}

    def configure(self, i: int, name: str, seconds, sound: bool = True) -> None:
        self.slots[i] = self._clean({"name": name, "seconds": seconds, "sound": sound})

    def start(self, i: int) -> None:
        """Startet den Timer neu (erneuter Druck setzt ihn zurück)."""
        self.running[i] = self.clock() + self.slots[i]["seconds"]

    def stop(self, i: int) -> None:
        self.running.pop(i, None)

    def stop_all(self) -> None:
        self.running.clear()

    def remaining(self, i: int) -> float | None:
        end = self.running.get(i)
        return None if end is None else max(0.0, end - self.clock())

    def due(self) -> list[int]:
        """Abgelaufene Timer (jeder nur einmal); sie werden aus der Liste der laufenden entfernt."""
        now = self.clock()
        fin = [i for i, end in self.running.items() if end <= now]
        for i in fin:
            self.running.pop(i)
        return fin

    @staticmethod
    def fmt(seconds: float) -> str:
        s = int(seconds + 0.999)
        return f"{s // 60:02d}:{s % 60:02d}"

    def lines(self) -> list[str]:
        return [f"{self.slots[i]['name']}  {self.fmt(r)}" for i in sorted(self.running) if (r := self.remaining(i)) is not None]

    def to_list(self) -> list[dict]:
        return [dict(s) for s in self.slots]


class Notes:
    """Notizen je Karte/Spiel. Das Overlay zeigt die Notiz der gewählten Karte."""

    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        raw = data.get("maps") if isinstance(data.get("maps"), dict) else {}
        self.maps: dict[str, str] = {str(k)[:40]: str(v)[:MAX_NOTE] for k, v in list(raw.items())[:60]}
        cur = str(data.get("current", ""))[:40]
        self.current = cur if cur in self.maps else (next(iter(self.maps), ""))

    def set_text(self, name: str, text: str) -> str:
        name = (name or "").strip()[:40]
        if not name:
            return ""
        if len(self.maps) >= 60 and name not in self.maps:
            return ""
        self.maps[name] = (text or "")[:MAX_NOTE]
        self.current = name
        return name

    def delete(self, name: str) -> None:
        self.maps.pop(name, None)
        if self.current == name:
            self.current = next(iter(self.maps), "")

    def text(self) -> str:
        return self.maps.get(self.current, "")

    def to_dict(self) -> dict:
        return {"maps": dict(self.maps), "current": self.current}


class PingHistory:
    """Letzte Messungen: Ping (Mittel) und Paketverlust in Prozent."""

    def __init__(self, size: int = 20, graph_size: int = 30):
        self.values: deque = deque(maxlen=size)         # None = verloren
        self.series: deque = deque(maxlen=graph_size)   # Verlauf für den Graphen (30 Messungen à 2 s = 60 s)

    def add(self, ms: float | None) -> None:
        self.values.append(ms)
        self.series.append(ms)

    def clear(self) -> None:
        self.values.clear()
        self.series.clear()

    def loss_pct(self) -> int:
        n = len(self.values)
        return round(100 * sum(1 for v in self.values if v is None) / n) if n else 0

    def average(self) -> int | None:
        ok = [v for v in self.values if v is not None]
        return round(sum(ok) / len(ok)) if ok else None

    def worst(self) -> int | None:
        ok = [v for v in self.values if v is not None]
        return round(max(ok)) if ok else None

    def text(self) -> str:
        avg = self.average()
        if avg is None:
            return "Ping: –  Loss: " + (f"{self.loss_pct()} %" if self.values else "–")
        return f"Ping: {avg} ms (max {self.worst()})  Loss: {self.loss_pct()} %"


def split_host(text: str) -> tuple[str, int]:
    """'server.example:27015' -> ('server.example', 27015); ohne Port wird 443 benutzt (TCP-Verbindungsaufbau)."""
    host, _, port = (text or "").strip().partition(":")
    try:
        port_n = int(port) if port else 443
    except ValueError:
        port_n = 443
    return host or "1.1.1.1", max(1, min(65535, port_n))


def graph_points(values, width: int, height: int, vmax: float | None = None, pad: int = 4) -> tuple[list, list]:
    """Wandelt Messwerte in Linienpunkte (x, y) um. Verlorene Pakete (None) unterbrechen die Linie.
    Gibt (Liniensegmente, Verlustmarken-x) zurück; Segment = Liste von (x, y). Größere Werte liegen weiter oben."""
    vals = list(values)
    ok = [v for v in vals if v is not None]
    if not vals:
        return [], []
    top = float(vmax) if vmax else max(50.0, max(ok) * 1.2 if ok else 50.0)
    n = len(vals)
    step = (width - 2 * pad) / max(1, n - 1)
    segs, cur, lost = [], [], []
    for i, v in enumerate(vals):
        x = pad + i * step
        if v is None:
            lost.append(x)
            if len(cur) > 0:
                segs.append(cur)
            cur = []
            continue
        y = height - pad - (min(float(v), top) / top) * (height - 2 * pad)
        cur.append((round(x, 1), round(y, 1)))
    if cur:
        segs.append(cur)
    return segs, lost
