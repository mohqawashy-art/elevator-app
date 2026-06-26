# JAMA — اختصار سطح المكتب (نافذة متصفح واحدة بدون تبويبات)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Url = 'https://jama.liftcoreapp.com/login'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'JAMA.lnk'

$Browsers = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:LocalAppData}\Google\Chrome\Application\chrome.exe"
)
$Browser = $Browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Browser) {
    Write-Host 'Edge/Chrome not found — using run_jama_desktop.bat' -ForegroundColor Yellow
    $Browser = Join-Path $Root 'run_jama_desktop.bat'
    $Arguments = ''
} else {
    $Arguments = "--app=$Url --start-maximized"
}

$IconCandidates = @(
    (Join-Path $Root 'static\images\liftcore.ico'),
    'E:\04-تنزيلات\Liftcore-icon.ico',
    (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico')
)
$Icon = $IconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Browser
if ($Arguments) { $Sc.Arguments = $Arguments }
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = 'JAMA — LiftCore (نافذة واحدة)'
if ($Icon) { $Sc.IconLocation = "$Icon,0" }
$Sc.Save()

Write-Host "تم تحديث اختصار JAMA:" $ShortcutPath -ForegroundColor Green
Write-Host "يفتح نافذة Edge/Chrome منفصلة — بدون تبويبات — بحجم الشاشة"
