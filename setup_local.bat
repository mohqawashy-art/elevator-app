@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 set "PY=%%P"
  )
)

if not defined PY (
  echo.
  echo Python غير موجود. ثبّته من https://www.python.org/downloads/
  echo وفعّل: Add python.exe to PATH
  pause
  exit /b 1
)

echo ==^> Python: %PY%
%PY% --version

if not exist ".venv\Scripts\python.exe" (
  echo ==^> إنشاء البيئة الافتراضية .venv
  %PY% -m venv .venv
  if errorlevel 1 (
    echo فشل إنشاء venv
    pause
    exit /b 1
  )
)

echo ==^> تثبيت المكتبات
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo ==^> إنشاء قاعدة البيانات
.venv\Scripts\python.exe init_db.py
.venv\Scripts\python.exe scripts\init_install_module.py

echo.
echo [تم] الإعداد اكتمل. شغّل الآن: run.bat
pause
