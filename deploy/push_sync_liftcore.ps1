# مزامنة LiftCore مع جما على السيرفر (git pull + restart)
# powershell -ExecutionPolicy Bypass -File deploy\push_sync_liftcore.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$sshOpts = @("-o", "StrictHostKeyChecking=no")
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "=== مزامنة LiftCore مع جما على السيرفر ===" -ForegroundColor Cyan
Write-Host "Remote: $Remote" -ForegroundColor Gray
Write-Host ""

# رفع سكربت المزامنة أولاً (قد لا يكون على السيرفر بعد)
$syncScript = Join-Path $PSScriptRoot "sync_liftcore_with_jama.sh"
scp @sshOpts $syncScript "${Remote}:~/liftcore/elevator-app/deploy/sync_liftcore_with_jama.sh"

ssh @sshOpts $Remote @"
chmod +x ~/liftcore/elevator-app/deploy/sync_liftcore_with_jama.sh
bash ~/liftcore/elevator-app/deploy/sync_liftcore_with_jama.sh ~/liftcore/elevator-app ~/liftcore/jama-elevator-app
"@

Write-Host ""
Write-Host "Done. Hard refresh: Ctrl+Shift+R" -ForegroundColor Green
Write-Host "  https://app.liftcoreapp.com" -ForegroundColor Green
Write-Host "  https://jama.liftcoreapp.com" -ForegroundColor Green
