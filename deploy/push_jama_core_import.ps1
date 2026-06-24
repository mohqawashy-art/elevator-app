# رفع ملفات Excel + استيراد عملاء/فنيين/مصاعد على جما
# powershell -ExecutionPolicy Bypass -File deploy\push_jama_core_import.ps1

$ErrorActionPreference = "Stop"
$Remote = "info@34.18.56.21"
$JamaApp = "~/liftcore/jama-elevator-app"
$DataDir = "$JamaApp/deploy/data/jama_import"
$sshOpts = @("-o", "StrictHostKeyChecking=no")
$Root = Split-Path $PSScriptRoot -Parent
$Downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"

$files = @(
    @{ Local = "$Downloads\العملاء 24_6_2026.xlsx"; Remote = "العملاء 24_6_2026.xlsx" },
    @{ Local = "$Downloads\الفنيين 24_6_2026.xlsx"; Remote = "الفنيين 24_6_2026.xlsx" },
    @{ Local = "$Downloads\المصاعد 24_6_2026.xlsx"; Remote = "المصاعد 24_6_2026.xlsx" }
)

Write-Host "=== رفع واستيراد جما (عملاء + فنيين + مصاعد) ===" -ForegroundColor Cyan

foreach ($f in $files) {
    if (-not (Test-Path $f.Local)) {
        throw "ملف غير موجود: $($f.Local)"
    }
}

ssh @sshOpts $Remote "mkdir -p $DataDir"
foreach ($f in $files) {
    Write-Host "  -> $($f.Remote)" -ForegroundColor Gray
    scp @sshOpts $f.Local "${Remote}:${DataDir}/$($f.Remote)"
}

# رفع سكربتات الاستيراد
scp @sshOpts "$Root\scripts\import_jama_core_three.py" "${Remote}:${JamaApp}/scripts/import_jama_core_three.py"
scp @sshOpts "$Root\deploy\import_jama_core_three.sh" "${Remote}:${JamaApp}/deploy/import_jama_core_three.sh"

ssh @sshOpts $Remote @"
cd $JamaApp
git fetch origin main -q
git reset --hard origin/main 2>/dev/null || true
chmod +x deploy/import_jama_core_three.sh
bash deploy/import_jama_core_three.sh --dry-run
echo '---'
bash deploy/import_jama_core_three.sh
"@

Write-Host ""
Write-Host "Done. https://jama.liftcoreapp.com/clients" -ForegroundColor Green
