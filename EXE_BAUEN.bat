@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Bevorzugt eine bewaehrte Python-Version (3.13, 3.12, 3.11, 3.14), sonst die neueste vorhandene.
set "PY="
for %%V in (3.13 3.12 3.11 3.14) do (
  if not defined PY (
    py -%%V --version >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python wurde nicht gefunden.
  echo Bitte von https://www.python.org/downloads/ installieren und dabei "Add Python to PATH" anhaken.
  pause
  exit /b 1
)
echo Verwende: %PY%
%PY% --version

if not exist ".venv-build\Scripts\python.exe" (
  %PY% -m venv .venv-build
  if errorlevel 1 (
    echo Konnte die Python-Umgebung nicht anlegen.
    pause
    exit /b 1
  )
)
.venv-build\Scripts\python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Installation fehlgeschlagen. Meldung oben lesen.
  pause
  exit /b 1
)
.venv-build\Scripts\python tools\make_icon.py
set "PYIARGS="
for /f "delims=" %%A in ('.venv-build\Scripts\python tools\pyi_args.py') do set "PYIARGS=%%A"
.venv-build\Scripts\pyinstaller --noconfirm --clean --noconsole --onefile --name JaronsOPMakro --icon build\icon.ico --collect-all customtkinter --collect-all lupa --collect-submodules pynput %PYIARGS% main.py
if errorlevel 1 (
  echo Build fehlgeschlagen. Meldung oben lesen.
  pause
  exit /b 1
)
echo.
if exist selftest.txt del selftest.txt
start /wait "" "%~dp0dist\JaronsOPMakro.exe" --selftest "%~dp0selftest.txt"
if exist selftest.txt (type selftest.txt) else (echo Selbsttest: keine Ausgabe - EXE startet nicht!)
findstr /b "FAIL" selftest.txt >nul 2>&1 && (echo Selbsttest FEHLGESCHLAGEN. Bitte selftest.txt an Claude schicken. & pause & exit /b 1)
echo.
echo Fertig! Die Datei liegt hier: %~dp0dist\JaronsOPMakro.exe
echo Weiter: Launcher starten, mit Admin-Konto anmelden, Menue Publish.
pause
