# LiftCore — حزمة حالة العميل (نشط / غير نشط)
# Usage: powershell -ExecutionPolicy Bypass -File deploy\pack_client_status.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$OutZip = Join-Path $PSScriptRoot "liftcore-client-status.zip"

$files = @(
    "app.py",
    "templates/clients.html",
    "static/liftcore-translations.js",
    "static/customer_profile.js",
    "deploy/set_clients_active.py"
)

if (Test-Path $OutZip) { Remove-Item -Force $OutZip }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($OutZip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($rel in $files) {
        $local = Join-Path $Root ($rel -replace '/', '\')
        if (-not (Test-Path $local)) { throw "Missing: $rel" }
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $Zip, $local, ($rel -replace '\\', '/'), [System.IO.Compression.CompressionLevel]::Optimal
        )
        Write-Host "  + $rel"
    }
} finally { $zip.Dispose() }

$kb = [math]::Round((Get-Item $OutZip).Length / 1KB, 1)
Write-Host ""
Write-Host "=== client-status ZIP ready ===" -ForegroundColor Green
Write-Host "File: $OutZip ($kb KB)"
Write-Host ""
Write-Host "On server:" -ForegroundColor Cyan
Write-Host '  unzip -o ~/liftcore-client-status.zip -d ~/liftcore/elevator-app'
Write-Host '  python3 ~/liftcore/elevator-app/deploy/set_clients_active.py'
Write-Host '  sudo systemctl restart liftcore'
