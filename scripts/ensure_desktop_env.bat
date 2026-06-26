@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "VENV_PYW=%ROOT%\.venv\Scripts\pythonw.exe"
set "BOOT_PY="

if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "BOOT_PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined BOOT_PY if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" set "BOOT_PY=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not defined BOOT_PY set "BOOT_PY=py"

if not exist "%VENV_PY%" (
  echo [LiftCore] إنشاء بيئة Python المحلية...
  "%BOOT_PY%" -m venv "%ROOT%\.venv" 2>>"%TEMP%\liftcore-desktop-setup.log"
)

if not exist "%VENV_PY%" (
  echo [LiftCore] تعذّر إنشاء .venv
  exit /b 1
)

"%VENV_PY%" -c "import webview" 2>nul
if errorlevel 1 (
  echo [LiftCore] تثبيت متطلبات سطح المكتب...
  "%VENV_PY%" -m pip install -q --upgrade pip >>"%TEMP%\liftcore-desktop-setup.log" 2>&1
  "%VENV_PY%" -m pip install -q -r "%ROOT%\requirements-desktop.txt" >>"%TEMP%\liftcore-desktop-setup.log" 2>&1
)

"%VENV_PY%" -c "import webview" 2>nul
if errorlevel 1 (
  echo [LiftCore] فشل تثبيت pywebview — راجع %TEMP%\liftcore-desktop-setup.log
  exit /b 1
)

for %%I in ("%~dp0..") do endlocal & set "LIFTCORE_DESKTOP_PY=%%~fI\.venv\Scripts\pythonw.exe" & exit /b 0
