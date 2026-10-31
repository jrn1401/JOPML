import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from core import errors, module_history, module_import, module_review, theme, ui
from core.i18n import tr

from . import logic, templates

DISCLOSURE = ("You are chatting with an AI, not with a person. Answers can be wrong or incomplete: check them, and check any macro, script or module code "
              "before you run or add it. Your messages are sent through our server to the AI you choose (Google Gemini or Groq, USA). "
              "Do not type passwords or personal data. The chat is only saved on this PC if you switch that on (under Chats).")


class ChatPage(ctk.CTkFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color="transparent")
        self.plugin, self.app = plugin, plugin.app
        self.history: list[dict] = []
        self.busy = False
        self.avail: list[str] | None = None
        self.defaults: dict = {}
        self.model_lists: dict = {}
        self.policy: dict = {}
        self.last_code: str | None = None
        self.pending: tuple | None = None            # (Text, Vorlage), wenn vom Dashboard geschickt, bevor die Seite fertig war
        self.project = logic.GENERAL                   # Chats gehören zu einem Projekt: "General" oder ein eigenes Modul
        self.chat_id: str | None = None
        self.extra_ctx = ""                            # Vorlagen-Code, der für den ganzen Chat als Hintergrund mitgeht
        self.cancel: threading.Event | None = None
        self._head = "end"
        self._mark = None                              # Anfang der gerade laufenden Antwort im Verlauf
        self._last_paint = 0.0
        pr = logic.prefs()
        self.saved_models: dict = dict(pr["models"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        ctk.CTkLabel(self, text="🤖  " + tr("AI Chat"), font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=24, pady=(18, 0))
        ui.muted(self, DISCLOSURE).grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=24)
        self.names = {k: v[0] for k, v in logic.PROVIDERS.items()}
        self.prov = ctk.CTkSegmentedButton(bar, values=list(self.names.values()), command=lambda _v: self._provider_changed(True))
        self.prov.set(self.names[pr["provider"]])
        self.prov.pack(side="left", padx=(0, 10))
        self.model = ctk.CTkOptionMenu(bar, values=["…"], width=230, command=lambda _v: self._model_changed())
        self.model.pack(side="left", padx=(0, 10))
        self.preset_names = {tr(k): k for k in logic.presets()}
        self.preset = ctk.CTkOptionMenu(bar, values=list(self.preset_names), width=170)
        self.preset.set(tr("Free chat"))
        self.preset.pack(side="left")
        ctk.CTkButton(bar, text=tr("New chat"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self.clear).pack(side="right")
        bar2 = ctk.CTkFrame(self, fg_color="transparent")
        bar2.grid(row=3, column=0, sticky="ew", padx=24, pady=(6, 0))
        ctk.CTkLabel(bar2, text=tr("Project"), text_color=theme.MUTED).pack(side="left", padx=(0, 6))
        self.proj = ctk.CTkOptionMenu(bar2, values=[tr(logic.GENERAL)], width=190, command=lambda _v: self._project_changed())
        self.proj.pack(side="left", padx=(0, 10))
        ctk.CTkButton(bar2, text="💬  " + tr("Chats"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self._chats_dialog).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar2, text="🧩  " + tr("Templates"), width=130, fg_color=theme.c("hover"), text_color=theme.TEXT, command=self._templates_dialog).pack(side="left")
        self._refresh_projects()
        self.act = ctk.CTkFrame(self, fg_color="transparent")          # Knöpfe unter dem Verlauf: Modul prüfen/hinzufügen, Fehler fragen/melden
        self.act.grid(row=4, column=0, sticky="ew", padx=24, pady=(6, 0))
        self.log = ctk.CTkTextbox(self, wrap="word", fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        self.log.grid(row=5, column=0, sticky="nsew", padx=24, pady=8)
        self.log.configure(state="disabled")
        self.info = ctk.CTkLabel(self, text="", anchor="w", wraplength=760, justify="left", text_color=theme.MUTED)
        self.info.grid(row=6, column=0, sticky="ew", padx=24)
        inp = ctk.CTkFrame(self, fg_color="transparent")
        inp.grid(row=7, column=0, sticky="ew", padx=24, pady=(4, 16))
        inp.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(inp, placeholder_text=tr("Write a message …"), height=38)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda e: self.send())
        self.btn = ctk.CTkButton(inp, text=tr("Send"), width=100, height=38, command=self._send_or_stop)
        self.btn.grid(row=0, column=1, padx=(8, 0))
        self._load_status()

    # ------------------------------------------------------------------ Anbieter und Modell
    def _key(self) -> str:
        label = self.prov.get()
        return next((k for k, v in self.names.items() if v == label), logic.DEFAULT_PROVIDER)

    def _model(self) -> str | None:
        v = self.model.get()
        return v if v and v != "…" else None

    def _load_status(self):
        def work():
            try:
                st = logic.status(self.app)
                try:
                    ml = logic.models(self.app).get("models", {})
                except Exception:
                    ml = {}
                self.app.call_soon(self._status_ok, st, ml)
            except Exception as exc:
                self.app.call_soon(self._fail_info, exc)
        threading.Thread(target=work, daemon=True).start()

    def _status_ok(self, st, ml):
        if not self.winfo_exists():
            return
        self.avail = list(st.get("providers", []))
        self.defaults = st.get("models", {}) or {}
        self.policy = st.get("policy", {}) or {}
        self.model_lists = {p: (ml.get(p) or [self.defaults.get(p, "?")]) for p in logic.REAL}
        if not self.avail:
            self._set_info(tr("The AI chat is not set up on the server yet (an admin has to add the AI keys).") + " [E-AI-001]", False)
        else:
            if self._key() not in self.avail:                      # gespeicherter Anbieter nicht eingerichtet: auf einen vorhandenen wechseln
                self.prov.set(self.names[self.avail[0]])
            self._provider_changed(False)
        if self.pending:
            text, preset = self.pending
            self.pending = None
            self.ask_external(text, preset)

    def _provider_changed(self, user=False):
        k = self._key()
        lst = self.model_lists.get(k) or ([self.defaults[k]] if self.defaults.get(k) else ["…"])
        self.model.configure(values=lst)
        want = self.saved_models.get(k) or self.defaults.get(k)
        self.model.set(want if want in lst else lst[0])
        if user:
            self._model_changed()
        self._info_line()

    def _model_changed(self):
        k, m = self._key(), self._model()
        if m:
            self.saved_models[k] = m
        logic.save_prefs(k, self.saved_models)
        self._info_line()

    def _info_line(self):
        if self.avail is None:
            return
        k = self._key()
        if k not in self.avail:
            self._set_info(tr("This AI is not set up on the server yet. Choose the other one.") + " [E-AI-001]", False)
            return
        p = self.policy
        ma, dt, used = p.get("max_answer"), p.get("daily_tokens"), p.get("tokens_used", 0)
        a = tr("no limit") if ma is not None and ma < 0 else (str(ma) if ma is not None else "?")
        t = tr("no limit") if dt is not None and dt < 0 else (f"{used}/{dt}" if dt is not None else "?")
        self._set_info(tr("Model: {m} · Answer length: {a} tokens · Tokens today: {t}", m=self._model() or "?", a=a, t=t), True)

    def _set_info(self, text, ok=True):
        if self.winfo_exists():
            self.info.configure(text=text, text_color=theme.MUTED if ok else theme.DANGER)

    def _fail_info(self, exc):
        code = getattr(exc, "code", None) or errors.classify(str(exc))
        self.last_code = code
        self._set_info(errors.tag(tr(str(exc)), code), False)

    # ------------------------------------------------------------------ Verlauf
    def _append(self, who: str, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"{who}\n{text}\n\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _clear_actions(self):
        for w in self.act.winfo_children():
            w.destroy()

    def clear(self):
        if self.busy:
            return
        self.history.clear()
        self.chat_id = None
        self.extra_ctx = ""
        self._clear_actions()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _consent(self, key) -> bool:
        miss = logic.missing_consent(key)
        if not miss:
            return True
        who = ", ".join(self.names[m] for m in miss)
        if not messagebox.askyesno(tr("AI data notice"), tr(
                "Your messages are sent through our server to {who} (USA) to get an answer. The AI provider processes them under its own terms. "
                "Do not send passwords or personal data. Allow this?", who=who)):
            return False
        logic.give_consent(key)
        return True

    def ask_external(self, text: str, preset: str = "Free chat"):
        """Wird vom Dashboard-Assistenten und vom Fehlerfenster ("Ask AI") aufgerufen: Vorlage wählen, Text einsetzen, senden."""
        if self.avail is None:
            self.pending = (text, preset)
            return
        label = next((k for k, v in self.preset_names.items() if v == preset), None)
        if label:
            self.preset.set(label)
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.send()

    def _send_or_stop(self):
        if self.busy:
            self.stop()
        else:
            self.send()

    def stop(self):
        if self.cancel is not None:
            self.cancel.set()
            self.btn.configure(state="disabled")

    def _extra(self) -> str:
        """Hintergrund für die KI: Code des gewählten Modul-Projekts und/oder der gewählten Vorlage."""
        parts = [self.extra_ctx] if self.extra_ctx else []
        if self.project != logic.GENERAL:
            code = module_history.current_code(self.project)
            if code:
                parts.append(logic.fix_prompt(self.project, code)[1])
        return "\n\n".join(parts)

    def _can_fallback(self, key) -> bool:
        """Auto-Wechsel nur zu einer KI, der du schon zugestimmt hast (sonst gingen deine Texte ohne Einwilligung dorthin)."""
        return any(p != key and p in (self.avail or []) and logic.consented(p) for p in logic.REAL)

    def send(self):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        key = self._key()
        if self.avail is not None and key not in self.avail:
            self._info_line()
            return
        if not self._consent(key):
            return
        self.entry.delete(0, "end")
        self._clear_actions()
        self.history.append({"role": "user", "content": text})
        self._append(tr("You"), text)
        self.busy = True
        self.cancel = threading.Event()
        self._mark = None
        self.btn.configure(text=tr("Stop"), fg_color=theme.DANGER)
        self._set_info(tr("The AI is answering …"), True)
        preset = self.preset_names.get(self.preset.get(), "Free chat")
        hist, model, cancel = list(self.history), self._model(), self.cancel
        extra, fb = self._extra(), self._can_fallback(key)

        def on_start(prov, mdl, fb_from):
            self.app.call_soon(self._stream_start, prov, mdl, fb_from)

        def on_text(t):
            now = time.monotonic()
            if now - self._last_paint > 0.12:                      # nicht bei jedem Häppchen neu zeichnen
                self._last_paint = now
                self.app.call_soon(self._stream_text, t)

        def work():
            try:
                res = logic.ask_stream(self.app, key, hist, preset, model, extra, on_text, cancel, on_start, fb)
                self.app.call_soon(self._answer, res, preset)
            except Exception as exc:
                self.app.call_soon(self._failed, exc)
        threading.Thread(target=work, daemon=True).start()

    def _header(self, prov, mdl):
        who = self.names.get(prov, prov or "AI")
        return f"🤖 {tr('AI-generated')} · {who} ({mdl or '?'})"

    def _stream_start(self, prov, mdl, fb_from=""):
        if not self.winfo_exists() or not self.busy:
            return
        head = self._header(prov, mdl)
        if fb_from and fb_from != prov:
            note = tr("{a} is not available right now. This answer comes from {b}.", a=self.names.get(fb_from, fb_from), b=self.names.get(prov, prov))
            head += "\n↪ " + note
            self._set_info(note, True)
        self.log.configure(state="normal")
        self._head = self.log.index("end-1c")
        self.log.insert("end", head + "\n")
        self._mark = self.log.index("end-1c")
        self.log.insert("end", "…")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _stream_text(self, text):
        if not self.winfo_exists() or not self.busy or self._mark is None:
            return
        self.log.configure(state="normal")
        self.log.delete(self._mark, "end")
        self.log.insert("end", text)
        self.log.configure(state="disabled")
        self.log.see("end")

    def _finish_ui(self):
        self.busy = False
        self.cancel = None
        self.btn.configure(text=tr("Send"), state="normal", fg_color=theme.accent())

    def _answer(self, res, preset="Free chat"):
        if not self.winfo_exists():
            return
        self._finish_ui()
        reply = res["reply"]
        if self._mark is None:                                      # Server hat ohne Strom geantwortet (alter Stand)
            self._stream_start(res.get("provider"), res.get("model"), res.get("fallback_from") or "")
            self.busy = True
        self._stream_text(reply + ("\n\n⏹ " + tr("Stopped.") if res.get("cancelled") else ""))
        self.busy = False
        self.log.configure(state="normal")
        self.log.insert("end", "\n\n")
        self.log.configure(state="disabled")
        self._mark = None
        if reply:
            self.history.append({"role": "assistant", "content": reply})
        elif self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        self.chat_id = logic.save_chat(self.project, self.chat_id, self.history)
        used = int(res.get("tokens") or 0)
        if used and self.policy.get("daily_tokens") is not None:
            self.policy["tokens_used"] = int(self.policy.get("tokens_used", 0)) + used
        fb = res.get("fallback_from")
        if fb and fb != res.get("provider"):
            self._set_info(tr("{a} is not available right now. This answer comes from {b}.", a=self.names.get(fb, fb), b=self.names.get(res.get("provider"), "?")), True)
        else:
            self._info_line()
        code = logic.extract_module_code(reply)
        if code:
            self._offer_module(code)

    def _failed(self, exc):
        if not self.winfo_exists():
            return
        self._finish_ui()
        if self._mark is not None:                                  # halbe Antwort samt Kopfzeile entfernen
            self.log.configure(state="normal")
            self.log.delete(self._head, "end")
            self.log.configure(state="disabled")
            self._mark = None
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        code = getattr(exc, "code", None) or errors.classify(str(exc), "E-AI-004")
        self.last_code = code
        msg = tr(str(exc)) if isinstance(exc, logic.ChatUnavailable) else str(exc)
        self.app.record_error(code, msg, "ai-chat")
        self._set_info(errors.tag(msg, code), False)
        self._clear_actions()
        ctk.CTkButton(self.act, text="🤖  " + tr("Ask AI"), width=120, command=lambda: self._ask_about(code, msg)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.act, text="🚩  " + tr("Report"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: self.app.open_report(code, msg)).pack(side="left")

    def _ask_about(self, code, msg):
        # bewusst über die Hilfe-Assistentin, falls der Chat selbst nicht antwortet (Limit, Server): die Anfrage ist klein
        self.app.show("assistant")
        page = self.app.pages.get("assistant")
        if page is not None and hasattr(page, "ask"):
            page.ask(errors.explain_prompt(code, msg))

    # ------------------------------------------------------------------ Modul prüfen und übernehmen
    def _offer_module(self, code: str):
        self._clear_actions()
        name = self.project if self.project != logic.GENERAL else logic.module_name_of(code)
        fixing = self.project != logic.GENERAL and module_history.current_code(name) is not None
        label = "🔍  " + (tr("Review the fix for {n}", n=name) if fixing else tr("Review and add as module: {n}", n=name))
        ctk.CTkButton(self.act, text=label, width=300, command=lambda: module_review.review_change(self.app, self, name, code, self._set_info)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.act, text=tr("Copy code"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: self._copy(code)).pack(side="left")

    def _copy(self, code):
        self.clipboard_clear()
        self.clipboard_append(code)
        self._set_info(tr("Code copied."), True)

    # ------------------------------------------------------------------ Projekte und gespeicherte Chats
    def _refresh_projects(self):
        names = [logic.GENERAL] + sorted(set(module_import.installed()) | (set(logic.projects()) - {logic.GENERAL}))
        self.proj_names = {tr(n) if n == logic.GENERAL else n: n for n in names}
        self.proj.configure(values=list(self.proj_names))
        cur = next((k for k, v in self.proj_names.items() if v == self.project), tr(logic.GENERAL))
        self.proj.set(cur)

    def set_project(self, name: str, new_chat: bool = True):
        if self.busy:
            return
        self.project = name or logic.GENERAL
        self._refresh_projects()
        if new_chat:
            self.clear()
        if self.project != logic.GENERAL:
            self.preset.set(tr("Fix a module"))
        elif self.preset_names.get(self.preset.get()) == "Fix a module":
            self.preset.set(tr("Free chat"))

    def _project_changed(self):
        self.set_project(self.proj_names.get(self.proj.get(), logic.GENERAL))

    def open_fix(self, name: str, problem: str = ""):
        """Von der Modul-Verwaltung ('Fix with AI'): Projekt = Modul, Vorlage 'Fix a module'; mit Problemtext wird sofort gesendet."""
        self.set_project(name)
        msg, _ = logic.fix_prompt(name, "", problem)
        self.entry.delete(0, "end")
        self.entry.insert(0, msg)
        if problem.strip():
            self.send()
        else:
            self.entry.focus_set()

    def _chats_dialog(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Chats"))
        top.geometry("560x520")
        top.transient(self.winfo_toplevel())
        ctk.CTkLabel(top, text=tr("Saved chats – {p}", p=self.project if self.project != logic.GENERAL else tr(logic.GENERAL)), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        sw = ctk.CTkSwitch(top, text=tr("Save chats on this PC (encrypted)"))
        if logic.history_enabled():
            sw.select()
        sw.pack(anchor="w", padx=16)
        ui.muted(top, "Chats are stored only on this PC, encrypted for your Windows account, up to 30 per project. Switching this off deletes all saved chats. "
                      "The AI provider still processes each message you send (see the data notice).", wrap=520).pack(fill="x", padx=16, pady=(2, 6))
        lst = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        lst.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        def render():
            for w in lst.winfo_children():
                w.destroy()
            items = logic.chats(self.project) if logic.history_enabled() else []
            if not items:
                ui.muted(lst, "No saved chats here yet." if logic.history_enabled() else "Saving is off.", wrap=480).pack(fill="x", padx=10, pady=10)
            for c in items:
                row = ctk.CTkFrame(lst, fg_color="transparent")
                row.pack(fill="x", pady=2)
                when = time.strftime("%d.%m.%Y %H:%M", time.localtime(c.get("time", 0)))
                ctk.CTkButton(row, text=f"{when}  ·  {c.get('title', '')}"[:70], anchor="w", fg_color="transparent", text_color=theme.TEXT, hover_color=theme.c("hover"),
                              command=lambda ch=c: open_chat(ch)).pack(side="left", fill="x", expand=True)
                ctk.CTkButton(row, text="✕", width=32, fg_color="transparent", text_color=theme.DANGER, hover_color=theme.c("hover"),
                              command=lambda ch=c: drop(ch)).pack(side="right")

        def toggle():
            on = bool(sw.get())
            if not on and logic.history_enabled() and not messagebox.askyesno(tr("Chats"), tr("Switch off and delete all saved chats?")):
                sw.select()
                return
            logic.set_history_enabled(on)
            if not on:
                self.chat_id = None
            elif self.history:
                self.chat_id = logic.save_chat(self.project, self.chat_id, self.history)
            self._refresh_projects()
            render()

        def drop(ch):
            logic.delete_chat(self.project, ch.get("id"))
            if self.chat_id == ch.get("id"):
                self.chat_id = None
            self._refresh_projects()
            render()

        def open_chat(ch):
            if self.busy:
                return
            self.clear()
            self.history = [dict(m) for m in ch.get("messages", [])]
            self.chat_id = ch.get("id")
            for m in self.history:
                self._append(tr("You") if m["role"] == "user" else "🤖 " + tr("AI-generated"), m["content"])
            top.destroy()
        sw.configure(command=toggle)
        render()

    def _templates_dialog(self):
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Module templates"))
        top.geometry("620x520")
        top.transient(self.winfo_toplevel())
        ctk.CTkLabel(top, text=tr("Module templates"), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 2))
        ui.muted(top, "Add a ready module as it is, or let the AI change it for you (for example another look or extra buttons). You always see the code and the check result first.", wrap=580).pack(fill="x", padx=16)
        lst = ctk.CTkScrollableFrame(top, fg_color="transparent")
        lst.pack(fill="both", expand=True, padx=16, pady=8)

        def add(code):
            top.destroy()
            module_review.review_change(self.app, self, logic.module_name_of(code), code, self._set_info)

        def customize(label, code):
            top.destroy()
            if self.busy:
                return
            self.set_project(logic.GENERAL)
            self.preset.set(tr("Write a module"))
            self.extra_ctx = "Start from this template and change it as the user asks. Template '" + label + "':\n```python\n" + code + "\n```"
            self.entry.delete(0, "end")
            self.entry.insert(0, tr("Change the {t} template so that: ", t=tr(label)))
            self.entry.focus_set()
        for label, (desc, code) in templates.TEMPLATES.items():
            card = ctk.CTkFrame(lst, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=tr(label), anchor="w", font=ctk.CTkFont(size=15, weight="bold")).pack(fill="x", padx=12, pady=(8, 0))
            ui.muted(card, desc, wrap=540).pack(fill="x", padx=12)
            br = ctk.CTkFrame(card, fg_color="transparent")
            br.pack(anchor="w", padx=12, pady=8)
            ctk.CTkButton(br, text=tr("Add"), width=100, command=lambda c=code: add(c)).pack(side="left", padx=(0, 6))
            ctk.CTkButton(br, text="🤖  " + tr("Change with AI"), width=170, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda lb=label, c=code: customize(lb, c)).pack(side="left")
