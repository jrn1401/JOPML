"""Seite "Gamer & Stream"."""
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog

import customtkinter as ctk

from core import theme, ui
from core.hub import HubPage
from core.i18n import tr
from modules.community.market import MarketService

from . import cps, timer
from .overlaystyle import CORNERS, FONTS


def _say(label, text, ok=True):
    if label.winfo_exists():
        label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)


class GamerPage(HubPage):
    def __init__(self, parent, plugin):
        super().__init__(parent, plugin, "Gamer & Stream", "Timer, overlays, speed tests and screenshots.", [
            ("Session timer", self.tab_timer), ("System overlay", self.tab_stats), ("Key overlay", self.tab_keys),
            ("Match counter", self.tab_match), ("Timers", self.tab_timers), ("Notes", self.tab_notes), ("Network", self.tab_net),
            ("Speed tests", self.tab_tests), ("Screenshot", self.tab_shot)])

    # ---------------------------------------------------------------- Timer
    def tab_timer(self, area, plugin):
        t = plugin.timer
        body = self.card(area, "Session timer", 0)
        big = ctk.CTkLabel(body, text="00:00:00", font=ctk.CTkFont(size=40, weight="bold"))
        big.pack(anchor="w")
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text="▶  " + tr("Start"), width=100, fg_color="#2e9d5b", hover_color="#247a47", command=t.start).pack(side="left")
        ctk.CTkButton(r, text="■  " + tr("Pause"), width=100, fg_color="#c0392b", hover_color="#962d22", command=t.stop).pack(side="left", padx=6)
        ctk.CTkButton(r, text=tr("Reset"), width=90, fg_color="gray35", hover_color="gray25", command=t.reset).pack(side="left")
        rows = {}
        for key, label, val in (("break_min", "Break reminder every (min, 0 = off)", t.break_min), ("drink_min", "Drink reminder every (min, 0 = off)", t.drink_min)):
            rr = ctk.CTkFrame(body, fg_color="transparent")
            rr.pack(fill="x", pady=3)
            ctk.CTkLabel(rr, text=tr(label), width=300, anchor="w").pack(side="left")
            e = ctk.CTkEntry(rr, width=70)
            e.insert(0, str(val))
            e.pack(side="left")
            rows[key] = e

        def save():
            try:
                t.break_min = max(0, min(600, int(rows["break_min"].get())))
                t.drink_min = max(0, min(600, int(rows["drink_min"].get())))
            except ValueError:
                _say(msg, tr("Please enter a number."), False)
                return
            plugin.save()
            _say(msg, tr("Saved."))
        ctk.CTkButton(body, text=tr("Save"), width=90, command=save).pack(anchor="w", pady=4)
        msg.pack(fill="x")
        ui.muted(body, "Reminders appear here and with a short sound while the launcher is open.").pack(fill="x")

        def tick():
            if not big.winfo_exists():
                return
            if big.winfo_ismapped():
                ui.cfg(big, text=timer.SessionTimer.fmt(t.elapsed()))
            while plugin.reminders:
                kind = plugin.reminders.pop(0)
                _say(msg, "☕ " + tr("Time for a break! Stand up and stretch.") if kind == "break" else "💧 " + tr("Drink some water."), True)
            big.after(500, tick)
        tick()

    # ---------------------------------------------------------------- System-Overlay
    def tab_stats(self, area, plugin):
        o = plugin.stats_overlay
        body = self.card(area, "System overlay", 0)
        ui.muted(body, "Shows CPU, memory, graphics-card temperature (NVIDIA only), FPS and ping in a small window you can drag. "
                       "The ping value connects briefly to a public server (1.1.1.1). FPS is the frame rate the screen receives (Windows; windowed and borderless games, not exclusive fullscreen).").pack(fill="x", pady=(0, 6))
        flags = {}
        for k, label in (("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU temperature"), ("fps", "FPS"), ("ping", "Ping")):
            v = tk.BooleanVar(value=o.show_flags[k])
            flags[k] = v
            ctk.CTkSwitch(body, text=tr(label), variable=v, command=lambda k=k, v=v: (o.show_flags.__setitem__(k, v.get()), plugin.save())).pack(anchor="w", pady=2)
        sw = tk.BooleanVar(value=o.active)
        ctk.CTkSwitch(body, text=tr("Show the overlay"), variable=sw, command=lambda: plugin.show_overlay("stats") if sw.get() else plugin.hide_overlay("stats")).pack(anchor="w", pady=(8, 2))
        ui.muted(body, "The overlay appears over windows and borderless fullscreen. Over “exclusive fullscreen” no normal program can draw – "
                       "switch the game to windowed or borderless. For the exact FPS use the counter inside the game (Roblox: Shift+F5).").pack(fill="x", pady=(4, 0))
        self._design_card(area, o, plugin, 1, colour_label="Text colour")

    # ---------------------------------------------------------------- Tasten-Overlay
    def tab_keys(self, area, plugin):
        o = plugin.keys_overlay
        body = self.card(area, "Key overlay", 0)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        ui.muted(body, "Shows W A S D, Shift, Ctrl, Space, the mouse buttons and the last keys you pressed – handy for streams. "
                       "On macOS the keys light up briefly (no hold state) and the app needs “Input Monitoring”.").pack(fill="x", pady=(0, 6))
        sw = tk.BooleanVar(value=o.active)

        def toggle():
            if sw.get():
                err = plugin.show_overlay("keys")
                _say(msg, err, False) if err else _say(msg, "")
            else:
                plugin.hide_overlay("keys")
        ctk.CTkSwitch(body, text=tr("Show the key overlay"), variable=sw, command=toggle).pack(anchor="w", pady=4)
        msg.pack(fill="x")
        self._design_card(area, o, plugin, 1, colour_label="Highlight colour")

    # ---------------------------------------------------------------- Multiplayer-Helfer
    def _overlay_switch(self, body, plugin, key, label):
        o = plugin.overlay_map()[key]
        sw = tk.BooleanVar(value=o.active)
        ctk.CTkSwitch(body, text=tr(label), variable=sw,
                      command=lambda: plugin.show_overlay(key) if sw.get() else plugin.hide_overlay(key)).pack(anchor="w", pady=(8, 2))

    def _all_card(self, area, plugin, row):
        body = self.card(area, "All overlays", row)
        ui.muted(body, "One key shows or hides all overlays and the crosshair (set it under Settings > Hotkeys: “Show / hide all overlays”). "
                       "Streamer mode keeps the overlays out of recordings and streams (Windows 10/11); you still see them on your screen.").pack(fill="x", pady=(0, 6))
        sm = tk.BooleanVar(value=plugin.streamer_mode)
        ctk.CTkSwitch(body, text=tr("Streamer mode (overlays are not recorded)"), variable=sm, command=lambda: plugin.set_streamer_mode(sm.get())).pack(anchor="w", pady=2)
        ctk.CTkButton(body, text=tr("Show / hide all overlays"), width=220, command=plugin.toggle_all_overlays).pack(anchor="w", pady=6)

    def tab_match(self, area, plugin):
        m = plugin.match
        body = self.card(area, "Match counter", 0)
        ui.muted(body, "Count wins, losses, kills, deaths and rounds with a click or your own hotkeys (Settings > Hotkeys, group “Gaming & Stream”). "
                       "Wins and losses can also be counted automatically (card below). Nothing is read from the game itself.").pack(fill="x", pady=(0, 6))
        summary = ctk.CTkLabel(body, text="", anchor="w", font=ctk.CTkFont(size=15, weight="bold"))
        summary.pack(fill="x", pady=4)

        def refresh():
            if summary.winfo_exists():
                summary.configure(text=tr("Session") + ": " + m.summary())
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        for field, label in (("wins", "+ Win"), ("losses", "+ Loss"), ("kills", "+ Kill"), ("deaths", "+ Death"), ("rounds", "+ Round")):
            ctk.CTkButton(r, text=tr(label), width=88, command=lambda f=field: (plugin.count(f), refresh())).pack(side="left", padx=2)
        ctk.CTkButton(r, text=tr("Reset"), width=80, fg_color="#c0392b", hover_color="#962d22", command=lambda: (m.reset(), plugin.save(), refresh())).pack(side="left", padx=8)
        self._overlay_switch(body, plugin, "match", "Show the match overlay")
        refresh()

        def tick():
            if summary.winfo_exists():
                if summary.winfo_ismapped():
                    refresh()
                summary.after(1000, tick)
        tick()
        self._auto_card(area, plugin, 1)
        self._design_card(area, plugin.match_overlay, plugin, 2, colour_label="Text colour")
        self._all_card(area, plugin, 3)

    def _auto_card(self, area, plugin, row):
        a = plugin.auto
        body = self.card(area, "Automatic win / loss detection", row)
        ui.muted(body, "The launcher looks at an area of your screen (like a screen recording does) and recognises your victory and defeat screens. "
                       "Teach it once: choose the area around the “Victory” / “Defeat” text, then press “Learn” while that screen is showing "
                       "(the screen is captured 5 seconds later, so you can switch to your game; or use the hotkeys under Settings > Hotkeys). "
                       "Nothing is read from the game itself. Works best with the game in windowed or borderless mode.").pack(fill="x", pady=(0, 6))
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        info = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left", text_color=theme.MUTED)

        def refresh():
            if not info.winfo_exists():
                return
            reg = tr("Area") + ": " + (f"{a.region[2] - a.region[0]} × {a.region[3] - a.region[1]} px" if a.region else "–")
            info.configure(text=f"{reg}   ·   " + tr("Win screens: {n}", n=len(a.win)) + "   ·   " + tr("Loss screens: {n}", n=len(a.loss))
                           + (("\n" + tr("Last detection") + ": " + plugin.auto_last) if plugin.auto_last else ""))
        sw = tk.BooleanVar(value=a.on)

        def toggle():
            if sw.get() and not a.ready():
                sw.set(False)
                _say(msg, tr("Choose an area and teach at least one screen first."), False)
                return
            plugin.set_auto(sw.get())
        ctk.CTkSwitch(body, text=tr("Count wins and losses automatically"), variable=sw, command=toggle).pack(anchor="w", pady=(2, 6))

        def choose_now():
            from .screenshot import RegionSelector
            sel = RegionSelector(self.winfo_toplevel(), lambda _img: (plugin.set_auto_region(sel.box), refresh(), _say(msg, tr("Area saved."))))
            try:
                sel.start()
            except Exception as exc:
                _say(msg, f"{type(exc).__name__}: {exc}", False)

        def choose():
            _say(msg, tr("Show your victory screen: the area picker opens in 5 seconds."))
            self.after(5000, choose_now)

        def learn_later(kind):
            _say(msg, tr("Switch to your game: the screen is captured in 5 seconds."))
            self.after(5000, lambda: (_say(msg, plugin.learn(kind), plugin.auto_ok), refresh()))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkButton(r, text=tr("Choose screen area"), width=150, command=choose).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r, text=tr("Learn win screen"), width=150, command=lambda: learn_later("win")).pack(side="left", padx=3)
        ctk.CTkButton(r, text=tr("Learn loss screen"), width=150, command=lambda: learn_later("loss")).pack(side="left", padx=3)
        r2 = ctk.CTkFrame(body, fg_color="transparent")
        r2.pack(fill="x", pady=3)
        ctk.CTkButton(r2, text=tr("Forget win screens"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: (a.forget("win"), plugin.save(), refresh())).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r2, text=tr("Forget loss screens"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: (a.forget("loss"), plugin.save(), refresh())).pack(side="left", padx=3)
        ctk.CTkButton(r2, text=tr("Test now"), width=110, command=lambda: _say(msg, plugin.probe())).pack(side="left", padx=3)
        tr_row = ctk.CTkFrame(body, fg_color="transparent")
        tr_row.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(tr_row, text=tr("Tolerance (higher = recognises more, but may count wrongly)"), anchor="w").pack(side="left")
        tv = ctk.CTkSlider(tr_row, from_=5, to=60, number_of_steps=55, width=180)
        tv.set(a.tolerance)

        def tol(v):
            a.tolerance = int(float(v))
        tv.configure(command=tol)
        tv.bind("<ButtonRelease-1>", lambda _e: plugin.save())
        tv.pack(side="left", padx=10)
        info.pack(fill="x", pady=(4, 0))
        msg.pack(fill="x")
        refresh()

    def tab_timers(self, area, plugin):
        tm = plugin.timers
        body = self.card(area, "Timers", 0)
        ui.muted(body, "Up to six named timers (respawn, objective, cooldown). Start them with a click or your own hotkey (Settings > Hotkeys: “Start timer 1 …”); "
                       "pressing again restarts the timer. At the end you get a message with a sound. Running timers show in the timer overlay.").pack(fill="x", pady=(0, 6))
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        rows = []
        for i in range(len(tm.slots)):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=str(i + 1), width=24).pack(side="left")
            name = ctk.CTkEntry(r, width=170)
            name.insert(0, tm.slots[i]["name"])
            name.pack(side="left", padx=4)
            sec = ctk.CTkEntry(r, width=70)
            sec.insert(0, str(tm.slots[i]["seconds"]))
            sec.pack(side="left", padx=4)
            ctk.CTkLabel(r, text=tr("seconds"), text_color=theme.MUTED).pack(side="left")
            rows.append((name, sec))
            ctk.CTkButton(r, text="▶", width=40, command=lambda i=i: (save(quiet=True), plugin.start_timer(i))).pack(side="left", padx=6)
            ctk.CTkButton(r, text="■", width=40, fg_color=theme.c("hover"), text_color=theme.TEXT, command=lambda i=i: tm.stop(i)).pack(side="left")

        def save(quiet=False):
            try:
                for i, (n, sc) in enumerate(rows):
                    tm.configure(i, n.get(), int(sc.get()))
            except ValueError:
                _say(msg, tr("Please enter a number."), False)
                return
            plugin.save()
            if not quiet:
                _say(msg, tr("Saved."))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text=tr("Save"), width=90, command=save).pack(side="left")
        ctk.CTkButton(r, text=tr("Stop all timers"), width=150, fg_color="#c0392b", hover_color="#962d22", command=plugin.stop_timers).pack(side="left", padx=8)
        msg.pack(fill="x")
        self._overlay_switch(body, plugin, "timers", "Show the timer overlay")
        self._design_card(area, plugin.timers_overlay, plugin, 1, colour_label="Text colour")

    def tab_notes(self, area, plugin):
        n = plugin.notes
        body = self.card(area, "Notes per map", 0)
        ui.muted(body, "Short notes for strategies, builds or callouts – one per map or game. The overlay shows the note of the chosen map; "
                       "a hotkey (Settings > Hotkeys: “Notes: next map”) switches between them.").pack(fill="x", pady=(0, 6))
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Map / game"), width=110, anchor="w").pack(side="left")
        name = ctk.CTkComboBox(r, values=list(n.maps) or [""], width=220)
        name.set(n.current)
        name.pack(side="left")
        text = ctk.CTkTextbox(body, height=150, width=560)
        text.pack(anchor="w", pady=4)
        text.insert("1.0", n.text())

        def load(choice=None):
            n.current = (choice or name.get()).strip()
            text.delete("1.0", "end")
            text.insert("1.0", n.text())
        name.configure(command=load)

        def save():
            saved = n.set_text(name.get(), text.get("1.0", "end").rstrip("\n"))
            if not saved:
                _say(msg, tr("Please enter a name."), False)
                return
            name.configure(values=list(n.maps))
            plugin.save()
            _say(msg, tr("Saved."))

        def delete():
            n.delete(name.get().strip())
            name.configure(values=list(n.maps) or [""])
            name.set(n.current)
            load(n.current)
            plugin.save()
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkButton(r, text=tr("Save"), width=90, command=save).pack(side="left")
        ctk.CTkButton(r, text=tr("Delete"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT, command=delete).pack(side="left", padx=6)
        msg.pack(fill="x")
        self._overlay_switch(body, plugin, "notes", "Show the notes overlay")
        self._design_card(area, plugin.notes_overlay, plugin, 1, colour_label="Text colour")

    def tab_net(self, area, plugin):
        body = self.card(area, "Ping & connection", 0)
        ui.muted(body, "Measures the ping to a server every 2 seconds and shows the average and the packet loss of the last 20 measurements. "
                       "Enter the address of your game server, with a port if you know it (server.example:27015), or leave 1.1.1.1 for a general check. The ping is the time to open a connection to that address (port 443 if none is given); it sends no game data.").pack(fill="x", pady=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Server address"), width=130, anchor="w").pack(side="left")
        host = ctk.CTkEntry(r, width=220)
        host.insert(0, plugin.ping_host)
        host.pack(side="left")
        msg = ctk.CTkLabel(body, text="", anchor="w")

        def save():
            h = host.get().strip()
            import re
            if not re.fullmatch(r"[A-Za-z0-9.\-]{1,60}(:\d{1,5})?", h):
                _say(msg, tr("Please enter a host name or an IP address."), False)
                return
            plugin.ping_host = h
            plugin.pings.values.clear()
            plugin.save()
            _say(msg, tr("Saved."))
        ctk.CTkButton(r, text=tr("Save"), width=80, command=save).pack(side="left", padx=6)
        msg.pack(fill="x")
        live = ctk.CTkLabel(body, text="", anchor="w", font=ctk.CTkFont(size=15, weight="bold"))
        live.pack(fill="x", pady=4)

        def tick():
            if live.winfo_exists():
                if live.winfo_ismapped():
                    live.configure(text=plugin.pings.text())
                live.after(1000, tick)
        tick()
        self._overlay_switch(body, plugin, "net", "Show the network overlay")
        ui.muted(body, "The graph shows the ping of the last 60 seconds as a line; red bars are lost packets. "
                       "It shows the network only: the frame rate of a game cannot be measured without intervening in the game.").pack(fill="x", pady=(8, 0))
        self._overlay_switch(body, plugin, "netgraph", "Show the ping graph")
        self._design_card(area, plugin.net_overlay, plugin, 1, colour_label="Text colour")

    # ---------------------------------------------------------------- Overlay-Aussehen
    def _design_card(self, area, o, plugin, row, colour_label):
        """Schrift, Farbe, Größe, Position (mit "Position speichern") und Sperre für ein Overlay."""
        st = o.style
        body = self.card(area, "Overlay design", row)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")

        def changed(restyle=True):
            st.clamp()
            if restyle:
                o.restyle()
            plugin.save()

        def line(label):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            return r

        r = line("Font")
        fm = ctk.CTkOptionMenu(r, values=FONTS, width=170, command=lambda v: (setattr(st, "font", v), changed()))
        fm.set(st.font)
        fm.pack(side="left")
        r = line("Size")
        sz = ctk.CTkSlider(r, from_=8, to=48, number_of_steps=40, width=200)
        sz.set(min(48, st.size))
        szl = ctk.CTkLabel(r, text=str(st.size), width=36)
        sz.configure(command=lambda v: szl.configure(text=str(int(v))))
        sz.bind("<ButtonRelease-1>", lambda _e: (setattr(st, "size", int(sz.get())), changed()))
        sz.pack(side="left")
        szl.pack(side="left", padx=6)
        r = line(colour_label)
        sw = ctk.CTkButton(r, text="", width=44, fg_color=st.color, hover=False)

        def pick():
            c = colorchooser.askcolor(color=st.color, parent=self.app)[1]
            if c:
                st.color = c
                sw.configure(fg_color=st.color)
                changed()
        sw.configure(command=pick)
        sw.pack(side="left")
        r = line("Opacity")
        op = ctk.CTkSlider(r, from_=30, to=100, number_of_steps=70, width=200)
        op.set(st.opacity)
        op.bind("<ButtonRelease-1>", lambda _e: (setattr(st, "opacity", int(op.get())), changed()))
        op.pack(side="left")
        for attr, label in (("bold", "Bold text"), ("outline", "Dark outline (readable on any background)"), ("background", "Dark box behind the text")):
            v = tk.BooleanVar(value=getattr(st, attr))
            ctk.CTkSwitch(body, text=tr(label), variable=v, command=lambda a=attr, v=v: (setattr(st, a, v.get()), changed())).pack(anchor="w", pady=2)

        ctk.CTkLabel(body, text=tr("Position"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(10, 2))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ex, ey = ctk.CTkEntry(r, width=70), ctk.CTkEntry(r, width=70)
        ctk.CTkLabel(r, text="X").pack(side="left")
        ex.pack(side="left", padx=(4, 12))
        ctk.CTkLabel(r, text="Y").pack(side="left")
        ey.pack(side="left", padx=4)

        def fill():
            x, y = o.current_position()
            for e, val in ((ex, x), (ey, y)):
                e.delete(0, "end")
                e.insert(0, str(val))
        fill()

        def apply_xy():
            try:
                o.move_to(int(ex.get()), int(ey.get()))
            except ValueError:
                _say(msg, tr("Please enter a number."), False)
                return
            fill()
            plugin.save()
            _say(msg, "")
        ctk.CTkButton(r, text=tr("Apply"), width=80, command=apply_xy).pack(side="left", padx=8)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        for name in CORNERS:
            ctk.CTkButton(r, text=tr(name), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda n=name: (o.move_corner(n), fill(), plugin.save())).pack(side="left", padx=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=(6, 3))

        def save_pos():
            x, y = o.current_position()
            o.move_to(x, y)
            fill()
            plugin.save()
            _say(msg, tr("Position saved: {x}, {y}", x=x, y=y))
        ctk.CTkButton(r, text="📌  " + tr("Save position"), width=170, command=save_pos).pack(side="left")
        ctk.CTkButton(r, text=tr("Read current position"), width=170, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=fill).pack(side="left", padx=8)
        lk = tk.BooleanVar(value=st.locked)
        ctk.CTkSwitch(body, text=tr("Lock (clicks pass through – use this in games)"), variable=lk,
                      command=lambda: (o.lock(lk.get()), plugin.save())).pack(anchor="w", pady=(8, 2))
        ui.muted(body, "Unlocked, you can drag the overlay with the mouse and then press “Save position”.").pack(fill="x")
        msg.pack(fill="x")

    # ---------------------------------------------------------------- Tests
    def tab_tests(self, area, plugin):
        market = None
        comm = self.app.plugin_by_id.get("community")
        body = self.card(area, "CPS test (5 seconds)", 0)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        st = {"test": cps.CpsTest()}
        btn = ctk.CTkButton(body, text=tr("Click here as fast as you can!"), height=110, font=ctk.CTkFont(size=18, weight="bold"))
        btn.pack(fill="x", pady=6)
        info = ctk.CTkLabel(body, text=tr("Waiting for the first click …"), anchor="w")
        info.pack(fill="x")

        def board(kind, holder, fmt):
            def load():
                svc = comm.service() if comm else None
                if svc is None:
                    self.app.call_soon(_say, msg, tr("The leaderboard needs a cloud account."), False)
                    return
                try:
                    rows = MarketService(svc).top(kind)
                except Exception as exc:
                    self.app.call_soon(_say, msg, tr(str(exc)), False)
                    return
                self.app.call_soon(show, rows)

            def show(rows):
                if not holder.winfo_exists():
                    return
                for w in holder.winfo_children():
                    w.destroy()
                if not rows:
                    ctk.CTkLabel(holder, text=tr("No scores yet."), text_color=theme.MUTED).pack(anchor="w")
                for i, r in enumerate(rows, 1):
                    ctk.CTkLabel(holder, text=f"{i}.  {r['display_name']} (@{r['handle']})  –  {fmt(r['value'])}", anchor="w",
                                 text_color=theme.accent() if r["mine"] else theme.TEXT).pack(fill="x")
            threading.Thread(target=load, daemon=True).start()

        def submit(kind, value, holder, fmt):
            def work():
                svc = comm.service() if comm else None
                if svc is None:
                    self.app.call_soon(_say, msg, tr("The leaderboard needs a cloud account."), False)
                    return
                try:
                    best = MarketService(svc).submit_score(kind, value)
                    self.app.call_soon(_say, msg, tr("Your best: {v}", v=fmt(best)))
                except Exception as exc:
                    self.app.call_soon(_say, msg, tr(str(exc)), False)
                board(kind, holder, fmt)
            threading.Thread(target=work, daemon=True).start()

        cps_board = ctk.CTkFrame(body, fg_color="transparent")
        fmt_cps = lambda v: f"{float(v):g} CPS"

        def click():
            t = st["test"]
            if t.finished:
                st["test"] = t = cps.CpsTest()
            t.click()
            info.configure(text=tr("{n} clicks – {s:.1f} s left", n=t.clicks, s=t.remaining()))
            if t.clicks == 1:
                btn.after(100, check)

        def check():
            t = st["test"]
            if t.finished:
                info.configure(text=tr("Done: {c} CPS ({n} clicks)", c=f"{t.cps():g}", n=t.clicks))
                if t.valid():
                    submit("cps5", t.cps(), cps_board, fmt_cps)
            else:
                info.configure(text=tr("{n} clicks – {s:.1f} s left", n=t.clicks, s=t.remaining()))
                btn.after(100, check)
        btn.configure(command=click)
        ctk.CTkLabel(body, text=tr("Leaderboard – CPS"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(8, 0))
        cps_board.pack(fill="x")
        msg.pack(fill="x")
        board("cps5", cps_board, fmt_cps)

        body2 = self.card(area, "Reaction test", 1)
        rbtn = ctk.CTkButton(body2, text=tr("Start"), height=110, font=ctk.CTkFont(size=18, weight="bold"))
        rbtn.pack(fill="x", pady=6)
        rinfo = ctk.CTkLabel(body2, text="", anchor="w")
        rinfo.pack(fill="x")
        rboard = ctk.CTkFrame(body2, fg_color="transparent")
        fmt_ms = lambda v: f"{float(v):g} ms"
        rs = {"t": None}

        def rclick():
            t = rs["t"]
            if t is None or t.result is not None or t.too_early:
                rs["t"] = t = cps.ReactionTest()
                rbtn.configure(text=tr("Wait for green …"), fg_color="#b45309")
                rbtn.after(int(t.delay * 1000), lambda: rs["t"] is t and rbtn.configure(text=tr("CLICK NOW!"), fg_color="#2e9d5b"))
                rinfo.configure(text="")
                return
            res = t.click()
            if res is None:
                rbtn.configure(text=tr("Too early! Click to try again."), fg_color="#c0392b")
                rinfo.configure(text="")
            else:
                rbtn.configure(text=tr("Click to try again"), fg_color=theme.accent())
                rinfo.configure(text=f"{res:g} ms – {tr(cps.rating(res))}")
                if 80 <= res <= 2000:
                    submit("reaction", res, rboard, fmt_ms)
        rbtn.configure(command=rclick)
        ctk.CTkLabel(body2, text=tr("Leaderboard – reaction time"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(8, 0))
        rboard.pack(fill="x")
        board("reaction", rboard, fmt_ms)
        ui.muted(body2, "Scores are shown with your community name. You need a set-up community account. Impossible values are rejected.").pack(fill="x", pady=(6, 0))

    # ---------------------------------------------------------------- Screenshot
    def tab_shot(self, area, plugin):
        body = self.card(area, "Screenshot", 0)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        ui.muted(body, "Press Ctrl+Shift+F11 anywhere (or the button), drag an area, and it is saved as a PNG. "
                       "On macOS the app needs the permission “Screen Recording”.").pack(fill="x", pady=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkButton(r, text="✂  " + tr("Take a screenshot"), width=190, command=lambda: self.app.after(300, plugin.screenshot)).pack(side="left")

        def folder():
            d = filedialog.askdirectory()
            if d:
                plugin.shot_folder = d
                plugin.save()
                _say(msg, tr("Saved to:") + " " + d)
        ctk.CTkButton(r, text=tr("Choose folder …"), width=150, fg_color=theme.c("hover"), text_color=theme.TEXT, command=folder).pack(side="left", padx=6)
        if plugin.shot_error:
            _say(msg, plugin.shot_error, False)
        msg.pack(fill="x")

        def tick():
            if not msg.winfo_exists():
                return
            if plugin.last_shot:
                s, plugin.last_shot = plugin.last_shot, ""
                _say(msg, s if s.startswith("error") else tr("Saved to:") + " " + s, not s.startswith("error"))
            msg.after(700, tick)
        tick()
