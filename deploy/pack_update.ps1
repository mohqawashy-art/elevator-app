# LiftCore — تجميع الملفات المحدّثة في zip واحد
# الاستخدام: powershell -ExecutionPolicy Bypass -File deploy\pack_update.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$OutZip = Join-Path $PSScriptRoot "liftcore-update.zip"

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
    "static/client_location.css",
    "static/client_map_picker.js",
    "static/fault-report.js",
    "static/ops-common.js",
    "static/liftcore-layout.css",
    "static/liftcore-format.js",
    "static/tax_calc.js",
    "static/liftcore-shell.css",
    "static/liftcore-shell.js",
    "static/liftcore-i18n.js",
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
    "templates/_tax_amount_block.html",
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
    "templates/report-technicians.html",
    "deploy/apply_update_zip.sh"
)

$staging = Join-Path $env:TEMP ("liftcore-pack-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $staging -Force | Out-Null

$added = 0
$missing = @()
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace '/', '\')
    if (-not (Test-Path $local)) {
        $missing += $rel
        continue
    }
    $dest = Join-Path $staging ($rel -replace '/', '\')
    $destDir = Split-Path $dest -Parent
    if ($destDir -and -not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $local -Destination $dest -Force
    $added++
}

if ($added -eq 0) {
    Remove-Item -Recurse -Force $staging
    throw "No files found to pack."
}

if (Test-Path $OutZip) { Remove-Item -Force $OutZip }

# ZipFile with Unix paths (/) - Compress-Archive uses backslash and breaks Linux unzip
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open(
    $OutZip,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    foreach ($rel in $files) {
        $local = Join-Path $Root ($rel -replace '/', '\')
        if (-not (Test-Path $local)) { continue }
        $entryName = ($rel -replace '\\', '/')
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip,
            $local,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        )
    }
} finally {
    $zip.Dispose()
}
Remove-Item -Recurse -Force $staging

$sizeMb = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
Write-Host ""
Write-Host "=== LiftCore update ZIP ready ===" -ForegroundColor Green
Write-Host "File:   $OutZip"
Write-Host "Size:   ${sizeMb} MB"
Write-Host "Files:  $added"
$check = [System.IO.Compression.ZipFile]::OpenRead($OutZip)
$hasBackslash = $false
foreach ($entry in $check.Entries) {
    if ($entry.FullName.Contains([char]92)) {
        $hasBackslash = $true
        break
    }
}
$check.Dispose()
if ($hasBackslash) {
    Write-Host "WARNING: ZIP has backslash paths - rebuild failed." -ForegroundColor Red
} else {
    Write-Host "Paths:  Unix-style (OK for Linux)" -ForegroundColor Green
}
if ($missing.Count) {
    Write-Host ""
    Write-Host "Skipped (missing):" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  $_" }
}
Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  1) Upload deploy\liftcore-update.zip to server /home/info/"
Write-Host "  2) ssh info@34.18.56.21"
Write-Host "  3) bash ~/liftcore/elevator-app/deploy/apply_update_zip.sh ~/liftcore-update.zip"
Write-Host ""
Write-Host "Or run: powershell -File deploy\push_update_zip.ps1" -ForegroundColor Cyan
