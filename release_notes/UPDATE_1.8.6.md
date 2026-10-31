# Update 1.8.6 – Änderungen, Ablaufplan, Ideen

Launcher 1.8.6 · Recoil Arena 1.3.1 · Rechtsfassung 2026-10-31a (neue Zustimmung nötig) · enthält alles aus 1.8.5

## 1. Was sich geändert hat
- **Arena: PLAY-Knopf fehlte.** Das Menü war höher als dein Fenster, der Knopf lag unten außerhalb. Jetzt ist die Start-Leiste fest unten, die Spalten scrollen (Mausrad), **Enter** startet. Arena 1.3.1.
- **Modules > „Modul-Anforderungen ansehen“**: genaue Regeln für Module, Lua-Skripte, geteilte Module, Makros, verbotene Inhalte, Modul-Schnittstelle. Der Text wird **aus den echten Grenzwerten im Code erzeugt** (Dateitypen, Größen, Anzahl …) und aktualisiert sich selbst, auch bei geöffnetem Fenster. Speichern als Datei, Kopieren.
- **Admin > Publish**: oben Liste „Das kannst du hochladen“ mit Kriterien (Launcher .exe/.dmg, Arena-ZIP, Modul für alle); neue Karte **„Modul für alle hochladen“** (sofort freigegeben für Admins, mit Auffälligkeitsliste); unten **Wiederherstellen** – jetzt auch für Arena-ZIPs (aktiv setzen / löschen).
- **Neues Modul „KI-Chat“**: Claude, ChatGPT, Gemini oder Auto; Vorlagen (Freier Chat, Makro schreiben, Modul schreiben mit den Modul-Anforderungen, Fehler erklären); Kennzeichnung „KI-erzeugt“ mit Anbieter und Modell; Einwilligung je Anbieter vor der ersten Nutzung; Verlauf wird nicht gespeichert; Tageslimit 100.
- **Server-Funktion `jopml-chat`** ist auf Supabase bereitgestellt. Sie braucht die Schlüssel (siehe unten).
- Hilfe-Assistent/KI-Wissen: neue FAQ-Einträge, Handbuch 1.8.6.
- **Rechtstext überarbeitet** (siehe Abschnitt 3).

## 2. Was du noch tun musst (Server-Schlüssel)
Ohne Schlüssel meldet der KI-Chat „nicht eingerichtet“. Als Secrets der Funktion setzen (Supabase > Edge Functions > Secrets):
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`. Optional `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL`. Die voreingestellten Modellnamen (`claude-sonnet-5-5`, `gpt-5`, `gemini-3.5-flash-lite`) konnte ich nicht gegen die Anbieter prüfen – bei Fehlermeldung dort den aktuellen Namen eintragen. Nicht eingerichtete Anbieter sind im Chat als nicht verfügbar markiert; „Auto“ nutzt nur eingerichtete.

## 3. Rechtliches (Abgleich mit deiner Recherche-Datei)
- AGB-Haftung: „as is“ entfernt (unwirksam in vorformulierten Bedingungen); § 2 Abs. 6: unbeschränkt bei Vorsatz, grober Fahrlässigkeit, Leben/Körper/Gesundheit (§ 309 Nr. 7 BGB); bei leichter Fahrlässigkeit nur Kardinalpflichten, begrenzt auf vorhersehbaren Schaden; unwesentliche Pflichten ausgeschlossen.
- DSA: neues Meldeverfahren § 9 Abs. 3a (Inhalt der Meldung, Eingangsbestätigung, menschliche Prüfung, Begründung an beide Seiten, Rechtsbehelfe).
- KI-Verordnung: § 10 neu (Art. 50 Kennzeichnung, keine Art.-5-Praktiken, Auto-Auswahl erklärt, Drittland-USA, Einwilligung Art. 6/49 DSGVO, Kontingent).
- TDDDG § 25 für die Diagnose; Cyberresilienzgesetz (§ 13 Abs. 3), Modul-Kriterien und verbotene Inhalte (§ 16 Abs. 11), Recoil Arena (§ 16 Abs. 12), OpenAI in den Drittanbietern.
- **Offen / Risiko:** Der Text ist weiterhin **nicht anwaltlich geprüft**. Die Diagnose läuft als Opt-out; ob § 25 TDDDG eine Einwilligung (Opt-in) verlangt, ist unsicher – bitte juristisch klären lassen. Ob die Dienste unter den DSA-Ausnahmen für Kleinstunternehmen fallen, ist ebenfalls zu klären (Text sagt: Verfahren gilt freiwillig weiter).

## 4. Ablaufplan: wie es gemacht wurde
1. Fehlerursache Arena-Menü gesucht (Packreihenfolge: PLAY nach der expandierenden Spaltenfläche) → Leiste zuerst unten packen, Spalten in scrollbarer Fläche, Menü-Bindungen beim Spielstart lösen.
2. `core/requirements_doc.py` liest die Grenzen direkt aus `module_import`, `modshare`, `market`, `publisher.logic`; `core/doc_viewer.py` zeigt/aktualisiert/speichert; Test ändert eine Grenze und prüft, dass der Text folgt.
3. Publisher-Seite umgebaut: Übersicht (Zeile 1), EXE-Karte, Arena, Modul-Karte, Wiederherstellen unten; `arena_entries`/`arena_manifest` in `logic.py`; `read_manifest(name)` in `cloud.py`.
4. KI: Edge Function `jopml-chat` (Anbieter-Aufrufe, Auto-Regel, Fallback, Limit über `jopml_ai_hit`), Client `CloudClient.chat/chat_status`, Modul `modules/aichat` (Logik testbar, Einwilligungsdatei, Vorlagen mit Live-Wissen aus `core/ai_context.py` und `requirements_doc`).
5. Rechtstext Absatz für Absatz an der Recherche-Datei ausgerichtet; Verweise (§ 2 Abs. 6 Nr. 5) bereinigt; Versionen/Datum erhöht.
6. Übersetzungen (5 Sprachen), Handbuch, FAQ, Wissensdatei, Tests (54), Release-ZIP mit neuester Arena-ZIP.

## 5. Nicht getestet
Keine echten Fenster (nur Logik- und Attrappen-Tests), kein Aufruf der KI-Anbieter (keine Schlüssel), EXE nicht gebaut, Maus-Abfrage der Arena nur auf Windows relevant.

## 6. Ideen für das nächste Update
- KI-Chat: Antworten streamen, „Antwort von zwei KIs vergleichen“-Knopf, Verlauf optional lokal verschlüsselt speichern, Kosten-/Kontingentanzeige.
- Modul-Assistent: KI-Code direkt in „Add from code“ übernehmen (mit Prüfung und Auffälligkeitsliste).
- Modul-Marktplatz: Bewertungen, Versionsverlauf, automatische Updates installierter geteilter Module.
- Admin: Upload-Protokoll (wer/wann/was), Vorabprüfung der EXE (`--selftest` inkl. Arena), geplante Veröffentlichung.
- Rechtliches: Einwilligungs-Dialog für Diagnose beim ersten Start (Opt-in), SBOM-Erzeugung im Build, Meldeformular mit Pflichtfeldern nach Art. 16 DSA.
- Arena: Empfindlichkeit in cm/360, Aufwärmprogramme, Tracking-Modus.
