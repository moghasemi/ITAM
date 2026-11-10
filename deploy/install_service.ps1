# ==========================================================================
#  نصب سامانه ITAM به‌صورت سرویس خودکار روی ویندوز
#  روش: زمان‌بند ویندوز (Task Scheduler) — بدون نیاز به نرم‌افزار جانبی
#
#  اجرا در PowerShell با دسترسی Administrator:
#      .\install_service.ps1
#      .\install_service.ps1 -ProjectPath "D:\itam"
# ==========================================================================
[CmdletBinding()]
param(
    [string]$ProjectPath = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PythonPath  = "",
    [string]$TaskUser    = "SYSTEM",
    [switch]$SkipServerTask,
    [switch]$SkipScheduledJobs
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

if (-not (Test-Path (Join-Path $ProjectPath ".env"))) {
    throw "فایل .env یافت نشد. ابتدا deploy\.env.example را به .env کپی و تنظیم کنید."
}

$envSettings = @{}
Get-Content (Join-Path $ProjectPath ".env") | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $pair = $line.Split("=", 2)
        $envSettings[$pair[0].Trim()] = $pair[1].Trim().Trim('"').Trim("'")
    }
}
$debugValue = $envSettings["ITAM_DEBUG"]
if ($debugValue -notin @("0", "false", "False", "no", "No")) {
    throw "نصب سرویس عملیاتی فقط با ITAM_DEBUG=0 مجاز است."
}
$dbEngine = [string]$envSettings["ITAM_DB_ENGINE"]
if ($dbEngine.ToLowerInvariant() -notin @("postgres", "postgresql")) {
    throw "نصب سرویس عملیاتی فقط با PostgreSQL مجاز است؛ SQLite صرفاً برای دموی محلی است."
}
$secret = $envSettings["ITAM_SECRET_KEY"]
if (-not $secret -or $secret.Length -lt 50 -or $secret -match "REPLACE|CHANGE_ME") {
    throw "ITAM_SECRET_KEY باید کلید تصادفی واقعی با حداقل ۵۰ نویسه باشد."
}
$allowedHosts = [string]$envSettings["ITAM_ALLOWED_HOSTS"]
$hostEntries = @($allowedHosts.Split(",") | ForEach-Object { $_.Trim() })
if ([string]::IsNullOrWhiteSpace($allowedHosts) -or $hostEntries -contains "*") {
    throw "ITAM_ALLOWED_HOSTS باید میزبان‌های واقعی و بدون wildcard داشته باشد."
}
if ($envSettings["ITAM_SECURE_COOKIES"] -notin @("1", "true", "True", "yes", "Yes")) {
    throw "ITAM_SECURE_COOKIES باید فعال باشد."
}
if ($envSettings["ITAM_USE_PROXY_SSL_HEADER"] -notin @("1", "true", "True", "yes", "Yes")) {
    throw "ITAM_USE_PROXY_SSL_HEADER باید برای Reverse Proxy فعال باشد."
}
if ($envSettings["ITAM_PUBLIC_BASE_URL"] -notmatch "^https://") {
    throw "ITAM_PUBLIC_BASE_URL باید نشانی HTTPS باشد."
}
foreach ($key in @("ITAM_DB_NAME", "ITAM_DB_USER", "ITAM_DB_PASSWORD", "ITAM_DB_HOST")) {
    if (-not $envSettings[$key]) { throw "مقدار $key در .env الزامی است." }
}

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

Write-Step "بررسی تنظیمات و آماده‌سازی فایل‌های ایستا"
Push-Location $ProjectPath
try {
    $env:PYTHONIOENCODING = "utf-8"
    & $PythonPath -c "import django, waitress"
    if ($LASTEXITCODE -ne 0) { throw "Django یا Waitress نصب نیست؛ requirements.txt را نصب کنید." }
    & $PythonPath manage.py check
    if ($LASTEXITCODE -ne 0) { throw "بررسی تنظیمات Django ناموفق بود." }
    & $PythonPath manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { throw "جمع‌آوری فایل‌های ایستا ناموفق بود." }
} finally {
    Pop-Location
}
Write-Ok "بررسی برنامه انجام شد؛ هیچ Migrationای اجرا نشد."
Write-Warn "Migration را جداگانه، پس از پشتیبان‌گیری و طبق راهنمای استقرار اجرا کنید."
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

Write-Host "پورت برنامه روی Loopback است؛ برای دسترسی شبکه، TLS Reverse Proxy را جداگانه پیکربندی کنید." -ForegroundColor Yellow

Write-Host "`n================= نصب کامل شد =================" -ForegroundColor Green
Write-Host "نشانی دسترسی از داخل شبکه اداره:"
Write-Host "    http://127.0.0.1:8000/  (فقط روی خود سرور)" -ForegroundColor White
Write-Host "`nبرای دسترسی کاربران شبکه، Reverse Proxy با HTTPS تنظیم کنید و نام میزبان را در ITAM_ALLOWED_HOSTS قرار دهید."

