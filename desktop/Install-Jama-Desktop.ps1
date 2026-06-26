# Replace JAMA.url with a real desktop app shortcut (single window, taskbar icon)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

$Bat = Join-Path $Root 'run_jama_desktop.bat'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'JAMA.lnk'
$OldUrl = Join-Path $Desktop 'JAMA.url'

$IconCandidates = @(
    (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico'),
    (Join-Path $Root 'static\images\liftcore.ico')
)
$Icon = $IconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

$Py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path (Join-Path $Root 'static\images\liftcore.ico')) -and (Test-Path $Py)) {
    & $Py (Join-Path $Root 'scripts\build_desktop_icon.py') | Out-Null
}

if (Test-Path $OldUrl) {
    $Backup = Join-Path $Desktop 'JAMA.url.bak'
    if (-not (Test-Path $Backup)) {
        Move-Item -LiteralPath $OldUrl -Destination $Backup -Force
        Write-Host "Backed up old shortcut:" $Backup
    } else {
        Remove-Item -LiteralPath $OldUrl -Force -ErrorAction SilentlyContinue
    }
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Bat
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 7
$Sc.Description = 'JAMA - LiftCore (jama.liftcoreapp.com)'
if ($Icon) { $Sc.IconLocation = "$Icon,0" }
$Sc.Save()

Write-Host "JAMA desktop app shortcut:" $ShortcutPath -ForegroundColor Green
Write-Host "First-time setup: pip install -r requirements-desktop.txt"
