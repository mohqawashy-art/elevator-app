# LiftCore — تشغيل محلي (PowerShell)
# إذا ظهر خطأ ExecutionPolicy استخدم أحد:
#   run_local.cmd
#   start_local.bat
#   powershell -ExecutionPolicy Bypass -File .\run_local.ps1
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================"
Write-Host "  LiftCore — تشغيل محلي"
Write-Host "========================================"
Write-Host ""

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[1/4] انشاء بيئة افتراضية..."
    py -m venv .venv
}

Write-Host "[2/4] تثبيت المتطلبات..."
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

if (-not (Test-Path ".\.env")) {
    $secret = "SECRET_KEY=liftcore-local-dev-$([guid]::NewGuid())"
    [System.IO.File]::WriteAllText("$PSScriptRoot\.env", $secret + "`n")
    Write-Host "  تم انشاء .env بمفتاح تطوير محلي"
}

Write-Host "[3/4] فحص امني + اختبارات..."
& .\.venv\Scripts\python.exe scripts\security_audit.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe -m pytest tests\ -q --tb=line
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[4/4] تشغيل التطبيق..."
Write-Host "  http://127.0.0.1:5001"
Write-Host "  admin / admin123"
Write-Host "  Ctrl+C للايقاف"
Write-Host ""
& .\.venv\Scripts\python.exe -c "from app import app; app.run(debug=True, port=5001, use_reloader=False)"
