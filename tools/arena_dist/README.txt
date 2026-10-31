JOPML Arena 1.3.1
===============
Ein kleines, eigenständiges Übungsspiel (Ego-Perspektive) mit ausgedachten Waffen, Bots, Farbthemen und Spielstilen.
Alles darin ist erfunden und hat nichts mit echten Spielen oder deren Rückstoßmustern zu tun. Die Arena liest Maus und Tastatur nur in ihrem
eigenen Fenster und sendet nichts an andere Programme.

Starten (braucht Python 3.10 oder neuer mit tkinter; für Texturen zusätzlich: pip install numpy - ohne numpy läuft eine einfache Darstellung):
  Windows: START_ARENA.bat doppelklicken     Andere: python3 -m arena

Eigene EXE bauen: ARENA_BAUEN.bat (braucht Internet für PyInstaller). Danach JOPML-Arena.exe in den Ordner
%APPDATA%\JOPML\arena_app kopieren oder im Launcher unter "Recoil Arena" > "Install Arena ZIP ..." eine ZIP mit der EXE installieren.

Im Launcher (EXE) ist die Arena fest eingebaut (JaronsOPMakro.exe --arena); diese ZIP ist nur für den Quellcode-Weg.

Steuerung: Das Spiel startet im Vollbild und fängt die Maus selbst ein (F11 Vollbild an/aus) - WASD laufen (weich anfahren/bremsen) - Leertaste springen - Shift rennen - Strg halten oder C umschalten = ducken - Q letzte Waffe - Maus umsehen (Pfeiltasten auch) - linke Maustaste schießen - rechte Maustaste visieren (Zoom je Waffe, Halten oder Umschalten) - R nachladen - 1-5 oder Mausrad Waffe wechseln - F3 Hitboxen und FPS - Esc Pause/Menü.
Modi: Bots (laufende Gegner, auf Wunsch schießen sie zurück) und Targets (leuchtende Zielkugeln wie in einem Zieltrainer).
Trefferzonen: Kopf (Kugel), Rumpf (Kapsel), Beine; die Hitboxen sind etwas kleiner als das Bild. Schüsse hinterlassen Leuchtspuren, Funken und Einschusslöcher.
Spielstile: Tactical und Precision bestrafen Bewegung beim Schießen (still stehen!), Arcade nicht.
Auswertung: Treffer, Kopfschüsse, Anteil der Schüsse im Stand und mittlerer "Spray-Fehler" (Abweichung während einer Salve; kleiner = besser).
