@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -m arena & goto :eof)
python -m arena
