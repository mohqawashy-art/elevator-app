@echo off
setlocal
cd /d "%~dp0"

set "LIFTCORE_URL=https://jama.liftcoreapp.com/login"
set "LIFTCORE_TITLE=JAMA"
set "LIFTCORE_MUTEX=Global\LiftCoreJamaDesktopSingleton_v1"
if exist "%USERPROFILE%\Downloads\Liftcore-icon.ico" (
  set "LIFTCORE_ICON=%USERPROFILE%\Downloads\Liftcore-icon.ico"
)

set "PY="
if exist ".venv\Scripts\pythonw.exe" set "PY=.venv\Scripts\pythonw.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\HOME\ELEVATOR-APP\.venv\Scripts\pythonw.exe" set "PY=C:\Users\HOME\ELEVATOR-APP\.venv\Scripts\pythonw.exe"
if not defined PY set "PY=pythonw"

"%PY%" "%~dp0scripts\liftcore_desktop.py" 2>>"%TEMP%\liftcore-jama-desktop.log"
if errorlevel 1 (
  echo.
  echo JAMA Desktop - خطأ في التشغيل.
  echo راجع: %TEMP%\liftcore-jama-desktop.log
  echo.
  echo ثبّت المتطلبات: pip install -r requirements-desktop.txt
  pause
)
endlocal
