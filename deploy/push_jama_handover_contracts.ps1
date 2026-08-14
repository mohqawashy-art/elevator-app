# رفع ملف عقود التسليم وكود الاستيراد على مستأجر جما
# من جهازك (إن نجح SSH). من GCP Console استخدم git pull + رفع الـ xlsx يدوياً.
#
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_handover_contracts.ps1 -DryRun
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_handover_contracts.ps1 -WipeFirst

param(
    [switch]$DryRun,
    [switch]$WipeFirst
)

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$sshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20")
$Root = Split-Path $PSScriptRoot -Parent
$App = "~/liftcore/elevator-app"
$DataDir = "$App/deploy/data/jama_import"
$LocalXlsx = Join-Path $Root "deploy\data\jama_import\jama_handover_contracts_1_11_2025.xlsx"
$RemoteXlsx = "$DataDir/jama_handover_contracts_1_11_2025.xlsx"

if (-not (Test-Path -LiteralPath $LocalXlsx)) {
    throw "File not found: $LocalXlsx"
}

Write-Host "=== Jama handover contracts import ===" -ForegroundColor Cyan
ssh @sshOpts $Remote "mkdir -p $DataDir"

scp @sshOpts $LocalXlsx "${Remote}:${RemoteXlsx}"
scp @sshOpts "$Root\scripts\import_jama_contracts.py" "${Remote}:${App}/scripts/import_jama_contracts.py"
scp @sshOpts "$Root\scripts\delete_jama_contracts.py" "${Remote}:${App}/scripts/delete_jama_contracts.py"
scp @sshOpts "$Root\deploy\import_jama_contracts_tenant.sh" "${Remote}:${App}/deploy/import_jama_contracts_tenant.sh"
scp @sshOpts "$Root\contract_codes.py" "${Remote}:${App}/contract_codes.py"
scp @sshOpts "$Root\import_real_data.py" "${Remote}:${App}/import_real_data.py"
scp @sshOpts "$Root\customer_billing.py" "${Remote}:${App}/customer_billing.py"
scp @sshOpts "$Root\app.py" "${Remote}:${App}/app.py"
scp @sshOpts "$Root\templates\contracts.html" "${Remote}:${App}/templates/contracts.html"

$remoteCmd = @"
set -euo pipefail
cd $App
set -a; source /etc/liftcore/platform.env; set +a
chmod +x deploy/import_jama_contracts_tenant.sh
$(if ($WipeFirst) { "python3 scripts/delete_jama_contracts.py --slug jama --all --yes" } else { "true" })
XLSX='$RemoteXlsx' bash deploy/import_jama_contracts_tenant.sh $(if ($DryRun) { "--dry-run" } else { "" })
"@

ssh @sshOpts $Remote $remoteCmd
Write-Host ""
Write-Host "Check: https://jama.liftcoreapp.com/contracts" -ForegroundColor Green
