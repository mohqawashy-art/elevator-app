# إعداد سريع — أيقونة JAMA + فتح نافذة واحدة بدون تبويبات
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$Url = 'https://jama.liftcoreapp.com/login'
$Desktop = [Environment]::GetFolderPath('Desktop')
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
    [System.Windows.Forms.MessageBox]::Show('لم يُعثر على Chrome أو Edge.', 'JAMA', 0, 'Error') | Out-Null
    exit 1
}

$Icons = @(
    (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico'),
    (Join-Path $Root 'static\images\liftcore.ico')
)
$Icon = $Icons | Where-Object { Test-Path $_ } | Select-Object -First 1

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Browser.Path
$Sc.Arguments = "--app=$Url --start-maximized"
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = 'JAMA — LiftCore'
if ($Icon) { $Sc.IconLocation = "$Icon,0" }
$Sc.Save()

Start-Process $Browser.Path -ArgumentList "--app=$Url", '--start-maximized'

[System.Windows.Forms.MessageBox]::Show(
    @"
تم إنشاء أيقونة JAMA على سطح المكتب.

• نافذة واحدة بدون تبويبات
• بحجم الشاشة
• للأيقونة في شريط المهام:
  كليك يمين على JAMA → تثبيت على شريط المهام
"@,
    'JAMA — تم',
    0,
    'Information'
) | Out-Null
