@echo off

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

python import_real_data.py "%USERPROFILE%\Downloads"
echo.
echo افتح صفحة العملاء وتاب الخريطة لتحديد المواقع تلقائيا من العناوين.
pause

