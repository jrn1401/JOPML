# Cheat-Menü für JOPML

Einzelspieler-Cheats für **Minecraft Java (1.21.11 / 1.26.x)** und **GTA 5 Enhanced (Story-Modus)**.

- Minecraft: 44 Cheats als Chat-Befehle (Spielmodus, Gott-Modus, Riese/Winzig, Mega-Sprung, Mond-Schwerkraft,
  verzauberte Ausrüstung, Zeit/Wetter, Spielregeln, Blitz …) plus eigener Befehl. Die Welt braucht „Cheats erlauben“.
- GTA 5 Enhanced: die offiziellen Rockstar-Cheat-Codes (Unverwundbar, Waffen, explosive Munition, Fahrzeuge …),
  getippt in die Cheat-Konsole, plus zwei Pakete. Nur Windows, nur Story-Modus.
- Rückstoß-Trainer: Übungsfeld mit vier Rückstoß-Mustern, Stärke, Feuerrate, Hilfslinie, Punkten und Bestwerten.
  Er liest die Maus nur im eigenen Feld und gibt selbst keine Eingaben ab – er trainiert die Hand und wirkt nicht in Spielen.
- Jeder Cheat lässt sich in Einstellungen > Hotkeys (Gruppe „Cheat menu“) auf eine Taste legen.

Bewusst nicht enthalten: Anti-Recoil-Scripts, Aimbot und alles für Online-Spiele.

## Dateien
- `plugin.py` – Klasse `Plugin`, Hotkeys, Ausführen
- `cheats.py` – Cheat-Listen und Bau des Minecraft-Makros
- `gta_input.py` – Tastatureingabe über Scan-Codes für die GTA-Konsole
- `trainer.py` – Rückstoß-Trainer: Muster, Treffer, Punkte
- `trainer_view.py` – Übungsfeld des Trainers
- `page.py` – Oberfläche

Hinweis: Mit automatischen Tests geprüft, aber nicht in den Spielen selbst ausprobiert.
