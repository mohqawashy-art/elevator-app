@echo off
cd /d "%~dp0"
title LiftCore — محلي
echo.
echo ========================================
echo   LiftCore — تشغيل محلي (بدون سيرفر)
echo ========================================
echo.

where py >nul 2>&1 && set PY=py || set PY=python

if not exist ".env" (
  echo SECRET_KEY=liftcore-local-dev-%RANDOM%%RANDOM% > .env
  echo   تم انشاء .env بمفتاح تطوير محلي
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] انشاء بيئة افتراضية...
  %PY% -m venv .venv
)

echo [2/4] تثبيت المتطلبات...
call .venv\Scripts\python.exe -m pip install -q -r requirements.txt

echo [3/4] فحص امني + اختبارات...
call .venv\Scripts\python.exe scripts\security_audit.py
if errorlevel 1 (
  echo.
  echo فشل الفحص الامني — اصلح قبل التشغيل.
  pause
  exit /b 1
)
call .venv\Scripts\python.exe -m pytest tests\ -q --tb=line
if errorlevel 1 (
  echo.
  echo فشلت الاختبارات — اصلح قبل التشغيل.
  pause
  exit /b 1
)

echo.
echo [4/4] تشغيل التطبيق...
echo   http://127.0.0.1:5001
echo   admin / LiftCore2026
echo   Ctrl+C للايقاف
echo.
call .venv\Scripts\python.exe -c "from app import app; app.run(debug=True, port=5001, use_reloader=False)"
