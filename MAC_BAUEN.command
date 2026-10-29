#!/bin/bash
# Baut JOPML.dmg auf dem Mac. Doppelklick (beim ersten Mal: Rechtsklick -> Öffnen) oder im Terminal: bash MAC_BAUEN.command
# Voraussetzung: Python 3.11 bis 3.13 von python.org (enthält Tk). Danach liegt die Datei in ./dist/JOPML.dmg
set -e
cd "$(dirname "$0")"
PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)
echo "Verwende: $PY ($($PY --version))"
$PY -c "import tkinter" || { echo "Tk fehlt: bitte Python von python.org installieren."; exit 1; }
$PY -m venv .venv-build
. .venv-build/bin/activate
pip install -q -r requirements.txt pyinstaller
python tools/make_icon.py
python -c "from PIL import Image; Image.open('build/icon.png').convert('RGBA').resize((1024,1024)).save('build/icon.icns')"
pyinstaller --noconfirm --clean --windowed --name JOPML --icon build/icon.icns --osx-bundle-identifier de.jopml.launcher \
  --collect-all customtkinter --collect-all lupa --collect-submodules pynput $(python tools/pyi_args.py) main.py
dist/JOPML.app/Contents/MacOS/JOPML --selftest "$PWD/selftest.txt" || true
cat selftest.txt
if grep -q '^FAIL' selftest.txt; then echo "Selbsttest fehlgeschlagen – Abbruch."; exit 1; fi
codesign --force --deep -s - dist/JOPML.app
rm -rf dmgroot && mkdir dmgroot && cp -R dist/JOPML.app dmgroot/ && ln -s /Applications dmgroot/Applications
rm -f dist/JOPML.dmg
hdiutil create -volname "JOPML" -srcfolder dmgroot -ov -format UDZO dist/JOPML.dmg
rm -rf dmgroot
echo; echo "Fertig: $PWD/dist/JOPML.dmg"
echo "Weiter im Launcher: Menü 'Publish' (nur mit Admin-Konto)."
