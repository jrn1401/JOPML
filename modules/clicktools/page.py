"""Seite "Click tools" (Reiter)."""
import threading
import time
import tkinter as tk
from tkinter import colorchooser

import customtkinter as ctk

from core import theme, ui, winutil
from core.hub import HubPage
from core.i18n import tr

from . import appprofiles, hotkeys, mousekeys, pixel, scheduler
from .crosshair import COVER_SHAPES, PRESETS, REACTIONS, SHAPES, CrosshairConfig


def _say(label, text, ok=True):
    if label.winfo_exists():
        label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)


def _entry(parent, label, value="", width=120):
    r = ctk.CTkFrame(parent, fg_color="transparent")
    r.pack(fill="x", pady=3)
    ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
    e = ctk.CTkEntry(r, width=width)
    e.insert(0, str(value))
    e.pack(side="left")
    return e


class ClickToolsPage(HubPage):
    def __init__(self, parent, plugin, mode="crosshair", clicker=None):
        """mode "crosshair": nur das Fadenkreuz. mode "clicker": Menüpunkt "Autoclicker" mit dem Autoclicker (clicker = dessen Plugin)
        und den Klick-Werkzeugen als Reiter."""
        self.clicker = clicker
        if mode == "clicker":
            super().__init__(parent, plugin, "Autoclicker & click tools",
                             "The autoclicker plus mouse and keyboard tools, hotkeys, colour trigger, scheduler and per-program profiles.", [
                ("Autoclicker", self._autoclicker_page, True), ("Mouse & keyboard", self.tab_mousekeys), ("Hotkeys", self.tab_hotkeys),
                ("Colour trigger", self.tab_pixel), ("Scheduler", self.tab_schedule), ("Program profiles", self.tab_apps)])
        else:
            super().__init__(parent, plugin, "Crosshair", "A crosshair overlay for the middle of your screen.", [
                ("Crosshair", self.tab_crosshair)])

    def _autoclicker_page(self, hub, plugin):
        from modules.autoclicker.page import AutoClickerPage
        return AutoClickerPage(self, self.clicker, embedded=True)

    # ---------------------------------------------------------------- Fadenkreuz
    def tab_crosshair(self, area, plugin):
        cfg = CrosshairConfig.from_dict(plugin.crosshair_cfg.to_dict())
        body = self.card(area, "Crosshair overlay", 0)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        vars_ = {}

        def apply(*_):
            try:
                cfg.shape = shape.get()
                cfg.color = col.get().strip()
                for k, s in vars_.items():
                    setattr(cfg, k, int(s.get()))
                plugin.update_crosshair(CrosshairConfig.from_dict(cfg.to_dict()))
            except (ValueError, tk.TclError):
                pass

        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Shape"), width=170, anchor="w").pack(side="left")
        shape = ctk.CTkOptionMenu(r, values=SHAPES, width=170, command=apply)
        shape.set(cfg.shape)
        shape.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Colour"), width=170, anchor="w").pack(side="left")
        col = ctk.CTkEntry(r, width=100)
        col.insert(0, cfg.color)
        col.pack(side="left")
        col.bind("<Return>", apply)

        def pick():
            c = colorchooser.askcolor(color=cfg.color)[1]
            if c:
                col.delete(0, "end")
                col.insert(0, c)
                apply()
        ctk.CTkButton(r, text=tr("Pick …"), width=70, command=pick).pack(side="left", padx=6)
        for key, label, lo, hi in (("size", "Size", 2, 80), ("thickness", "Thickness", 1, 8), ("gap", "Gap", 0, 40),
                                   ("opacity", "Opacity (%)", 20, 100), ("offset_x", "Shift left/right", -400, 400),
                                   ("offset_y", "Shift up/down", -400, 400)):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            s = ctk.CTkSlider(r, from_=lo, to=hi, number_of_steps=hi - lo, width=240, command=apply)
            s.set(getattr(cfg, key))
            s.pack(side="left")
            vars_[key] = s
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(r, text=tr("Presets"), width=170, anchor="w").pack(side="left")

        def preset(name):
            p = CrosshairConfig.from_dict(PRESETS[name])
            shape.set(p.shape)
            col.delete(0, "end")
            col.insert(0, p.color)
            for k, s in vars_.items():
                s.set(getattr(p, k))
            apply()
        for n in PRESETS:
            ctk.CTkButton(r, text=tr(n), width=95, height=26, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda n=n: preset(n)).pack(side="left", padx=2)
        # Abdecken und Reagieren
        ctk.CTkLabel(body, text=tr("Game crosshair and reactions"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(12, 2))
        cv = tk.BooleanVar(value=cfg.cover)
        hv = tk.BooleanVar(value=cfg.hide_on_aim)
        rv = tk.BooleanVar(value=cfg.react_on)
        kv = tk.BooleanVar(value=cfg.keep_top)

        def cover_changed():
            cfg.cover, cfg.hide_on_aim, cfg.react_on, cfg.keep_top = cv.get(), hv.get(), rv.get(), kv.get()
            apply()
        ctk.CTkSwitch(body, text=tr("Cover the crosshair of the game"), variable=cv, command=cover_changed).pack(anchor="w", pady=2)
        ui.muted(body, "Draws a filled shape under your crosshair so the game's own crosshair is hidden. “Cross” covers only the lines of the game's crosshair, "
                       "so you still see everything else. Set the size so the lines are just covered (the game's crosshair must be completely inside).").pack(fill="x")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=2)
        ctk.CTkLabel(r, text=tr("Cover shape"), width=170, anchor="w").pack(side="left")
        cshown = [tr(x) for x in COVER_SHAPES]
        csm = ctk.CTkOptionMenu(r, values=cshown, width=170, command=lambda v: (setattr(cfg, "cover_shape", COVER_SHAPES[cshown.index(v)]), apply()))
        csm.set(tr(cfg.cover_shape))
        csm.pack(side="left")
        for key, label, lo, hi in (("cover_size", "Cover size", 2, 120), ("cover_thickness", "Cover line width (Cross)", 1, 40)):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            sl = ctk.CTkSlider(r, from_=lo, to=hi, number_of_steps=hi - lo, width=240,
                               command=lambda _v, k=key: (setattr(cfg, k, int(vars_[k].get())), apply()))
            sl.set(getattr(cfg, key))
            sl.pack(side="left")
            vars_[key] = sl
        av = tk.BooleanVar(value=cfg.cover_auto)
        ctk.CTkSwitch(body, text=tr("Take the cover colour from the surroundings (blends in)"), variable=av,
                      command=lambda: (setattr(cfg, "cover_auto", av.get()), apply())).pack(anchor="w", pady=(4, 2))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=2)
        ctk.CTkLabel(r, text=tr("Fixed cover colour"), width=170, anchor="w").pack(side="left")
        ccb = ctk.CTkButton(r, text="", width=44, fg_color=cfg.cover_color, hover=False)

        def pick_cover():
            c = colorchooser.askcolor(color=cfg.cover_color)[1]
            if c:
                cfg.cover_color = c
                ccb.configure(fg_color=c)
                apply()
        ccb.configure(command=pick_cover)
        ccb.pack(side="left")
        ctk.CTkSwitch(body, text=tr("React while shooting (left mouse button held)"), variable=rv, command=cover_changed).pack(anchor="w", pady=(8, 2))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(r, text=tr("Reaction while shooting"), width=170, anchor="w").pack(side="left")
        shown = [tr(x) for x in REACTIONS]
        rm = ctk.CTkOptionMenu(r, values=shown, width=170, command=lambda v: (setattr(cfg, "react", REACTIONS[shown.index(v)]), apply()))
        rm.set(tr(cfg.react))
        rm.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=2)
        ctk.CTkLabel(r, text=tr("Reaction colour"), width=170, anchor="w").pack(side="left")
        rcb = ctk.CTkButton(r, text="", width=44, fg_color=cfg.react_color, hover=False)

        def pick_react():
            c = colorchooser.askcolor(color=cfg.react_color)[1]
            if c:
                cfg.react_color = c
                rcb.configure(fg_color=c)
                apply()
        rcb.configure(command=pick_react)
        rcb.pack(side="left")
        for key, label, lo, hi in (("spread_px", "Spread when shooting (px)", 0, 60), ("spread_rise_ms", "Opens in (ms)", 10, 600),
                                   ("spread_fall_ms", "Closes in (ms)", 10, 1000)):
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            sl = ctk.CTkSlider(r, from_=lo, to=hi, number_of_steps=hi - lo, width=240,
                               command=lambda _v, k=key: (setattr(cfg, k, int(vars_[k].get())), apply()))
            sl.set(getattr(cfg, key))
            sl.pack(side="left")
            vars_[key] = sl
        ctk.CTkLabel(body, text=tr("Measure the spread from the game"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", pady=(10, 2))
        ui.muted(body, "Copies how far the crosshair of your game opens when you shoot. The launcher watches the lines of the game's crosshair on your screen "
                       "(only what you see anyway; no game memory). Your own crosshair is hidden during the measurement. "
                       "Start, switch to the game, stand still, then hold the left mouse button for about 2 seconds. Works in windowed or borderless mode.").pack(fill="x")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Crosshair colour in the game"), width=170, anchor="w").pack(side="left")
        game_col = ctk.CTkEntry(r, width=100, placeholder_text="#ff0000")
        game_col.pack(side="left")
        ctk.CTkLabel(r, text=tr("(empty = detect)"), text_color=theme.MUTED).pack(side="left", padx=8)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Colour tolerance"), width=170, anchor="w").pack(side="left")
        tol = ctk.CTkSlider(r, from_=10, to=120, number_of_steps=110, width=240)
        tol.set(40)
        tol.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        cal_btn = ctk.CTkButton(r, text="📏  " + tr("Measure the spread"), width=190,
                                command=lambda: _say(cal_msg, tr(err), False) if (err := plugin.calibrate_spread_start(game_col.get(), int(tol.get()))) else None)
        cal_btn.pack(side="left")
        cal_stop = ctk.CTkButton(r, text=tr("Cancel"), width=90, fg_color=theme.c("hover"), text_color=theme.TEXT, command=plugin.calibrate_spread_cancel)
        cal_stop.pack(side="left", padx=8)
        cal_msg = ctk.CTkLabel(body, text="", wraplength=620, justify="left", anchor="w")
        cal_msg.pack(fill="x")

        def cal_tick():
            if not cal_msg.winfo_exists():
                return
            st = plugin.spread_cal
            ui.cfg(cal_btn, state="disabled" if st["running"] else "normal")
            ui.cfg(cal_stop, state="normal" if st["running"] else "disabled")
            ui.cfg(cal_msg, text=st["text"], text_color=theme.TEXT if st["running"] or st["ok"] is None else (theme.OK if st["ok"] else theme.DANGER))
            cal_msg.after(400, cal_tick)

        def cal_done():
            if not cal_msg.winfo_exists():
                return
            new = plugin.crosshair_cfg
            for k in ("spread_px", "spread_rise_ms", "spread_fall_ms"):
                cfg.__dict__[k] = new.__dict__[k]
                vars_[k].set(new.__dict__[k])
            cfg.react_on, cfg.react = new.react_on, new.react
            rv.set(cfg.react_on)
            rm.set(tr(cfg.react))
        plugin.on_spread_change = cal_done
        cal_tick()
        ctk.CTkSwitch(body, text=tr("Hide while aiming (right mouse button held)"), variable=hv, command=cover_changed).pack(anchor="w", pady=(6, 2))
        ctk.CTkSwitch(body, text=tr("Keep the crosshair on top of the game"), variable=kv, command=cover_changed).pack(anchor="w", pady=2)
        ui.muted(body, "The reaction follows the left mouse button (colour change or spreading apart), hiding follows the right one. "
                       "It reacts to your clicks, not to what happens in the game.").pack(fill="x")
        sw = tk.BooleanVar(value=plugin.crosshair_on)
        ctk.CTkSwitch(body, text=tr("Show the crosshair"), variable=sw,
                      command=lambda: plugin.show_crosshair() if sw.get() else plugin.hide_crosshair()).pack(anchor="w", pady=(10, 2))
        ui.muted(body, "Only a visual aid on top of your screen. On Windows clicks pass through it; on macOS and Linux it may catch the mouse "
                       "depending on the desktop. Some games in exclusive fullscreen hide it – use borderless window mode. "
                       "Check the rules of your game: overlays can be forbidden in online games.").pack(fill="x", pady=(6, 0))
        msg.pack(fill="x")
        self._profiles_card(area, plugin)

    def _profiles_card(self, area, plugin):
        """Fadenkreuz-Profile je Spiel: speichern, laden, beim Wechsel in ein Programm automatisch laden."""
        body = self.card(area, "Crosshair profiles per game", 1)
        ui.muted(body, "Save the current crosshair (with cover and spread) under a name. If you enter part of the program's window title or file name "
                       "(for example “valorant”), the profile loads by itself when that program is in the foreground. "
                       "Keys for “Crosshair: next profile” and “show / hide” are set under Settings > Hotkeys.").pack(fill="x", pady=(0, 6))
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        names = list(plugin.xh_profiles)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        menu = ctk.CTkOptionMenu(r, values=names or ["–"], width=200)
        menu.set(plugin.xh_current if plugin.xh_current in names else (names[0] if names else "–"))
        menu.pack(side="left")

        def rebuild():
            for w in area.winfo_children():
                w.destroy()
            self.tab_crosshair(area, plugin)

        def load():
            if plugin.xh_load_profile(menu.get()):
                rebuild()

        def delete():
            if menu.get() in plugin.xh_profiles:
                plugin.xh_delete_profile(menu.get())
                rebuild()
        ctk.CTkButton(r, text=tr("Load"), width=80, command=load).pack(side="left", padx=6)
        ctk.CTkButton(r, text=tr("Delete"), width=80, fg_color=theme.c("hover"), text_color=theme.TEXT, command=delete).pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        name = ctk.CTkEntry(r, width=160, placeholder_text=tr("Profile name"))
        name.pack(side="left")
        prog = ctk.CTkEntry(r, width=180, placeholder_text=tr("Program (optional)"))
        prog.pack(side="left", padx=6)
        if plugin.xh_current in plugin.xh_profiles:
            name.insert(0, plugin.xh_current)
            prog.insert(0, plugin.xh_profiles[plugin.xh_current]["program"])

        def save():
            err = plugin.xh_save_profile(name.get(), prog.get())
            if err:
                _say(msg, tr(err), False)
            else:
                rebuild()
        ctk.CTkButton(r, text=tr("Save profile"), width=120, command=save).pack(side="left")
        msg.pack(fill="x")

    # ---------------------------------------------------------------- Maus & Tastatur
    def tab_mousekeys(self, area, plugin):
        mk = plugin.mk
        msg = ctk.CTkLabel(area, text="", anchor="w", wraplength=620, justify="left")

        def save():
            plugin.save()
            err = plugin.apply_hotkeys()
            _say(msg, err or tr("Saved."), not err)

        def menu(parent, label, values, current, labels=None, width=170):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            shown = [tr(labels.get(v, v)) if labels else tr(v) for v in values]
            m = ctk.CTkOptionMenu(r, values=shown, width=width)
            m.set(tr(labels.get(current, current)) if labels else tr(current))
            m.pack(side="left")
            return lambda: values[shown.index(m.get())] if m.get() in shown else values[0]

        def header(parent, key, label, on_toggle=None):
            v = tk.BooleanVar(value=mk.cfg[key]["on"])

            def changed():
                mk.cfg[key]["on"] = v.get()
                if on_toggle:
                    on_toggle(v.get())
                save()
            ctk.CTkSwitch(parent, text=tr(label), variable=v, command=changed).pack(anchor="w", pady=(0, 4))

        def number(parent, key, field, label, lo, hi, width=80):
            e = _entry(parent, label, mk.cfg[key][field], width=width)

            def done(_e=None):
                try:
                    mk.cfg[key][field] = max(lo, min(hi, int(float(e.get()))))
                except ValueError:
                    pass
                e.delete(0, "end")
                e.insert(0, str(mk.cfg[key][field]))
                save()
            e.bind("<FocusOut>", done)
            e.bind("<Return>", done)

        def hotkey(parent, key):
            e = _entry(parent, "Shortcut", mk.cfg[key]["hotkey"].replace("<", "").replace(">", ""), width=140)

            def done(_e=None):
                try:
                    mk.cfg[key]["hotkey"] = hotkeys.normalize_hotkey(e.get())
                    save()
                except ValueError as exc:
                    _say(msg, str(exc), False)
            e.bind("<FocusOut>", done)
            e.bind("<Return>", done)

        body = self.card(area, "Multi-click on one key", 0)
        ui.muted(body, "Pressing the shortcut sends a double, triple (or more) click at the mouse position – handy where one click is not enough.").pack(fill="x", pady=(0, 6))
        header(body, "multiclick", "On")
        hotkey(body, "multiclick")
        btn = menu(body, "Mouse button", mousekeys.BUTTONS, mk.cfg["multiclick"]["button"])
        number(body, "multiclick", "count", "Clicks (2–5)", 2, 5)
        number(body, "multiclick", "delay_ms", "Pause between clicks (ms)", 0, 500)
        btn_get = btn

        def btn_changed(*_):
            mk.cfg["multiclick"]["button"] = btn_get()
            save()
        ctk.CTkButton(body, text=tr("Apply button"), width=120, command=btn_changed).pack(anchor="w", pady=(4, 0))

        body = self.card(area, "Hold instead of press", 1)
        ui.muted(body, "One press of the shortcut holds a key or mouse button down, the next press releases it – for toggle sprint or auto-walk.").pack(fill="x", pady=(0, 6))
        header(body, "holdtoggle", "On", lambda on: (not on) and mk.holding and mk.toggle_hold())
        hotkey(body, "holdtoggle")
        tgt = menu(body, "Key to hold", mousekeys.HOLD_TARGETS, mk.cfg["holdtoggle"]["target"],
                   labels={"mouse_left": "Left mouse button", "mouse_right": "Right mouse button"})

        def tgt_changed(*_):
            if mk.holding:
                mk.toggle_hold()
            mk.cfg["holdtoggle"]["target"] = tgt()
            save()
        ctk.CTkButton(body, text=tr("Apply key"), width=120, command=tgt_changed).pack(anchor="w", pady=(4, 0))

        body = self.card(area, "Auto-scroll", 2)
        ui.muted(body, "The shortcut starts and stops slow automatic scrolling in the window under the mouse.").pack(fill="x", pady=(0, 6))
        header(body, "autoscroll", "On", lambda on: (not on) and mk.scrolling and mk.toggle_scroll())
        hotkey(body, "autoscroll")
        direction = menu(body, "Direction", ["down", "up"], mk.cfg["autoscroll"]["direction"], labels={"down": "Down", "up": "Up"})
        number(body, "autoscroll", "speed", "Speed (steps per second)", 1, 30)

        def dir_changed(*_):
            was = mk.scrolling
            if was:
                mk.toggle_scroll()
            mk.cfg["autoscroll"]["direction"] = direction()
            save()
        ctk.CTkButton(body, text=tr("Apply direction"), width=140, command=dir_changed).pack(anchor="w", pady=(4, 0))

        body = self.card(area, "Anti-AFK", 3)
        ui.muted(body, "Keeps you from being marked away (Teams, Discord, games that allow it): from time to time the mouse moves one pixel and back, "
                       "or a harmless Shift key is tapped. Check the rules of your game – some forbid it.").pack(fill="x", pady=(0, 6))
        header(body, "antiafk", "On", lambda on: mk.start_afk() if on else mk.stop_afk())
        number(body, "antiafk", "interval_s", "Every (seconds, 10–600)", 10, 600)
        mode = menu(body, "Method", ["mouse", "key"], mk.cfg["antiafk"]["mode"], labels={"mouse": "Move the mouse by one pixel", "key": "Tap the Shift key"}, width=240)

        def mode_changed(*_):
            mk.cfg["antiafk"]["mode"] = mode()
            if mk.afk_running:
                mk.start_afk()
            save()
        ctk.CTkButton(body, text=tr("Apply method"), width=140, command=mode_changed).pack(anchor="w", pady=(4, 0))

        body = self.card(area, "More", 4)
        ui.muted(body, "Record click sequences and play them back under “My macros”. Random pauses: write “wait 100ms-300ms” in a macro (a random time "
                       "in between). All of these stop at once with the emergency stop.").pack(fill="x")
        msg.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 10))

    # ---------------------------------------------------------------- Hotkeys
    def tab_hotkeys(self, area, plugin):
        body = self.card(area, "Hotkey manager", 0)
        ui.muted(body, "A shortcut can press a key, type a text block or start a saved macro. The original shortcut still reaches "
                       "other programs (keys are not blocked).").pack(fill="x", pady=(0, 6))
        listbox = ctk.CTkFrame(body, fg_color="transparent")
        listbox.pack(fill="x")
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")

        def render():
            for w in listbox.winfo_children():
                w.destroy()
            for r in plugin.rules:
                f = ctk.CTkFrame(listbox, fg_color=theme.c("inset"), corner_radius=8)
                f.pack(fill="x", pady=2)
                shown = r.value if len(r.value) < 40 else r.value[:37] + "…"
                ctk.CTkLabel(f, text=f"{r.hotkey}   →   {tr(r.action.capitalize())}: {shown}", anchor="w").pack(side="left", padx=10, pady=6)
                ctk.CTkButton(f, text="🗑", width=30, height=24, fg_color="gray35", hover_color="gray25",
                              command=lambda rr=r: remove(rr)).pack(side="right", padx=6)

        def remove(r):
            plugin.rules.remove(r)
            plugin.save()
            _say(msg, plugin.apply_hotkeys() or tr("Saved."), not plugin.hotkey_error)
            render()
        render()
        hk = _entry(body, "Shortcut (e.g. ctrl+alt+k)", width=180)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Action"), width=170, anchor="w").pack(side="left")
        action = ctk.CTkOptionMenu(r, values=[tr("Text"), tr("Key"), tr("Macro")], width=120)
        action.pack(side="left")
        val = _entry(body, "Text / key / macro name", width=280)

        def add():
            act = {tr("Text"): "text", tr("Key"): "key", tr("Macro"): "macro"}[action.get()]
            try:
                if len(plugin.rules) >= hotkeys.MAX_RULES:
                    raise ValueError(tr("Too many shortcuts."))
                rule = hotkeys.Rule(hk.get(), act, val.get()).validate()
                if any(x.hotkey == rule.hotkey for x in plugin.rules):
                    raise ValueError(tr("This shortcut is already used."))
            except ValueError as exc:
                _say(msg, str(exc), False)
                return
            plugin.rules.append(rule)
            plugin.save()
            err = plugin.apply_hotkeys()
            _say(msg, err or tr("Saved."), not err)
            render()
        ctk.CTkButton(body, text=tr("Add shortcut"), width=150, command=add).pack(anchor="w", pady=(6, 2))
        if plugin.hotkey_error:
            _say(msg, plugin.hotkey_error, False)
        msg.pack(fill="x")

    # ---------------------------------------------------------------- Farb-Trigger
    def tab_pixel(self, area, plugin):
        body = self.card(area, "Colour trigger", 0)
        ui.muted(body, "Watches one pixel on the screen. When it shows the colour you chose, a saved macro starts. "
                       "On macOS the app needs the permission “Screen Recording”.").pack(fill="x", pady=(0, 6))
        c = plugin.pixel_cfg
        ex, ey = _entry(body, "X position", c.get("x", 500)), _entry(body, "Y position", c.get("y", 300))
        ecol = _entry(body, "Colour (#rrggbb)", c.get("color", "#ff0000"))
        etol = _entry(body, "Tolerance (0–255)", c.get("tol", 20))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Macro"), width=170, anchor="w").pack(side="left")
        macros = self.app.plugin_by_id.get("macros")
        names = macros.list_macros() if macros else []
        menu = ctk.CTkOptionMenu(r, values=names or [tr("(none saved)")], width=220)
        menu.set(c.get("macro") if c.get("macro") in names else (names[0] if names else tr("(none saved)")))
        menu.pack(side="left")
        once = tk.BooleanVar(value=bool(c.get("once", True)))
        ctk.CTkSwitch(body, text=tr("Only once, then stop"), variable=once).pack(anchor="w", pady=4)
        chg = tk.BooleanVar(value=bool(c.get("on_change", False)))
        ctk.CTkSwitch(body, text=tr("Trigger on any colour change (ignores the colour above; tolerance = how much it must change)"),
                      variable=chg).pack(anchor="w", pady=4)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        pick_btn = ctk.CTkButton(body, text=tr("Take position and colour from the mouse (3 s)"), width=330)

        def pick():
            pick_btn.configure(state="disabled")

            def work():
                for i in (3, 2, 1):
                    self.app.call_soon(pick_btn.configure, text=tr("Move the mouse … {n}", n=i))
                    time.sleep(1)
                try:
                    from pynput import mouse
                    x, y = mouse.Controller().position
                    px = pixel.grab_pixel(int(x), int(y))
                    self.app.call_soon(fill, int(x), int(y), "#%02x%02x%02x" % tuple(px[:3]))
                except Exception as exc:
                    self.app.call_soon(_say, msg, f"{type(exc).__name__}: {exc}", False)
                self.app.call_soon(pick_btn.configure, text=tr("Take position and colour from the mouse (3 s)"), state="normal")
            threading.Thread(target=work, daemon=True).start()

        def fill(x, y, hx):
            for e, v in ((ex, x), (ey, y), (ecol, hx)):
                e.delete(0, "end")
                e.insert(0, str(v))
            _say(msg, f"{x}, {y}  {hx}")
        pick_btn.configure(command=pick)
        pick_btn.pack(anchor="w", pady=4)

        def start():
            m = menu.get()
            plugin.pixel_cfg = {"x": ex.get(), "y": ey.get(), "color": ecol.get(), "tol": etol.get(), "macro": m, "once": once.get(), "on_change": chg.get()}
            plugin.save()
            err = plugin.start_pixel(ex.get(), ey.get(), ecol.get(), etol.get(), m if m in names else "", once.get(), chg.get())
            _say(msg, tr(err) if err else tr("Watching … (press Stop to end)"), not err)

        def stop():
            plugin.stop_pixel()
            _say(msg, tr("Stopped."))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkButton(r, text="▶  " + tr("Start watching"), width=150, fg_color="#2e9d5b", hover_color="#247a47", command=start).pack(side="left")
        ctk.CTkButton(r, text="■  " + tr("Stop"), width=100, fg_color="#c0392b", hover_color="#962d22", command=stop).pack(side="left", padx=6)
        msg.pack(fill="x")

        def tick():
            if msg.winfo_exists():
                if plugin.pixel_status and msg.winfo_ismapped():
                    _say(msg, tr(plugin.pixel_status), not plugin.pixel_status.startswith(("Err", "OS", "Attr")))
                    plugin.pixel_status = ""
                msg.after(500, tick)
        tick()

    # ---------------------------------------------------------------- Zeitplaner
    def tab_schedule(self, area, plugin):
        body = self.card(area, "Scheduler", 0)
        ui.muted(body, "Starts saved macros at a time of day or every N minutes. Works only while the launcher is running. "
                       "Missed appointments are not caught up.").pack(fill="x", pady=(0, 6))
        listbox = ctk.CTkFrame(body, fg_color="transparent")
        listbox.pack(fill="x")
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        logbox = ctk.CTkTextbox(body, height=110, fg_color=theme.c("inset"))

        def render():
            for w in listbox.winfo_children():
                w.destroy()
            for e in plugin.entries:
                f = ctk.CTkFrame(listbox, fg_color=theme.c("inset"), corner_radius=8)
                f.pack(fill="x", pady=2)
                when = tr("daily at {t}", t=e.at) if e.mode == "daily" else tr("every {n} min", n=e.minutes)
                ctk.CTkLabel(f, text=f"{e.name}  ·  {when}", anchor="w").pack(side="left", padx=10, pady=6)
                ctk.CTkButton(f, text="🗑", width=30, height=24, fg_color="gray35", hover_color="gray25",
                              command=lambda ee=e: remove(ee)).pack(side="right", padx=6)

        def remove(e):
            plugin.entries.remove(e)
            plugin.set_schedule(plugin.entries, on.get())
            render()
        macros = self.app.plugin_by_id.get("macros")
        names = macros.list_macros() if macros else []
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Macro"), width=170, anchor="w").pack(side="left")
        menu = ctk.CTkOptionMenu(r, values=names or [tr("(none saved)")], width=220)
        menu.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("When"), width=170, anchor="w").pack(side="left")
        mode = ctk.CTkOptionMenu(r, values=[tr("daily at"), tr("every N minutes")], width=150)
        mode.pack(side="left")
        val = ctk.CTkEntry(r, width=80)
        val.insert(0, "18:30")
        val.pack(side="left", padx=6)

        def add():
            daily = mode.get() == tr("daily at")
            try:
                if len(plugin.entries) >= scheduler.MAX_ENTRIES:
                    raise ValueError(tr("Too many entries."))
                m = menu.get() if menu.get() in names else ""
                e = scheduler.Entry(m, m, "daily" if daily else "interval",
                                    val.get() if daily else "12:00", val.get() if not daily else 30).validate()
            except ValueError as exc:
                _say(msg, str(exc), False)
                return
            plugin.entries.append(e)
            plugin.set_schedule(plugin.entries, on.get())
            _say(msg, tr("Saved."))
            render()
        ctk.CTkButton(body, text=tr("Add entry"), width=140, command=add).pack(anchor="w", pady=4)
        on = tk.BooleanVar(value=plugin.schedule_on)
        ctk.CTkSwitch(body, text=tr("Scheduler is on"), variable=on, command=lambda: plugin.set_schedule(plugin.entries, on.get())).pack(anchor="w", pady=4)
        ctk.CTkLabel(body, text=tr("Log"), anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", pady=(6, 0))
        logbox.pack(fill="x")
        msg.pack(fill="x")
        render()

        def tick():
            if logbox.winfo_exists():
                if logbox.winfo_ismapped():
                    txt = "\n".join(f"{t}  {s}" for t, s in plugin.sched.log[-30:])
                    if txt != getattr(tick, "last", None):
                        logbox.configure(state="normal")
                        logbox.delete("1.0", "end")
                        logbox.insert("1.0", txt)
                        logbox.configure(state="disabled")
                        tick.last = txt
                logbox.after(1500, tick)
        tick()

    # ---------------------------------------------------------------- Profile pro Programm
    def tab_apps(self, area, plugin):
        body = self.card(area, "Profiles per program", 0)
        ui.muted(body, "When the window you work in matches a name below, the autoclicker profile switches automatically "
                       "(never while it is clicking). Profiles are the ones you saved on the Autoclicker page.").pack(fill="x", pady=(0, 6))
        cur = ctk.CTkLabel(body, text="", anchor="w")
        cur.pack(fill="x")
        listbox = ctk.CTkFrame(body, fg_color="transparent")
        listbox.pack(fill="x", pady=4)
        msg = ctk.CTkLabel(body, text="", anchor="w", wraplength=620, justify="left")
        ac = self.app.plugin_by_id.get("autoclicker")
        names = sorted(p.stem for p in ac.profiles_dir().glob("*.json")) if ac else []

        def render():
            for w in listbox.winfo_children():
                w.destroy()
            for rl in plugin.app_rules:
                f = ctk.CTkFrame(listbox, fg_color=theme.c("inset"), corner_radius=8)
                f.pack(fill="x", pady=2)
                ctk.CTkLabel(f, text=f"“{rl.match}”  →  {rl.profile}", anchor="w").pack(side="left", padx=10, pady=6)
                ctk.CTkButton(f, text="🗑", width=30, height=24, fg_color="gray35", hover_color="gray25",
                              command=lambda x=rl: remove(x)).pack(side="right", padx=6)

        def remove(rl):
            plugin.app_rules.remove(rl)
            plugin.set_app_rules(plugin.app_rules, on.get())
            render()
        match = _entry(body, "Window or program contains", width=220)
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=tr("Profile"), width=170, anchor="w").pack(side="left")
        menu = ctk.CTkOptionMenu(r, values=names or [tr("(none saved)")], width=220)
        menu.pack(side="left")

        def add():
            try:
                rl = appprofiles.AppRule(match.get(), menu.get() if menu.get() in names else "").validate()
            except ValueError as exc:
                _say(msg, str(exc), False)
                return
            plugin.app_rules.append(rl)
            plugin.set_app_rules(plugin.app_rules, on.get())
            _say(msg, tr("Saved."))
            render()

        def look():
            w = winutil.active_window()
            cur.configure(text=tr("Active window:") + " " + (f"{w['title']}  [{w['proc']}]" if w else tr("not detected")))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkButton(r, text=tr("Add rule"), width=120, command=add).pack(side="left")
        ctk.CTkButton(r, text=tr("Show the active window (3 s)"), width=240, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: (cur.configure(text=tr("Switch to the window …")), cur.after(3000, look))).pack(side="left", padx=6)
        on = tk.BooleanVar(value=plugin.app_profiles_on)
        ctk.CTkSwitch(body, text=tr("Automatic switching is on"), variable=on, command=lambda: plugin.set_app_rules(plugin.app_rules, on.get())).pack(anchor="w", pady=4)
        msg.pack(fill="x")
        render()
