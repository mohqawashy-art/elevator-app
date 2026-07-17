@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LIFTCORE_INSTALL_MODULE=1

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
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
  echo  [خطأ] Python غير مثبت على هذا الجهاز.
  echo.
  echo  الحل:
  echo    1. نزّل Python من: https://www.python.org/downloads/
  echo    2. أثناء التثبيت فعّل: [x] Add python.exe to PATH
  echo    3. شغّل: setup_local.bat
  echo    4. ثم شغّل: run.bat
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [تنبيه] البيئة الافتراضية .venv غير موجودة — شغّل setup_local.bat أولاً
  echo محاولة التشغيل بـ Python الموجود...
  echo.
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5001" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
if exist installation\__pycache__ rmdir /s /q installation\__pycache__

echo LiftCore - المنفذ 5001
echo موديول التركيب: مفعّل ^(تجريبي^)
echo افتح: http://127.0.0.1:5001
echo تسجيل الدخول: admin / admin123
echo.

if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import sys; sys.dont_write_bytecode=True; from app import app; app.run(debug=True, port=5001, host='127.0.0.1', use_reloader=True)"
) else (
  %PY% -c "import sys; sys.dont_write_bytecode=True; from app import app; app.run(debug=True, port=5001, host='127.0.0.1', use_reloader=True)"
)

if errorlevel 1 (
  echo.
  echo [خطأ] فشل التشغيل. جرّب: setup_local.bat
  pause
)
