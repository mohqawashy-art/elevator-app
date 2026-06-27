# رفع إصلاح تقرير الصحة المالية (تسعير لكل مصعد + عرض التكاليف) إلى جما
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_financial_health.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$JamaApp = "~/liftcore/jama-elevator-app"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no")

$files = @(
    "report_data.py",
    "templates/report-financial-health.html",
    "static/liftcore-theme.css"
)

Write-Host "=== Jama financial health fix ===" -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace '/', '\')
    if (-not (Test-Path $local)) { throw "Missing: $rel" }
    $remoteDir = Split-Path $rel -Parent
    if ($remoteDir -and $remoteDir -ne ".") {
        ssh @sshOpts $Remote "mkdir -p $JamaApp/$($remoteDir -replace '\\','/')"
    }
    Write-Host "  -> $rel"
    scp @sshOpts $local "${Remote}:${JamaApp}/$($rel -replace '\\','/')"
}

Write-Host "Restarting liftcore-jama..." -ForegroundColor Cyan
ssh @sshOpts $Remote "sudo systemctl restart liftcore-jama && sudo systemctl is-active liftcore-jama"

Write-Host ""
Write-Host "Done. Hard refresh (Ctrl+F5): https://jama.liftcoreapp.com/reports/financial-health" -ForegroundColor Green
Write-Host "Expect: تسعير صيانة المصاعد + السعر المقترح للمصعد" -ForegroundColor Green
