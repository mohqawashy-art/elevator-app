@echo off
cd /d "%~dp0"
python tools\db_snapshot.py restore
pause
