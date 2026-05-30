@echo off
echo Starting OPMD Backend...
cd /d "%~dp0backend"
python app.py
pause
