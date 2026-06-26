@echo off
setlocal
cd /d "%~dp0"

call "%~dp0scripts\ensure_desktop_env.bat"
if errorlevel 1 (
  echo.
  echo تعذّر تجهيز بيئة سطح المكتب.
  echo راجع: %TEMP%\liftcore-desktop-setup.log
  pause
  exit /b 1
)

set "LIFTCORE_URL=https://jama.liftcoreapp.com/login"
set "LIFTCORE_TITLE=JAMA"
set "LIFTCORE_MUTEX=Global\LiftCoreJamaDesktopSingleton_v1"
if exist "%USERPROFILE%\Downloads\Liftcore-icon.ico" (
  set "LIFTCORE_ICON=%USERPROFILE%\Downloads\Liftcore-icon.ico"
)

"%LIFTCORE_DESKTOP_PY%" "%~dp0scripts\liftcore_desktop.py" 2>>"%TEMP%\liftcore-jama-desktop.log"
if errorlevel 1 (
  echo.
  echo JAMA Desktop - خطأ في التشغيل.
  echo راجع: %TEMP%\liftcore-jama-desktop.log
  pause
)
endlocal
