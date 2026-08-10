@echo off
setlocal
cd /d "%~dp0"

rem Dit bestand staat in <projectroot>\scripts\scraper\ -- twee mappen omhoog is de projectroot.
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"

rem Gebruik de venv van het project als die bestaat, anders de python uit PATH.
set "PY=python"
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"

echo.
echo === TreeEbb scraper starten ===
echo Projectmap : %PROJECT_ROOT%
echo Python     : %PY%
echo Output     : %PROJECT_ROOT%\data\treeebb_planten_allfields.csv
echo.

"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt

echo.
echo Scraper draait nu... (sluit dit venster pas als hij klaar is)
echo.

"%PY%" treeebb_scraper_allfields.py

echo.
echo Klaar! Druk op een toets om af te sluiten.
pause >nul
