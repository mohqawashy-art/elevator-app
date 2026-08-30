# Deploy client status field (clients.html + app.py)
$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$RemoteApp = "~/liftcore/elevator-app"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no")

$files = @(
    "templates/clients.html",
    "app.py"
)

Write-Host "=== LiftCore client status deploy ===" -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace '/', '\')
    if (-not (Test-Path $local)) { throw "Missing: $rel" }
    $remoteDir = Split-Path $rel -Parent
    if ($remoteDir -and $remoteDir -ne ".") {
        ssh @sshOpts $Remote "mkdir -p $RemoteApp/$($remoteDir -replace '\\','/')"
    }
    Write-Host "  -> $rel"
    scp @sshOpts $local "${Remote}:${RemoteApp}/$($rel -replace '\\','/')"
}

Write-Host "=== restart ===" -ForegroundColor Cyan
ssh @sshOpts $Remote "grep -q lc-client-status-v3 $RemoteApp/templates/clients.html && echo clients.html OK || echo WARN old file; sudo systemctl restart liftcore && sudo systemctl is-active liftcore"

Write-Host ""
Write-Host "Done. Hard refresh: https://app.liftcoreapp.com/clients" -ForegroundColor Green
