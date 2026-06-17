# LiftCore — إصلاح هيدر + شعار
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$OutZip = Join-Path $PSScriptRoot "liftcore-header-fix.zip"

$files = @(
    "app.py",
    "static/liftcore-shell.css",
    "static/liftcore-shell.js",
    "templates/partials/app_header.html",
    "templates/partials/liftcore_head.html",
    "templates/settings.html",
    "templates/clients.html"
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
    }
} finally { $zip.Dispose() }

Write-Host "=== header-fix ZIP: $OutZip ===" -ForegroundColor Green
Write-Host 'Server: unzip -o ~/liftcore-header-fix.zip -d ~/liftcore/jama-elevator-app && sudo systemctl restart liftcore-jama'
