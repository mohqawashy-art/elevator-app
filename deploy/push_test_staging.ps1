# Deploy test branch only — does NOT touch production or jama
# powershell -ExecutionPolicy Bypass -File deploy\push_test_staging.ps1
# powershell -ExecutionPolicy Bypass -File deploy\push_test_staging.ps1 -SkipPush

param(
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$sshOpts = @("-o", "StrictHostKeyChecking=no")
$Branch = "staging/department-hubs"

$LiftCoreRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$TestDir = Join-Path $LiftCoreRoot "test-elevator-app"

if (-not (Test-Path (Join-Path $TestDir ".git"))) {
    Write-Host "Missing $TestDir — run: deploy\clone_test_local.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== Deploy test.liftcoreapp.com ===" -ForegroundColor Cyan
Write-Host "Test dir: $TestDir" -ForegroundColor Gray
Write-Host "Branch:   $Branch" -ForegroundColor Gray
Write-Host ""

if (-not $SkipPush) {
    Push-Location $TestDir
    $status = git status --porcelain
    if ($status) {
        Write-Host "Uncommitted changes in test-elevator-app:" -ForegroundColor Yellow
        git status -s
        Write-Host ""
        Write-Host "Commit and push to $Branch first, then re-run." -ForegroundColor Red
        Pop-Location
        exit 1
    }
    $local = git rev-parse HEAD
    git fetch origin $Branch -q
    $remote = git rev-parse "origin/$Branch"
    if ($local -ne $remote) {
        Write-Host "ERROR: local branch != origin/$Branch — push first" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "Git OK @ $($local.Substring(0,7))" -ForegroundColor Green
}

$provision = Join-Path $PSScriptRoot "staging\provision_test_clone.sh"
$deploy = Join-Path $PSScriptRoot "staging\deploy_staging.sh"
scp @sshOpts $provision "${Remote}:~/liftcore/elevator-app/deploy/staging/provision_test_clone.sh"
scp @sshOpts $deploy "${Remote}:~/liftcore/elevator-app/deploy/staging/deploy_staging.sh"

ssh @sshOpts $Remote @"
set -e
chmod +x ~/liftcore/elevator-app/deploy/staging/provision_test_clone.sh
chmod +x ~/liftcore/elevator-app/deploy/staging/deploy_staging.sh
bash ~/liftcore/elevator-app/deploy/staging/provision_test_clone.sh ~/liftcore/test-elevator-app
sudo bash ~/liftcore/test-elevator-app/deploy/staging/deploy_staging.sh
"@

Write-Host ""
Write-Host "Done. test: https://test.liftcoreapp.com" -ForegroundColor Green
Write-Host "(production and jama were not touched)" -ForegroundColor Gray
