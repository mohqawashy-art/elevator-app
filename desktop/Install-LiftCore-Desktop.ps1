# Create LiftCore desktop shortcut (Windows)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

$Bat = Join-Path $Root 'run_desktop.bat'
$Icon = Join-Path $Root 'static\images\liftcore.ico'
$Py = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $Icon)) {
    if (Test-Path $Py) {
        & $Py (Join-Path $Root 'scripts\build_desktop_icon.py')
    }
}

$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'LiftCore.lnk'

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Bat
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 7
$Sc.Description = 'LiftCore Elevator Management'
if (Test-Path $Icon) { $Sc.IconLocation = "$Icon,0" }
$Sc.Save()

Write-Host "Shortcut created:" $ShortcutPath
Write-Host "First-time setup: pip install -r requirements-desktop.txt"
