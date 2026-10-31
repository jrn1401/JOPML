@echo off
rem Baut JOPML-Arena.exe (braucht Python 3.10+ mit tkinter). Ergebnis: dist\JOPML-Arena.exe
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller numpy
py -3 -m PyInstaller --noconfirm --onefile --windowed --name JOPML-Arena arena\__main__.py --paths . --collect-submodules arena
echo.
echo Fertig: dist\JOPML-Arena.exe
pause
