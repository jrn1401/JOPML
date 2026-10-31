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
from core.ai_context import MACRO_SPEC as spec  # noqa: E402      # Englische Fassung von modules/macros/dsl.py (Modell-Prompt)
out = f"""// AUTOMATISCH ERZEUGT von tools/gen_knowledge.py – nicht von Hand ändern.
export const APP = {json.dumps(f"{APP_NAME} v{APP_VERSION}")};
export const MANUAL = {json.dumps(manual, ensure_ascii=False)};
export const MACRO_SPEC = {json.dumps(spec, ensure_ascii=False)};
export const MACRO_LIMITS = {json.dumps(f"max {dsl.MAX_LINES} lines, loops nested max {dsl.MAX_DEPTH} levels, 'repeat forever' only on the outermost level and only with a wait of at least 1ms inside, coordinates 0..{dsl.MAX_COORD}, text max {dsl.MAX_TEXT} characters.")};
"""
(ROOT / "supabase" / "functions" / "jopml-ai" / "knowledge.ts").write_text(out, encoding="utf-8")
print("knowledge.ts geschrieben:", len(out), "Zeichen")
