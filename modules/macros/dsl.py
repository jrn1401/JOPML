"""Makro-Sprache (DSL), Prüfer, Ausführer und Offline-Generator. Kein pynput/GUI-Import (gut testbar).

Befehle (eine pro Zeile, Groß-/Kleinschreibung egal, '#' beginnt einen Kommentar):
  click [left|right|middle] [X Y]        Klick (optional an Position)
  doubleclick [left|right|middle] [X Y]  Doppelklick
  move X Y                               Maus bewegen (Bildschirmkoordinaten)
  key NAME                               Taste drücken (a, 5, f5, space, enter, ctrl, ...)
  hold NAME DAUER                        Taste halten
  down NAME / up NAME                    Taste oder Maustaste (mouse_left, mouse_right, mouse_middle) gedrückt halten / loslassen
  type "Text"                            Text eintippen
  scroll N                               Scrollen (positiv = hoch, negativ = runter)
  wait DAUER                             Warten (50ms, 1.5s, 2m; ohne Einheit = ms); 100ms-300ms = zufällige Dauer dazwischen
  repeat N | repeat forever   ...   end  Wiederholen (bis zu 3 Ebenen; 'forever' nur ganz außen)
  set NAME N / add NAME N                Variable setzen / um N erhöhen (Name: Buchstaben, Ziffern, _; höchstens 12 Variablen)
  if NAME OP N ... [else ...] end        Bedingung (OP: == != < > <= >=); zählt mit den Schleifen zur Verschachtelungstiefe
  stop                                   Makro an dieser Stelle beenden
  In type "Text" wird {NAME} durch den Wert der Variablen ersetzt.
"""
import random
import re
import threading
import time
from dataclasses import dataclass, field

from core.i18n import tr

MAX_LINES = 400
MAX_DEPTH = 3
MAX_STEPS = 2_000_000          # geplante Aktionen insgesamt (bei endlichen Schleifen)
MAX_COORD = 20000
MAX_TEXT = 500
MAX_WAIT_S = 3600
BUTTONS = ("left", "right", "middle")
KEY_NAMES = set([chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(i) for i in range(10)] +
                [f"f{i}" for i in range(1, 13)] +
                ["space", "enter", "tab", "backspace", "esc", "up", "down", "left", "right", "shift", "ctrl", "alt",
                 "home", "end", "page_up", "page_down", "delete", "insert"])
MOUSE_NAMES = {"mouse_left": "left", "mouse_right": "right", "mouse_middle": "middle"}
MAX_VARS = 12
_VAR = re.compile(r"^[a-z_][a-z0-9_]{0,15}$")
OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b, ">": lambda a, b: a > b,
       "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}


class MacroError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(f"{tr('Line')} {line}: {message}" if line else message)
        self.line, self.message = line, message


@dataclass
class Cmd:
    op: str
    args: tuple = ()
    line: int = 0
    body: list = field(default_factory=list)       # nur für repeat und if (Dann-Zweig)
    orelse: list = field(default_factory=list)     # nur für if (Sonst-Zweig)


_DUR = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(ms|s|m|min)?$", re.I)


def parse_duration(text: str, line: int = 0) -> float:
    m = _DUR.match(text.strip())
    if not m:
        raise MacroError(line, tr("Invalid duration: {t}", t=text))
    value = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "ms").lower()
    sec = value / 1000 if unit == "ms" else value if unit == "s" else value * 60
    if sec > MAX_WAIT_S:
        raise MacroError(line, tr("Duration too long (max. 1 hour)."))
    return sec


def _tokens(line: str, n: int) -> list[str]:
    """Teilt eine Zeile; Text in Anführungszeichen bleibt ein Token."""
    out = re.findall(r'"[^"]*"|\S+', line)
    return out


def _int(tok: str, line: int, lo=-MAX_COORD, hi=MAX_COORD) -> int:
    try:
        v = int(tok)
    except ValueError:
        raise MacroError(line, tr("Number expected, found: {t}", t=tok)) from None
    if not lo <= v <= hi:
        raise MacroError(line, tr("Number out of range: {t}", t=tok))
    return v


def parse(text: str) -> list[Cmd]:
    raw = text.replace("\r\n", "\n").split("\n")
    if len(raw) > MAX_LINES:
        raise MacroError(0, tr("Too many lines (max. {n}).", n=MAX_LINES))
    root: list[Cmd] = []
    stack: list[tuple[Cmd | None, list[Cmd]]] = [(None, root)]
    names: set[str] = set()

    def var(tok: str, no: int) -> str:
        n = tok.lower()
        if not _VAR.match(n):
            raise MacroError(no, tr("Invalid variable name: {t}", t=tok))
        names.add(n)
        if len(names) > MAX_VARS:
            raise MacroError(no, tr("Too many variables (max. {n}).", n=MAX_VARS))
        return n

    for no, orig in enumerate(raw, start=1):
        line = orig.split("#", 1)[0].strip() if '"' not in orig else _strip_comment(orig)
        if not line:
            continue
        tok = _tokens(line, 0)
        op, rest = tok[0].lower(), tok[1:]
        cur = stack[-1][1]
        if op == "end":
            if len(stack) == 1:
                raise MacroError(no, tr("'end' without 'repeat'."))
            stack.pop()
        elif op == "else":
            top = stack[-1][0]
            if top is None or top.op != "if" or stack[-1][1] is top.orelse:
                raise MacroError(no, tr("'else' without 'if'."))
            stack[-1] = (top, top.orelse)
        elif op == "stop":
            if rest:
                raise MacroError(no, tr("Usage: stop"))
            cur.append(Cmd("stop", (), no))
        elif op in ("set", "add"):
            if len(rest) != 2:
                raise MacroError(no, tr("Usage: {op} NAME N", op=op))
            cur.append(Cmd(op, (var(rest[0], no), _int(rest[1], no, -1_000_000, 1_000_000)), no))
        elif op == "if":
            if len(rest) != 3 or rest[1] not in OPS:
                raise MacroError(no, tr("Usage: if NAME == N  (also != < > <= >=)"))
            if len(stack) > MAX_DEPTH:
                raise MacroError(no, tr("Loops may be nested at most {n} levels deep.", n=MAX_DEPTH))
            c = Cmd("if", (var(rest[0], no), rest[1], _int(rest[2], no, -1_000_000, 1_000_000)), no)
            cur.append(c)
            stack.append((c, c.body))
        elif op == "repeat":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: repeat N  or  repeat forever"))
            if len(stack) > MAX_DEPTH:
                raise MacroError(no, tr("Loops may be nested at most {n} levels deep.", n=MAX_DEPTH))
            if rest[0].lower() == "forever":
                if len(stack) > 1:
                    raise MacroError(no, tr("'repeat forever' is only allowed on the outermost level."))
                count = 0
            else:
                count = _int(rest[0], no, 1, 1_000_000)
            c = Cmd("repeat", (count,), no)
            cur.append(c)
            stack.append((c, c.body))
        elif op in ("click", "doubleclick"):
            btn, xy = "left", None
            r = list(rest)
            if r and r[0].lower() in BUTTONS:
                btn = r.pop(0).lower()
            if r:
                if len(r) != 2:
                    raise MacroError(no, tr("Usage: {op} [left|right|middle] [X Y]", op=op))
                xy = (_int(r[0], no, 0), _int(r[1], no, 0))
            cur.append(Cmd(op, (btn, xy), no))
        elif op == "move":
            if len(rest) != 2:
                raise MacroError(no, tr("Usage: move X Y"))
            cur.append(Cmd("move", (_int(rest[0], no, 0), _int(rest[1], no, 0)), no))
        elif op == "key":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: key NAME"))
            cur.append(Cmd("key", (_key(rest[0], no),), no))
        elif op == "hold":
            if len(rest) != 2:
                raise MacroError(no, tr("Usage: hold NAME DURATION"))
            cur.append(Cmd("hold", (_key(rest[0], no, True), parse_duration(rest[1], no)), no))
        elif op in ("down", "up"):
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: {op} NAME", op=op))
            cur.append(Cmd(op, (_key(rest[0], no, True),), no))
        elif op == "type":
            if len(rest) != 1 or not rest[0].startswith('"') or not rest[0].endswith('"') or len(rest[0]) < 2:
                raise MacroError(no, tr('Usage: type "text"'))
            s = rest[0][1:-1]
            if len(s) > MAX_TEXT:
                raise MacroError(no, tr("Text too long."))
            cur.append(Cmd("type", (s,), no))
        elif op == "scroll":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: scroll N"))
            cur.append(Cmd("scroll", (_int(rest[0], no, -1000, 1000),), no))
        elif op == "wait":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: wait DURATION"))
            lo_s, sep, hi_s = rest[0].partition("-")
            if sep and lo_s and hi_s:                      # 100ms-300ms: zufällige Dauer
                lo, hi = parse_duration(lo_s, no), parse_duration(hi_s, no)
                if hi < lo:
                    raise MacroError(no, tr("The second duration must not be shorter than the first."))
                cur.append(Cmd("wait", (lo, hi), no))
            else:
                cur.append(Cmd("wait", (parse_duration(rest[0], no),), no))
        else:
            raise MacroError(no, tr("Unknown command: {op}", op=tok[0]))
    if len(stack) > 1:
        top = stack[-1][0]
        raise MacroError(top.line, tr("'if' without 'end'.") if top.op == "if" else tr("'repeat' without 'end'."))
    if not root:
        raise MacroError(0, tr("The macro is empty."))
    check(root)
    return root


def _strip_comment(orig: str) -> str:
    out, quoted = [], False
    for ch in orig:
        if ch == '"':
            quoted = not quoted
        if ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out).strip()


def _key(tok: str, line: int, mouse: bool = False) -> str:
    k = tok.lower() if len(tok) > 1 else tok
    if k.lower() not in KEY_NAMES and not (mouse and k.lower() in MOUSE_NAMES):
        raise MacroError(line, tr("Unknown key: {t}", t=tok))
    return k.lower()


def _wait_in(cmds: list[Cmd]) -> float:
    total = 0.0
    for c in cmds:
        if c.op == "wait":
            total += c.args[0]
        elif c.op == "hold":
            total += c.args[1]
        elif c.op == "repeat":
            total += _wait_in(c.body) * (c.args[0] or 1)
        elif c.op == "if":
            total += min(_wait_in(c.body), _wait_in(c.orelse))        # vorsichtig: der Zweig mit weniger Pause zählt
    return total


def _steps(cmds: list[Cmd]) -> int:
    n = 0
    for c in cmds:
        if c.op == "repeat":
            n += (c.args[0] or 1) * max(1, _steps(c.body))
        elif c.op == "if":
            n += 1 + max(_steps(c.body), _steps(c.orelse))
        else:
            n += 1
        if n > MAX_STEPS * 10:
            break
    return n


def check(cmds: list[Cmd]) -> None:
    """Schutzregeln: keine Endlosschleife ohne Pause, begrenzte Gesamtmenge."""
    for c in cmds:
        if c.op == "repeat":
            if not c.body:
                raise MacroError(c.line, tr("The loop is empty."))
            if c.args[0] == 0 and _wait_in(c.body) < 0.001:
                raise MacroError(c.line, tr("'repeat forever' needs at least a 'wait 1ms' inside."))
            check(c.body)
        elif c.op == "if":
            if not c.body and not c.orelse:
                raise MacroError(c.line, tr("The condition has no commands."))
            check(c.body)
            check(c.orelse)
    if _steps(cmds) > MAX_STEPS:
        raise MacroError(0, tr("The macro would run too many actions."))


# ---------------------------------------------------------------- Ausführung
class Runner:
    """backend: Objekt mit click(button, xy, count), move(x, y), key(name), hold(name, sec), type(text), scroll(n)."""

    def __init__(self, backend, sleep=None):
        self.backend = backend
        self.stop_event = threading.Event()
        self.steps = 0
        self._sleep = sleep or self._wait

    def _wait(self, sec: float) -> None:
        self.stop_event.wait(sec)       # lässt sich sofort abbrechen

    def stop(self) -> None:
        self.stop_event.set()

    def run(self, cmds: list[Cmd]) -> str:
        """Gibt 'done' oder 'stopped' zurück."""
        self.stop_event.clear()
        self.steps = 0
        self._down = set()
        self._halt = False
        self.vars: dict[str, int] = {}
        try:
            self._block(cmds)
        finally:
            for name in list(self._down):          # nie eine Taste gedrückt zurücklassen (Ende, Abbruch oder Fehler)
                try:
                    self.backend.release(name)
                except Exception:
                    pass
            self._down.clear()
        return "stopped" if self.stop_event.is_set() else "done"

    def _block(self, cmds):
        for c in cmds:
            if self.stop_event.is_set() or self._halt:
                return
            op, a = c.op, c.args
            if op == "repeat":
                n = 0
                while (a[0] == 0 or n < a[0]) and not self.stop_event.is_set() and not self._halt:
                    self._block(c.body)
                    n += 1
                continue
            if op == "if":
                self._block(c.body if OPS[a[1]](self.vars.get(a[0], 0), a[2]) else c.orelse)
                continue
            if op == "set":
                self.vars[a[0]] = a[1]
                continue
            if op == "add":
                self.vars[a[0]] = max(-1_000_000_000, min(1_000_000_000, self.vars.get(a[0], 0) + a[1]))
                continue
            if op == "stop":
                self._halt = True
                return
            if op == "click":
                self.backend.click(a[0], a[1], 1)
            elif op == "doubleclick":
                self.backend.click(a[0], a[1], 2)
            elif op == "move":
                self.backend.move(*a)
            elif op == "key":
                self.backend.key(a[0])
            elif op == "hold":
                self.backend.hold(a[0], a[1], self)
            elif op == "type":
                self.backend.type(re.sub(r"\{(\w+)\}", lambda m: str(self.vars[m.group(1).lower()]) if m.group(1).lower() in self.vars else m.group(0), a[0]))
            elif op == "scroll":
                self.backend.scroll(a[0])
            elif op == "down":
                self.backend.press(a[0])
                self._down.add(a[0])
            elif op == "up":
                self.backend.release(a[0])
                self._down.discard(a[0])
            elif op == "wait":
                self._sleep(random.uniform(a[0], a[1]) if len(a) > 1 else a[0])
            self.steps += 1


class PynputBackend:
    def __init__(self):
        from pynput import keyboard, mouse
        self.kb, self.ms = keyboard.Controller(), mouse.Controller()
        self._Key, self._KeyCode, self._Button = keyboard.Key, keyboard.KeyCode, mouse.Button

    def _k(self, name):
        return self._KeyCode.from_char(name) if len(name) == 1 else self._Key[name]

    def press(self, name):
        if name in MOUSE_NAMES:
            self.ms.press(getattr(self._Button, MOUSE_NAMES[name]))
        else:
            self.kb.press(self._k(name))

    def release(self, name):
        if name in MOUSE_NAMES:
            self.ms.release(getattr(self._Button, MOUSE_NAMES[name]))
        else:
            self.kb.release(self._k(name))

    def click(self, button, xy, count):
        if xy:
            self.ms.position = xy
        self.ms.click(getattr(self._Button, button), count)

    def move(self, x, y):
        self.ms.position = (x, y)

    def key(self, name):
        self.kb.tap(self._k(name))

    def hold(self, name, sec, runner):
        self.press(name)
        try:
            runner.stop_event.wait(sec)
        finally:
            self.release(name)

    def type(self, text):
        self.kb.type(text)

    def scroll(self, n):
        self.ms.scroll(0, n)


# ---------------------------------------------------------------- Offline-Generator (Deutsch/Englisch)
_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(ms|millisekunden?|milliseconds?|sekunden?|sek|s|seconds?|sec|minuten?|min|minutes?|m)"
_RE_INTERVAL = re.compile(r"(?:alle|jede[nr]?|every|each)\s+" + _NUM + r"\s*" + _UNIT + r"\b", re.I)
_RE_FOR = re.compile(r"(?:für|fuer|for|während|innerhalb)\s+" + _NUM + r"\s*" + _UNIT + r"\b", re.I)
_RE_TIMES = re.compile(r"(\d+)\s*(?:mal|x|times|malig)\b", re.I)
_RE_POS = re.compile(r"(?:position|pos\.?|at|an|auf|bei|nach|to|zu)?\s*\(?\s*(\d{1,5})\s*[,; /x]\s*(\d{1,5})\s*\)?", re.I)
_RE_WAIT = re.compile(r"(?:warte|wait|pause|sleep)\s*" + _NUM + r"\s*" + _UNIT + r"?", re.I)
_RE_TEXT = re.compile(r"(?:tippe|schreibe|eingeben|type|write|enter)\s+(?:den text\s+|the text\s+)?[\"“„']([^\"”“']+)[\"”“']", re.I)
_RE_KEY = re.compile(r"(?:drücke|druecke|drück|press|hit|tippe)\s+(?:die\s+|the\s+)?(?:taste\s+|key\s+)?([a-z0-9_]+)\b", re.I)
_RE_SCROLL = re.compile(r"(?:scrolle|scroll)\w*\s*(hoch|runter|up|down)?\s*(\d+)?", re.I)
_SPLIT = re.compile(r"\s*(?:,|;|\.\s|\bdann\b|\bund dann\b|\banschließend\b|\banschliessend\b|\bdanach\b|\bthen\b|\band then\b|\bafter that\b)\s*", re.I)
_KEYALIAS = {"leertaste": "space", "space": "space", "enter": "enter", "eingabe": "enter", "tab": "tab", "escape": "esc",
             "esc": "esc", "strg": "ctrl", "ctrl": "ctrl", "umschalt": "shift", "shift": "shift", "alt": "alt"}


def _sec(num: str, unit: str | None) -> float:
    v = float(num.replace(",", "."))
    u = (unit or "ms").lower()
    if u.startswith("ms") or u.startswith("milli"):
        return v / 1000
    if u in ("m", "min") or u.startswith("minut"):
        return v * 60
    return v


def _fmt(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms}ms" if ms % 1000 else f"{ms // 1000}s"


def generate_offline(text: str) -> tuple[str, list[str]] | None:
    """Erzeugt ein Makro aus einfachen deutschen/englischen Sätzen. None = nicht verstanden (dann KI fragen)."""
    lines: list[str] = []
    notes: list[str] = []
    for seg in [s for s in _SPLIT.split(text.strip()) if s.strip()]:
        low = seg.lower()
        interval = _RE_INTERVAL.search(seg)
        dur = _RE_FOR.search(seg)
        times = _RE_TIMES.search(seg)
        action: list[str] = []
        tm = _RE_TEXT.search(seg)
        wm = _RE_WAIT.search(seg)
        pos = _RE_POS.search(seg[:interval.start()] + " " + seg[interval.end():] if interval else seg)
        if interval and pos and interval.group(0).strip() and pos.group(0).strip().isdigit():
            pos = None
        xy = f" {pos.group(1)} {pos.group(2)}" if pos and not (dur and pos.start() >= dur.start() and pos.end() <= dur.end()) else ""
        btn = "right" if re.search(r"rechts|right", low) else "middle" if re.search(r"mittel|middle", low) else "left"
        if tm:
            action = [f'type "{tm.group(1)}"']
        elif re.search(r"doppel\s*klick|double\s*-?\s*click", low):
            action = [f"doubleclick {btn}{xy}".strip()]
        elif re.search(r"klick|click|klicke", low):
            action = [f"click {btn}{xy}".strip()]
        elif re.search(r"bewege|move|mauszeiger", low) and xy:
            action = [f"move{xy}"]
        elif _RE_SCROLL.search(seg) and re.search(r"scroll", low):
            sm = _RE_SCROLL.search(seg)
            n = int(sm.group(2) or 3) * (-1 if (sm.group(1) or "").lower() in ("runter", "down") else 1)
            action = [f"scroll {n}"]
        elif _RE_KEY.search(seg) and not (wm and not re.search(r"dr[üu]ck|press|hit", low)):
            k = _RE_KEY.search(seg).group(1).lower()
            k = _KEYALIAS.get(k, k)
            if k in KEY_NAMES:
                action = [f"key {k}"]
        if not action and wm:
            lines.append(f"wait {_fmt(_sec(wm.group(1), wm.group(2)))}")
            continue
        if not action:
            notes.append(tr("Not understood: {s}", s=seg.strip()))
            continue
        if interval:
            gap = _sec(interval.group(1), interval.group(2))
            body = action + [f"wait {_fmt(max(gap, 0.001))}"]
            if dur:
                n = max(1, round(_sec(dur.group(1), dur.group(2)) / max(gap, 0.001)))
                lines += [f"repeat {n}"] + ["  " + b for b in body] + ["end"]
            elif times:
                lines += [f"repeat {int(times.group(1))}"] + ["  " + b for b in body] + ["end"]
            else:
                lines += ["repeat forever"] + ["  " + b for b in body] + ["end"]
        elif times:
            lines += [f"repeat {int(times.group(1))}"] + ["  " + b for b in action] + ["  wait 10ms", "end"]
        else:
            lines += action
    if not lines:
        return None
    script = "\n".join(lines)
    try:
        parse(script)
    except MacroError as exc:
        notes.append(str(exc))
        return None
    return script, notes


def extract_script(ai_text: str) -> str:
    """Zieht das Skript aus einer KI-Antwort (entfernt Codezäune und Erklärungen)."""
    m = re.search(r"```(?:\w+)?\n(.*?)```", ai_text, re.S)
    body = m.group(1) if m else ai_text
    return body.strip()


# ---------------------------------------------------------------- Testlauf (nichts wird gedrückt)
class _LogBackend:
    """Schreibt auf, was ein Makro tun würde, statt es zu tun."""

    def __init__(self, runner_ref, limit: int):
        self.log: list[str] = []
        self.ref, self.limit = runner_ref, limit

    def _add(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) >= self.limit:
            self.ref[0].stop()

    def click(self, button, xy, count):
        self._add(("double-click " if count == 2 else "click ") + button + (f" at {xy[0]},{xy[1]}" if xy else ""))

    def move(self, x, y):
        self._add(f"move mouse to {x},{y}")

    def key(self, name):
        self._add(f"press {name}")

    def hold(self, name, sec, runner):
        self._add(f"hold {name} for {sec:g}s")

    def press(self, name):
        self._add(f"hold down {name}")

    def release(self, name):
        pass

    def type(self, text):
        self._add(f'type "{text}"')

    def scroll(self, n):
        self._add(f"scroll {n}")


def dry_run(cmds: list[Cmd], limit: int = 120) -> tuple[list[str], bool]:
    """Spielt das Makro ohne Wartezeiten und ohne Eingaben durch. Gibt (Zeilen, abgeschnitten) zurück; Endlosschleifen enden nach `limit` Zeilen."""
    ref: list = [None]
    be = _LogBackend(ref, limit)
    runner = Runner(be, sleep=lambda _s: None)
    ref[0] = runner
    runner.run(cmds)
    return be.log, len(be.log) >= limit
