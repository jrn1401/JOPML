"""Makro-Aufnahme: Maus (und, außer auf macOS, Tastatur) mitschneiden und als Makro-Text ausgeben.

`events_to_script` ist reine Logik ohne Eingabe-Bibliothek und daher testbar.
Ereignisse: ("click", zeit, button, x, y) · ("key", zeit, name) · ("scroll", zeit, dy)
"""
import sys
import threading
import time

from . import dsl

MIN_WAIT = 0.02
MAX_WAIT = 600.0
TYPE_GAP = 0.7                 # Zeichen innerhalb dieser Pause werden zu einem type "…" zusammengefasst


def _fmt_wait(sec: float) -> str:
    ms = max(10, int(round(sec * 1000 / 10.0)) * 10)
    return f"wait {ms // 1000}s" if ms % 1000 == 0 and ms >= 1000 else f"wait {ms}ms"


def events_to_script(events: list[tuple]) -> str:
    lines: list[str] = []
    last_t = None
    typed = ""
    typed_t = 0.0

    def flush():
        nonlocal typed
        if typed:
            lines.append(f'type "{typed}"')
            typed = ""

    for ev in sorted(events, key=lambda e: e[1]):
        kind, t = ev[0], ev[1]
        is_char = kind == "key" and len(ev[2]) == 1 and (ev[2].isalnum() and ev[2].isascii() or ev[2] == " ")
        if last_t is not None:
            gap = min(t - last_t, MAX_WAIT)
            if is_char and typed and t - typed_t <= TYPE_GAP:
                pass                                     # innerhalb eines Wortes keine Pause
            elif gap >= MIN_WAIT:
                flush()
                lines.append(_fmt_wait(gap))
        last_t = t
        if is_char:
            typed += ev[2]
            typed_t = t
            continue
        flush()
        if kind == "click" and ev[2] in dsl.BUTTONS:
            lines.append(f"click {ev[2]} {int(ev[3])} {int(ev[4])}")
        elif kind == "key" and ev[2] in dsl.KEY_NAMES:
            lines.append(f"key {ev[2]}")
        elif kind == "scroll" and int(ev[2]):
            lines.append(f"scroll {int(ev[2])}")
    flush()
    return "\n".join(lines)


class Recorder:
    """Schneidet im Hintergrund mit. start() -> '' oder Fehlertext; stop() -> Makro-Text."""

    def __init__(self):
        self.events: list[tuple] = []
        self._ml = self._kl = None
        self._t0 = 0.0
        self.running = False
        self.keyboard = sys.platform != "darwin"      # pynput-Tastaturüberwachung stürzt auf neuem macOS ab

    def start(self) -> str:
        try:
            from pynput import keyboard, mouse
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        self.events, self._t0 = [], time.perf_counter()

        def now():
            return time.perf_counter() - self._t0

        def on_click(x, y, button, pressed):
            if pressed:
                self.events.append(("click", now(), str(button).split(".")[-1], x, y))

        def on_scroll(x, y, dx, dy):
            self.events.append(("scroll", now(), dy))

        def key_name(k):
            ch = getattr(k, "char", None)
            if ch:
                return ch.lower()
            n = getattr(k, "name", "") or ""
            return {"esc": "esc", "page_up": "page_up", "page_down": "page_down", "shift_r": "shift", "ctrl_r": "ctrl",
                    "alt_r": "alt", "shift_l": "shift", "ctrl_l": "ctrl", "alt_l": "alt", "alt_gr": "alt"}.get(n, n)

        def on_press(k):
            self.events.append(("key", now(), key_name(k)))

        try:
            self._ml = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
            self._ml.daemon = True
            self._ml.start()
            if self.keyboard:
                self._kl = keyboard.Listener(on_press=on_press)
                self._kl.daemon = True
                self._kl.start()
        except Exception as exc:
            self.stop()
            return f"{type(exc).__name__}: {exc}"
        self.running = True
        return ""

    def stop(self, drop_last_clicks_s: float = 0.0) -> str:
        for lis in (self._ml, self._kl):
            if lis is not None:
                try:
                    lis.stop()
                except Exception:
                    pass
        self._ml = self._kl = None
        self.running = False
        evs = list(self.events)
        if drop_last_clicks_s and evs:
            end = time.perf_counter() - self._t0
            evs = [e for e in evs if not (e[0] == "click" and end - e[1] <= drop_last_clicks_s)]
        return events_to_script(evs)
