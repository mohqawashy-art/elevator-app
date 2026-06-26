# تثبيت JAMA كتطبيق (أيقونة LiftCore في شريط المهام)
$ErrorActionPreference = 'Stop'
$Url = 'https://jama.liftcoreapp.com/login'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'JAMA.lnk'
$Root = Split-Path -Parent $PSScriptRoot

$IconCandidates = @(
    (Join-Path $Root 'static\images\liftcore.ico'),
    'E:\04-تنزيلات\Liftcore-icon.ico',
    (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico')
)
$Icon = $IconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

# ابحث عن تطبيق JAMA المثبّت مسبقاً من Edge (أفضل أيقونة في شريط المهام)
$PwaShortcut = @(
    Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\JAMA.lnk'
    Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\LiftCore\JAMA.lnk'
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $PwaShortcut) {
    $PwaShortcut = Get-ChildItem -Path (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs') -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'JAMA|LiftCore' } |
        Select-Object -First 1 -ExpandProperty FullName
}

$Edge = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$Wsh = New-Object -ComObject WScript.Shell

if ($PwaShortcut) {
    Copy-Item -LiteralPath $PwaShortcut -Destination $ShortcutPath -Force
    Write-Host "تم ربط اختصار سطح المكتب بتطبيق JAMA المثبت:" $ShortcutPath -ForegroundColor Green
    Write-Host "ثبّته على شريط المهام من هذا الاختصار للحصول على أيقونة LiftCore."
    exit 0
}

if (-not $Edge) {
    Write-Host 'Edge غير موجود.' -ForegroundColor Red
    exit 1
}

# فتح Edge لتثبيت التطبيق (مرة واحدة)
Write-Host ""
Write-Host "=== خطوة واحدة للأيقونة في شريط المهام ===" -ForegroundColor Yellow
Write-Host "1) سيفتح Edge على تسجيل الدخول"
Write-Host "2) من القائمة (...): تطبيقات -> تثبيت هذا الموقع كتطبيق"
Write-Host "3) الاسم: JAMA ثم تثبيت"
Write-Host "4) شغّل هذا السكربت مرة أخرى لتحديث اختصار سطح المكتب"
Write-Host ""

Start-Process $Edge -ArgumentList $Url

$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Edge
$Sc.Arguments = "--app=$Url --start-maximized"
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = 'JAMA — LiftCore'
if ($Icon) { $Sc.IconLocation = "$Icon,0" }
$Sc.Save()

Write-Host "اختصار مؤقت على سطح المكتب (أيقونة Edge في شريط المهام حتى التثبيت):" $ShortcutPath
