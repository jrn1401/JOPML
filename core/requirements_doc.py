"""Anforderungen für Module, Skripte und Uploads - wird bei jedem Aufruf aus den echten Grenzwerten im Code erzeugt.

Dadurch ist die Anzeige "Modul-Anforderungen" immer auf dem Stand des Programms: ändert sich eine Grenze (Dateigröße, erlaubte Endungen,
Anzahl Dateien ...), ändert sich der Text automatisch. Sprache: Deutsch, sonst Englisch.
"""
import hashlib

from core.version import APP_VERSION


def _mb(n: int) -> str:
    return f"{n / 1048576:g} MB"


def _kb(n: int) -> str:
    return f"{n / 1000:g} KB"


def facts() -> dict:
    """Alle Grenzwerte an einer Stelle (Quelle: der Code, der sie auch durchsetzt)."""
    from core import module_import as mi
    from modules.community import modshare as ms, market
    from modules.publisher import logic as pl
    return {
        "name_re": mi.NAME_RE.pattern, "ext": sorted(mi.ALLOWED_EXT), "reserved": sorted(mi.RESERVED),
        "max_files": mi.MAX_FILES, "max_file": mi.MAX_FILE_BYTES, "max_total": mi.MAX_TOTAL_BYTES, "lua_max": mi.LUA_MAX_BYTES,
        "share_ext": sorted(ms.TEXT_EXT), "share_files": ms.MAX_FILES, "share_total": ms.MAX_TOTAL,
        "risky_imports": sorted(ms.RISKY_IMPORTS), "risky_calls": sorted(ms.RISKY_CALLS),
        "macro_max": market.MAX_SCRIPT, "release_max": pl.MAX_BYTES, "platforms": {k: v[0] for k, v in pl.PLATFORMS.items()},
    }


def modules_text(lang: str = "de") -> str:
    f = facts()
    de = lang == "de"
    t = (lambda d, e: d if de else e)
    L = []
    add = L.append
    add(t("MODUL-ANFORDERUNGEN – Jaron's OP Makro Launcher", "MODULE REQUIREMENTS – Jaron's OP Makro Launcher"))
    add(t(f"Stand: Programmversion {APP_VERSION}. Dieser Text wird aus den echten Grenzwerten im Programm erzeugt und ändert sich mit ihnen.",
          f"Status: program version {APP_VERSION}. This text is generated from the real limits in the program and changes with them."))
    add("")
    add(t("1. EIGENES MODUL HINZUFÜGEN (Menü „Modules“)", "1. ADDING YOUR OWN MODULE (menu “Modules”)"))
    add(t("Möglich als Ordner, ZIP-Datei, einzelne .py-Datei oder eingefügter Code.", "Possible as a folder, ZIP file, single .py file or pasted code."))
    add(t(f"- Name: nur Kleinbuchstaben, Ziffern und _, 2–31 Zeichen, beginnt mit einem Buchstaben (Muster {f['name_re']}).",
          f"- Name: lowercase letters, digits and _, 2–31 characters, starting with a letter (pattern {f['name_re']})."))
    add(t(f"- Verboten (reserviert oder von eingebauten Modulen belegt): {', '.join(f['reserved'])} und alle Namen eingebauter Module.",
          f"- Not allowed (reserved or used by built-in modules): {', '.join(f['reserved'])} and all names of built-in modules."))
    add(t(f"- Pflicht: eine Datei plugin.py auf oberster Ebene mit einer Klasse namens Plugin (von core.plugin_api.BasePlugin).",
          "- Required: a plugin.py file at the top level containing a class named Plugin (based on core.plugin_api.BasePlugin)."))
    add(t(f"- Erlaubte Dateitypen: {' '.join(f['ext'])}", f"- Allowed file types: {' '.join(f['ext'])}"))
    add(t(f"- Grenzen: höchstens {f['max_files']} Dateien, je Datei höchstens {_mb(f['max_file'])}, insgesamt höchstens {_mb(f['max_total'])}.",
          f"- Limits: at most {f['max_files']} files, each file at most {_mb(f['max_file'])}, in total at most {_mb(f['max_total'])}."))
    add(t("- Pfade dürfen nicht absolut sein und kein „..“ oder „:“ enthalten (Schutz vor Pfad-Tricks in ZIP-Dateien).",
          "- Paths must not be absolute and must not contain “..” or “:” (protection against path tricks in ZIP files)."))
    add(t("- plugin.py muss lesbarer Python-Code sein (wird vor dem Hinzufügen geprüft).", "- plugin.py must be readable Python code (checked before adding)."))
    add(t("- Ein bereits vorhandenes eigenes Modul wird nur nach ausdrücklicher Bestätigung ersetzt.", "- An existing own module is only replaced after explicit confirmation."))
    add(t("- Das Modul wird beim nächsten Start geladen (der Launcher kann sich selbst neu starten) und bleibt bei Updates erhalten; vor Updates wird eine Sicherung angelegt.",
          "- The module is loaded at the next start (the launcher can restart itself) and survives updates; a backup is made before updates."))
    add("")
    add(t("2. SICHERHEIT UND VERANTWORTUNG", "2. SECURITY AND RESPONSIBILITY"))
    add(t("- Ein Modul ist Python-Code und läuft mit ALLEN Rechten des Programms. Füge nur Module aus Quellen hinzu, denen du vertraust.",
          "- A module is Python code and runs with ALL rights of the program. Only add modules from sources you trust."))
    add(t("- Vor dem Hinzufügen zeigt das Programm auffällige Stellen (Netzwerk, andere Programme starten, Systemaufrufe, Dateien löschen, Code zur Laufzeit ausführen). "
          "Diese Liste ist eine Lesehilfe, KEINE Garantie.",
          "- Before adding, the program shows conspicuous places (network, starting programs, system calls, deleting files, running code at runtime). "
          "This list is a reading aid, NOT a guarantee."))
    add(t(f"- Auf Auffälligkeit geprüfte Importe: {', '.join(f['risky_imports'])}.", f"- Imports checked for attention: {', '.join(f['risky_imports'])}."))
    add(t(f"- Auf Auffälligkeit geprüfte Aufrufe: {', '.join(f['risky_calls'])}.", f"- Calls checked for attention: {', '.join(f['risky_calls'])}."))
    add("")
    add(t("3. LUA-SKRIPTE", "3. LUA SCRIPTS"))
    add(t(f"- Nur Lua-Quelltext (keine kompilierten Dateien), höchstens {_kb(f['lua_max'])}, nicht leer, Name wie bei Modulen.",
          f"- Lua source text only (no compiled files), at most {_kb(f['lua_max'])}, not empty, name rules as for modules."))
    add(t("- Läuft in einer geschützten Umgebung: kein Zugriff auf Dateien (io), Betriebssystem (os) oder Debug-Funktionen; Stopp, Notaus und Zeitlimit beenden auch Endlosschleifen.",
          "- Runs in a protected environment: no access to files (io), the operating system (os) or debug functions; stop, emergency stop and time limit also end endless loops."))
    add("")
    add(t("4. MODUL FÜR ALLE TEILEN (Community > Module)", "4. SHARING A MODULE WITH EVERYONE (Community > Modules)"))
    add(t(f"- Nur Textdateien: {' '.join(f['share_ext'])}; höchstens {f['share_files']} Dateien und {_kb(f['share_total'])} Text insgesamt; plugin.py ist Pflicht.",
          f"- Text files only: {' '.join(f['share_ext'])}; at most {f['share_files']} files and {_kb(f['share_total'])} of text in total; plugin.py is required."))
    add(t("- Titel 3–60 Zeichen, Beschreibung höchstens 500 Zeichen. Titel, Beschreibung und Text laufen durch den Wortfilter.",
          "- Title 3–60 characters, description at most 500 characters. Title, description and text pass the word filter."))
    add(t("- Module normaler Konten erscheinen erst nach Freigabe durch einen Admin; Admin-Konten teilen sofort.",
          "- Modules from normal accounts only appear after approval by an admin; admin accounts share immediately."))
    add(t("- Jeder kann ein Modul melden (Meldung mit Begründung, Modul-ID und Melder). Gemeldete Module werden ausgeblendet, bis ein Admin geprüft hat; du bekommst die Entscheidung mit Begründung.",
          "- Anyone can report a module (report with reason, module ID and reporter). Reported modules are hidden until an admin has reviewed them; the decision is given with a reason."))
    add(t("- Vor jeder Installation fremder Module siehst du den ganzen Code und die Liste auffälliger Stellen und musst zweimal bestätigen.",
          "- Before installing someone else’s module you see the whole code and the list of conspicuous places and must confirm twice."))
    add("")
    add(t("5. MAKROS TEILEN (Makro-Marktplatz)", "5. SHARING MACROS (macro marketplace)"))
    add(t(f"- Makro-Text höchstens {f['macro_max']} Zeichen, muss als Makro gültig sein und läuft durch den Wortfilter.",
          f"- Macro text at most {f['macro_max']} characters, must be a valid macro and passes the word filter."))
    add("")
    add(t("6. WAS NICHT ERLAUBT IST (gilt für Module, Skripte, Makros und geteilte Inhalte)", "6. WHAT IS NOT ALLOWED (applies to modules, scripts, macros and shared content)"))
    for d, e in (
        ("Cheats für Mehrspieler-Spiele: Zielhilfen (Aimbot), Wallhacks/ESP, automatische Rückstoß-Kompensation, Auslesen oder Verändern des Arbeitsspeichers anderer Programme, Code-Einschleusung.",
         "Cheats for multiplayer games: aim assistance (aimbot), wallhacks/ESP, automatic recoil compensation, reading or changing other programs’ memory, code injection."),
        ("Umgehen von Schutzmaßnahmen (Anti-Cheat, Kopierschutz, Spielsperren) – vgl. § 95a UrhG.", "Bypassing protection measures (anti-cheat, copy protection, game bans) – cf. § 95a UrhG."),
        ("Schadsoftware, Passwort-/Datendiebstahl, Verstecken von Code (z. B. verschleierte Blöcke), unerlaubtes Mitlesen von Tastatur, Maus oder Zwischenablage.",
         "Malware, password/data theft, hiding code (e.g. obfuscated blocks), unauthorised reading of keyboard, mouse or clipboard."),
        ("Rechtswidrige Inhalte, Beleidigungen, Hass, Bedrohungen, Inhalte, die Rechte Dritter (Urheberrecht, Marken) verletzen.",
         "Unlawful content, insults, hate, threats, content that infringes third-party rights (copyright, trademarks)."),
        ("Ausgenommen davon sind Einzelspieler-Funktionen und Übungsprogramme mit erfundenen Waffen (z. B. die Recoil Arena).",
         "Single-player functions and practice programs with invented weapons (e.g. the Recoil Arena) are not affected."),
    ):
        add("- " + t(d, e))
    add("")
    add(t("7. WAS EIN MODUL KANN (Programmierschnittstelle)", "7. WHAT A MODULE CAN DO (programming interface)"))
    add(t("Klasse Plugin(BasePlugin) mit: id, name, icon, version, description, order (Reihenfolge), nav (Menüpunkt ja/nein); "
          "Methoden on_load() beim Start, create_page(parent) liefert die Seite, on_shutdown() beim Beenden, dashboard_summary() für die Übersicht. "
          "Beispielvorlage: Knopf „Add from code …“ > „Insert example“.",
          "Class Plugin(BasePlugin) with: id, name, icon, version, description, order (position), nav (menu item yes/no); "
          "methods on_load() at start, create_page(parent) returns the page, on_shutdown() at exit, dashboard_summary() for the overview. "
          "Example template: button “Add from code …” > “Insert example”."))
    add("")
    add(t("Hinweis: Dies ist eine technische Beschreibung, keine Rechtsberatung.", "Note: this is a technical description, not legal advice."))
    return "\n".join(L)


def uploads_catalog(lang: str = "de") -> list[dict]:
    """Alles, was der Admin hochladen kann: Name, Ziel, Format, Kriterien. Grenzen kommen aus dem Code."""
    f = facts()
    de = lang == "de"
    t = (lambda d, e: d if de else e)
    plats = f["platforms"]
    return [
        {"id": "exe", "name": t("Launcher Windows (.exe)", "Launcher Windows (.exe)"), "where": "releases/JaronsOPMakro-<Version>.exe + version.json",
         "criteria": [t(f"Datei .exe, höchstens {_mb(f['release_max'])}", f"File .exe, at most {_mb(f['release_max'])}"),
                      t("Versionsnummer wie 1.8.6 (2–4 Zahlen)", "Version number like 1.8.6 (2–4 numbers)"),
                      t("Die EXE meldet ihre Nummer selbst (--version); sie muss mit der eingetragenen übereinstimmen", "The EXE reports its own number (--version); it must equal the typed one"),
                      t("Enthält die Recoil Arena (Start mit --arena); bei Update ist kein extra Arena-Upload nötig", "Contains the Recoil Arena (started with --arena); no extra Arena upload needed"),
                      t("Prüfsumme (SHA-256) wird berechnet und im Manifest gespeichert", "Checksum (SHA-256) is computed and stored in the manifest")]},
        {"id": "dmg", "name": t("Launcher Mac (.dmg)", "Launcher Mac (.dmg)"), "where": "releases/JOPML-<Version>.dmg + version.json",
         "criteria": [t(f"Datei .dmg, höchstens {_mb(f['release_max'])}", f"File .dmg, at most {_mb(f['release_max'])}"),
                      t("Nummer lässt sich nicht aus der Datei prüfen – du bestätigst sie", "The number cannot be read from the file – you confirm it")]},
        {"id": "arena", "name": t("Recoil Arena (ZIP, nur Quellcode-Weg)", "Recoil Arena (ZIP, source route only)"), "where": "releases/jopml-arena-<Version>.zip + arena.json",
         "criteria": [t("Wird aus der mitgelieferten Arena gepackt (Pflicht: arena/__main__.py)", "Packed from the bundled Arena (required: arena/__main__.py)"),
                      t("Nutzer der EXE brauchen das nicht – die Arena steckt in der EXE", "EXE users do not need it – the Arena is inside the EXE"),
                      t("Prüfsumme und Größe stehen in arena.json", "Checksum and size are stored in arena.json")]},
        {"id": "module", "name": t("Modul für alle", "Module for everyone"), "where": t("Community-Datenbank (Module), sofort freigegeben für Admin", "Community database (modules), approved immediately for admins"),
         "criteria": [t(f"Name: Kleinbuchstaben/Ziffern/_, 2–31 Zeichen", "Name: lowercase/digits/_, 2–31 characters"),
                      t(f"Nur Textdateien ({' '.join(f['share_ext'])}), höchstens {f['share_files']} Dateien, {_kb(f['share_total'])} gesamt", f"Text files only ({' '.join(f['share_ext'])}), at most {f['share_files']} files, {_kb(f['share_total'])} total"),
                      t("plugin.py mit Klasse Plugin ist Pflicht; Titel 3–60, Beschreibung bis 500 Zeichen", "plugin.py with class Plugin required; title 3–60, description up to 500 characters"),
                      t("Auffällige Stellen werden vorher angezeigt; Wortfilter und Meldefunktion gelten", "Conspicuous places are shown first; word filter and report function apply")]},
    ]


def uploads_text(lang: str = "de") -> str:
    de = lang == "de"
    out = ["UPLOAD-ÜBERSICHT (Admin)" if de else "UPLOAD OVERVIEW (admin)", ""]
    for u in uploads_catalog(lang):
        out += [f"* {u['name']}  →  {u['where']}"] + [f"    - {c}" for c in u["criteria"]] + [""]
    return "\n".join(out)


def stamp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
