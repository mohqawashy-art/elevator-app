# Upload Excel + import clients/technicians/elevators to Jama
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_core_import.ps1 `
#   -Clients "C:\...\Downloads\clients.xlsx" -Technicians "..." -Elevators "..."

param(
    [string]$Clients,
    [string]$Technicians,
    [string]$Elevators
)

$ErrorActionPreference = "Stop"
$Remote = "info@2.29.6.41"
$JamaApp = "~/liftcore/jama-elevator-app"
$DataDir = "$JamaApp/deploy/data/jama_import"
$sshOpts = @("-o", "StrictHostKeyChecking=no")
$Root = Split-Path $PSScriptRoot -Parent
$Downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"

$all = @(Get-ChildItem -LiteralPath $Downloads -Filter "*24_6_2026.xlsx" -ErrorAction SilentlyContinue) |
    Sort-Object Length

if ($all.Count -ge 3 -and -not $PSBoundParameters.ContainsKey('Clients')) {
    $Technicians = $all[0].FullName
    $Clients = $all[1].FullName
    $Elevators = $all[2].FullName
}

$files = @(
    @{ Local = $Clients; Remote = "clients_24_6_2026.xlsx" },
    @{ Local = $Technicians; Remote = "technicians_24_6_2026.xlsx" },
    @{ Local = $Elevators; Remote = "elevators_24_6_2026.xlsx" }
)

Write-Host "=== Jama import: clients + technicians + elevators ===" -ForegroundColor Cyan

foreach ($f in $files) {
    if (-not $f.Local -or -not (Test-Path -LiteralPath $f.Local)) {
        throw "File not found: $($f.Local)"
    }
    Write-Host "  -> $($f.Remote)  ($($f.Local))" -ForegroundColor Gray
}

ssh @sshOpts $Remote "mkdir -p $DataDir"
foreach ($f in $files) {
    scp @sshOpts "$($f.Local)" "${Remote}:${DataDir}/$($f.Remote)"
}

scp @sshOpts "$Root\scripts\import_jama_core_three.py" "${Remote}:${JamaApp}/scripts/import_jama_core_three.py"
scp @sshOpts "$Root\deploy\import_jama_core_three.sh" "${Remote}:${JamaApp}/deploy/import_jama_core_three.sh"

$remoteCmd = @"
cd $JamaApp
git fetch origin main -q && git reset --hard origin/main
chmod +x deploy/import_jama_core_three.sh
export CLIENTS_XLSX='$DataDir/clients_24_6_2026.xlsx'
export TECHS_XLSX='$DataDir/technicians_24_6_2026.xlsx'
export ELEVATORS_XLSX='$DataDir/elevators_24_6_2026.xlsx'
bash deploy/import_jama_core_three.sh --dry-run
echo '---'
bash deploy/import_jama_core_three.sh
"@

ssh @sshOpts $Remote $remoteCmd

Write-Host ""
Write-Host "Done: https://jama.liftcoreapp.com/clients" -ForegroundColor Green
