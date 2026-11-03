# ==========================================================================
#  نصب سامانه ITAM به‌صورت سرویس خودکار روی ویندوز
#  روش: زمان‌بند ویندوز (Task Scheduler) — بدون نیاز به نرم‌افزار جانبی
#
#  اجرا در PowerShell با دسترسی Administrator:
#      .\install_service.ps1
#      .\install_service.ps1 -ProjectPath "D:\itam" -Port 8080
# ==========================================================================
[CmdletBinding()]
param(
    [string]$ProjectPath = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PythonPath  = "",
    [int]   $Port        = 8000,
    [string]$TaskUser    = "SYSTEM",
    [switch]$SkipServerTask,
    [switch]$SkipScheduledJobs,
    [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"

function Write-Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "  [OK] $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  [!]  $text" -ForegroundColor Yellow }

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "این اسکریپت باید با دسترسی Administrator اجرا شود."
}

Write-Step "بررسی محیط"
if (-not (Test-Path (Join-Path $ProjectPath "manage.py"))) {
    throw "پوشه پروژه معتبر نیست: $ProjectPath (فایل manage.py یافت نشد)"
}
Write-Ok "پوشه پروژه: $ProjectPath"

if (-not $PythonPath) {
    $candidates = @(
        (Join-Path $ProjectPath ".venv\Scripts\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        "C:\Python313\python.exe",
        "C:\Python312\python.exe"
    )
    $PythonPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $PythonPath) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $PythonPath = $command.Source }
}
if (-not $PythonPath) {
    throw "مفسر پایتون یافت نشد. با پارامتر -PythonPath مسیر python.exe را مشخص کنید."
}
Write-Ok "پایتون: $PythonPath"

# نسخه پایتون و وجود جنگو
$version = & $PythonPath -c "import sys; print(sys.version.split()[0])"
Write-Ok "نسخه پایتون: $version"
& $PythonPath -c "import django" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "جنگو نصب نیست. اجرا کنید:  `"$PythonPath`" -m pip install -r requirements.txt"
}

Write-Step "اعمال مهاجرت‌ها و جمع‌آوری فایل‌های ایستا"
Push-Location $ProjectPath
$env:PYTHONIOENCODING = "utf-8"
& $PythonPath manage.py migrate --noinput
& $PythonPath manage.py collectstatic --noinput | Out-Null
Pop-Location
Write-Ok "پایگاه داده آماده است"

if (-not $SkipServerTask) {
    Write-Step "ایجاد وظیفه اجرای سرور در زمان راه‌اندازی سیستم"
    $taskName = "ITAM-Server"
    schtasks /Delete /TN $taskName /F 2>$null | Out-Null
    $action  = "`"$ProjectPath\deploy\run_server.bat`""
    schtasks /Create /TN $taskName /TR $action /SC ONSTART /RU $TaskUser /RL HIGHEST /F | Out-Null
    Write-Ok "وظیفه $taskName ساخته شد (کاربر: $TaskUser)"

    Write-Host "  راه‌اندازی همین حالا..."
    schtasks /Run /TN $taskName | Out-Null
    Write-Ok "سرویس در حال راه‌اندازی است"
}

if (-not $SkipScheduledJobs) {
    Write-Step "ایجاد وظایف دوره‌ای (SLA، بازدیدها، ارسال رخدادها، پشتیبان‌گیری)"
    $jobs = @(
        @{ Name = "ITAM-Dispatch";  Args = "manage.py dispatch_outbox --limit 200"; Schedule = "/SC MINUTE /MO 5";  Desc = "ارسال رخدادها به سامانه مدیریت" },
        @{ Name = "ITAM-SLA";       Args = "manage.py check_sla_breaches";           Schedule = "/SC MINUTE /MO 30"; Desc = "بررسی نقض SLA" },
        @{ Name = "ITAM-Visits";    Args = "manage.py mark_missed_visits";           Schedule = "/SC DAILY /ST 07:00"; Desc = "بازدیدهای خارج از مهلت" },
        @{ Name = "ITAM-Backup";    Args = "-File `"$ProjectPath\deploy\backup.ps1`" -PythonPath `"$PythonPath`" -ProjectPath `"$ProjectPath`""; Schedule = "/SC DAILY /ST 23:30"; Desc = "پشتیبان‌گیری روزانه" }
    )
    foreach ($job in $jobs) {
        schtasks /Delete /TN $job.Name /F 2>$null | Out-Null
        if ($job.Args -like "-File*") {
            $command = "powershell.exe -NoProfile -ExecutionPolicy Bypass $($job.Args)"
        } else {
            $command = "cmd.exe /c cd /d `"$ProjectPath`" && `"$PythonPath`" $($job.Args)"
        }
        schtasks /Create /TN $job.Name /TR $command $job.Schedule /RU $TaskUser /RL HIGHEST /F | Out-Null
        Write-Ok "$($job.Name) — $($job.Desc)"
    }
}

if (-not $SkipFirewall) {
    Write-Step "بازکردن پورت در فایروال ویندوز"
    $ruleName = "ITAM Web ($Port)"
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    Write-Ok "قاعده فایروال برای پورت $Port ایجاد شد"
}

$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -ExpandProperty IPAddress

Write-Host "`n================= نصب کامل شد =================" -ForegroundColor Green
Write-Host "نشانی دسترسی از داخل شبکه اداره:"
Write-Host "    http://<IP-سرور>:$Port/" -ForegroundColor White
foreach ($ip in $addresses) { Write-Host "    http://${ip}:$Port/" -ForegroundColor White }
Write-Host "`nیادآوری: پس از تغییر IP سرور، مقدار «آدرس پایه سامانه» را در بخش تنظیمات به‌روزرسانی کنید"
Write-Host "تا QR برچسب تجهیزات درست ساخته شود.`n"
