# إنشاء اختصار سطح مكتب لأي شركة — نافذة واحدة بدون تبويبات
param(
    [string]$CompanyName,
    [string]$Url,
    [string]$IconPath,
    [switch]$Launch,
    [switch]$Interactive,
    [switch]$Menu
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath('Desktop')
$ConfigPath = Join-Path $PSScriptRoot 'companies.json'

function Get-Browser {
    $paths = @(
        "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
        "${env:LocalAppData}\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Resolve-Icon([string]$CustomIcon) {
    if ($CustomIcon -and (Test-Path $CustomIcon)) { return $CustomIcon }
    $candidates = @(
        (Join-Path $env:USERPROFILE 'Downloads\Liftcore-icon.ico'),
        (Join-Path $Root 'static\images\liftcore.ico')
    )
    return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function New-CompanyShortcut {
    param(
        [string]$Name,
        [string]$LoginUrl,
        [string]$Icon = '',
        [bool]$OpenNow = $true
    )

    if (-not $Name) { throw 'اسم الشركة مطلوب' }
    if (-not $LoginUrl) { throw 'رابط تسجيل الدخول مطلوب' }
    if ($LoginUrl -notmatch '^https?://') { $LoginUrl = "https://$LoginUrl" }
    if ($LoginUrl -notmatch '/login') {
        $LoginUrl = $LoginUrl.TrimEnd('/') + '/login'
    }

    $browser = Get-Browser
    if (-not $browser) {
        [System.Windows.Forms.MessageBox]::Show('لم يُعثر على Chrome أو Edge.', $Name, 0, 'Error') | Out-Null
        exit 1
    }

    $iconFile = Resolve-Icon $Icon
    $safeName = ($Name -replace '[\\/:*?"<>|]', '').Trim()
    $shortcutPath = Join-Path $Desktop "$safeName.lnk"

    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($shortcutPath)
    $sc.TargetPath = $browser
    $sc.Arguments = "--app=$LoginUrl --start-maximized"
    $sc.WorkingDirectory = $Root
    $sc.WindowStyle = 1
    $sc.Description = "$safeName — LiftCore"
    if ($iconFile) { $sc.IconLocation = "$iconFile,0" }
    $sc.Save()

    if ($OpenNow) {
        Start-Process $browser -ArgumentList "--app=$LoginUrl", '--start-maximized'
    }

  [System.Windows.Forms.MessageBox]::Show(
        @"
تم إنشاء أيقونة «$safeName» على سطح المكتب.

الرابط: $LoginUrl

• نافذة واحدة بدون تبويبات
• بحجم الشاشة
• للأيقونة في شريط المهام:
  كليك يمين على $safeName → تثبيت على شريط المهام
"@,
        "$safeName — تم",
        0,
        'Information'
    ) | Out-Null
}

function Read-CompaniesConfig {
    if (-not (Test-Path $ConfigPath)) { return @() }
    $raw = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    return @($raw.companies)
}

function Show-CompanyMenu {
    $list = Read-CompaniesConfig
    if (-not $list -or $list.Count -eq 0) {
        Write-Host 'لا توجد شركات في desktop\companies.json'
        return
    }
    Write-Host ''
    Write-Host '=== اختر الشركة ===' -ForegroundColor Cyan
    for ($i = 0; $i -lt $list.Count; $i++) {
        Write-Host "  $($i + 1)) $($list[$i].name) — $($list[$i].url)"
    }
    Write-Host "  0) شركة جديدة (إدخال يدوي)"
    Write-Host ''
    $pick = Read-Host 'رقم الشركة'
    if ($pick -eq '0') {
        $n = Read-Host 'اسم الشركة (مثال: شركة النور)'
        $u = Read-Host 'رابط الموقع (مثال: demo.liftcoreapp.com)'
        New-CompanyShortcut -Name $n -LoginUrl $u -OpenNow:(-not $Launch.IsPresent)
        return
    }
    $idx = [int]$pick - 1
    if ($idx -lt 0 -or $idx -ge $list.Count) {
        Write-Host 'اختيار غير صحيح' -ForegroundColor Red
        exit 1
    }
    $c = $list[$idx]
    New-CompanyShortcut -Name $c.name -LoginUrl $c.url -Icon $c.icon -OpenNow:(-not $Launch.IsPresent)
}

function Show-InteractiveForm {
    $n = Read-Host 'اسم الشركة (مثال: JAMA أو شركة النور)'
    $u = Read-Host 'رابط تسجيل الدخول (مثال: jama.liftcoreapp.com)'
    $i = Read-Host 'مسار الأيقونة .ico (اختياري — Enter للافتراضي)'
    New-CompanyShortcut -Name $n -LoginUrl $u -Icon $i -OpenNow:(-not $Launch.IsPresent)
}

if ($Menu) {
    Show-CompanyMenu
    exit 0
}

if ($Interactive) {
    Show-InteractiveForm
    exit 0
}

if ($CompanyName -and $Url) {
    New-CompanyShortcut -Name $CompanyName -LoginUrl $Url -Icon $IconPath -OpenNow:(-not $Launch.IsPresent)
    exit 0
}

Show-CompanyMenu
