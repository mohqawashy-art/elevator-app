@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desktop\Install-Jama-PWA.ps1"
pause
