# رفع إصلاح بحث الخريطة إلى جما مباشرة
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_map_fix.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$JamaApp = "~/liftcore/jama-elevator-app"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no")

$files = @(
    "static/client_map_picker.js",
    "static/liftcore_map.js",
    "static/client_location.css",
    "templates/clients.html",
    "templates/contracts.html",
    "templates/elevators.html",
    "templates/partials/google_maps_head.html"
)

Write-Host "=== Jama map search fix ===" -ForegroundColor Cyan
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
Write-Host "Done. Hard refresh: https://jama.liftcoreapp.com/clients" -ForegroundColor Green
Write-Host "Expect: blue [بحث] button (NOT موقعي) and client_map_picker.js?v=7" -ForegroundColor Green
