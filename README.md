# Jaron's OP Makro Launcher (JOPML) – v1.1

Modularer Launcher (Python, CustomTkinter, pynput) mit Auto-Clicker, Makro-Editor, Extensions und Recoil-Modul.
Download der fertigen Windows-EXE: <https://github.com/delft-ante/JOPML/releases/latest/download/JaronsOPMakro.exe>

## Entwickeln
```
pip install -r requirements.txt
python main.py            # Programm starten
python tests/test_all.py  # Tests (laufen ohne Fenster, mit Attrappen)
```
EXE lokal bauen: `EXE_BAUEN.bat` (Windows).

## Automatische Veröffentlichung (GitHub Actions)
- `.github/workflows/release.yml`: Tests, Windows-EXE bauen, GitHub-Release `v<APP_VERSION>` anlegen, Spiegel im Supabase-Bucket `releases`.
  Neue Version = `APP_VERSION` in `core/version.py` erhöhen und auf `main` pushen.
- `.github/workflows/supabase.yml`: rollt Migrationen, Auth-Konfiguration und die KI-Funktion nach Supabase aus (nur mit Secrets).
- `.github/workflows/build-protected.yml`: optionaler Nuitka-Build (manuell, ungetestet).

## Supabase einrichten (einmalig)
1. Kostenloses Projekt auf supabase.com anlegen.
2. `SUPABASE_URL` und den **publishable key** in `core/version.py` eintragen (nie den service_role-Key).
3. Google: Im Google-Cloud-Client (Typ "Webanwendung", Client-ID steht in `core/version.py`) die Redirect-URI
   `https://<projekt>.supabase.co/auth/v1/callback` erlauben; das Client-Secret nur in Supabase eintragen.
4. Repository-Secrets setzen: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD`,
   `SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET`, `GEMINI_API_KEY` (aus Google AI Studio; die OAuth-Client-ID ist kein Gemini-Schlüssel),
   optional `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` für den Download-Spiegel.
5. Push auf `main` unter `supabase/` rollt alles aus. In Auth muss "Confirm email" aus sein (Konten ohne E-Mail).

## Struktur
`core/` Kern (Konten, Cloud, Design, Sprachen, Rechtstext), `modules/` Plugins (autoclicker, macros, extensions, recoil),
`supabase/` Datenbank + Edge Function, `csharp/` ungetestete Avalonia-Vorlage, `tools/` Hilfsskripte, `tests/` Tests.

## Hinweise
Das Recoil-Modul ist nur für Offline-Spiele gedacht; moderne Anti-Cheat-Systeme können es erkennen. Der Rechtstext wurde nicht anwaltlich geprüft.
`server_examples/assistant_worker.js` ist ein optionaler eigener KI-Endpunkt (Anthropic, ungetestet); der Standard ist die Supabase-Funktion mit Gemini.

## Neue Version veröffentlichen (ohne GitHub)
1. `APP_VERSION` in `core/version.py` erhöhen.
2. Bauen: Windows `EXE_BAUEN.bat` (liefert `dist\JaronsOPMakro.exe`), Mac `MAC_BAUEN.command` (liefert `dist/JOPML.dmg`).
3. Im Launcher mit dem Admin-Konto anmelden, Menü **Publish** öffnen, Version und Datei wählen, „Hochladen und veröffentlichen“.
   Die Dateien landen im öffentlichen Supabase-Bereich `releases`; die Apps lesen `version.json` von dort.
4. Admin-Konto einmalig freischalten (SQL-Editor in Supabase):
   `insert into public.jopml_admins (user_id, note) select id, 'owner' from auth.users where email = '<deine-google-mail>';`
   Nur diese Konten dürfen in `releases` schreiben (Prüfung auf dem Server, nicht nur in der App).


## Community, Anordnung (ab 1.3.0)
- **Community** (`modules/community`): Server mit Kanälen, Direktnachrichten, öffentliches Forum. Chats sind Ende-zu-Ende-verschlüsselt (X25519/AES-256-GCM/Ed25519, Schlüssel mit Passphrase gesichert); der Server sieht nur Chiffretext und Metadaten. Einladung per Code oder Benutzername. Voice/Bildschirmübertragung sind noch nicht gebaut.
- **Wortfilter** (`core/chatfilter*.py`): Erkennt viele Schreibweisen. Nach Änderung der Wortliste `python tools/gen_filter_sql.py` ausführen und die erzeugte Migration neu einspielen.
- **Anordnung** (Einstellungen -> Anordnung): Module ein-/ausblenden, Reihenfolge ändern, eigenes Bannerbild.
- **Datenbank:** neue Migrationen `supabase/migrations/20261028*` in dieser Reihenfolge einspielen. `tests/sql/*` sind nur Test-Hilfen, nicht einspielen.
- Abhängigkeit: `cryptography` (steht in requirements.txt).


## Neue Module (ab 1.4.0)
- **Click tools:** Fadenkreuz-Overlay, Hotkey-Manager (Taste/Text/Makro), Farb-Trigger (Bildschirmpunkt startet ein Makro), Zeitplaner, Profile pro Programm.
- **Gamer & Stream:** Session-Timer mit Erinnerungen, System-Overlay (CPU/RAM/GPU-Temperatur/Ping), Tasten-Overlay, CPS- und Reaktionstest mit Bestenliste, Screenshot-Bereich.
- **Productivity:** Zwischenablage-Verlauf, Fenster-Manager (Hälften/Viertel, Layouts), KI-Makro-Assistent mit Gespräch.
- **Community:** Makro-Marktplatz (teilen, bewerten, importieren mit Prüfhinweisen) und Ankündigungen.
- Datenbank: `supabase/migrations/20261030000000_jopml_market.sql` (zusätzlich zu den älteren Migrationen).
