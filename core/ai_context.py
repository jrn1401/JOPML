"""Texte, die der KI-Chat als Hintergrundwissen mitschickt (eine Quelle für tools/gen_knowledge.py und den KI-Chat)."""

MACRO_SPEC = """Macro language (one command per line, case-insensitive, '#' starts a comment):
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
  if color X Y == #RRGGBB [tol N] ... [else ...] end   condition on the pixel colour at screen point X Y (also !=; tol = allowed difference per colour channel, default 20); counts towards the nesting depth
  stop                                   end the macro at this point
  In type "Text", {NAME} is replaced by the variable's value."""

MODULE_SPEC = """When asked to build a module, deliver the COMPLETE module as exactly ONE ```python code block containing the whole plugin.py (no placeholders, no "..."). Before the block write at most two short sentences, after it a short usage note.
A module is one file plugin.py with a class `Plugin(BasePlugin)`:

from core.i18n import tr
from core.plugin_api import BasePlugin
from core import theme

class Plugin(BasePlugin):
    id = "my_module"          # unique, lowercase letters/digits/_, 2-31 chars, starts with a letter
    name = "My module"        # shown in the side menu
    icon = "🧩"
    version = "1.0.0"
    order = 200               # position in the menu
    description = "What it does."

    def on_load(self):        # program start (register things, load saved values)
        pass

    def create_page(self, parent):   # build the USER INTERFACE; return a customtkinter widget
        import customtkinter as ctk
        page = ctk.CTkFrame(parent, fg_color="transparent")
        ...  # labels, entries, buttons, textboxes; use grid/pack; keep it readable
        return page

    def on_shutdown(self):    # program end (stop threads, save)
        pass

Rules and helpers you may rely on:
- Import customtkinter inside create_page (import ctk). Colours: theme.c("card"), theme.c("hover"), theme.c("main"), theme.MUTED, theme.TEXT, theme.DANGER, theme.OK, theme.CARD_RADIUS. Cards: ctk.CTkFrame(page, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS).
- self.app.settings is a dict that is saved automatically (store small values under a key that starts with your module id). self.app.call_soon(fn, *args) runs fn on the UI thread - use it whenever a background thread updates the UI.
- Never block the UI thread: run long work in threading.Thread(daemon=True) and report back with self.app.call_soon.
- Wrap user-visible texts in tr("...") (English source text). Keep the module self-contained; use only the Python standard library plus customtkinter and pynput (already installed).
- No network access, no deleting files, no eval/exec, no starting other programs unless the user explicitly asked for it - the launcher warns about these.
- Never build cheats for online games (aimbot, wallhack, recoil compensation, memory reading, anti-cheat bypass).
"""
