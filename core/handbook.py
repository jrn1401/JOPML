"""Handbuch für die KI-Hilfe (Englisch, eine Quelle der Wahrheit).

Der Launcher schickt dieses Handbuch bei jeder KI-Frage mit (core/cloud.py -> Edge Function jopml-ai). So kennt die KI immer
genau die Version, die der Nutzer hat, ohne dass die Server-Funktion neu eingespielt werden muss. tools/gen_knowledge.py schreibt
es zusätzlich als Rückfallebene in supabase/functions/jopml-ai/knowledge.ts.

BEI JEDER NEUEN VERSION: oben in CHANGELOG einen Eintrag mit der neuen Nummer ergänzen (neueste zuerst) und neue Funktionen in
SECTIONS beschreiben. tests/test_all.py (test_handbook_current) lässt den Build sonst fehlschlagen.
"""
from core.version import APP_VERSION

# (Version, [Änderungen]) – neueste zuerst
CHANGELOG = [
    ("1.7.9", ["Recoil trainer leaderboards: the new 'Leaderboard' tick box (on by default) sets the fixed standard values; before, the guide line was on by default, so no round ever counted. The trainer now also says why a round was not counted.",
               "New module 'Lua scripts' (menu item): run your own Lua scripts in a safe box (engine: lupa). A script can calculate, print(...), wait(ms) and run macro commands with macro(\"click left 500 300\") (same checks and panic key as the macro editor). os, io, require and similar are blocked; a counter hook ends endless loops when you press Stop or after 10 minutes. Add scripts on the page or in Settings > Import modules (\"Add Lua script …\"); .lua is now an allowed file type in imported module folders. Not tested with the real Lua engine yet."]),
    ("1.7.8", ["Recoil trainer leaderboards fixed: the server list now accepts the four pattern boards (the database update was missing before), and the trainer now says why a score was not sent (not signed in, no network) instead of staying silent.",
               "Imported modules that cannot be loaded now show the exact reason (which id is already taken and by which module, or that the id is missing) instead of just 'already in use'. A faulty imported module can no longer stop the launcher from starting: modules that do not inherit from BasePlugin are skipped with a message."]),
    ("1.7.7", ["Community > Leaderboards: leaderboards for the recoil trainer (one per pattern: Straight up, Up then right, Zigzag, Random) plus the CPS and reaction tests. A full round of 30 shots with the standard settings (strength 1, 10 shots/s, guide line off) is sent automatically after the round when you have a cloud account and the community set up; scores come from the players' programs and are not checked by the server.",
               "The old Recoil module (anti-recoil in Game macros) was removed completely; its 'Recoil' setting disappears. The practice field 'Recoil trainer' in the Cheat menu stays.",
               "Community > Modules: share your imported modules with everyone and install modules of others. Only text files (.py .json .txt .md .csv, up to 40 files and 300 KB) can be shared. A module of a normal account is visible to others only after an admin approved it (admins can share at once); admins have a 'Review queue'. Before installing you see the complete code and a list of conspicuous places (internet, programs, deleting files, hidden code ...); installing needs two confirmations and loads at the next start. Two reports hide a module until an admin looks at it; authors and admins can delete modules. Approval is no security guarantee. Terms of use extended (new consent needed). Import from ZIP, folder, .py file or pasted code is still in Settings > System > Import modules."]),
    ("1.7.6", ["New module 'Cheat menu' (menu item with its own tabs): single-player cheats for Minecraft Java (44 chat commands such as game mode, god mode, giant/tiny, mega jump, enchanted gear, time and weather; needs a world with cheats allowed) and GTA 5 Enhanced story mode (the official Rockstar cheat codes typed into the cheat console, Windows only), a free command field, start delay, and a hotkey for every cheat in Settings > Hotkeys (group 'Cheat menu'). It also has a recoil trainer: a practice field with four recoil patterns where you pull the mouse against the recoil and get points and best scores; it reads the mouse only inside its own field and sends no input to games.",
               "Includes everything from 1.7.4 (modules from pasted code, kept across updates) and 1.7.5 (much larger chat filter with spelling tricks)."]),
    ("1.7.5", ["Chat/forum filter greatly extended: several hundred insults, sexual terms, hate terms and threats from about 40 languages (also in Chinese, Japanese, Korean, Arabic, Hebrew, Hindi, Bengali and Cyrillic script) plus thousands of typical phrases. It also catches spelling tricks: characters in between (f.u.c.k, f-u-c-k, f_u_c_k), spaces, look-alike letters and numbers, repeated letters and masking with * or #. Harmless words stay allowed. The server filter was updated to match."]),
    ("1.7.4", ["Import modules: modules can now also be added by pasting code (with an example template). Imported modules are stored in the data folder and stay when the program is updated."]),
    ("1.7.3", ["Settings > System > Import modules: add your own modules from a folder, a .zip file, a single .py file or by pasting code (needs a plugin.py with a class Plugin); imported modules are stored in the data folder, so they stay when the program is updated. A warning must be confirmed because a module is program code with all rights of the program. Imported modules load at the next start and can be removed again; they cannot replace built-in modules.",
               "Terms of use extended by a section on imported modules. You must accept the new version once."]),
    ("1.7.2", ["Gaming & Stream > Match counter: optional automatic win/loss detection. You choose a screen area once and teach the program your victory and defeat screens; it then counts them by itself (only screen colours are compared, nothing is read from the game).",
               "Overlays that were switched on stay on: after closing and restarting the program they come back automatically.",
               "Menu: Contact now sits directly below the Help assistant.",
               "Window manager: with several monitors a window stays on its own monitor, you can pick a target monitor, send a window to the next monitor (Ctrl+Alt+M) and save the open windows with their exact position and monitor as a layout. In layouts add @2 for monitor 2.",
               "Hover mode: modules in the menu and the Module overview are highlighted slightly when the mouse is over them (Settings > Appearance, can be turned off)."]),
    ("1.7.1", ["Dashboard: greeting with version, update check, a big AI chat box and a collapsible 'Module overview'. The Help assistant now sits in the sidebar between Settings and Sign out.",
               "Changing settings no longer reloads everything: icons, potato mode, menu order and background picture only refresh the sidebar or banner.",
               "Community: new switch 'Stay signed in to the Community on this computer' (remembers the passphrase locally); community settings can be changed without being signed in to the Community.",
               "Terms of use roughly doubled: community, AI, diagnostics and admin view, local data, updates, allowed use and more. You must accept the new version once.",
               "Bug fixes: menu icons no longer cover the text, tab highlight follows tab changes."]),
    ("1.7.0", ["New menu 'Admin' (admin accounts only): Overview (users online, accounts, server status, database size, connections, uptime), Accounts, Errors (error reports from the apps) and Publish.",
               "Potato mode (Settings > Performance): turns off background picture, coloured icons and pre-building, and slows polling for weak PCs.",
               "Less lag: the page is hidden while you resize the window, interface scaling is only applied when it changes, pages are pre-built only when idle.",
               "Colour trigger: new option 'Trigger on any colour change'. Tab bars wrap into several rows in narrow windows (no more squashed headings).",
               "Coloured menu icons (e.g. yellow lightning bolt for Productivity), switchable in Settings > Appearance. Anonymous diagnostics (sign of life and error reports) can be switched off in Settings > Performance.",
               "AI assistant knows the new features; translations reviewed."]),
    ("1.6.0", ["Settings > Hotkeys: all shortcuts in one list (search, change by pressing keys, duplicates in red, on/off, restrict to one program, profiles, export/import, reset).",
               "Game macros: own start and optional stop hotkey per macro, several chat messages in a row with placeholders {zeit} {runde} {name}, chat-spam protection, GG in several languages.",
               "Gaming & Stream: match counter, up to six named timers, notes per map, ping and packet-loss overlay, one key hides all overlays, streamer mode.",
               "Macro language: variables (set/add), if/else, stop, {variable} in texts; errors are marked in the line while typing; Preview shows what a macro would do.",
               "Crosshair profiles per game (switch automatically by program or with a hotkey).",
               "Notifications: no pop-ups in fullscreen (summary afterwards), community messages even when the Community page is closed, choose sources and servers.",
               "Faster settings: fewer disk writes, background image cached."]),
    ("1.5.4", ["Crosshair: the cover no longer blacks out the view. Shape Cross covers only the thin lines of the game's crosshair (Disc and Square remain), and its colour can be taken live from the surroundings so it blends in.",
               "Crosshair: smooth spreading with speed settings, and 'Measure the spread' copies how far the game's crosshair opens while shooting (switchable with the reaction 'Spread on fire').",
               "Setup installer script (installer.iss, SETUP_BAUEN.bat) for a Windows setup file."]),
    ("1.5.3", ["Crosshair: every new function has its own switch (cover the game's crosshair, react while shooting, hide while aiming, keep on top)."]),
    ("1.5.2", ["The AI help answers more naturally and individually (new prompt, longer answers, better memory of the conversation); the macro generator can write advanced macros and shows what it can do plus clickable examples.",
               "Crosshair: can cover the crosshair of the game with a filled disc (size and colour), changes colour or spreads apart while the left mouse button is held, and hides while the right mouse button is held; it is kept on top of games."]),
    ("1.5.1", ["Overlays: no black box any more (transparent with outline), choose font, size, colour, opacity, position (corners, X/Y, drag) with a 'Save position' button, lock so clicks pass through; FPS reads the foreground game window first.",
               "Pop-up notifications are round, the colour can be set in Settings > Notifications, long messages wrap onto further lines.",
               "The sidebar adapts to the window height: Emergency stop, Settings, Sign out and the version stay visible; the ad box and logo hide when the window is low.",
               "Faster module switching: pages are prepared in idle time, the dashboard is built only when shown, several settings changes rebuild the interface once."]),
    ("1.5.0", ["New menu structure: Dashboard, Autoclicker & click tools, Crosshair, Game macros, My macros, Productivity, Gaming & Stream, Community (then Publish, Help assistant, Contact, Settings).",
               "New 'Mouse & keyboard' tab: multi-click on one key, hold instead of press, auto-scroll, anti-AFK.",
               "New Game macros module: ready-made macros for Minecraft, idle games, inventory and chat.",
               "Macro language: down/up keep a key or mouse button pressed, random waits like 'wait 100ms-300ms'. The autoclicker has a random variation setting.",
               "Extensions moved into Productivity."]),
    ("1.4.5", ["The AI help answers faster: the answer appears piece by piece while it is written.",
               "The launcher runs smoother: status displays redraw only when something changed and pause while their page is hidden."]),
    ("1.4.4", ["The AI help now knows every function and always the installed version, including the newest changes (this handbook)."]),
    ("1.4.3", ["Test version for checking publishing and updating (no change to the program)."]),
    ("1.4.2", ["Publish checks the version number on the chosen EXE itself, so a new version can be published from an older app."]),
    ("1.4.1", ["New rounder design: sidebar and content are equally coloured rounded panels with a dark gap between them.",
               "System overlay no longer flashes a window and shows FPS.",
               "Window manager moves the window instantly (Windows) instead of after 3 seconds.",
               "A window layout can be applied automatically when the app starts."]),
    ("1.4.0", ["New modules: Click tools, Gamer & Stream, Productivity.",
               "Community: macro marketplace, news/announcements, invite to a server by e-mail address.",
               "Settings: Notifications (sound, own sound file, pop-up, quiet hours).",
               "Publish: list of all uploaded versions with switching back to an older one."]),
    ("1.3.3", ["Emergency stop, macro recording, export/import, statistics, backup and restore, interface size, two new colour presets.",
               "Community: replies, @mentions, unread counter, mute and slow mode."]),
    ("1.3.0", ["New module Community: servers, end-to-end encrypted direct messages, public forum, invitations, word filter, reporting.",
               "Free order of the sidebar entries and a background image banner."]),
    ("1.2.0", ["Publish menu for the admin to release new versions; updates now come from Supabase."]),
    ("1.1.0", ["First release: auto-clicker, macro editor with AI, extensions, recoil module, themes, languages, accounts."]),
]

# Abschnitte je Modul-ID (die Schlüssel müssen zu modules.BUILTIN_MODULES passen, "core" = Programmkern)
SECTIONS = {
    "autoclicker": "MENU 'AUTOCLICKER' (tabs: Autoclicker, Mouse & keyboard, Hotkeys, Colour trigger, Scheduler, Program profiles; the last four are described under CLICK TOOLS). "
                   "AUTO-CLICKER ('Jaron Op Makro'): Simulates a mouse button (left/right/middle) or any key at a precise interval (minutes, seconds, "
                   "milliseconds, minimum 1 ms). 'Repeat forever' or 'X times', optional run-time limit. Global start/stop hotkeys (click 'Record', press the "
                   "key, e.g. F6); the same key toggles. Profiles are saved/loaded as JSON files at the top of the page. 'Random variation (±%)' (0-50) makes the pauses between clicks slightly random for a more natural pace. "
                   "MOUSE & KEYBOARD tab: multi-click (a shortcut sends a double, triple or more click, default F9); hold instead of press (a shortcut holds a key or mouse button, the next press releases it, e.g. toggle sprint, default F10); auto-scroll (slow automatic scrolling, default F11); "
                   "anti-AFK (every 10-600 seconds the mouse moves one pixel and back or Shift is tapped). The emergency stop stops all of these.",
    "macros": "MY MACROS (menu 'My macros'): Write commands (click, doubleclick, move, key, hold, type, scroll, wait, repeat N / repeat forever ... end) or describe the "
              "macro in a sentence and press 'Generate' (simple sentences offline, harder ones with the AI when signed in with a cloud account). "
              "'Record' captures your own mouse and key actions into a macro. Macros can be exported/imported as files. Variables and conditions: 'set n 0', 'add n 1', 'if n >= 3 ... else ... end' (== != < > <= >=), 'stop', and {n} inside the text of a type command. Typing errors are marked red in their line, 'Preview' shows what a macro would do without pressing anything. Extra commands: 'down NAME' / 'up NAME' keep a key or mouse button (mouse_left, mouse_right, mouse_middle) pressed (released automatically at the end or on stop); 'wait 100ms-300ms' waits a random time in between. Every macro is checked before it "
              "runs. F7 starts/stops.",
    "gamemacros": "GAME MACROS (menu 'Game macros', tabs Minecraft, Idle & clicker games, Inventory & crafting, Chat & emotes): ready-made macros; choose a card, set a few values (start delay, positions, texts), press Start; 'Save to My macros' keeps it as your own macro. General holds Anti-recoil (see RECOIL). "
                  "Minecraft: auto-mining (holds the left mouse button), auto-fishing (reel in and cast again after a wait; it does not see bites), commands (/time, /tp - only where commands are allowed). Idle games: fast auto-click (e.g. Cookie Clicker), buy upgrades regularly at a screen position. "
                  "Inventory: Shift+click a row of slots, crafting sequence of clicked positions. Chat: prepared message (placeholders {zeit}, {runde}, {name}), several messages in a row with a pause, GG in several languages, callout, emote/dance key combo; chat macros have spam protection (2 s). Each macro card has its own start hotkey (toggles) and an optional stop hotkey, optionally only in one program. Use them only where the game allows it (single player, idle games, own server); never to cheat in online games.",
    "extensions": "EXTENSIONS (tab 'Extensions' in Productivity): Ready-made extensions (Quick links, Web search, Notes) added with one click, switched on/off and configured.",
    "luascripts": "LUA SCRIPTS (menu item 'Lua scripts'): runs your own .lua scripts in a safe box. Press 'Add script …' (or Settings > Import modules > 'Add Lua script …') to add a .lua or .txt file (UTF-8 text, up to 300 KB); the list shows each script with Start and a remove button, the output box shows print(...) lines and errors. A script can use normal Lua (string, table, math, coroutine, utf8), print(...), wait(ms) and macro(\"...\") with the commands of the macro editor (click, key, type, wait, repeat ...). os, io, debug, require, load and similar are blocked, so a script cannot read files or start programs. Stop, the panic key (Ctrl+Shift+F12) or the 10-minute limit end a script, also endless loops. Scripts made for other programs (G Hub, Roblox, LOVE) do not run here. Needs the Lua engine 'lupa' in the build; without it the page says so.",
    "cheatmenu": "CHEAT MENU (menu item 'Cheat menu', tabs Minecraft, GTA 5 Enhanced, Recoil trainer, Help): single-player cheats only. Minecraft: each button runs a chat command (opens the chat key, types the command, Enter) through the macro runner; the world needs 'cheats allowed' (Esc > Open to LAN > Allow cheats); a free command field exists. GTA 5 Enhanced: the official Rockstar cheat codes are typed into the cheat console with scan codes (Windows only, story mode only; cheats do not work in GTA Online). Start delay (default 3 s) lets you switch to the game; with a hotkey (Settings > Hotkeys, group 'Cheat menu') there is no delay. Stop button, emergency stop and F7 stop it. The recoil trainer is a practice field with four patterns, strength, shots per second, guide line, points and best scores; it only reads the mouse inside its own field and never sends input to games; full standard rounds are sent to leaderboards in Community > Leaderboards (one per pattern). Not for online games. "
              "Not tested inside the games themselves.",
    "clicktools": "CROSSHAIR (own menu item) and CLICK TOOLS (tabs in the Autoclicker menu). Crosshair: a small always-visible crosshair in the screen centre with shapes Cross, Cross with gap, Dot, Circle, "
                  "Circle + dot, T-shape; size, thickness, colour, opacity; 'Cover the crosshair of the game' draws a shape under it so the game's own crosshair is hidden (Cross = only thin lines, Disc, Square; size, line width; colour from the surroundings automatically or fixed); 'Spread when shooting' sets how far it opens plus opening/closing time and 'Measure the spread' copies this from the game's crosshair on the screen (start, switch to the game, hold the left mouse button about 2 s; the colour of the game's lines can be entered or detected); 'React while shooting' is a switch; 'Reaction while shooting' picks colour change or spreading apart (it changes colour or spreads the lines apart while the left mouse button is held; 'Hide while aiming' hides it while the right button is held; 'Keep the crosshair on top of the game' is also a switch; every function can be switched off; presets such as Classic green, Tactical, Red dot, Ring, Sniper T.; crosshair profiles per game that load by program name or with a hotkey. Tabs of the Autoclicker menu: Hotkeys (own shortcuts that press a key, type a text or start a saved macro; "
                  "use Ctrl/Alt/Shift plus a key, or an F key alone; up to 30 rules); Colour trigger (watches a screen point and starts a macro as soon as the target colour appears, or - with 'Trigger on any colour change' - as soon as the colour there changes at all "
                  "there; needs screen capture permission on macOS); Scheduler (starts saved macros at a set time or at fixed intervals, only while the launcher is running); Program profiles "
                  "(switches the clicker profile automatically depending on which program is in the foreground).",
    "gamer": "OVERLAY DESIGN (System overlay and Key overlay tabs): no black box, transparent with a dark outline; font, size, colour, bold, opacity, optional dark box; position by dragging, X/Y, four corners, "
             "button 'Save position', and 'Lock' so clicks pass through in games. Overlays show over windows and borderless fullscreen but not over exclusive fullscreen; FPS is read from the foreground window, "
             "the in-game counter is exact. GAMER & STREAM (menu 'Gamer & Stream') has nine tabs (new: Match counter with wins, losses, kills, deaths, rounds counted by hand or hotkey, and optional AUTOMATIC win/loss detection (choose a screen area once, teach the victory and defeat screen with the buttons or hotkeys, then switch the automatic counting on; only screen colours are compared); overlays that were on stay on after a restart; Timers = six named countdowns with sound; Notes per map; Network = ping and packet loss overlay to a server of your choice; every overlay can be hidden with one hotkey and streamer mode keeps overlays out of recordings on Windows): Session timer (play time with break and water reminders as notifications); System overlay "
             "(small draggable always-on-top window with CPU, RAM, GPU temperature (NVIDIA only), FPS and ping; FPS is the frame rate the screen receives on "
             "Windows, works for windowed and borderless games but not exclusive fullscreen; ping connects briefly to 1.1.1.1); Key overlay (shows W A S D, "
             "Shift, Ctrl, Space, mouse buttons and last keys for streams; macOS needs Input Monitoring); Speed tests (CPS test and reaction test with a "
             "leaderboard); Screenshot (screen capture to a file; macOS needs Screen Recording permission).",
    "productivity": "PRODUCTIVITY (menu 'Productivity') has four tabs (the last is Extensions): Clipboard (history of copied texts with pinning); Windows (window manager: move the window you "
                    "used last to a half, quarter, centre or maximise it, with optional global shortcuts Ctrl+Alt+arrows, U I J K for quarters, C centre, Enter "
                    "maximise; Layouts put several programs in their places at once, e.g. 'chrome:left, discord:right', and one layout can be applied "
                    "automatically when the app starts; with several monitors (Windows) a window stays on its own monitor, a target monitor can be chosen, Ctrl+Alt+M sends a window to the next monitor, "
                    "'chrome:left@2' places it on monitor 2 and 'Save open windows as layout' stores the exact position and monitor of the ticked windows; Windows moves instantly, macOS needs Accessibility, Linux needs wmctrl); AI macro assistant (describe "
                    "what you need and get a ready macro).",
    "community": "COMMUNITY (menu 'Community', needs a cloud account) has tabs Chats, Forum, Marketplace, Modules, Leaderboards, News and (for moderators) Moderation. Chats: servers with "
                 "channels and roles, direct messages (end-to-end encrypted), replies, @mentions, unread counter. You invite people to a server by invite code, by "
                 "username or by e-mail address (the person gets the invitation in the launcher only if an account with that address exists; you always see 'sent' "
                 "for privacy; no real e-mail is sent; accounts created with only a username cannot be found by e-mail). Forum: public posts for all users. "
                 "Marketplace: publish and download macros, rate them, report bad ones. Modules: share modules you imported (Settings > System > Import modules) and install modules of others; text files only, up to 300 KB; modules of normal accounts need an admin to approve them first (admins use the Review queue button), you see all code and a list of conspicuous places before installing and must confirm twice; reports hide a module; installing takes effect at the next start; approval is no security guarantee. News: announcements from the admin. Moderators can mute members and set "
                 "slow mode. A word filter protects chats and names; messages can be reported.",
    "admin": "ADMIN (admin only, menu 'Admin'): tabs Overview (users online now and in 24 h, registered accounts, errors, database size, connections, how long the server runs, cache rate; the server's own RAM/CPU/disk are only visible in the Supabase dashboard), Accounts (e-mail list with online dot), Errors (anonymous error reports from the apps, Delete all) and Publish.",
    "publisher": "PUBLISH (tab 'Publish' in the Admin menu): Upload a new version (.exe for Windows, .dmg for Mac), choose the version number and release notes. The app checks "
                 "the number on the chosen EXE itself. Below, all uploaded version files are listed; 'Set active' switches back to an older version if the new one "
                 "is faulty (apps from 1.4.0 on then also go back), 'Delete' removes a file.",
    "core": "SETTINGS have sections: Account (display name, optional e-mail, 2FA for local accounts, export data, delete account); Appearance (Dark/Light/System, accent "
            "colour, presets such as Graphite, Ocean, Forest, Sunset, Contrast, Rose, own colours, app icon background, interface size 80-150 %); Layout (show/hide "
            "and reorder sidebar entries, own background image banner with darken and height); Language (English, Deutsch, Español, Русский, Français, 中文); "
            "System (desktop shortcut, autostart, emergency stop key, statistics, backup and restore, import of your own modules from a folder, .zip, .py file or pasted code, kept across updates - program code, so only from trusted sources; loaded at the next start); Hotkeys (every shortcut of the app in one list: search, change by pressing keys, red = used twice, on/off, only in one program, profiles, export/import, reset); Notifications (on/off, which events: chat messages, direct messages, "
            "mentions, invitations, announcements, marketplace, timers; no pop-ups while a program is fullscreen; community messages in the background; muted servers; sound Chime/Pop/Ding/System beep/Own file/Off with volume; pop-up on/off, corner, display time, "
            "opacity, pop-up colour (round pop-ups, long text wraps); quiet hours; test buttons; these settings are per device); Performance (POTATO MODE for weak PCs: no background picture, no coloured icons, no pre-building, slower polling; hide page while resizing; anonymous diagnostics switch; download limit in KB/s, CPU priority, CPU cores, RAM limit on Windows); Appearance also has a switch for coloured menu icons; "
            "Legal & sources. The DASHBOARD shows the greeting with the version, the update check, a big box to chat with the AI assistant (questions and macro creation) and a collapsible Module overview. The HELP ASSISTANT has its own menu entry in the sidebar between Settings and Sign out. Settings > Notifications > Community sign-in: switch to stay signed in to the Community (the passphrase is remembered on this computer). The SIDEBAR adapts to the window height (low window: ad box and logo hide, Emergency stop/Settings/Sign out/version stay visible). EMERGENCY STOP: the red button in the sidebar or Ctrl+Shift+F12 stops everything at once. UPDATES: checked on start and on the "
            "dashboard ('Update now'); a faulty release can be rolled back by the admin. Passwords cannot be changed or recovered; create a new account if lost. "
            "'Sign in with Google' needs a one-time setup by the operator. Windows may warn about unknown programs (More info -> Run anyway). Feedback via "
            "'Contact'. The ad box is only a placeholder. The sidebar shows the installed version (v...).",
}


def text() -> str:
    parts = [f"INSTALLED VERSION: {APP_VERSION}.",
             "NEWEST CHANGES (newest first; the first entry is the newest function):"]
    parts += [f"- v{v}: " + " ".join(items) for v, items in CHANGELOG]
    parts.append("FEATURES BY MODULE:")
    parts += list(SECTIONS.values())
    return "\n".join(parts)
