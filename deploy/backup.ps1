# ==========================================================================
#  پشتیبان‌گیری از سامانه ITAM
#  - پایگاه داده با روش امن SQLite Backup API (سازگار با حالت WAL)
#  - پوشه رسانه‌ها (عکس‌ها و پیوست‌ها)
#  - حذف پشتیبان‌های قدیمی‌تر از حد تعیین‌شده
#
#  اجرای دستی:
#      .\backup.ps1
#  اجرای زمان‌بندی‌شده: توسط install_service.ps1 به‌صورت روزانه ثبت می‌شود.
# ==========================================================================
[CmdletBinding()]
param(
    [string]$ProjectPath = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PythonPath  = "",
    [string]$BackupRoot  = "",
    [int]   $KeepDays    = 30
)

$ErrorActionPreference = "Stop"

if (-not $PythonPath) {
    $candidates = @(
        (Join-Path $ProjectPath ".venv\Scripts\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    )
    $PythonPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $PythonPath) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($command) { $PythonPath = $command.Source }
    }
}
if (-not $PythonPath) { throw "مفسر پایتون یافت نشد." }
if (-not $BackupRoot) { $BackupRoot = Join-Path $ProjectPath "backups" }

# تاریخ شمسی برای نام‌گذاری
$now      = Get-Date
$stamp    = "{0:yyyy-MM-dd_HH-mm}" -f $now
$target   = Join-Path $BackupRoot "itam-$stamp"
New-Item -ItemType Directory -Force -Path $target | Out-Null

$dbFile   = Join-Path $ProjectPath "db.sqlite3"
$mediaDir = Join-Path $ProjectPath "media"

Write-Host "[ITAM] پشتیبان‌گیری در: $target"

if (Test-Path $dbFile) {
    $backupDb = Join-Path $target "db.sqlite3"
    $script = @"
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
target.close()
source.close()
"@
    $tempScript = Join-Path $env:TEMP "itam_backup_$stamp.py"
    Set-Content -Path $tempScript -Value $script -Encoding UTF8
    & $PythonPath $tempScript $dbFile $backupDb
    Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
    Write-Host "[ITAM] پایگاه داده پشتیبان‌گیری شد."
} else {
    Write-Warning "فایل پایگاه داده یافت نشد: $dbFile"
}

if (Test-Path $mediaDir) {
    $mediaTarget = Join-Path $target "media"
    New-Item -ItemType Directory -Force -Path $mediaTarget | Out-Null
    robocopy $mediaDir $mediaTarget /E /NFL /NDL /NJH /NJS /NP | Out-Null
    Write-Host "[ITAM] پوشه رسانه‌ها پشتیبان‌گیری شد."
}

# فایل تنظیمات و کلید امنیتی
foreach ($extra in @("secret_key.txt", ".env")) {
    $path = Join-Path $ProjectPath $extra
    if (Test-Path $path) { Copy-Item $path $target -Force }
}

# حذف پشتیبان‌های قدیمی
$limit = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -Path $BackupRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $limit -and $_.Name -like "itam-*" } |
    ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Host "[ITAM] پشتیبان قدیمی حذف شد: $($_.Name)"
    }

Write-Host "[ITAM] پشتیبان‌گیری با موفقیت پایان یافت."
