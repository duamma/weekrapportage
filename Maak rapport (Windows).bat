@echo off
REM Dubbelklik om het weekrapport te maken. Het rapport opent daarna in je browser.
cd /d "%~dp0"
py maak_rapport.py --open
if errorlevel 9009 python maak_rapport.py --open
echo.
pause
