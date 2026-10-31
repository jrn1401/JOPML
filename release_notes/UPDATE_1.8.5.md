# Update 1.8.5 – Änderungen, Ablaufplan, Ideen

Launcher 1.8.5 · Recoil Arena 1.3.0 · (alles aus 1.8.4 enthalten)

## 1. Was sich geändert hat

### Arena steckt in der EXE
- Die Recoil Arena ist jetzt **in `JaronsOPMakro.exe` eingebaut**. Sie startet als eigener Prozess mit `JaronsOPMakro.exe --arena` (eigenes Fenster, wie bisher).
- Für ein Update reicht es, **nur die EXE hochzuladen**. Kein getrennter Arena-Upload, kein Arena-Download für Nutzer der EXE.
- Die Arena-Seite zeigt „Im Launcher eingebaut · v1.3.0“. Server-Download/Update der Arena wird in der EXE übersprungen (sie kommt mit dem Launcher-Update).
- Im Quellcode-Betrieb (Python) und für den ZIP-Weg (Arena-ZIP im Ordner `arena_release/`) bleibt alles wie vorher.
- Build: `tools/pyi_args.py` nimmt `arena` und `numpy` mit; `numpy` steht in `requirements.txt`.

### Steuerung wie in modernen Spielen
- **Leertaste** springen, **Ctrl** halten oder **C** umschalten = ducken, **Q** = letzte Waffe, Mausrad/1–5 = Waffen, rechte Maustaste = visieren.
- Standard-Empfindlichkeit niedriger (0.0009), damit die Maus nicht „wegrutscht“.
- **Maus wird in eigenem Faden ~500-mal pro Sekunde abgefragt** (Windows, mit genauer Zeitauflösung). Bei schnellen Bewegungen oder niedriger Bildrate geht nichts mehr verloren.
- Bewegung läuft in festen Schritten (1/120 s): gleiche Geschwindigkeit bei 15 und 144 Bildern pro Sekunde, schnelleres Anlaufen/Bremsen, Luftsteuerung.
- Klick kurz vor Schussbereitschaft wird gemerkt (0,15 s Puffer), Feuerrate hängt nicht mehr von der Bildrate ab.
- Qualität **„Auto“** (neuer Standard): rendert gröber, wenn die Bildrate unter 45 fällt, und schärfer, wenn über 80.

### Rückstoß fühlt sich natürlicher an
- Der Rückstoß wird nicht mehr als Sprung pro Schuss aufgebracht, sondern **weich in ~0,04 s eingeblendet**.
- Rückkehr zur Ausgangslage **exponentiell** (schnell am Anfang, sanft am Ende), beginnt 0,12 s nach dem letzten Schuss.
- In der Luft gilt volle Bewegungsstreuung; „Stehend“-Statistik zählt Sprünge nicht.
- Alle Waffen und Rückstoßmuster sind weiterhin erfunden; es werden keine Muster echter Spiele nachgebaut.

### Sonstiges
- Übersetzungen (de/es/fr/ru/zh) für die neuen Texte, Handbuch und KI-Wissen auf 1.8.5.
- Neuer Test `test_v185_arena_feel_poller_builtin`.

## 2. Ablaufplan: wie es gemacht wurde
1. **Ursache für „fühlt sich komisch an“ gesucht**: zu hohe Empfindlichkeit, Eingabe und Schussrate an die Bildrate gekoppelt, Rückstoß als harter Sprung pro Schuss, lineare langsame Rückkehr, träge Beschleunigung, fehlende Standardtasten.
2. **Spiellogik (`arena/game.py`)**: feste Zeitschritte (`STEP = 1/120`), `_kick` blendet Rückstoß weich ein, `_recover` exponentiell, Schuss-Puffer, Sprung (`JUMP_V`, `GRAVITY`), Luftsteuerung. Gemessen: Schussrate bei 20 und 120 fps gleich; Rückstoßverlauf ohne harten Sprung.
3. **Maus (`arena/grab.py`)**: Klasse `Poller` (eigener Faden, 500 Hz, Zeiger zurück in die Mitte, Summe thread-sicher). `Grab` nutzt sie unter Windows mit `timeBeginPeriod(1)`. Die Klasse bekommt die Positionsfunktionen übergeben und ist dadurch testbar.
4. **Tasten und Qualität (`arena/ui.py`, `settings.py`)**: `space` in der Tastenbelegung, C-Umschalter, Q-Waffenwechsel, Hinweiszeile, `Auto`-Qualität mit Schrittweite alle 1,5 s.
5. **Arena in die EXE**: `main.py --arena` (vor dem Launcher-Start), `modules/arena/plugin.py` mit `builtin()` (Erkennung per `importlib`, nur in gebauter EXE), Start mit `[sys.executable, "--arena"]` und `relaunch.clean_env()` (damit der Kindprozess nicht auf den temporären Ordner der Eltern zeigt), `sync/update_info/download_game` überspringen den Server.
6. **Build-Dateien**: `tools/pyi_args.py` (`--collect-submodules arena`, `numpy`), `requirements.txt`.
7. **Texte**: Übersetzungen, Handbuch (alte Einträge gekürzt, damit es unter 30 000 Zeichen bleibt), `RELEASE_NOTES.txt`, Wissensdatei neu erzeugt.
8. **Tests**: neue Tests, Gesamtlauf. **Release**: `git archive` des Standes plus die neueste Arena-ZIP (`arena_release/jopml-arena-1.3.0.zip`) in den Update-Ordner.

## 3. Nicht getestet (ehrlich)
- Keine echte Fensteroberfläche und kein echter Windows-Lauf in dieser Umgebung: Maus-Faden, `--arena` in der gebauten EXE und das Spielgefühl sind **nur über Logik-Tests und simulierte Oberfläche geprüft**.
- Die EXE wurde hier nicht gebaut. Mit numpy wird sie größer; der erste Start von `--arena` entpackt wie jede Einzeldatei-EXE kurz.
- Bitte nach dem Bauen testen: Arena starten, Maus, Springen, Ducken, Rückstoß-Gefühl, Beenden, danach Launcher-Neustart.

## 4. Ideen für die nächsten Updates
- **Empfindlichkeit in cm/360** statt Rohwert, mit Umrechnung, plus Standardwerte-Vorschläge.
- **Rückstoß-Stärke-Regler** (0.5×–1.5×) und Wahl „Natürlich / Straff / Weich“.
- **Eigene Tastenbelegung** in der Arena (jede Taste umlegbar), Controller-Unterstützung.
- **Aufwärmroutinen**: 2-Minuten-Programm (Tracking, Flicking, Wechsel), Ergebnis-Verlauf als Diagramm.
- **Tracking-Modus**: bewegliche Ziele, Trefferzeit-Anteil statt Einzeltreffer.
- **Replay des letzten Durchgangs** (Blickverlauf als Linie), Heatmap der Fehlschüsse.
- **Ziel-Wellen/Level** mit Freischaltungen, tägliche Aufgabe, lokale Bestzeiten.
- **Waffenanpassung**: Aufsatz-Auswahl (nur erfundene Werte), Skins für Waffen.
- **Mehrere Karten** und Tag/Nacht-Themen.
- **Launcher**: Arena-Start über Hotkey/Befehlspalette, Arena-Statistik im Dashboard.
- **Update-Prüfung**: vor dem Upload automatisch prüfen, ob die EXE `--arena` kann (`--selftest` um Arena-Importe erweitern).
