@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo إيقاف أي سيرفر قديم على المنفذ 5001...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5001" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%P >nul 2>&1
)
if exist installation\__pycache__ rmdir /s /q installation\__pycache__
echo تشغيل سيرفر جديد...
call run.bat
