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

"%LIFTCORE_DESKTOP_PY%" "%~dp0scripts\liftcore_desktop.py" 2>>"%TEMP%\liftcore-desktop.log"
if errorlevel 1 (
  echo.
  echo LiftCore Desktop - خطأ في التشغيل.
  echo راجع: %TEMP%\liftcore-desktop.log
  pause
)
endlocal
