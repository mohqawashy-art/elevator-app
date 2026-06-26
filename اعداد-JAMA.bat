@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desktop\Setup-Company-Desktop.ps1" -CompanyName JAMA -Url "https://jama.liftcoreapp.com/login"
