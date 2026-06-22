# رفع إصلاحات العقود + نوع باب المصعد
# powershell -ExecutionPolicy Bypass -File deploy\push_contracts_fix.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no")

$files = @(
    "app.py",
    "models.py",
    "live_sync.py",
    "customer_billing.py",
    "templates/contracts.html",
    "templates/elevators.html"
)

$targets = @(
    @{ Name = "liftcore"; Path = "~/liftcore/elevator-app" },
    @{ Name = "liftcore-jama"; Path = "~/liftcore/jama-elevator-app" }
)

Write-Host "=== LiftCore contracts + door type deploy ===" -ForegroundColor Cyan
foreach ($target in $targets) {
    Write-Host ""
    Write-Host "Target: $($target.Name) -> $($target.Path)" -ForegroundColor Yellow
    foreach ($rel in $files) {
        $local = Join-Path $Root ($rel -replace '/', '\')
        if (-not (Test-Path $local)) { throw "Missing: $rel" }
        $remoteDir = Split-Path $rel -Parent
        if ($remoteDir -and $remoteDir -ne ".") {
            ssh @sshOpts $Remote "mkdir -p $($target.Path)/$($remoteDir -replace '\\','/')"
        }
        Write-Host "  -> $rel"
        scp @sshOpts $local "${Remote}:$($target.Path)/$($rel -replace '\\','/')"
    }
    Write-Host "Restarting $($target.Name)..." -ForegroundColor Cyan
    ssh @sshOpts $Remote "sudo systemctl restart $($target.Name) && sudo systemctl is-active $($target.Name)"
}

Write-Host ""
Write-Host "Done. Hard refresh: Ctrl+Shift+R" -ForegroundColor Green
Write-Host "  https://app.liftcoreapp.com/contracts" -ForegroundColor Green
Write-Host "  https://jama.liftcoreapp.com/contracts" -ForegroundColor Green
