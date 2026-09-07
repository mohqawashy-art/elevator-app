# Clone local test folder — separate from elevator-app (prod) and jama
# powershell -ExecutionPolicy Bypass -File deploy\clone_test_local.ps1

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/mohqawashy-art/elevator-app.git"
$Branch = "staging/department-hubs"

$LiftCoreRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$TestDir = Join-Path $LiftCoreRoot "test-elevator-app"

Write-Host "=== LiftCore test (isolated clone) ===" -ForegroundColor Cyan
Write-Host "Folder: $TestDir" -ForegroundColor Gray
Write-Host "Branch: $Branch" -ForegroundColor Gray
Write-Host ""

if (Test-Path (Join-Path $TestDir ".git")) {
    Write-Host "==> Updating existing clone" -ForegroundColor Yellow
    Push-Location $TestDir
    git fetch origin $Branch -q
    git checkout $Branch 2>$null
    if ($LASTEXITCODE -ne 0) { git checkout -b $Branch "origin/$Branch" }
    git pull --ff-only "origin/$Branch"
    Pop-Location
} else {
    if (Test-Path $TestDir) {
        Write-Host "ERROR: $TestDir exists but is not a git repo" -ForegroundColor Red
        exit 1
    }
    Write-Host "==> Fresh clone" -ForegroundColor Yellow
    git clone --branch $Branch --single-branch $RepoUrl $TestDir
}

Push-Location $TestDir
$rev = git rev-parse --short HEAD
Pop-Location

Write-Host ""
Write-Host "Ready @ $rev" -ForegroundColor Green
Write-Host "  cd $TestDir" -ForegroundColor Green
Write-Host "  Open this folder in Cursor for test-only work" -ForegroundColor Gray
Write-Host ""
Write-Host "Deploy to test.liftcoreapp.com:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File deploy\push_test_staging.ps1" -ForegroundColor Gray
