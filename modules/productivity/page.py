"""Seite "Productivity"."""
import os
import threading
import tkinter as tk

import customtkinter as ctk

from core import ai_client, theme, ui, winutil
from core.hub import HubPage
from core.i18n import tr
from modules.macros import generator

from . import winmgr
from .assistant import Conversation
from .clipboard import preview


def _say(label, text, ok=True):
    if label.winfo_exists():
        label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)


class ProductivityPage(HubPage):
    def __init__(self, parent, plugin):
        super().__init__(parent, plugin, "Productivity", "Clipboard history, window layouts, the AI macro assistant and extensions.", [
            ("Clipboard", self.tab_clip), ("Windows", self.tab_windows), ("AI macro assistant", self.tab_ai),
            ("Extensions", lambda hub, plugin: self._extensions_page(), True)])

    def _extensions_page(self):
        from modules.extensions.page import ExtensionsPage
        return ExtensionsPage(self, self.app.plugin_by_id["extensions"], embedded=True)

    # ---------------------------------------------------------------- Zwischenablage
    def tab_clip(self, area, plugin):
        body = self.card(area, "Clipboard history", 0)
        ui.muted(body, "Remembers the last texts you copied. The history lives only in memory and disappears when the launcher closes; "
                       "only pinned entries are saved on this computer. Pause it before you copy passwords.").pack(fill="x", pady=(0, 6))
        bar = ctk.CTkFrame(body, fg_color="transparent")
        bar.pack(fill="x", pady=4)
        q = ctk.CTkEntry(bar, width=240, placeholder_text=tr("Search …"))
        q.pack(side="left")
        on = tk.BooleanVar(value=plugin.clip_on)
        ctk.CTkSwitch(bar, text=tr("Record"), variable=on, command=lambda: (setattr(plugin, "clip_on", on.get()), plugin.save())).pack(side="left", padx=12)
        ctk.CTkButton(bar, text=tr("Clear history"), width=120, fg_color="gray35", hover_color="gray25",
                      command=lambda: (plugin.clip.clear(), render())).pack(side="left")
        listbox = ctk.CTkFrame(body, fg_color="transparent")
        listbox.pack(fill="x", pady=4)
        msg = ctk.CTkLabel(body, text="", anchor="w")
        msg.pack(fill="x")
        state = {"seen": -1}

        def copy(t):
            self.app.clipboard_clear()
            self.app.clipboard_append(t)
            _say(msg, tr("Copied."))

        def row(t, pinned):
            f = ctk.CTkFrame(listbox, fg_color=theme.c("inset"), corner_radius=8)
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=("📌 " if pinned else "") + preview(t), anchor="w", justify="left", wraplength=470).pack(side="left", padx=10, pady=6)
            ctk.CTkButton(f, text="🗑", width=30, height=24, fg_color="gray35", hover_color="gray25",
                          command=lambda: ((plugin.clip.unpin(t), plugin.save()) if pinned else plugin.clip.remove(t), render())).pack(side="right", padx=4)
            ctk.CTkButton(f, text=tr("Unpin") if pinned else tr("Pin"), width=60, height=24, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda: ((plugin.clip.unpin(t) if pinned else plugin.clip.pin(t)), plugin.save(), render())).pack(side="right", padx=4)
            ctk.CTkButton(f, text=tr("Copy"), width=60, height=24, command=lambda: copy(t)).pack(side="right", padx=4)

        def render(*_):
            for w in listbox.winfo_children():
                w.destroy()
            pins, items = plugin.clip.search(q.get())
            for t in pins:
                row(t, True)
            for t in items[:30]:
                row(t, False)
            if not pins and not items:
                ctk.CTkLabel(listbox, text=tr("Nothing here yet. Copy some text!"), text_color=theme.MUTED).pack(anchor="w")
            state["seen"] = plugin.changed
        q.bind("<KeyRelease>", render)
        render()

        def tick():
            if not listbox.winfo_exists():
                return
            if plugin.changed != state["seen"] and listbox.winfo_ismapped():
                render()
            listbox.after(900, tick)
        tick()

    # ---------------------------------------------------------------- Fenster
    def _capture_dialog(self, plugin, name, lmsg, on_saved):
        """Liste der offenen Fenster zum Ankreuzen; gespeichert wird die genaue Lage samt Monitor."""
        if not name:
            _say(lmsg, tr("Enter a name and at least one window."), False)
            return
        wins = [w for w in winutil.list_windows(detail=True) if w.get("rect") and w.get("pid") != os.getpid()]
        if not wins:
            _say(lmsg, tr("No open windows found (this works on Windows)."), False)
            return
        top = ctk.CTkToplevel(self, fg_color=theme.c("main"))
        top.title(tr("Save open windows as layout…"))
        top.geometry("560x520")
        top.transient(self.winfo_toplevel())
        ui.muted(top, "Tick the windows that belong to the layout. Their exact position and monitor are saved.").pack(fill="x", padx=16, pady=(14, 6))
        box = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"))
        box.pack(fill="both", expand=True, padx=16, pady=6)
        mons = plugin.monitors()
        checks = []
        for w in wins:
            m = winmgr.monitor_of_rect(w["rect"], mons)
            var = tk.BooleanVar(value=False)
            label = f"{w['title'][:48]}   ·   {w.get('proc', '')}" + (f"   ·   {tr('Monitor')} {m['no']}" if m and len(mons) > 1 else "")
            ctk.CTkCheckBox(box, text=label, variable=var).pack(anchor="w", pady=2, padx=6)
            checks.append((var, w))

        def save():
            chosen = [w for v, w in checks if v.get()]
            n = plugin.capture_layout(name, chosen)
            top.destroy()
            if n:
                _say(lmsg, tr("Saved."))
                on_saved()
            else:
                _say(lmsg, tr("Enter a name and at least one window."), False)
        ctk.CTkButton(top, text=tr("Save layout"), width=150, command=save).pack(pady=12)

    def tab_windows(self, area, plugin):
        body = self.card(area, "Window manager", 0)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        ui.muted(body, "Moves the window you are working in to a half or quarter of the screen. Click a button to move the window you used last (Windows: "
                       "instantly; Mac/Linux: switch to it within 1 second) – or turn on the shortcuts below. On macOS the app needs “Accessibility”, on Linux the tool wmctrl.").pack(fill="x", pady=(0, 6))
        mons = plugin.monitors()
        mon_var = {"v": None}
        if len(mons) > 1:                       # Monitorwahl nur zeigen, wenn es mehrere gibt
            mr = ctk.CTkFrame(body, fg_color="transparent")
            mr.pack(anchor="w", pady=(0, 4))
            ctk.CTkLabel(mr, text=tr("Target monitor"), anchor="w").pack(side="left", padx=(0, 8))
            choices = {tr("Same as the window"): None, tr("Main monitor"): 0}
            choices.update({f"{tr('Monitor')} {m['no']}": m["no"] for m in mons})
            mm = ctk.CTkOptionMenu(mr, values=list(choices), width=190, command=lambda lab: mon_var.update(v=choices.get(lab)))
            mm.set(tr("Same as the window"))
            mm.pack(side="left")
            ctk.CTkButton(mr, text=tr("→ Next monitor"), width=140, command=lambda: plugin.next_monitor_from_button(lambda t, ok: _say(msg, t, ok))).pack(side="left", padx=10)
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(anchor="w")
        for i, kind in enumerate(winmgr.KINDS):
            ctk.CTkButton(grid, text=tr(kind.replace("-", " ").title()), width=130, height=28, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda k=kind: plugin.snap_from_button(k, lambda t, ok: _say(msg, t, ok), mon_var["v"])
                          ).grid(row=i // 5, column=i % 5, padx=3, pady=3)
        sw = tk.BooleanVar(value=plugin.snap_on)

        def toggle():
            plugin.snap_on = sw.get()
            err = plugin.apply_snap_hotkeys()
            plugin.save()
            _say(msg, err or tr("Saved."), not err)
        ctk.CTkSwitch(body, text=tr("Shortcuts on (Ctrl+Alt+arrows, U I J K = quarters, C = centre, Enter = maximise)"), variable=sw,
                      command=toggle).pack(anchor="w", pady=8)
        ui.muted(body, "With several monitors (Windows) a window stays on its own monitor; Ctrl+Alt+M sends it to the next monitor. "
                       "Layouts can also place windows on other monitors.").pack(fill="x")
        msg.pack(fill="x")

        lay = self.card(area, "Layouts", 1)
        ui.muted(lay, "A layout puts several programs in their places at once, e.g. “chrome → left, discord → right”.").pack(fill="x", pady=(0, 6))
        listbox = ctk.CTkFrame(lay, fg_color="transparent")
        listbox.pack(fill="x")
        lmsg = ctk.CTkLabel(lay, text="", anchor="w", wraplength=620, justify="left")

        def render():
            for w in listbox.winfo_children():
                w.destroy()
            for name, slots in plugin.layouts.items():
                f = ctk.CTkFrame(listbox, fg_color=theme.c("inset"), corner_radius=8)
                f.pack(fill="x", pady=2)
                ctk.CTkLabel(f, text=name + "   " + ", ".join(s.label() for s in slots), anchor="w", wraplength=380, justify="left").pack(side="left", padx=10, pady=6)
                ctk.CTkButton(f, text="🗑", width=30, height=24, fg_color="gray35", hover_color="gray25",
                              command=lambda n=name: (plugin.layouts.pop(n, None), plugin.save(), render())).pack(side="right", padx=4)
                ctk.CTkButton(f, text=tr("Apply"), width=70, height=24,
                              command=lambda n=name: _say(lmsg, tr("{n} windows moved.", n=plugin.run_layout(n)))).pack(side="right", padx=4)
        render()
        names = list(plugin.layouts) or [tr("(none)")]
        sr = ctk.CTkFrame(lay, fg_color="transparent")
        sr.pack(fill="x", pady=(8, 2))
        sv = tk.BooleanVar(value=plugin.start_layout_on)
        om = ctk.CTkOptionMenu(sr, values=names, width=180)
        om.set(plugin.start_layout if plugin.start_layout in plugin.layouts else names[0])

        def start_changed(*_):
            plugin.start_layout_on = sv.get()
            plugin.start_layout = om.get() if om.get() in plugin.layouts else ""
            plugin.save()
        ctk.CTkSwitch(sr, text=tr("Apply a layout when the app starts"), variable=sv, command=start_changed).pack(side="left", padx=(0, 10))
        om.configure(command=start_changed)
        om.pack(side="left")
        nm = ctk.CTkEntry(lay, width=200, placeholder_text=tr("Layout name"))
        nm.pack(anchor="w", pady=(6, 2))
        spec = ctk.CTkEntry(lay, width=420, placeholder_text="chrome:left, discord:right@2")
        spec.pack(anchor="w", pady=2)

        def add():
            try:
                slots = []
                for part in spec.get().split(","):
                    slots.append(winmgr.parse_slot(part))
                if not nm.get().strip() or not slots:
                    raise ValueError(tr("Enter a name and at least one window."))
            except ValueError as exc:
                _say(lmsg, str(exc), False)
                return
            plugin.layouts[nm.get().strip()[:40]] = slots[:12]
            plugin.save()
            _say(lmsg, tr("Saved."))
            render()
        ui.muted(lay, "Positions: left, right, top, bottom, top-left, top-right, bottom-left, bottom-right, center, maximize. "
                      "Add @2 for monitor 2 (left to right; without it the main monitor).").pack(fill="x")
        br = ctk.CTkFrame(lay, fg_color="transparent")
        br.pack(anchor="w", pady=4)
        ctk.CTkButton(br, text=tr("Save layout"), width=130, command=add).pack(side="left", padx=(0, 8))
        ctk.CTkButton(br, text=tr("Save open windows as layout…"), width=230,
                      command=lambda: self._capture_dialog(plugin, nm.get().strip(), lmsg, render)).pack(side="left")
        lmsg.pack(fill="x")

    # ---------------------------------------------------------------- KI-Makro-Assistent
    def tab_ai(self, area, plugin):
        body = self.card(area, "AI macro assistant", 0)
        use_ai = ai_client.available(self.app)
        ask = (lambda messages: ai_client.ask(self.app, "macro", messages)) if use_ai else None
        convo = Conversation(ask)
        ui.muted(body, "Describe the macro in your own words. Then ask for changes (“faster”, “click twice”) – the assistant remembers the macro. "
                       "Simple sentences work offline; changes and harder wishes need the AI (cloud account).").pack(fill="x", pady=(0, 6))
        chat = ctk.CTkTextbox(body, height=120, fg_color=theme.c("inset"), state="disabled")
        chat.pack(fill="x", pady=4)
        script = ctk.CTkTextbox(body, height=170, font=ctk.CTkFont(family="Consolas", size=13), fg_color=theme.c("inset"))
        script.pack(fill="x", pady=4)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        entry = ctk.CTkEntry(row, height=36, placeholder_text=tr("e.g. Click every 50 ms at 500 300"))
        entry.pack(side="left", fill="x", expand=True)
        busy = {"v": False}

        def log(role, text):
            chat.configure(state="normal")
            chat.insert("end", ("🧑 " if role == "u" else "🤖 ") + text + "\n")
            chat.configure(state="disabled")
            chat.see("end")

        def send(_e=None):
            if busy["v"]:
                return
            text = entry.get().strip()
            if not text:
                return
            busy["v"] = True
            entry.delete(0, "end")
            log("u", text)
            _say(msg, tr("Working …"))

            def work():
                try:
                    res, err = convo.send(text), ""
                except generator.GenerateError as exc:
                    res, err = None, str(exc)
                self.app.call_soon(done, res, err)

            def done(res, err):
                busy["v"] = False
                if err:
                    _say(msg, err, False)
                    return
                s, src = res
                script.delete("1.0", "end")
                script.insert("1.0", s)
                log("a", tr("Macro ready ({how}).", how=tr("created offline") if src == "offline" else tr("created by the AI and checked")))
                _say(msg, tr("Ask for a change, or send it to the editor."))
            threading.Thread(target=work, daemon=True).start()
        entry.bind("<Return>", send)
        ctk.CTkButton(row, text=tr("Send"), width=90, height=36, command=send).pack(side="left", padx=6)

        def to_editor():
            macros = self.app.plugin_by_id.get("macros")
            text = script.get("1.0", "end").strip()
            if macros is None or not text:
                return
            macros.current_text = text
            old = self.app.pages.pop("macros", None)         # Seite beim nächsten Öffnen mit dem neuen Text bauen
            if old is not None:
                old.destroy()
            self.app.show("macros")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text=tr("Send to the macro editor"), width=200, command=to_editor).pack(side="left")
        ctk.CTkButton(r, text=tr("New conversation"), width=160, fg_color="gray35", hover_color="gray25",
                      command=lambda: (convo.reset(), chat.configure(state="normal"), chat.delete("1.0", "end"), chat.configure(state="disabled"),
                                       script.delete("1.0", "end"))).pack(side="left", padx=6)
        msg.pack(fill="x")
