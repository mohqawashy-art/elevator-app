@echo off
REM تشغيل سريع بدون اختبارات — للتطوير اليومي
cd /d "%~dp0"
title LiftCore — محلي

where py >nul 2>&1 && set PY=py || set PY=python

if not exist ".venv\Scripts\python.exe" (
  echo انشاء .venv...
  %PY% -m venv .venv
  call .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)

if not exist ".env" (
  echo SECRET_KEY=liftcore-local-dev-%RANDOM%%RANDOM% > .env
)

echo.
echo LiftCore: http://127.0.0.1:5001
echo admin / LiftCore2026
echo Ctrl+C للايقاف
echo.
call .venv\Scripts\python.exe reset_admin_password.py
call .venv\Scripts\python.exe -c "from app import app; app.run(debug=True, port=5001, use_reloader=False)"
