"""Modul-Vorlagen als Startpunkt: direkt hinzufügen oder von der KI anpassen lassen. Jede Vorlage ist ein vollständiges, lauffähiges plugin.py
(nur customtkinter + Programm-Schnittstellen, keine Netzwerk- oder Datei-Zugriffe)."""

TIMER = '''from core.i18n import tr
from core.plugin_api import BasePlugin
from core import theme


class Plugin(BasePlugin):
    id = "timer_tool"
    name = "Timer"
    icon = "⏱"
    version = "1.0.0"
    order = 210
    description = "A simple countdown timer."

    def create_page(self, parent):
        import customtkinter as ctk
        page = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(page, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        card.pack(fill="x", padx=24, pady=24)
        ctk.CTkLabel(card, text="⏱  " + tr("Timer"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=20, pady=(16, 4))
        show = ctk.CTkLabel(card, text="00:00", font=ctk.CTkFont(size=48, weight="bold"))
        show.pack(pady=8)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=(0, 16))
        minutes = ctk.CTkEntry(row, width=80, placeholder_text=tr("minutes"))
        minutes.pack(side="left", padx=6)
        state = {"left": 0, "job": None}

        def tick():
            state["job"] = None
            if state["left"] <= 0:
                show.configure(text=tr("Done!"))
                page.bell()
                return
            m, s = divmod(state["left"], 60)
            show.configure(text=f"{m:02d}:{s:02d}")
            state["left"] -= 1
            state["job"] = page.after(1000, tick)

        def start():
            stop()
            try:
                state["left"] = max(1, int(float(minutes.get().replace(",", ".")) * 60))
            except ValueError:
                show.configure(text=tr("Enter minutes"))
                return
            tick()

        def stop():
            if state["job"] is not None:
                page.after_cancel(state["job"])
                state["job"] = None

        ctk.CTkButton(row, text=tr("Start"), width=90, command=start).pack(side="left", padx=6)
        ctk.CTkButton(row, text=tr("Stop"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT, command=stop).pack(side="left", padx=6)
        return page
'''

NOTES = '''from core.i18n import tr
from core.plugin_api import BasePlugin
from core import theme

KEY = "notes_tool_text"


class Plugin(BasePlugin):
    id = "notes_tool"
    name = "Notes"
    icon = "📝"
    version = "1.0.0"
    order = 211
    description = "A notepad that remembers your text."

    def create_page(self, parent):
        import customtkinter as ctk
        page = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(page, text="📝  " + tr("Notes"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=24, pady=(18, 6))
        box = ctk.CTkTextbox(page, wrap="word", fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        box.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        box.insert("1.0", str(self.app.settings.get(KEY, "")))
        info = ctk.CTkLabel(page, text=tr("Saved automatically."), text_color=theme.MUTED, anchor="w")
        info.pack(fill="x", padx=24, pady=(0, 14))
        job = {"id": None}

        def save():
            job["id"] = None
            self.app.settings[KEY] = box.get("1.0", "end-1c")[:20000]
            self.app.save_settings()

        def changed(_e=None):
            if job["id"] is not None:
                page.after_cancel(job["id"])
            job["id"] = page.after(800, save)
        box.bind("<KeyRelease>", changed)
        return page
'''

COUNTER = '''from core.hotkey_registry import Entry
from core.i18n import tr
from core.plugin_api import BasePlugin
from core import theme

KEY = "counter_tool_count"


class Plugin(BasePlugin):
    id = "counter_tool"
    name = "Hotkey counter"
    icon = "🔢"
    version = "1.0.0"
    order = 212
    description = "Counts up with a hotkey you choose in Settings > Hotkeys."

    def on_load(self):
        # Die Taste legst du unter Einstellungen > Hotkeys fest (Gruppe "Hotkey counter").
        self.label = None
        self.app.hotkeys.register(Entry("counter_tool.plus", "Counter +1", "Hotkey counter", "", action=self.bump))

    def bump(self):
        self.app.settings[KEY] = int(self.app.settings.get(KEY, 0)) + 1
        self.app.save_settings()
        self.refresh()

    def refresh(self):
        try:
            if self.label is not None and self.label.winfo_exists():
                self.label.configure(text=str(self.app.settings.get(KEY, 0)))
        except Exception:
            self.label = None

    def create_page(self, parent):
        import customtkinter as ctk
        page = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(page, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
        card.pack(fill="x", padx=24, pady=24)
        ctk.CTkLabel(card, text="🔢  " + tr("Hotkey counter"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=20, pady=(16, 4))
        self.label = ctk.CTkLabel(card, text=str(self.app.settings.get(KEY, 0)), font=ctk.CTkFont(size=56, weight="bold"))
        self.label.pack(pady=8)
        ctk.CTkLabel(card, text=tr("Set the key in Settings > Hotkeys (group 'Hotkey counter')."), text_color=theme.MUTED).pack()
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=14)
        ctk.CTkButton(row, text="+1", width=80, command=self.bump).pack(side="left", padx=6)

        def reset():
            self.app.settings[KEY] = 0
            self.app.save_settings()
            self.refresh()
        ctk.CTkButton(row, text=tr("Reset"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT, command=reset).pack(side="left", padx=6)
        return page
'''

SNIPPETS = '''from core.i18n import tr
from core.plugin_api import BasePlugin
from core import theme

KEY = "snippets_tool_list"


class Plugin(BasePlugin):
    id = "snippets_tool"
    name = "Text snippets"
    icon = "📋"
    version = "1.0.0"
    order = 213
    description = "Your favourite texts: one click copies them."

    def items(self):
        v = self.app.settings.get(KEY, [])
        return [str(x) for x in v][:30] if isinstance(v, list) else []

    def create_page(self, parent):
        import customtkinter as ctk
        page = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(page, text="📋  " + tr("Text snippets"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=24, pady=(18, 6))
        add = ctk.CTkFrame(page, fg_color="transparent")
        add.pack(fill="x", padx=24)
        entry = ctk.CTkEntry(add, placeholder_text=tr("New text …"))
        entry.pack(side="left", fill="x", expand=True)
        info = ctk.CTkLabel(page, text="", text_color=theme.MUTED, anchor="w")
        lst = ctk.CTkScrollableFrame(page, fg_color="transparent")

        def copy(text):
            page.clipboard_clear()
            page.clipboard_append(text)
            info.configure(text=tr("Copied."))

        def drop_item(i):
            data = self.items()
            if 0 <= i < len(data):
                data.pop(i)
                self.app.settings[KEY] = data
                self.app.save_settings()
            render()

        def render():
            for w in lst.winfo_children():
                w.destroy()
            for i, text in enumerate(self.items()):
                row = ctk.CTkFrame(lst, fg_color=theme.c("card"), corner_radius=8)
                row.pack(fill="x", pady=3)
                ctk.CTkButton(row, text=text[:80], anchor="w", fg_color="transparent", text_color=theme.TEXT, hover_color=theme.c("hover"),
                              command=lambda t=text: copy(t)).pack(side="left", fill="x", expand=True)
                ctk.CTkButton(row, text="✕", width=32, fg_color="transparent", text_color=theme.DANGER, hover_color=theme.c("hover"),
                              command=lambda n=i: drop_item(n)).pack(side="right")

        def add_item():
            t = entry.get().strip()
            if t:
                self.app.settings[KEY] = (self.items() + [t[:500]])[-30:]
                self.app.save_settings()
                entry.delete(0, "end")
                render()
        ctk.CTkButton(add, text=tr("Add"), width=80, command=add_item).pack(side="left", padx=(8, 0))
        info.pack(fill="x", padx=24, pady=(4, 0))
        lst.pack(fill="both", expand=True, padx=24, pady=8)
        render()
        return page
'''

TEMPLATES = {
    "Timer": ("A countdown timer with start and stop.", TIMER),
    "Notes": ("A notepad that saves automatically.", NOTES),
    "Hotkey counter": ("Counts up with a hotkey you choose in Settings > Hotkeys.", COUNTER),
    "Text snippets": ("Favourite texts, one click copies them.", SNIPPETS),
}
