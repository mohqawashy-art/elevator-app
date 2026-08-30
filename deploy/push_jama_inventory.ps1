# رفع جدول الأصناف + استيراده في مخزون جما
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_inventory.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$JamaApp = "~/liftcore/jama-elevator-app"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=30")

$files = @(
    "import_inventory_csv.py",
    "deploy/import_jama_inventory.sh",
    "deploy/data/jama_import/inventory_items_25_6_2026.xlsx"
)

Write-Host "=== Jama inventory import ===" -ForegroundColor Cyan
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

Write-Host "Running import on server..." -ForegroundColor Cyan
ssh @sshOpts $Remote "cd $JamaApp && chmod +x deploy/import_jama_inventory.sh && bash deploy/import_jama_inventory.sh"

Write-Host ""
Write-Host "Done: https://jama.liftcoreapp.com/inventory" -ForegroundColor Green
