# Update 1.10.0 – Änderungen, Ablaufplan, Ideen

Launcher 1.10.0 · Recoil Arena 1.3.1 (unverändert, neueste Version liegt bei) · Rechtsfassung 2026-10-31e (neue Zustimmung nötig) · enthält alles aus 1.9.0

## 1. Was sich geändert hat (deine 9 Ideen + Aufräumen)
1. **Auto-Fallback Gemini → Groq (und umgekehrt):** Erreicht eine KI ihr Limit oder fällt aus, antwortet die andere; im Chat steht „↪ Gemini ist gerade nicht verfügbar. Diese Antwort kommt von Groq.“ Aus Datenschutzgründen nur, wenn du auch für die andere KI zugestimmt hast.
2. **Admin > neuer Reiter „AI“:** Tagesdiagramm der letzten 14 Tage (Tokens oder Nachrichten, je Anbieter, Farben), Balken „heute“ gegen das Tagesbudget aller Konten, **Warnung ab 80 %** (im Reiter AI und in der Übersicht), Budget bearbeiten, Zähler „automatische Wechsel“. Die Standard-Limits wanderten aus „Berechtigungen“ hierher (dort bleiben nur Admin-Rechte und persönliche Limits).
3. **Fehler-Tickets:** Reiter „Tickets“ (Neu / In Arbeit / Behoben + Notiz). „Ticket anlegen“ direkt an jeder Fehlergruppe. Meldungen mit gleichem Fehlercode werden automatisch verknüpft, andere von Hand („Mit Ticket verknüpfen“). **Antwort an den Melder** (Dialog); der Spieler sieht Status und Antwort unter **Melden > Meine Meldungen**, beim Start kommt ein Hinweis.
4. **Fehler beheben lassen:** Modules > Modul wählen > „Mit KI reparieren“ springt in den Chat (Projekt = dieses Modul, Code und Fehlertext gehen als Hintergrund mit). Die Antwort wird **nie automatisch übernommen**: „Korrektur prüfen“ zeigt die **Diff-Ansicht** (grün/rot, Zeilenzahlen) plus Prüfergebnis, **„Änderung übernehmen“** schreibt die Datei und startet neu.
5. **Vorlagen-Galerie:** Chat > „Vorlagen“: Timer, Notizen, Hotkey-Zähler, Textbausteine – „Hinzufügen“ (mit Prüfung) oder „Mit KI ändern“. **Versionsverlauf/Rückgängig:** vor jeder Änderung wird der alte Stand gesichert (15 je Modul), Modules > „Verlauf“ zeigt Unterschiede und stellt wieder her (auch das ist umkehrbar).
6. **Chat-Verlauf lokal:** Chat > „Chats“, Schalter standardmäßig **aus**; verschlüsselt (Windows-DPAPI), 30 Chats je Projekt, löscht sich beim Ausschalten. **Projekte:** „Allgemein“ oder je eigenes Modul.
7. **Streaming + Abbrechen:** Antworten erscheinen beim Schreiben; der Senden-Knopf wird zu „Stop“.
8. **Fehler-Kontext (optional):** Haken im Melden-Fenster (aktuelle + letzte Seiten, nur Namen, ≤ 300 Zeichen) und Schalter in den Einstellungen für automatische Berichte; beides standardmäßig aus.
9. **Fehlercode-Katalog:** Hilfe-Assistent > „Fehlercodes“: alle 32 Codes mit Bedeutung und Lösung, durchsuchbar, je Code „KI fragen“/„Melden“. Das Fehlerfenster zeigt jetzt die Lösung und „Alle Codes“.

10. **Release-Notes automatisch (Nachtrag):** Beim Hochladen (Admin > Publish) schreibt das Programm selbst eine Release-Note (aus `RELEASE_NOTES.txt`, plus dein „Was ist neu?“-Text) und trägt sie in **Community > News** ein: **eine aufklappbare Zeile je Version** (neueste offen, ältere zu), jede mit Stichpunkt-Übersicht. Erneutes Hochladen derselben Version aktualisiert den Eintrag. Schlägt der Eintrag fehl, bleibt der Upload gültig und es erscheint ein Hinweis. **Einmalig nachgetragen:** alle 41 bisherigen Versionen (1.1.1 bis 1.10.0) stehen bereits in den News (live per SQL eingespielt, Migration `jopml_1100_release_notes`). Hinweis: Alle Nutzer bekommen deshalb einmal die Meldung „Neue Ankündigung“.

**Aufgeräumt, damit sich nichts überlappt:** Dashboard-Assistent hat eine Weiche (Bedienfragen → Hilfe-Assistent, Schreiben/Bauen/Fehler → KI-Chat). Hilfe-Assistent verweist auf Fehlercodes und KI-Chat. Kontaktseite sagt klar: Lob/Fragen hier, Probleme über „Melden“. Modul-Änderungen laufen nur über einen Weg (Prüfen → Übernehmen), Fehlerhilfe nur über einen Katalog, „Melden“ ist die einzige Stelle für Probleme mit Verlauf.

Weiteres: Edge-Function `jopml-chat` v3 (Streaming, Fallback, Nutzungslog), E-AI-007 „Tagesbudget aufgebraucht“, Handbuch/FAQ/Release-Notes aktualisiert.

## 2. Rechtliches (aktualisiert)
Rechtstext neu (§ 9 Abs. 6 + 9.7 EN: Release-Notes; Fassung 2026-10-31e, Zustimmung wird erneut abgefragt): § 10 Abs. 7 (Auto-Wechsel nur mit Einwilligung für beide, Streaming, lokaler Verlauf/DPAPI, Modulcode an die KI, Vorlagen, Nutzungsstatistik/Budget), § 10 Abs. 3 (Verlauf), § 11 Abs. 1 Nr. 6–7 (Kontext, Tickets, Antworten, Löschfrist 180 Tage), Kurzfassung DE/EN. **Weiterhin kein Anwalt geprüft**; offen: TDDDG § 25, Auftragsverarbeitung/SCC mit Google und Groq, Art. 22 DSGVO bei KI-Auswertung.

## 3. Übersetzung geprüft
Alle neuen Oberflächentexte in de/es/fr/ru/zh (ca. 135 Einträge, auch alle 32 Fehlercode-Lösungen, Vorlagen, Ticketstatus); Prüfung per Skript: de 0 fehlend. Nicht übersetzt (wie bisher): die langen FAQ-Antworten des Hilfe-Assistenten (nur Deutsch/Englisch).

## 4. Das musst du tun
- Nichts an den Schlüsseln: GEMINI_API_KEY und GROQ_API_KEY sind gesetzt. Datenbank-Migration `jopml_1100_tickets_budget` und Edge Function `jopml-chat` (v10) sind bereits live.
- Neue EXE bauen, ZIP hochladen (Admin > Publish), Version 1.10.0.

## 5. Ablaufplan: wie es gemacht wurde
1. Chat-Ausfall der Vorversion bleibt behoben; Datenbank zuerst: Tabellen `jopml_ai_log`, `jopml_tickets`, neue Spalten (Antwort, Kontext, Ticket), RPCs für Budget/Statistik/Tickets/Antworten (Admin-Prüfung `jopml_is_admin()`, RLS an, kein Direktzugriff).
2. Edge Function `jopml-chat` v3: Streaming (Gemini/Groq SSE), Fallback-Reihenfolge, Zähler pro Tag/Anbieter/Modell, Budget aus Einstellungen; mit Node-Attrappen getestet.
3. Client: `chat_stream`, `core/module_history.py` (sichern/Diff/zurück), `core/module_review.py` (Diff- und Verlaufsdialog, gemeinsam für Chat und Modul-Verwaltung), Chat-Logik (Verlauf verschlüsselt, Projekte, Fix-Vorlage, Weiche), Vorlagen.
4. Oberflächen: Chat-Seite umgebaut, Modul-Buttons, Admin (AI, Tickets, Meldungen), Fehlerfenster, Melden-Fenster mit „Meine Meldungen“, Katalog-Seite, Einstellungsschalter.
5. Aufräumen der Überlappungen (siehe oben), Rechtstext, Handbuch (< 30 000 Zeichen), FAQ, Übersetzungen (`tools/translations_1100.py` → `tools/apply_translations.py`).
6. Tests: 56/56 (neuer Test `test_v1100…`: Vorlagen-Prüfung, Verlauf verschlüsselt, Modul-Verlauf, Diagramm/Budget/Ticket-Logik, SQL, Node-Test der Edge Function, Rechtstext; GUI-Smoke mit Attrappen für Chat, Dialoge, Admin-Reiter). Supabase-Sicherheitscheck: nur bekannte Hinweise (Admin-RPCs prüfen intern `jopml_is_admin()`; Leaked-Password-Schutz ist im Supabase-Dashboard ein Schalter für dich).
7. Paket: git archive + Arena 1.3.1 + diese Datei; Übersicht und Umsetzungsstand als Projekt-Dokumente.

## 6. Nicht getestet / offene Punkte (ehrlich)
- Release-Note beim Upload und Aufklappen in den News: nur mit Attrappen geprüft (kein echter Upload, kein echtes Fenster). Die Texte sind deutsch (Quelle RELEASE_NOTES.txt), nicht übersetzt.
- **Kein echtes Fenster:** Die Oberfläche wurde nur mit Attrappen (ohne echtes customtkinter) gebaut/gebrochen; Aussehen, Abstände und das Diagramm im echten Fenster habe ich nicht gesehen. Bitte kurz durchklicken: Chat (Stop, Projekte, Vorlagen), Modules (Reparieren, Verlauf), Admin (AI, Tickets), Melden > Meine Meldungen.
- **Echte KI-Aufrufe** (Gemini/Groq live) konnte ich ohne Nutzer-Anmeldung nicht auslösen; Server-Logik ist mit Attrappen geprüft.
- **DPAPI-Verschlüsselung** des Verlaufs läuft nur unter Windows; hier getestet wurde der Ersatzweg (Verschleierung).
- Streaming-Anzeige: bei sehr langen Antworten kann das Textfeld kurz flackern (Neuzeichnen alle ~0,12 s).

## 7. Neue Ideen für das nächste Update
- Chat: Antwort „Neu generieren“, Markdown/Code-Blöcke mit Kopier-Knopf je Block, Suche im Verlauf, Verlauf als Datei exportieren.
- Module: „Test-Lauf in Sandbox“ (Modul erst in einem Probefenster öffnen), automatische Rückkehr zum letzten guten Stand, wenn ein neues Modul beim Start abstürzt.
- Tickets: E-Mail/Hinweis an alle Melder bei „Behoben“, Zusammenführen doppelter Tickets, Admin-Statistik (Zeit bis Behebung).
- KI-Kosten: Wochen-/Monatsansicht, Budget je Anbieter, automatisches Umschalten des Standard-Anbieters nach Auslastung.
- Fehlercodes: Lösung mit Knopf „Jetzt beheben“ (z. B. Verbindung testen, Update-Cache leeren).
- Vorlagen: eigene Vorlagen speichern und teilen (Community-Marktplatz), mehr Beispiele (Zufallszahl, Stoppuhr, Zwischenablage-Verlauf).
- Barrierefreiheit: Tastatur-Bedienung für Diff-Ansicht, größere Schrift-Option.

## 8. Prüfung vor dem Release (Repo jrn1401/JOPML)
- **Lua-Sandbox wieder gehärtet:** Das Update brachte erneut die ungehärtete Fassung von `modules/luascripts/runner.py` (Stand 1.7.9) mit. Ohne `attribute_filter` kann ein Skript über `wait.__self__` an Python und damit an Dateien und Programme kommen. Die gehärtete Fassung (Attributsperre, Lua-Hüllen für wait/macro, 64 MB Speichergrenze) bleibt; der Test mit der echten Lua-Engine läuft im CI.
- **Doppelte Migrationsnummer behoben:** `20261031000300` war doppelt (`jopml_permissions` und `jopml_market_downup`). Die noch nicht eingespielte Marktplatz-Migration heißt jetzt `20261031000700_jopml_market_downup.sql`.
- **Neue Migrationen im Datenbank-Test:** `permissions`, `190_limits_reports`, `1100_tickets_budget`, `1100_release_notes` liefen bisher in keinem Test gegen PostgreSQL; jetzt stehen sie in `tests/pg_shim.py`. Prüfung aller Migrationen auf einer frischen Datenbank: alle Tabellen mit RLS, keine Tabellenrechte für Clients, keine SECURITY-DEFINER-Funktion für `anon`, alle setzen `search_path`, jede `jopml_admin_*`-Funktion prüft `jopml_is_admin()`.
- **Test angepasst:** Automatische Fehlerberichte werden seit 1.9.0 gruppiert (`jopml_error_groups`) – der alte Test auf `jopml_errors` prüft jetzt die Gruppierung.
- **Release-Paket:** Das GitHub-Release enthält jetzt automatisch auch die neueste Arena (`arena_release/jopml-arena-<Version>.zip`) und diese Änderungsdatei (`release_notes/UPDATE_<Version>.md`); ein Test prüft, dass beide vorhanden sind und die Arena-Version stimmt.
- Rechtstext und Übersetzungen: durch diese Prüfung keine neuen Oberflächentexte oder Funktionen → keine Änderung nötig (Rechtsfassung 2026-10-31e bleibt).
- Hinweis (nicht geändert): Automatische Fehlerberichte haben seit 1.9.0 kein Limit pro Nutzer mehr, nur höchstens 2000 Gruppen (älteste fliegen raus). Ein Nutzer mit vielen verschiedenen Fehlertexten könnte echte Fehlergruppen verdrängen. Vorschlag für das nächste Update: wieder ein Limit pro Nutzer (z. B. 20 neue Gruppen in 10 Minuten).

## 9. Weitere Ideen (aus der Prüfung)
- Admin > Fehler: „Spam-Schutz“-Anzeige, wie viele Berichte pro Nutzer abgelehnt wurden.
- Lua-Skripte: Vorlagen-Galerie wie beim KI-Chat (Zähler, Timer, Makro-Schleifen) und „Mit KI erklären“ für ein Skript.
- Arena: eigene Bestenliste je Waffe in Community > Bestenlisten, Replay der letzten Runde.
- Updates: Update-ZIPs aus dem aktuellen Repo-Stand bauen (git archive von main), damit Korrekturen aus dem Repo nicht mehr verloren gehen.
