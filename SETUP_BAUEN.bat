@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Baut aus der EXE eine Setup-Datei (Inno Setup noetig: https://jrsoftware.org/isdl.php)
if not exist "dist\JaronsOPMakro.exe" (
  echo Zuerst EXE_BAUEN.bat ausfuehren - dist\JaronsOPMakro.exe fehlt.
  pause
  exit /b 1
)
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
  echo Inno Setup 6 wurde nicht gefunden. Bitte von https://jrsoftware.org/isdl.php installieren und erneut starten.
  pause
  exit /b 1
)
for /f "delims=" %%V in ('python -c "import re;print(re.search(r'APP_VERSION = .(.+?).$',open('core/version.py').read(),re.M).group(1))"') do set "VER=%%V"
"%ISCC%" /DAppVersion=%VER% installer.iss
if errorlevel 1 (
  echo Setup-Bau fehlgeschlagen. Meldung oben lesen.
  pause
  exit /b 1
)
echo.
echo Fertig! Die Setup-Datei liegt in dist\JaronsOPMakro-Setup-%VER%.exe
pause
