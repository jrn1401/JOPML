"""Erzeugt supabase/functions/jopml-ai/knowledge.ts aus der FAQ und der Makro-Sprache (eine Quelle der Wahrheit).
Aufruf nach Änderungen an core/assistant.py oder modules/macros/dsl.py:  python tools/gen_knowledge.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for stub in (ROOT / "tests" / "stubs",):          # funktioniert auch ohne installierte GUI-Bibliotheken
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(stub))

from core import assistant, handbook  # noqa: E402
from core.version import APP_NAME, APP_VERSION  # noqa: E402
from modules.macros import dsl  # noqa: E402

# Das Handbuch schickt der Launcher bei jeder Frage mit (core/handbook.py + FAQ); auf dem Server nur eine kurze Rückfallebene.
manual = ("The manual was not sent by the app. Tell the user to update the launcher to the newest version and ask again; "
          "for anything else point to the Contact page.")
spec = """Macro language (one command per line, case-insensitive, '#' starts a comment):
  click [left|right|middle] [X Y]        click (optionally at a position)
  doubleclick [left|right|middle] [X Y]  double click
  move X Y                               move the mouse (screen coordinates)
  key NAME                               press a key (a, 5, f5, space, enter, ctrl, ...)
  hold NAME DURATION                     hold a key or mouse_left/mouse_right/mouse_middle
  down NAME / up NAME                    keep a key or mouse button (mouse_left, mouse_right, mouse_middle) pressed / release it
  type "Text"                            type text
  scroll N                               scroll (positive = up, negative = down)
  wait DURATION                          wait (50ms, 1.5s, 2m; no unit = ms); 100ms-300ms = random time in between
  repeat N | repeat forever   ...   end  repeat (up to 3 levels; 'forever' only outermost)
  set NAME N / add NAME N                set a variable / increase it by N (name: letters, digits, _; at most 12 variables)
  if NAME OP N ... [else ...] end        condition (OP: == != < > <= >=); counts towards the nesting depth like loops
  stop                                   end the macro at this point
  In type "Text", {NAME} is replaced by the variable's value."""      # Englische Fassung von modules/macros/dsl.py (Modell-Prompt)
out = f"""// AUTOMATISCH ERZEUGT von tools/gen_knowledge.py – nicht von Hand ändern.
export const APP = {json.dumps(f"{APP_NAME} v{APP_VERSION}")};
export const MANUAL = {json.dumps(manual, ensure_ascii=False)};
export const MACRO_SPEC = {json.dumps(spec, ensure_ascii=False)};
export const MACRO_LIMITS = {json.dumps(f"max {dsl.MAX_LINES} lines, loops nested max {dsl.MAX_DEPTH} levels, 'repeat forever' only on the outermost level and only with a wait of at least 1ms inside, coordinates 0..{dsl.MAX_COORD}, text max {dsl.MAX_TEXT} characters.")};
"""
(ROOT / "supabase" / "functions" / "jopml-ai" / "knowledge.ts").write_text(out, encoding="utf-8")
print("knowledge.ts geschrieben:", len(out), "Zeichen")
