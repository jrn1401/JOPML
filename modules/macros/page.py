"""Seite "My macros": Editor, Prüfen, Ausführen, Speichern, KI-/Offline-Generator."""
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import ai_client, theme, ui
from core.i18n import tr

from . import dsl, generator, recorder, timeline

REFERENCE = """click [left|right|middle] [X Y]
doubleclick [left|right|middle] [X Y]
move X Y
key NAME            (a, 5, f5, space, enter, ctrl ...)
hold NAME 500ms     (keys or mouse_left ...)
down NAME / up NAME (keep pressed / release)
type "text"
scroll 3            (negative = down)
wait 50ms           (ms, s, m; 100ms-300ms = random)
repeat 10 ... end   |   repeat forever ... end
set n 0 / add n 1    (variables; "type" shows {n})
if n >= 3 ... else ... end   (== != < > <= >=)
if color 500 300 == #FF0000 ... end   (pixel colour, also != and "tol 30")
stop                 (ends the macro)
# comment"""

EXAMPLE = '# click at 500,300 every 50 ms\nrepeat forever\n  click left 500 300\n  wait 50ms\nend'


GEN_HINT = ("The generator writes simple loops (“click every 50 ms for 2 minutes”) and also advanced macros: several steps in a row, nested repeats, "
            "random pauses, holding a key or mouse button, typing text and key combinations (holding Ctrl while pressing another key). "
            "It only uses the commands of the macro language and checks every result before you run it. It cannot see the screen or react to what happens in the game.")
GEN_EXAMPLES = [("Fast clicking", "Click every 50 ms for 2 minutes"),
                ("Hold & repeat", "Hold the left mouse button for 30 seconds, then wait 5 seconds, repeat 10 times"),
                ("Chat message", "Every 60 seconds press T, type gg and press Enter"),
                ("Random pauses", "Click at 500 300, then at 700 400 with random pauses of 100 to 300 ms, 100 times")]


DEBUG_SPEEDS = {"Debug: off": 0.0, "Debug: slow": 0.8, "Debug: normal": 0.4, "Debug: fast": 0.1}

# Autovervollständigung: Befehl -> Schreibweise (kurze Syntaxhilfe)
COMPLETIONS = {
    "click": "click [left|right|middle] [X Y]", "doubleclick": "doubleclick [left|right|middle] [X Y]", "move": "move X Y",
    "key": "key NAME", "hold": "hold NAME DURATION", "down": "down NAME", "up": "up NAME", "type": 'type "text"',
    "scroll": "scroll N", "wait": "wait 100ms", "repeat": "repeat N … end", "set": "set NAME N", "add": "add NAME N",
    "if": "if NAME == N … end   |   if color X Y == #RRGGBB [tol N] … end", "else": "else", "end": "end", "stop": "stop",
}


class MacroPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self._busy = False
        self.columnconfigure(0, weight=1)
        ui.page_title(self, "My macros", "Write macros yourself or describe them and let the generator write them.").grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 8))

        # --- Generator
        g = ui.card(self, "Describe it – I write the macro")
        g.grid(row=1, column=0, sticky="ew", padx=24, pady=6)
        line = ui.row(g)
        line.pack(fill="x", padx=16, pady=(0, 4))
        line.columnconfigure(0, weight=1)
        self.desc = ctk.CTkEntry(line, height=38, placeholder_text=tr("e.g. Click every 50 ms at 500 300"))
        self.desc.grid(row=0, column=0, sticky="ew")
        self.desc.bind("<Return>", lambda _e: self.generate())
        self.gen_btn = ctk.CTkButton(line, text=tr("Generate"), width=120, height=38, command=self.generate)
        self.gen_btn.grid(row=0, column=1, padx=(8, 0))
        self.gen_status = ui.muted(g, "Simple sentences work offline. For harder ones the AI is used (cloud account needed).")
        self.gen_status.pack(fill="x", padx=16, pady=(0, 4))
        ui.muted(g, GEN_HINT, wrap=620).pack(fill="x", padx=16, pady=(0, 4))
        ex = ui.row(g)
        ex.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(ex, text=tr("Try an example:"), text_color=theme.MUTED).pack(side="left", padx=(0, 6))
        for text in GEN_EXAMPLES:
            ctk.CTkButton(ex, text=tr(text[0]), height=26, width=10, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda t=text[1]: self._example(t)).pack(side="left", padx=2)

        # --- Editor
        e = ui.card(self, "Macro")
        e.grid(row=2, column=0, sticky="ew", padx=24, pady=6)
        top = ui.row(e)
        top.pack(fill="x", padx=16)
        self.name = ctk.CTkEntry(top, width=200, placeholder_text=tr("Name"))
        self.name.pack(side="left")
        ctk.CTkButton(top, text=tr("Save"), width=80, command=self.save).pack(side="left", padx=6)
        self.saved = ctk.CTkOptionMenu(top, values=[tr("Open saved …")], width=170, command=self.open_saved)
        self.saved.pack(side="left", padx=6)
        ctk.CTkButton(top, text=tr("Delete"), width=80, fg_color="gray35", hover_color="gray25",
                      command=self.delete).pack(side="left", padx=6)
        self.fav_btn = ctk.CTkButton(top, text="☆ " + tr("Favorite"), width=100, fg_color=theme.c("hover"), text_color=theme.TEXT,
                                     command=self.toggle_fav)
        self.fav_btn.pack(side="left", padx=6)
        self.text = ctk.CTkTextbox(e, height=230, font=ctk.CTkFont(family="Consolas", size=13), wrap="none",
                                   fg_color=theme.c("inset"))
        self.text.pack(fill="x", padx=16, pady=10)
        self.text.insert("1.0", plugin.current_text or EXAMPLE)
        try:
            self.text._textbox.tag_config("macro_error", background="#7f1d1d", foreground="#ffffff")
            self.text._textbox.tag_config("macro_run", background="#1d4ed8", foreground="#ffffff")
        except Exception:
            pass
        self._live_job = None
        self._tip = None
        self._sugg = None
        self.text.bind("<KeyRelease>", self._typed)
        self.text.bind("<Tab>", self._accept_suggestion)
        self.text.bind("<Escape>", lambda _e: self._hide_suggestions())
        self.text.bind("<FocusOut>", lambda _e: self.after(150, self._hide_suggestions))
        ctl = ui.row(e)
        ctl.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(ctl, text="▶  " + tr("Run"), width=110, fg_color="#2e9d5b", hover_color="#247a47",
                      command=self.run).pack(side="left")
        ctk.CTkButton(ctl, text="■  " + tr("Stop"), width=100, fg_color="#c0392b", hover_color="#962d22",
                      command=plugin.stop).pack(side="left", padx=6)
        ctk.CTkButton(ctl, text=tr("Check"), width=90, command=self.check).pack(side="left", padx=6)
        self.debug_menu = ctk.CTkOptionMenu(ctl, width=150, values=[tr(k) for k in DEBUG_SPEEDS])
        self.debug_menu.set(tr("Debug: off"))
        self.debug_menu.pack(side="left", padx=6)
        ctk.CTkButton(ctl, text=tr("Preview"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.preview).pack(side="left", padx=2)
        self.pos_btn = ctk.CTkButton(ctl, text=tr("Insert mouse position (3 s)"), width=210, command=self.capture_pos)
        self.pos_btn.pack(side="left", padx=6)
        ctl2 = ui.row(e)
        ctl2.pack(fill="x", padx=16, pady=(0, 6))
        self.rec_btn = ctk.CTkButton(ctl2, text="● " + tr("Record"), width=110, fg_color="#b91c1c", hover_color="#7f1d1d",
                                     command=self.toggle_record)
        self.rec_btn.pack(side="left")
        for label, cmd in ((tr("Copy"), self.copy_text), (tr("Export …"), self.export), (tr("Import …"), self.import_file)):
            ctk.CTkButton(ctl2, text=label, width=96, fg_color=theme.c("hover"), text_color=theme.TEXT, command=cmd).pack(side="left", padx=6)
        ctk.CTkButton(ctl2, text=tr("Explain"), width=96, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.explain).pack(side="left", padx=6)
        ctk.CTkButton(ctl2, text=tr("Timeline"), width=96, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.open_timeline).pack(side="left", padx=6)
        self.fix_btn = ctk.CTkButton(ctl2, text=tr("Fix with AI"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.fix_with_ai)
        self.fix_btn.pack(side="left", padx=6)
        self.recorder = recorder.Recorder()
        self.status = ctk.CTkLabel(e, text="", anchor="w", justify="left", wraplength=640)
        self.status.pack(fill="x", padx=16, pady=(0, 4))
        ui.muted(e, "Start/stop everywhere with F7. Move the mouse carefully: macros click for real. Test in a harmless place.").pack(
            fill="x", padx=16, pady=(0, 12))

        # --- Hilfe
        h = ui.card(self, "Commands")
        h.grid(row=3, column=0, sticky="ew", padx=24, pady=6)
        ctk.CTkLabel(h, text=REFERENCE, font=ctk.CTkFont(family="Consolas", size=12), justify="left", anchor="w").pack(
            fill="x", padx=16, pady=(0, 12))
        self.refresh_saved()
        self._tick()

    # ---------- Hilfen
    def _say(self, text, ok=True):
        self.status.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def script(self) -> str:
        return self.text.get("1.0", "end").strip()

    def refresh_saved(self, select=None):
        names = self.plugin.list_macros()
        self.saved.configure(values=names or [tr("(none saved)")])
        self.saved.set(select or tr("Open saved …"))

    # ---------- Fehler direkt in der Zeile
    def _mark(self, line: int = 0):
        """Hebt die fehlerhafte Zeile im Editor rot hervor (line 0 = Markierung entfernen)."""
        try:
            tb = self.text._textbox
            tb.tag_remove("macro_error", "1.0", "end")
            if line:
                tb.tag_add("macro_error", f"{line}.0", f"{line}.end+1c")
                tb.see(f"{line}.0")
        except Exception:
            pass

    # ---------- Autovervollständigung (Befehle am Zeilenanfang)
    def _current_word(self):
        """(Präfix, Startindex) des Wortes am Zeilenanfang, das gerade getippt wird, sonst ('', None)."""
        try:
            tb = self.text._textbox
            line = tb.get("insert linestart", "insert")
        except Exception:
            return "", None
        stripped = line.lstrip()
        if not stripped or " " in stripped or "\t" in stripped or stripped.startswith("#"):
            return "", None
        return stripped.lower(), f"insert-{len(stripped)}c"

    def _matches(self, prefix):
        return [c for c in COMPLETIONS if c.startswith(prefix) and c != prefix][:6] if prefix else []

    def _hide_suggestions(self):
        if self._sugg is not None:
            try:
                self._sugg.destroy()
            except Exception:
                pass
            self._sugg = None

    def _show_suggestions(self):
        prefix, _start = self._current_word()
        names = self._matches(prefix)
        self._hide_suggestions()
        if not names:
            return
        try:
            tb = self.text._textbox
            x, y, _w, h = tb.bbox("insert")
            box = ctk.CTkFrame(self.text, fg_color=theme.c("card"), corner_radius=8, border_width=1, border_color=theme.c("hover"))
            for n in names:
                ctk.CTkButton(box, text=COMPLETIONS[n], anchor="w", height=24, corner_radius=6, fg_color="transparent", text_color=theme.TEXT,
                              hover_color=theme.c("hover"), command=lambda n=n: self._complete(n)).pack(fill="x", padx=4, pady=1)
            box.place(x=x + 6, y=y + h + 4)
            self._sugg = box
        except Exception:
            self._sugg = None

    def _complete(self, name):
        prefix, start = self._current_word()
        if start is None:
            return
        tb = self.text._textbox
        tb.delete(start, "insert")
        tb.insert("insert", name + " ")
        self._hide_suggestions()
        self.text.focus_set()
        self._typed()

    def _accept_suggestion(self, _e=None):
        """Tab übernimmt den ersten Vorschlag (ohne Vorschläge bleibt Tab ein normaler Tabulator)."""
        prefix, _start = self._current_word()
        names = self._matches(prefix)
        if self._sugg is not None and names:
            self._complete(names[0])
            return "break"
        return None

    # ---------- Fehlerhinweis direkt an der Zeile
    def _show_tip(self, text, line):
        """Kleiner Hinweis neben der fehlerhaften Zeile (verschwindet nach einigen Sekunden)."""
        self._hide_tip()
        try:
            tb = self.text._textbox
            x, y, _w, h = tb.bbox(f"{line}.0")
            tip = ctk.CTkLabel(self.text, text="⚠ " + text, fg_color="#7f1d1d", text_color="#ffffff", corner_radius=6, wraplength=420,
                               justify="left", padx=8, pady=4)
            tip.place(x=min(max(x + 40, 8), 200), y=y + h + 2)
            self._tip = tip
            self.after(6000, self._hide_tip)
        except Exception:
            self._tip = None

    def _hide_tip(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _typed(self, _e=None):
        """Während des Tippens (nach kurzer Pause) prüfen: Fehler erscheinen sofort in der Zeile."""
        self._hide_tip()
        self._show_suggestions()
        if self._live_job is not None:
            self.after_cancel(self._live_job)
        self._live_job = self.after(700, self._live_check)

    def _live_check(self):
        self._live_job = None
        if not self.winfo_exists():
            return
        text = self.script()
        if not text.strip():
            self._mark(0)
            return
        try:
            dsl.parse(text)
        except dsl.MacroError as exc:
            self._mark(exc.line)
            self._say(str(exc), False)
        else:
            self._mark(0)

    def preview(self):
        """Zeigt, was das Makro tun würde (ohne Wartezeiten, ohne etwas zu drücken)."""
        try:
            cmds = dsl.parse(self.script())
        except dsl.MacroError as exc:
            self._mark(exc.line)
            self._say(str(exc), False)
            return
        lines, cut = dsl.dry_run(cmds)
        win = ctk.CTkToplevel(self)
        win.title(tr("Preview"))
        win.geometry("460x420")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text=tr("Test run – nothing is pressed. This is what the macro would do, in this order:"), wraplength=420, justify="left").pack(padx=14, pady=(12, 4), anchor="w")
        box = ctk.CTkTextbox(win)
        box.pack(fill="both", expand=True, padx=14, pady=6)
        box.insert("1.0", "\n".join(f"{i}. {l}" for i, l in enumerate(lines, start=1)) + (("\n… " + tr("(shortened)")) if cut else ""))
        box.configure(state="disabled")

    # ---------- Aktionen
    def check(self):
        try:
            cmds = dsl.parse(self.script())
        except dsl.MacroError as exc:
            self._mark(exc.line)
            self._say(str(exc), False)
            self._show_tip(str(exc), exc.line)
            return False
        self._mark(0)
        self._say(tr("OK – {n} top-level commands.", n=len(cmds)))
        return True

    def run(self):
        label = next((k for k in DEBUG_SPEEDS if tr(k) == self.debug_menu.get()), "Debug: off")
        delay = DEBUG_SPEEDS[label]
        if delay <= 0:
            self._mark_run(0)
            err = self.plugin.run(self.script())
        else:
            err = self.plugin.run(self.script(), debug_delay=delay, on_trace=self._on_trace)
        self._say(err, False) if err else self._say(tr("Running … (F7 or Stop ends it)"))

    # ---------- Fehlersuche: aktuelle Zeile hervorheben, Schleifenzähler und Variablen zeigen
    def _on_trace(self, line, loops, variables):
        self.app.call_soon(self._show_trace, line, loops, variables)

    def _show_trace(self, line, loops, variables):
        if not self.winfo_exists():
            return
        self._mark_run(line)
        parts = [tr("Line {n}", n=line)]
        parts += [tr("loop in line {l}: {i}/{n}", l=l, i=i, n=n if n else "∞") for l, (i, n) in sorted(loops.items())]
        if variables:
            parts.append(", ".join(f"{k}={v}" for k, v in sorted(variables.items())))
        self._say(" · ".join(parts))

    def _mark_run(self, line):
        try:
            tb = self.text._textbox
            tb.tag_remove("macro_run", "1.0", "end")
            if line:
                tb.tag_add("macro_run", f"{line}.0", f"{line}.end+1c")
                tb.see(f"{line}.0")
        except Exception:
            pass

    # ---------- Erklären und Reparieren
    def _ai_ask(self, kind):
        return lambda messages: ai_client.ask(self.app, kind, messages)

    def explain(self):
        try:
            cmds = dsl.parse(self.script())
        except dsl.MacroError as exc:
            self._mark(exc.line)
            self._say(str(exc), False)
            return
        show_explanation(self, self.app, self.script(), cmds)

    def fix_with_ai(self):
        script = self.script()
        try:
            dsl.check(dsl.parse(script))
        except dsl.MacroError as exc:
            error = str(exc)
        else:
            self._say(tr("No error found – nothing to fix."))
            return
        if not ai_client.available(self.app):
            self._say(tr("The AI needs a cloud account (sign in with a JOPMakro account or Google while the server is set up)."), False)
            return
        if self._busy:
            return
        self._busy = True
        self.fix_btn.configure(state="disabled")
        self._say(tr("Asking the AI for a fix …"))

        def work():
            try:
                fixed = generator.fix(script, error, self._ai_ask("macro"))
                self.app.call_soon(self._fix_done, script, fixed, "")
            except generator.GenerateError as exc:
                self.app.call_soon(self._fix_done, script, "", str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _fix_done(self, old, fixed, err):
        self._busy = False
        if not self.winfo_exists():
            return
        self.fix_btn.configure(state="normal")
        if err:
            self._say(err, False)
            return
        self._say(tr("The AI suggests a fix. Check it and press Apply."))
        win = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        win.title(tr("Fix suggestion"))
        win.geometry("520x420")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text=tr("Suggested fix (checked, valid):"), anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=12))
        box.pack(fill="both", expand=True, padx=14, pady=6)
        box.insert("1.0", fixed)
        box.configure(state="disabled")

        def apply():
            self.text.delete("1.0", "end")
            self.text.insert("1.0", fixed)
            self._mark(0)
            self._say(tr("Fix applied."))
            win.destroy()
        ctk.CTkButton(win, text=tr("Apply"), width=120, command=apply).pack(pady=10)

    # ---------- Zeitleiste: Schritte verschieben/löschen/kopieren und Pausen skalieren (statt Ziehen mit der Maus: ▲ ▼)
    def open_timeline(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Timeline"))
        top.geometry("560x520")
        top.transient(self.winfo_toplevel())
        ui.muted(top, "Each row is one step (a repeat or if block counts as one). Move steps with the arrows, copy or delete them, "
                      "or make all pauses faster or slower. The macro text is changed immediately.").pack(fill="x", padx=14, pady=(12, 4))
        info = ctk.CTkLabel(top, text="", anchor="w")
        info.pack(fill="x", padx=14)
        area = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"))
        area.pack(fill="both", expand=True, padx=12, pady=6)

        def apply(text):
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
            self._live_check()
            render()

        def render():
            for w in area.winfo_children():
                w.destroy()
            script = self.script()
            bl = timeline.blocks(script)
            ms = timeline.total_wait_ms(script)
            info.configure(text=tr("{n} steps · pauses add up to about {s} s per run (without repeats)", n=len(bl), s=round(ms / 1000, 1)))
            for i, b in enumerate(bl):
                r = ctk.CTkFrame(area, fg_color=theme.c("inset"), corner_radius=8)
                r.pack(fill="x", pady=2)
                ctk.CTkLabel(r, text=f"{i + 1}.", width=28).pack(side="left", padx=(8, 0))
                ctk.CTkLabel(r, text=timeline.summary(b)[:60], anchor="w", font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=6, pady=5)
                for txt, fn in (("✕", lambda i=i: apply(timeline.delete(script, i))), ("⧉", lambda i=i: apply(timeline.duplicate(script, i))),
                                ("▼", lambda i=i: apply(timeline.move(script, i, 1))), ("▲", lambda i=i: apply(timeline.move(script, i, -1)))):
                    ctk.CTkButton(r, text=txt, width=28, height=26, fg_color=theme.c("hover"), text_color=theme.TEXT, command=fn).pack(side="right", padx=1)
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(row, text=tr("Pause speed")).pack(side="left")
        for label, f in (("×2 faster", 0.5), ("×1.5 faster", 1 / 1.5), ("×1.5 slower", 1.5), ("×2 slower", 2.0)):
            ctk.CTkButton(row, text=tr(label), width=90, height=28, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda f=f: apply(timeline.scale_waits(self.script(), f))).pack(side="left", padx=3)
        ctk.CTkButton(row, text=tr("Close"), width=70, command=top.destroy).pack(side="right")
        render()

    def save(self):
        try:
            self.plugin.save(self.name.get() or "", self.script())
        except dsl.MacroError as exc:
            self._say(str(exc), False)
            return
        except ValueError as exc:
            self._say(tr(str(exc)), False)
            return
        self.refresh_saved(self.name.get().strip())
        self._say(tr("Saved."))

    def open_saved(self, name):
        try:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", self.plugin.load(name))
            self.name.delete(0, "end")
            self.name.insert(0, name)
            self._favs_changed()
        except (OSError, ValueError):
            self._say(tr("This macro could not be opened."), False)

    def delete(self):
        name = self.name.get().strip()
        if name and messagebox.askyesno(tr("Delete"), tr("Delete macro '{n}'?", n=name)):
            self.plugin.delete(name)
            self.refresh_saved()
            self._favs_changed()

    def toggle_fav(self):
        try:
            on = self.plugin.toggle_favorite(self.name.get())
        except ValueError as exc:
            self._say(tr(str(exc)), False)
            return
        self._say(tr("Added to the dashboard.") if on else tr("Removed from the dashboard."))
        self._favs_changed()

    def _favs_changed(self):
        try:
            self.fav_btn.configure(text=("★ " if self.plugin.is_favorite(self.name.get().strip()) else "☆ ") + tr("Favorite"))
            dash = self.app.dashboard
            if dash is not None and dash.winfo_exists():
                dash.refresh_favorites()
        except Exception:
            pass

    # ---------- Aufnahme, Export, Import
    def toggle_record(self):
        if not self.recorder.running:
            err = self.recorder.start()
            if err:
                self._say(err, False)
                return
            self.rec_btn.configure(text="■ " + tr("Stop recording"))
            note = "" if self.recorder.keyboard else " " + tr("(On macOS only the mouse is recorded.)")
            self._say(tr("Recording … do what the macro should do, then press the button again.") + note)
            return
        script = self.recorder.stop(drop_last_clicks_s=0.6)
        self.rec_btn.configure(text="● " + tr("Record"))
        if not script.strip():
            self._say(tr("Nothing was recorded."), False)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", script)
        self._say(tr("Recorded. Check it and press Run."))

    def copy_text(self):
        self.clipboard_clear()
        self.clipboard_append(self.script())
        self._say(tr("Copied."))

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".jopm", initialfile=(self.name.get().strip() or "macro") + ".jopm",
                                            filetypes=[("JOPML macro", "*.jopm"), ("Text", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.script() + "\n")
            self._say(tr("Exported."))
        except OSError as exc:
            self._say(str(exc), False)

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[("JOPML macro", "*.jopm *.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            name, text = self.plugin.import_from(path)
        except dsl.MacroError as exc:
            self._say(str(exc), False)
            return
        except ValueError as exc:
            self._say(tr(str(exc)), False)
            return
        except (OSError, UnicodeError):
            self._say(tr("This macro could not be opened."), False)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.name.delete(0, "end")
        self.name.insert(0, name)
        self.refresh_saved(name)
        self._say(tr("Imported as '{n}'.", n=name))

    def capture_pos(self):
        self.pos_btn.configure(state="disabled")

        def work():
            for i in (3, 2, 1):
                self.app.call_soon(self.pos_btn.configure, text=tr("Move the mouse … {n}", n=i))
                time.sleep(1)
            try:
                from pynput import mouse
                x, y = mouse.Controller().position
                self.app.call_soon(self._insert_pos, int(x), int(y))
            except Exception as exc:
                self.app.call_soon(self._say, str(exc), False)
            self.app.call_soon(self.pos_btn.configure, text=tr("Insert mouse position (3 s)"), state="normal")

        threading.Thread(target=work, daemon=True).start()

    def _insert_pos(self, x, y):
        self.text.insert("insert", f"{x} {y}")
        self._say(tr("Position {x} {y} inserted at the cursor.", x=x, y=y))

    # ---------- Generator
    def _example(self, text: str):
        self.desc.delete(0, "end")
        self.desc.insert(0, tr(text))

    def generate(self):
        if self._busy:
            return
        desc = self.desc.get()
        self._busy = True
        self.gen_btn.configure(state="disabled")
        self.gen_status.configure(text=tr("Working …"), text_color=theme.TEXT)
        use_ai = ai_client.available(self.app)

        def ask(messages):
            return ai_client.ask(self.app, "macro", messages)

        def work():
            try:
                script, source = generator.generate(desc, ask if use_ai else None)
                self.app.call_soon(self._generated, script, source, "")
            except generator.GenerateError as exc:
                self.app.call_soon(self._generated, "", "", str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _generated(self, script, source, err):
        self._busy = False
        if not self.winfo_exists():
            return
        self.gen_btn.configure(state="normal")
        if err:
            self.gen_status.configure(text=err, text_color=theme.DANGER)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", script)
        how = tr("created offline") if source == "offline" else tr("created by the AI and checked")
        self.gen_status.configure(text=tr("Done ({how}). Check it and press Run.", how=how), text_color=theme.OK)

    # ---------- Statusanzeige (nur sichtbar = günstig)
    def _tick(self):
        if not self.winfo_exists():
            return
        if self.winfo_ismapped():
            if self.plugin.state == "running":
                self.status.configure(text="● " + tr("Running …"), text_color=theme.OK)
            elif self.plugin.last == "done":
                self.status.configure(text=tr("Finished."), text_color=theme.TEXT)
                self.plugin.last = ""
            elif self.plugin.last == "stopped":
                self.status.configure(text=tr("Stopped."), text_color=theme.TEXT)
                self.plugin.last = ""
            elif self.plugin.last.startswith("error"):
                self.status.configure(text=self.plugin.last, text_color=theme.DANGER)
        self.after(300, self._tick)


def show_explanation(parent, app, script, cmds):
    """Fenster 'Was macht dieses Makro?': sofort die Beschreibung in Worten (offline), auf Wunsch zusätzlich die KI. Auch für Marktplatz-Makros."""
    win = ctk.CTkToplevel(parent, fg_color=theme.c("main"))
    win.title(tr("What does this macro do?"))
    win.geometry("560x520")
    win.after(120, win.lift)
    ctk.CTkLabel(win, text=tr("Step by step (the macro is only described, nothing is run):"), anchor="w").pack(fill="x", padx=14, pady=(12, 4))
    box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=12), height=240)
    box.pack(fill="both", expand=True, padx=14, pady=6)
    box.insert("1.0", "\n".join(dsl.describe(cmds)))
    box.configure(state="disabled")
    out = ctk.CTkLabel(win, text="", anchor="w", justify="left", wraplength=520)
    out.pack(fill="x", padx=14, pady=4)
    btn = ctk.CTkButton(win, text=tr("Explain with AI"), width=160)
    btn.pack(pady=(2, 12))

    def done(text, ok):
        if win.winfo_exists():
            btn.configure(state="normal")
            out.configure(text=text, text_color=theme.TEXT if ok else theme.DANGER)

    def ask():
        if not ai_client.available(app):
            done(tr("The AI needs a cloud account (sign in with a JOPMakro account or Google while the server is set up)."), False)
            return
        btn.configure(state="disabled")
        out.configure(text=tr("Working …"), text_color=theme.TEXT)

        def work():
            try:
                text = generator.explain(script, lambda m: ai_client.ask(app, "help", m))
                app.call_soon(done, text, True)
            except generator.GenerateError as exc:
                app.call_soon(done, str(exc), False)
        threading.Thread(target=work, daemon=True).start()
    btn.configure(command=ask)
