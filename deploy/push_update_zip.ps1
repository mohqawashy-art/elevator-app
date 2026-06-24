# LiftCore — تجميع zip + رفع + تطبيق على السيرفر
# الاستخدام: powershell -ExecutionPolicy Bypass -File deploy\push_update_zip.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$RemoteZip = "~/liftcore-update.zip"
$RemoteApp = "~/liftcore/elevator-app"
$DeployDir = $PSScriptRoot
$Root = Split-Path $DeployDir -Parent
$ZipLocal = Join-Path $DeployDir "liftcore-update.zip"
$sshOpts = @("-o", "StrictHostKeyChecking=no")

Write-Host "=== 1/4 Pack update ZIP ===" -ForegroundColor Cyan
& (Join-Path $DeployDir "pack_update.ps1")

Write-Host ""
Write-Host "=== 2/4 Upload ZIP ===" -ForegroundColor Cyan
scp @sshOpts $ZipLocal "${Remote}:${RemoteZip}"

Write-Host ""
Write-Host "=== 3/4 Apply on server ===" -ForegroundColor Cyan
ssh @sshOpts $Remote "bash $RemoteApp/deploy/apply_update_zip.sh $RemoteZip"

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Test: https://app.liftcoreapp.com/faults"
