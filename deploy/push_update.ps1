# LiftCore — رفع التحديثات فقط (بدون قاعدة البيانات)
# الاستخدام: powershell -ExecutionPolicy Bypass -File deploy\push_update.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$RemoteApp = "~/liftcore/elevator-app"
$Root = Split-Path $PSScriptRoot -Parent

$sshOpts = @("-o", "StrictHostKeyChecking=no")

$files = @(
    "app.py",
    "models.py",
    "operations.py",
    "fault_report.py",
    "customer_billing.py",
    "invoice_print.py",
    "zatca_qr.py",
    "zatca_invoice.py",
    "entity_links.py",
    "repair_links.py",
    "requirements.txt",
    "init_db.py",
    "seed_data.py",
    "reset_test_environment.py",
    "static/client_location.css",
    "static/client_map_picker.js",
    "static/fault-report.js",
    "static/ops-common.js",
    "static/liftcore-layout.css",
    "static/liftcore-shell.css",
    "static/liftcore-shell.js",
    "static/liftcore-table-hover.js",
    "static/liftcore-theme.css",
    "static/images/liftcore-header-logo.png",
    "static/name_translit.js",
    "templates/partials/app_header.html",
    "templates/partials/liftcore_head.html",
    "templates/settings.html",
    "templates/clients.html",
    "templates/technicians.html",
    "templates/elevators.html",
    "templates/dashboard.html",
    "templates/login.html",
    "templates/contracts.html",
    "templates/faults.html",
    "templates/inventory.html",
    "templates/invoices.html",
    "templates/invoice-print.html",
    "templates/expenses.html",
    "templates/revenues.html",
    "templates/reports.html",
    "templates/maintenance-visits.html",
    "templates/parts-billing.html",
    "templates/stock-movements.html",
    "templates/visit-report.html",
    "templates/fault-report.html",
    "templates/field.html",
    "templates/field-fault.html",
    "templates/report-annual.html",
    "templates/report-clients.html",
    "templates/report-contracts.html",
    "templates/report-dashboard.html",
    "templates/report-elevators.html",
    "templates/report-expenses.html",
    "templates/report-faults.html",
    "templates/report-inventory.html",
    "templates/report-invoices.html",
    "templates/report-maintenance.html",
    "templates/report-parts.html",
    "templates/report-revenues.html",
    "templates/report-stock.html",
    "templates/report-technicians.html"
)

Write-Host "=== LiftCore update deploy ===" -ForegroundColor Cyan
Write-Host "Local:  $Root"
Write-Host "Remote: $Remote`:$RemoteApp"
Write-Host ""

$missing = @()
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace '/', '\')
    if (-not (Test-Path $local)) {
        $missing += $rel
        continue
    }
    $remoteDir = Split-Path $rel -Parent
    if ($remoteDir -and $remoteDir -ne ".") {
        $remoteDir = ($remoteDir -replace '\\', '/')
        ssh @sshOpts $Remote "mkdir -p $RemoteApp/$remoteDir"
    }
    $remotePath = "$RemoteApp/$($rel -replace '\\', '/')"
    Write-Host "  -> $rel"
    scp @sshOpts $local "${Remote}:${remotePath}"
}

if ($missing.Count) {
    Write-Host ""
    Write-Host "Skipped (not found):" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  $_" }
}

Write-Host ""
Write-Host "Creating upload dirs on server..." -ForegroundColor Cyan
ssh @sshOpts $Remote "mkdir -p $RemoteApp/static/uploads/company $RemoteApp/static/uploads/users $RemoteApp/static/uploads/clients"

Write-Host "Installing Python deps (if needed)..." -ForegroundColor Cyan
ssh @sshOpts $Remote "cd $RemoteApp && if [ -f .venv/bin/pip ]; then .venv/bin/pip install -q -r requirements.txt; else pip3 install -q -r requirements.txt; fi"

Write-Host "Restarting liftcore..." -ForegroundColor Cyan
ssh @sshOpts $Remote "sudo systemctl restart liftcore && sudo systemctl is-active liftcore"

Write-Host ""
Write-Host "Done. Test: https://app.liftcoreapp.com/settings" -ForegroundColor Green
