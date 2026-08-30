# Deploy parts billing Excel import to Jama
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_parts_billing.ps1
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_parts_billing.ps1 -DryRun

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$JamaApp = "~/liftcore/jama-elevator-app"
$Root = Split-Path $PSScriptRoot -Parent
$sshOpts = @("-o", "StrictHostKeyChecking=no")
$DataDir = "$JamaApp/deploy/data/jama_import"
$XlsxLocal = Join-Path $Root "deploy\data\jama_import\parts_billing_27_6_2026.xlsx"
$XlsxRemote = "$DataDir/parts_billing_27_6_2026.xlsx"

$files = @(
    "parts_billing_import.py",
    "scripts/import_parts_billing_xlsx.py",
    "deploy/import_jama_parts_billing.sh"
)

if (-not (Test-Path -LiteralPath $XlsxLocal)) {
    throw "Missing Excel: deploy\data\jama_import\parts_billing_27_6_2026.xlsx"
}

Write-Host "=== 1/3 Upload code + Excel ===" -ForegroundColor Cyan
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

ssh @sshOpts $Remote "mkdir -p $DataDir"
Write-Host "  -> deploy/data/jama_import/parts_billing_27_6_2026.xlsx"
scp @sshOpts $XlsxLocal "${Remote}:${XlsxRemote}"

$importArgs = if ($DryRun) { "--dry-run --sync" } else { "--sync" }
Write-Host ""
Write-Host "=== 2/3 Import on server ($importArgs) ===" -ForegroundColor Cyan
$remoteCmd = "cd $JamaApp && chmod +x deploy/import_jama_parts_billing.sh && XLSX=$XlsxRemote bash deploy/import_jama_parts_billing.sh $importArgs"
ssh @sshOpts $Remote $remoteCmd

if (-not $DryRun) {
    Write-Host ""
    Write-Host "=== Done ===" -ForegroundColor Green
    Write-Host "https://jama.liftcoreapp.com/parts-billing" -ForegroundColor Green
}
