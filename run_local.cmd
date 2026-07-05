@echo off
REM يتجاوز قيود PowerShell ExecutionPolicy
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
pause
