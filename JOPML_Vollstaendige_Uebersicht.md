# Vollständige JOPML-Übersicht (Stand Version 1.10.0, 31.10.2026)

Jaron's OP Makro Launcher (JOPML): Python/CustomTkinter/pynput, EXE `JaronsOPMakro.exe`, Cloud: Supabase (Projekt `qeomooxbfpwvcprvmows`), 6 Sprachen (en/de/es/ru/fr/zh), 56 automatische Tests.

## 1. Module (Menü)
| Modul | Zweck |
|---|---|
| Autoclicker | Maus/Taste mit Intervall, Wiederholungen, Timer, globale Start/Stopp-Tasten |
| My macros | Makro-Sprache (click/wait/repeat…), Editor, Favoriten, KI-Generator |
| Crosshair (clicktools) | Fadenkreuz-Overlay, Profile |
| Game macros | Fertige Makros (Minecraft, Idle, Inventar, Chat mit Spam-Schutz) |
| Gamer & Stream | Sitzungs-Timer, System-/Tasten-Overlay, CPS- und Reaktionstest mit Bestenliste, Rückstoß-Trainer |
| Productivity | Zwischenablage-Verlauf, Fenster-Manager, Monitore, KI-Makro-Assistent |
| Extensions | Fertige Erweiterungen per Klick |
| Cheat menu | Einzelspieler-Cheats Minecraft/GTA 5 Enhanced (Story), kein Spielspeicher-Zugriff |
| Recoil Arena (1.3.1) | Eigenes Übungsspiel, erfundene Waffen, Bots |
| AI Chat 2.0 (neu in 1.10) | Gemini/Groq, Modellwahl, Streaming/Stop, Auto-Wechsel, Projekte, Verlauf, Vorlagen, Modulbau/-reparatur |
| Lua scripts | Sichere Lua-Skripte |
| Modules | Eigene Module/Lua verwalten, Prüfung, **Mit KI reparieren, Verlauf/Rückgängig** |
| Community | Chat (Ende-zu-Ende), DMs, Forum, Marktplatz, News, Bestenlisten |
| Publish / Admin | Nur Admins: Versionen hochladen; Reiter Overview, Accounts, Permissions, **AI**, **Tickets**, User reports, Automatic errors, Publish |
Feste Seiten: Dashboard (großer KI-Assistent mit Weiche), Settings, Help assistant (+ **Fehlercodes**), Contact, Report-Knopf.

## 2. Hilfe & Fehler (neu geordnet in 1.10)
- Bedienfragen → Hilfe-Assistent (FAQ/Handbuch, auch offline). Schreiben/Bauen/Fehler erklären → KI-Chat. Dashboard wählt automatisch (`guess_target`).
- Fehler: Code E-XXX-000 + Lösung (32 Codes) → „KI fragen“ / „Alle Codes“ / „Melden“. Melden → Meine Meldungen (Status, Antwort).
- Lob/Fragen → Kontakt.

## 3. KI
Anbieter Gemini (Standard) und Groq; Schlüssel nur als Supabase-Secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`, beide gesetzt). Limits: Nachrichten/Tag, Antwortlänge, Tokens/Tag (Zahl, Maximum, Kein Limit), globales Tagesbudget (80 %-Warnung). Auto-Wechsel nur mit Einwilligung für beide. Verlauf lokal, verschlüsselt, standardmäßig aus.

## 4. Server
Edge Functions: `jopml-ai` (Hilfe/Makro, v15), `jopml-chat` (v3, Deployment 10). Migrationen bis `20261031000600_jopml_1100_release_notes`. Tabellen u. a. `jopml_ai_log`, `jopml_tickets`, `jopml_user_reports`, `jopml_error_groups`. Admin-RPCs prüfen `jopml_is_admin()`.

## 5. Feste Regeln (Projekt)
Keine Rückstoß-Kompensation/Anti-Recoil/Spielspeicher-Tools; Arena nur erfundene Waffen; kein Passwort-Zurücksetzen lokaler Konten; API-Schlüssel nie im Programm. Jedes Update: Arena-Stand beilegen, Änderungsdatei, Ablaufplan, neue Ideen, Rechtliches, Übersicht, Übersetzungen.

## 6. Recht (nicht anwaltlich geprüft)
Rechtstext 2026-10-31e. Offen: TDDDG § 25, AV-Verträge/SCC Google und Groq, Art. 22 DSGVO.

## 7. Offen / Ideen
Siehe UPDATE_1.10.0.md Abschnitt 6 und 7.

## 8. Release-Notes (neu in 1.10.0)
Beim Upload schreibt `core/release_notes.py` die Note (RELEASE_NOTES.txt + Admin-Text) und ruft RPC `jopml_admin_release_note` auf; Community > News zeigt eine aufklappbare Zeile je Version. Alle 41 früheren Versionen sind nachgetragen.
