# Update 1.8.7 – Änderungen, Ablaufplan, Ideen

Launcher 1.8.7 · Recoil Arena 1.3.1 (unverändert, neueste liegt bei) · Rechtsfassung 2026-10-31b (neue Zustimmung) · enthält alles aus 1.8.6

## 1. Was sich geändert hat
- **Admin > neuer Reiter „Berechtigungen“**
  - Liste aller Konten mit Admin-Kennzeichnung, KI-Nutzung heute und persönlichem Limit.
  - **Zum Admin machen / Admin entziehen** (mit Rückfrage). Man kann sich nicht selbst entfernen und nicht den letzten Admin.
  - **KI-Limit pro Konto**: Zahl 0–100000 pro Tag eintragen → „Limit setzen“; „Standard“ entfernt die Sonderregel. Gilt für Hilfe-Assistent und KI-Chat zusammen.
  - Jede Änderung wird auf dem Server protokolliert (Tabelle `jopml_admin_audit`).
- **Server (bereits auf Supabase eingespielt, Datei `supabase/migrations/20261031000300_jopml_permissions.sql`)**: Funktionen `jopml_admin_people`, `jopml_admin_set_admin`, `jopml_admin_set_ai_limit` (alle prüfen serverseitig `jopml_is_admin()`), Tabelle `jopml_ai_limits`, und `jopml_ai_hit` nutzt ein persönliches Limit vor dem Standard.
- Rechtstext: Absatz zu Berechtigungen/Protokollierung und zum persönlichen KI-Limit. Handbuch, Übersetzungen (5 Sprachen), Test `test_v187_permissions` (54 Tests).

## 2. Hinweise
- Das **erste** Admin-Konto bleibt wie bisher per SQL in `jopml_admins` angelegt; weitere vergibst du jetzt im Programm.
- Wer Admin ist, sieht alle Konten (inkl. E-Mail), Fehlerberichte, kann Versionen hochladen und Module freigeben – nur an Vertraute vergeben.
- Das globale Tageslimit (2000) bleibt davon unberührt: ein hohes persönliches Limit hebt es nicht auf.

## 3. Kostenlose KI-Anbieter und Modellwechsel (Kurzfassung)
Siehe Chat-Antwort: Google AI Studio (Gemini), Groq, OpenRouter (Gratis-Modelle), Mistral, Cerebras u. a. haben Gratis-Stufen mit Limits (Stand der Quellen: ca. April 2026, bitte aktuell prüfen). Der Chat unterstützt bisher nur Claude, ChatGPT und Gemini; die Modelle wechselst du über die Secrets `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL` (Supabase > Edge Functions > Secrets), ohne neues Update.

## 4. Ablaufplan: wie es gemacht wurde
1. Bestehende Funktionen in der Datenbank gelesen (`jopml_admin_users`, `jopml_ai_hit`, `jopml_is_admin`), damit die neue Logik dazu passt.
2. Migration geschrieben und eingespielt: Tabellen mit RLS (nur über Funktionen erreichbar), drei Admin-Funktionen mit Schutz (Selbst-Entzug, letzter Admin, unbekanntes Konto, Grenzwert), Protokolltabelle, erweiterte `jopml_ai_hit`.
3. Oberfläche: Reiter in `modules/admin/page.py`, Eingabeprüfung und Fehlertexte in `modules/admin/logic.py` (testbar).
4. Übersetzungen, Handbuch, Rechtstext, Tests, Release-ZIP mit neuester Arena-ZIP.

## 5. Nicht getestet
Keine echte Oberfläche und kein Aufruf der neuen Funktionen mit einem echten Admin-Login (nur Attrappen- und Quelltext-Tests). Bitte einmal mit einem zweiten Testkonto probieren: Admin geben/entziehen, Limit setzen, im KI-Chat prüfen.

## 6. Ideen für das nächste Update
- Weitere Anbieter im KI-Chat (Groq, Mistral, OpenRouter mit Gratis-Modellen) als „Kostenlos“-Gruppe und Auto-Reihenfolge „erst kostenlos“.
- Verbrauchsanzeige pro Anbieter und Tag im Admin-Bereich (Anfragen, geschätzte Kosten), Warnung bei 80 % des Tageslimits.
- Rollen mit abgestuften Rechten (z. B. nur Moderator: Module freigeben, aber nicht hochladen).
- Protokoll der Admin-Änderungen als eigener Reiter mit Export.
- Limit-Anträge: Nutzer bitten im KI-Chat um mehr Kontingent, Admin bestätigt mit einem Klick.
