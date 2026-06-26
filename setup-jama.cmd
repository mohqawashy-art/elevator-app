@echo off
cd /d "%~dp0"
cscript //nologo "%~dp0desktop\Create-Shortcut.vbs" "JAMA" "https://jama.liftcoreapp.com/login" "%~dp0static\images\liftcore.ico" 1
echo.
echo تم. اضغط اي مفتاح...
pause >nul
