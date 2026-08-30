# إعداد سريع — أيقونة JAMA على سطح المكتب (نافذة واحدة بدون تبويبات)
# شغّل بالنقر المزدوج أو: powershell -ExecutionPolicy Bypass -File .\Setup-Jama-Quick.ps1
$ErrorActionPreference = 'Stop'
try { Add-Type -AssemblyName System.Windows.Forms } catch {}

$Url = 'https://jama.liftcoreapp.com/login'
$Desktop = [Environment]::GetFolderPath('Desktop')
if (-not $Desktop -or -not (Test-Path $Desktop)) {
    $Desktop = Join-Path $env:USERPROFILE 'Desktop'
    if (-not (Test-Path $Desktop)) {
        $Desktop = Join-Path $env:USERPROFILE 'OneDrive\Desktop'
    }
}
$ShortcutPath = Join-Path $Desktop 'JAMA.lnk'
$Root = Split-Path -Parent $PSScriptRoot

$Browsers = @(
    @{ Name = 'Chrome'; Path = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe" },
    @{ Name = 'Chrome'; Path = "${env:LocalAppData}\Google\Chrome\Application\chrome.exe" },
    @{ Name = 'Edge';   Path = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe" },
    @{ Name = 'Edge';   Path = "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe" }
)
$Browser = $Browsers | Where-Object { Test-Path $_.Path } | Select-Object -First 1
if (-not $Browser) {
    $msg = 'لم يُعثر على Chrome أو Edge.'
    if ([System.Windows.Forms.MessageBox]) {
        [System.Windows.Forms.MessageBox]::Show($msg, 'JAMA', 0, 'Error') | Out-Null
    } else {
        Write-Host $msg -ForegroundColor Red
    }
    exit 1
}

$IconDir = Join-Path $env:LOCALAPPDATA 'LiftCore\icons'
New-Item -ItemType Directory -Force -Path $IconDir | Out-Null
$IconDest = Join-Path $IconDir 'liftcore.ico'
$Icons = @(
    (Join-Path $Root 'static\images\liftcore.ico'),
    (Join-Path $Desktop 'Share\LiftCore\liftcore.ico'),
    (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico'),
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop\Share\LiftCore\liftcore.ico')
)
$IconSrc = $Icons | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($IconSrc) {
    Copy-Item -LiteralPath $IconSrc -Destination $IconDest -Force
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Browser.Path
$Sc.Arguments = "--app=$Url --start-maximized"
$Sc.WorkingDirectory = $env:USERPROFILE
$Sc.WindowStyle = 1
$Sc.Description = 'JAMA — LiftCore'
if (Test-Path $IconDest) { $Sc.IconLocation = "$IconDest,0" }
$Sc.Save()

Start-Process $Browser.Path -ArgumentList "--app=$Url", '--start-maximized'

$done = @"
تم إنشاء أيقونة JAMA على سطح المكتب:
$ShortcutPath

• نافذة واحدة بدون تبويبات
• بحجم الشاشة
• لتثبيتها على شريط المهام: كليك يمين على JAMA → تثبيت على شريط المهام

ملاحظة: سطح المكتب عندك عبر OneDrive — إن لم تظهر الأيقونة فوراً حدّث المجلد (F5).
"@

if ([System.Windows.Forms.MessageBox]) {
    [System.Windows.Forms.MessageBox]::Show($done, 'JAMA — تم', 0, 'Information') | Out-Null
} else {
    Write-Host $done -ForegroundColor Green
}
