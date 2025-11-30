@echo off
cd /d C:\Rob\Beplantingswijzer\PlantWijs
call .venv\Scripts\activate.bat
python -m uvicorn api:app --reload --port 9000
pause