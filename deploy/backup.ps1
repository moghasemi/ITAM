# ==========================================================================
# Secure backup for ITAM (SQLite or PostgreSQL) plus media and .env.
# PostgreSQL requires pg_dump on PATH. Never store backup sets on the same disk only.
# ==========================================================================
[CmdletBinding()]
param(
    [string]$ProjectPath = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PythonPath = "",
    [string]$BackupRoot = "",
    [int]$KeepDays = 30
)

$ErrorActionPreference = "Stop"
if (-not $BackupRoot) { $BackupRoot = Join-Path $ProjectPath "backups" }
$envFile = Join-Path $ProjectPath ".env"
if (-not (Test-Path $envFile)) { throw "Project .env not found; backup configuration cannot be verified." }

# Read only the DB values needed by this backup script. Django settings use the same file.
$settings = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $pair = $line.Split("=", 2)
        $key = $pair[0].Trim()
        $value = $pair[1].Trim().Trim('"').Trim("'")
        if ($key) { $settings[$key] = $value }
    }
}
$engine = if ($settings.ContainsKey("ITAM_DB_ENGINE")) { $settings["ITAM_DB_ENGINE"].ToLowerInvariant() } else { "sqlite" }
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$target = Join-Path $BackupRoot "itam-$stamp"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Write-Host "[ITAM] Backup destination: $target"

if ($engine -in @("postgres", "postgresql")) {
    $pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
    if (-not $pgDump) { throw "pg_dump is required for PostgreSQL backups but was not found on PATH." }
    foreach ($key in @("ITAM_DB_NAME", "ITAM_DB_USER", "ITAM_DB_PASSWORD", "ITAM_DB_HOST")) {
        if (-not $settings[$key]) { throw "Missing $key in .env; PostgreSQL backup aborted." }
    }
    $env:PGPASSWORD = $settings["ITAM_DB_PASSWORD"]
    try {
        $dumpPath = Join-Path $target "itam-postgresql.dump"
        $pgArgs = @(
            "--host=$($settings['ITAM_DB_HOST'])",
            "--port=$(if ($settings['ITAM_DB_PORT']) { $settings['ITAM_DB_PORT'] } else { '5432' })",
            "--username=$($settings['ITAM_DB_USER'])",
            "--format=custom",
            "--no-owner",
            "--file=$dumpPath",
            $settings["ITAM_DB_NAME"]
        )
        & $pgDump.Source @pgArgs
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dumpPath)) {
            throw "pg_dump failed; PostgreSQL backup is incomplete."
        }
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
    Write-Host "[ITAM] PostgreSQL database backed up."
}
elseif ($engine -eq "sqlite") {
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
    if (-not $PythonPath) { throw "Python interpreter not found; SQLite backup aborted." }
    $dbPath = if ($settings["ITAM_DB_PATH"]) { $settings["ITAM_DB_PATH"] } else { "db.sqlite3" }
    if (-not [System.IO.Path]::IsPathRooted($dbPath)) { $dbPath = Join-Path $ProjectPath $dbPath }
    if (-not (Test-Path $dbPath)) { throw "SQLite database not found at $dbPath; backup aborted." }
    $backupDb = Join-Path $target "db.sqlite3"
    $scriptText = @"
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
try:
    with target:
        source.backup(target)
finally:
    target.close()
    source.close()
"@
    $tempScript = Join-Path $env:TEMP "itam_backup_$stamp.py"
    Set-Content -Path $tempScript -Value $scriptText -Encoding UTF8
    try {
        & $PythonPath $tempScript $dbPath $backupDb
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $backupDb)) {
            throw "SQLite Backup API failed; backup is incomplete."
        }
    } finally {
        Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[ITAM] SQLite database backed up."
}
else {
    throw "Unsupported ITAM_DB_ENGINE '$engine'; refusing to create a misleading partial backup."
}

$mediaDir = Join-Path $ProjectPath "media"
if (Test-Path $mediaDir) {
    $mediaTarget = Join-Path $target "media"
    New-Item -ItemType Directory -Force -Path $mediaTarget | Out-Null
    robocopy $mediaDir $mediaTarget /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Media backup failed (robocopy exit code $LASTEXITCODE)." }
    Write-Host "[ITAM] Media files backed up."
}

# Preserve the exact configuration needed for recovery; protect the backup directory.
Copy-Item $envFile (Join-Path $target ".env") -Force
foreach ($extra in @("secret_key.txt")) {
    $path = Join-Path $ProjectPath $extra
    if (Test-Path $path) { Copy-Item $path $target -Force }
}

$limit = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -Path $BackupRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $limit -and $_.Name -like "itam-*" } |
    ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Host "[ITAM] Expired backup removed: $($_.Name)"
    }

Write-Host "[ITAM] Backup completed successfully."
