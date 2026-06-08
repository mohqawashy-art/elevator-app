@echo off
cd /d "%~dp0"
echo LiftCore - تشغيل النسخة الكاملة على المنفذ 5001
echo افتح: http://127.0.0.1:5001
echo تسجيل الدخول: admin / admin123
echo.
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe app.py
) else if exist "..\ELEVATOR-APP\.venv\Scripts\python.exe" (
    ..\ELEVATOR-APP\.venv\Scripts\python.exe -c "from app import app; app.run(debug=True, port=5001)"
) else (
    python -c "from app import app; app.run(debug=True, port=5001)"
)
