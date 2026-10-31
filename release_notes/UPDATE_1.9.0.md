# Update 1.9.0 – Änderungen, Ablaufplan, Ideen

Launcher 1.9.0 · Recoil Arena 1.3.1 (unverändert, neueste liegt bei) · Rechtsfassung 2026-10-31c (neue Zustimmung) · enthält alles aus 1.8.7

## 1. Was sich geändert hat
- **Gefundener Fehler, warum der KI-Chat nie ging:** In 1.8.6/1.8.7 fehlten im Programm die Methoden `chat` / `chat_status` (nur die Tests nutzten eine Attrappe). Jetzt vorhanden (`core/cloud.py`), dazu `chat_models` und `analyze_errors`. Die Meldung „Claude nicht verbunden“ gibt es nicht mehr.
- **KI-Chat nur noch Gemini + Groq** (Claude/ChatGPT entfernt: Programm, Server, Rechtstext, Einwilligung). Standard ist Gemini. Fehlt ein Schlüssel, steht „nicht eingerichtet“ mit Fehlercode.
- **Modellauswahl** im Chat: Anbieter-Knopf + Modell-Menü (Liste kommt live vom Anbieter über den Server, mit Zwischenspeicher; Auswahl wird gemerkt; unbekannte Modelle fallen auf das Standardmodell zurück).
- **KI-Assistent groß auf dem Dashboard** (oben, mit Begrüßung, Eingabefeld, Schnellfragen). Beim Senden öffnet sich das Modul „AI Chat“ und die Nachricht wird dort beantwortet; die Vorlage (Modul/Makro/Fehler/frei) wird aus dem Text erraten.
- **Die KI baut Module komplett:** Vorlage „Write a module“ liefert plugin.py mit Code **und** Fenster (customtkinter), kennt Theme, `call_soon`, Einstellungen, Regeln. Knopf **„Als Modul hinzufügen“** → automatische Prüfung + Warnung + Bestätigung → anlegen → Launcher startet neu. „Code kopieren“ gibt es auch.
- **Admin > Berechtigungen:** Standardwerte und persönliche Werte für **KI-Nachrichten pro Tag, Antwortlänge (Tokens), Token-Verbrauch pro Tag** – je Zahl, **Maximum** oder **Kein Limit**. (Eine einzelne Antwort bleibt technisch immer auf 16 384 Tokens begrenzt.) Anzeige der Tokens heute pro Konto. Tokens zählt der Server nach den Zahlen des Anbieters.
- **Fehlercodes überall** (`core/errors.py`, z. B. E-NET-001, E-MOD-005, E-AI-003): in Fehlermeldungen von Modul-Import/-Upload, Updates, KI, Community, Neustart, Profil laden, Absturz.
- **KI bei Fehlern:** Fehlerfenster mit **„KI fragen“** (Text geht erst nach Klick an die KI) und **„Melden“**; im Chat bei Fehlern ebenso.
- **Knopf „Melden“** in der Seitenleiste: Problem, Modul-Problem, Idee, Sonstiges → Admin-Bereich.
- **Admin > neue Reiter:** **„User reports“** (Meldungen der Spieler mit Kategorie/Code/Version/E-Mail, löschbar) und **„Automatic errors“** (Fehlergruppen: pro Code+Text eine Zeile mit Anzahl, erstes/letztes Mal, Versionen, Systeme; „Mit KI auswerten“ je Gruppe oder für die Top-Fehler; Auswertung wird gespeichert).
- **Server (bereits eingespielt):** Migration `20261031000400_jopml_190_limits_reports.sql` (Tabellen `jopml_ai_settings`, `jopml_error_groups`, `jopml_user_reports`, neue Funktionen, `jopml_ai_hit` mit Token-Limit) und Edge Function **`jopml-chat` v2** (Version 9 bei Supabase).
- **Rechtstext** (DE+EN): Claude/ChatGPT/OpenAI als Chat-Anbieter raus (Anthropic nur als Entwicklungswerkzeug), Groq rein, Modellwahl, Modul-Bau, Limits (Antwortlänge/Tokens/Maximum/Kein Limit), Fehlerhilfe „KI fragen“, KI-Auswertung durch den Admin (Art. 22 DSGVO), Fehlergruppen (verdichtet, ohne Kontozuordnung), Nutzer-Meldungen (Kontozuordnung, 10/Tag, 180 Tage), Reichweite des Diagnose-Schalters, Admin-Einsicht. Handbuch (<30000 Zeichen), FAQ, Übersetzungen (5 Sprachen), 55 Tests (neu: `test_v190_errors_chat_limits_reports`).

## 2. Das musst du tun (Supabase > Edge Functions > Secrets)
1. `GEMINI_API_KEY` (hast du) und **`GROQ_API_KEY`** (neu, von console.groq.com) eintragen.
2. Optional Standardmodelle: `GEMINI_MODEL`, `GROQ_MODEL` (sonst `gemini-3.5-flash-lite` / `llama-3.3-70b-versatile` – **Modellnamen habe ich nicht gegen die Live-Listen geprüft**; falls ein Name nicht mehr existiert, hier ändern, ohne Update).
3. `ANTHROPIC_API_KEY` und `OPENAI_API_KEY` können gelöscht werden (werden nicht mehr gelesen).
4. EXE bauen/hochladen wie gewohnt (Arena steckt drin; `arena_release/jopml-arena-1.3.1.zip` liegt bei).

## 3. Ablaufplan: wie es gemacht wurde
1. Anforderungen in Einzelpunkte zerlegt (Anbieter, Modelle, Dashboard, Modul-Bau, Limits, Fehlercodes, Fehlerspeicher, Melden, Rechtliches).
2. Ist-Zustand gelesen: `jopml-chat`, `modules/aichat`, `core/telemetry.py`, Admin-Seite, DB-Funktionen. Dabei fiel auf, dass `CloudClient.chat/chat_status` fehlten (Ursache des Chat-Fehlers).
3. Datenbank zuerst: Migration geschrieben (NULL = Standard erben, -1 = kein Limit; Grenzen geprüft; alle Admin-Funktionen mit `jopml_is_admin()`; RLS ohne Direktzugriff), eingespielt, Datei im Repo abgelegt.
4. Edge Function neu: nur Gemini/Groq, Modellliste mit Zwischenspeicher und Prüfung des gewünschten Modells (Muster + Liste), Richtlinie aus der DB, `max_tokens` gedeckelt, Token-Zählung (Gemini `usageMetadata`, Groq `usage`), Art `analyze` nur für Admins; deployt.
5. Client: `core/errors.py` (Codes, Zuordnung aus Text/Servercode), `core/error_dialog.py` (Fehlerfenster, Melden-Fenster), Telemetrie mit Code und Duplikat-Bündelung, Nutzer-Meldung; Einbau in App (Neustart, Modul-Laden, Updates), Modul-Import, Community, Publisher, Profil laden.
6. KI-Chat neu (Logik getrennt von Oberfläche: Einstellungen, Einwilligung je Anbieter, Modul-Code erkennen, Namen ableiten, Vorlage erraten), Seite mit Modellmenü, Infozeile (Limits), Modul-Knopf; Dashboard-Hero.
7. Admin: Berechtigungen (Standard + Dialog „Limits …“), Reiter Meldungen und Automatische Fehler mit KI-Auswertung.
8. Rechtstext (DE/EN), Handbuch, FAQ, 93 Übersetzungen × 5 Sprachen, Version/Rechtsfassung angehoben, alte Tests angepasst, neue Tests, komplette Testsuite (55/55), Release-ZIP.

## 4. Nicht getestet / offene Punkte
- **Keine echte Oberfläche**: Dashboard-Hero, Chat-Seite, Fehlerfenster, Melden-Fenster und Admin-Dialoge wurden nur geladen/quelltext-geprüft, nicht in einem echten Fenster angeschaut. Bitte durchklicken (v. a. Dashboard → Nachricht senden → Chat öffnet sich).
- Edge Function und Migration sind live, wurden aber **nicht mit einem echten Konto** durchgespielt (Gemini/Groq-Antwort, Limits, „Analyze with AI“, Melden). Groq-Schlüssel fehlt noch, bis du ihn einträgst → Groq zeigt „nicht eingerichtet“.
- Das Hinzufügen eines KI-Moduls wurde nur an den Prüf-/Import-Funktionen getestet, nicht mit einem echten KI-Modul im laufenden Launcher. KI-Code kann Fehler haben.
- Rechtstext ist **nicht anwaltlich geprüft**. Offen: § 25 TDDDG-Einordnung der Diagnose, Art. 22/Art. 28 DSGVO-Verträge mit Google und Groq, Datenschutzhinweise der Anbieter; bitte prüfen lassen, bevor du das breit veröffentlichst.
- Die automatische Fehler-Zusammenfassung nutzt Text-Muster; sehr ähnliche Fehler können getrennt, verschiedene selten zusammengelegt werden.
- Weiterhin keine Rückstoß-Kompensation / Spiel-Speicher-Werkzeuge; Arena nur mit erfundenen Waffen.

## 5. Neue Ideen für das nächste Update
- **Gratis-Gruppe und Auto-Fallback**: wenn Gemini das Limit erreicht, automatisch auf Groq wechseln (mit Hinweis).
- **Admin-Dashboard für KI-Kosten/Tokens** pro Tag und Anbieter (Diagramm), Warnung bei 80 % des Budgets.
- **Fehler-Tickets**: aus einer Fehlergruppe ein Ticket mit Status (neu/in Arbeit/behoben) machen; Meldungen der Spieler mit Gruppen verknüpfen; Antwort an den Melder.
- **„Fehler beheben lassen“**: KI schlägt einen Patch für ein eigenes Modul vor (Diff-Ansicht, Annahme mit Klick).
- **Modul-Vorlagen-Galerie** („Timer“, „Notizen“, „Hotkey-Tool“) als Startpunkt für die KI; Versionsverlauf/Rückgängig für KI-Module.
- **Chat-Verlauf lokal speichern** (verschlüsselt, abschaltbar) und Chats pro Modul-Projekt.
- **Streaming-Antworten** im Chat (wie beim Hilfe-Assistenten) und Abbrechen-Knopf.
- **Fehler-Kontext mitsenden** (optional, bereinigt): letzte Aktion/Seite, um Meldungen leichter nachzustellen.
- **Eigener Fehlercode-Katalog als Seite** in der Hilfe mit Lösungsvorschlägen pro Code.
