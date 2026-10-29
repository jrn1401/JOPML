"""Führt ein Lua-Skript in einer Sandbox aus (Bibliothek `lupa`). Kein GUI-Import.

Sandbox: os, io, debug, package, require, dofile, loadfile, load ... sind gesperrt. Das Skript kann nur rechnen, `print(...)`
ausgeben, `wait(ms)` und `macro("...")` benutzen. `macro` führt Text der Makro-Sprache des Launchers aus (gleiche Prüfungen, gleicher Notaus);
die Makro-Sprache kennt keine Spiel-Abfragen und keine relativen Mausbewegungen.
Ein Zähler-Hook bricht auch Endlosschleifen ab, sobald Stopp gedrückt wird oder die Höchstdauer erreicht ist.
Python-Objekte gelangen nie ins Skript: wait/macro sind Lua-Hüllen, Fehler kommen nur als Text an, und jeder Attributzugriff
auf Python-Objekte ist gesperrt (sonst käme ein Skript über wait.__self__ ... an Python heran). Speicher ist begrenzt (MAX_MEMORY).
Mit echtem lupa getestet in test_lua_sandbox_real (läuft im CI, lokal nur wenn lupa installiert ist).
"""
import threading
import time
import traceback

from core.i18n import tr

BLOCKED = ("os", "io", "debug", "package", "require", "dofile", "loadfile", "load", "loadstring", "collectgarbage", "module", "python")
MAX_SECONDS = 600
MAX_MACRO_CHARS = 8000
HOOK_EVERY = 10000
MAX_MEMORY = 64 * 1024 * 1024        # Bytes; schützt z. B. vor string.rep("x", 1e10)

PRELUDE = """
local chk, out, dbg = ...
local sethook = dbg.sethook
local function hook() if chk() then error("stopped", 0) end end
sethook(hook, "", 10000)
local cocreate, coresume, unpack = coroutine.create, coroutine.resume, table.unpack
coroutine.create = function(f) local co = cocreate(f); sethook(co, hook, "", 10000); return co end
coroutine.wrap = function(f)
  local co = coroutine.create(f)
  return function(...)
    local r = table.pack(coresume(co, ...))
    if not r[1] then error(r[2], 0) end
    return unpack(r, 2, r.n)
  end
end
function print(...)
  local t = table.pack(...)
  for i = 1, t.n do t[i] = tostring(t[i]) end
  out(table.concat(t, "\\t"))
end
"""


# Ersetzt wait/macro durch Lua-Funktionen: das Skript bekommt nie das Python-Objekt (bound method) in die Hand,
# und Fehler aus Python werden zu reinem Text (kein Exception-Objekt mit __traceback__ usw.).
WRAP = """
function(w, m)
  local pcall, error, tostring, tonumber = pcall, error, tostring, tonumber
  local function wait(ms)
    local ok, e = pcall(w, tonumber(ms) or 0)
    if not ok then error(tostring(e), 0) end
  end
  local function macro(text)
    local ok, e = pcall(m, tostring(text))
    if not ok then error(tostring(e), 0) end
  end
  return wait, macro
end
"""


def _deny_attributes(obj, name, is_setting):
    raise AttributeError("access to Python objects is not allowed in scripts")


class Stopped(Exception):
    def __init__(self):
        super().__init__("stopped")


def lupa_available() -> bool:
    try:
        import lupa  # noqa: F401
        return True
    except Exception:
        return False


class LuaRunner:
    def __init__(self, text: str, on_line, macros=None, max_seconds: int = MAX_SECONDS):
        """on_line(text, ok=True): wird aus dem Skript-Thread aufgerufen. macros: das Plugin "macros" (run/state/stop) oder None."""
        self.text, self.on_line, self.macros, self.max_seconds = text, on_line, macros, max_seconds
        self._stop = threading.Event()
        self._deadline = 0.0
        self._thread = None
        self.finished = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        """Gibt '' oder einen Fehlertext zurück (z. B. lupa fehlt)."""
        if self.running:
            return ""
        try:
            from lupa import LuaRuntime
        except Exception:
            return tr("The Lua engine (lupa) is not installed in this version of the launcher.")
        self._stop.clear()
        self.finished.clear()
        self._deadline = time.monotonic() + self.max_seconds
        self._thread = threading.Thread(target=self._work, args=(LuaRuntime,), daemon=True)
        self._thread.start()
        return ""

    def stop(self) -> None:
        self._stop.set()
        if self.macros is not None:
            try:
                self.macros.stop()
            except Exception:
                traceback.print_exc()

    # ---- im Skript-Thread ----
    def _should_stop(self) -> bool:
        return self._stop.is_set() or time.monotonic() > self._deadline

    def _wait(self, ms=0):
        end = time.monotonic() + max(0.0, min(float(ms or 0), 3_600_000.0)) / 1000.0
        while time.monotonic() < end:
            if self._should_stop():
                raise Stopped()
            time.sleep(min(0.02, max(0.0, end - time.monotonic())))
        if self._should_stop():
            raise Stopped()

    def _macro(self, text):
        m = self.macros
        if m is None:
            raise RuntimeError(tr("Macros are not available."))
        text = str(text)
        if len(text) > MAX_MACRO_CHARS:
            raise RuntimeError(tr("The macro text is too long."))
        err = m.run(text)
        if err:
            raise RuntimeError(err)
        while getattr(m, "state", "idle") == "running":
            if self._should_stop():
                m.stop()
                raise Stopped()
            time.sleep(0.02)

    def _work(self, LuaRuntime):
        out = self.on_line
        try:
            opts = dict(unpack_returned_tuples=True, register_eval=False, register_builtins=False,
                        attribute_filter=_deny_attributes, max_memory=MAX_MEMORY)
            try:
                lua = LuaRuntime(**opts)
            except TypeError:                      # ältere lupa-Version ohne max_memory/register_*: Attributfilter bleibt Pflicht
                lua = LuaRuntime(unpack_returned_tuples=True, attribute_filter=_deny_attributes)
            g = lua.globals()
            lua.eval("function(...) " + PRELUDE + " end")(self._should_stop, lambda s: out(str(s)), g.debug)
            g.wait = self._wait
            g.macro = self._macro
            wrapped = lua.eval(WRAP)(self._wait, self._macro)
            if wrapped:
                g.wait, g.macro = wrapped
            for name in BLOCKED:
                g[name] = None
            lua.execute(self.text)
            out(tr("Script finished."))
        except Stopped:
            out(tr("Script stopped."), False)
        except Exception as exc:
            msg = str(exc)
            if "stopped" in msg.lower() and self._should_stop():
                out(tr("Script stopped."), False)
            else:
                out(tr("Error: {e}", e=msg), False)
        finally:
            self.finished.set()
