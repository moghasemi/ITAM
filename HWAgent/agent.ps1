# ============================================================
#  Hardware Snapshot Agent - Local HTTP Server (ASCII-safe)
# ============================================================
$Port        = 8765
$SnapshotDir = "$env:USERPROFILE\HardwareSnapshots"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $SnapshotDir)) {
    New-Item -ItemType Directory -Path $SnapshotDir -Force | Out-Null
}

# ---------- Hash helpers ----------
function Get-Sha256($text) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
    $sha   = [System.Security.Cryptography.SHA256]::Create()
    $hash  = $sha.ComputeHash($bytes)
    return ($hash | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Get-MasterHash($snap) {
    $clone = [ordered]@{
        system = $snap.system; motherboard = $snap.motherboard
        cpu = $snap.cpu; bios = $snap.bios; ram = $snap.ram
        disks = $snap.disks; gpu = $snap.gpu; network = $snap.network; os = $snap.os
    }
    return Get-Sha256 ($clone | ConvertTo-Json -Depth 10 -Compress)
}

function Get-IdentityHash($snap) {
    $identity = [ordered]@{
        systemUUID    = $snap.system.uuid
        motherboardSN = $snap.motherboard.serial
        biosSN        = $snap.bios.serial
    }
    return Get-Sha256 ($identity | ConvertTo-Json -Compress)
}

function Get-ComponentHashes($snap) {
    $parts = [ordered]@{
        system      = $snap.system
        motherboard = $snap.motherboard
        cpu         = $snap.cpu
        bios        = $snap.bios
        ram         = $snap.ram
        disks       = $snap.disks
        gpu         = $snap.gpu
        network     = $snap.network
        os          = $snap.os
    }
    $result = [ordered]@{}
    foreach ($k in $parts.Keys) {
        $result[$k] = Get-Sha256 ($parts[$k] | ConvertTo-Json -Depth 10 -Compress)
    }
    return $result
}

# ---------- Collect hardware info ----------
function Get-HardwareSnapshot {
    $cs   = Get-CimInstance Win32_ComputerSystem
    $csp  = Get-CimInstance Win32_ComputerSystemProduct
    $mb   = Get-CimInstance Win32_BaseBoard
    $cpu  = Get-CimInstance Win32_Processor
    $bios = Get-CimInstance Win32_BIOS
    $osInfo = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue

    # Get-PhysicalDisk is unavailable on some Windows editions/storage providers.
    # Fall back to the broadly available Win32_DiskDrive WMI class.
    $physicalDisks = @()
    try {
        $physicalDisks = @(Get-PhysicalDisk -ErrorAction Stop)
    } catch {
        $physicalDisks = @(Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue)
    }
    if ($physicalDisks.Count -eq 0) {
        $physicalDisks = @(Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue)
    }

    $snap = [ordered]@{
        computerName = $env:COMPUTERNAME
        userName     = $env:USERNAME
        system = [ordered]@{
            manufacturer = "$($cs.Manufacturer)"
            model        = "$($cs.Model)"
            uuid         = "$($csp.UUID)"
        }
        motherboard = [ordered]@{
            manufacturer = "$($mb.Manufacturer)"
            product      = "$($mb.Product)"
            serial       = "$($mb.SerialNumber)"
        }
        cpu = [ordered]@{
            name    = "$($cpu.Name)".Trim()
            cores   = $cpu.NumberOfCores
            threads = $cpu.NumberOfLogicalProcessors
            speed   = $cpu.MaxClockSpeed
        }
        bios = [ordered]@{
            manufacturer = "$($bios.Manufacturer)"
            version      = "$($bios.SMBIOSBIOSVersion)"
            serial       = "$($bios.SerialNumber)"
        }
        os = if ($osInfo) { "$($osInfo.Caption)".Trim() } else { "" }
        ram = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
            [ordered]@{
                slot         = "$($_.DeviceLocator)"
                capacityGB   = [math]::Round($_.Capacity / 1GB, 0)
                speedMHz     = $_.Speed
                manufacturer = "$($_.Manufacturer)"
                partNumber   = "$($_.PartNumber)"
                serial       = "$($_.SerialNumber)"
            }
        })
        disks = @($physicalDisks | ForEach-Object {
            $diskName = if ($_.PSObject.Properties.Name -contains "FriendlyName" -and $_.FriendlyName) {
                "$($_.FriendlyName)"
            } elseif ($_.PSObject.Properties.Name -contains "Model") {
                "$($_.Model)"
            } else { "Unknown disk" }
            $mediaType = if ($_.PSObject.Properties.Name -contains "MediaType") {
                "$($_.MediaType)"
            } else { "Unknown" }
            [ordered]@{
                name      = $diskName.Trim()
                mediaType = $mediaType
                sizeGB    = [math]::Round($_.Size / 1GB, 0)
                serial    = "$($_.SerialNumber)".Trim()
            }
        })
        gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object {
            [ordered]@{
                name          = "$($_.Name)"
                driverVersion = "$($_.DriverVersion)"
            }
        })
        network = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
                    Where-Object Status -eq "Up" | ForEach-Object {
            [ordered]@{
                name = "$($_.Name)"
                mac  = "$($_.MacAddress)"
            }
        })
    }

    $snap.hashes = [ordered]@{
        master     = Get-MasterHash      $snap
        identity   = Get-IdentityHash    $snap
        components = Get-ComponentHashes $snap
    }

    return $snap
}

# ---------- Save / load ----------
function Save-Snapshot($snap) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $file  = Join-Path $SnapshotDir "snap_$($snap.computerName)_$stamp.json"
    $snap | Add-Member -NotePropertyName timestamp -NotePropertyValue ((Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Force
    $snap | ConvertTo-Json -Depth 15 | Out-File -FilePath $file -Encoding UTF8
    return $file
}

function Get-SnapshotFiles {
    Get-ChildItem $SnapshotDir -Filter "snap_*.json" |
        Sort-Object LastWriteTime -Descending
}

function Load-Snapshot($file) {
    Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json
}

# ---------- Compare ----------
function Compare-Snapshots($old, $new) {
    $result = [ordered]@{
        changed           = $false
        identityChanged   = ($old.hashes.identity -ne $new.hashes.identity)
        masterChanged     = ($old.hashes.master   -ne $new.hashes.master)
        changedComponents = @()
        details           = @()
    }

    foreach ($prop in $new.hashes.components.PSObject.Properties) {
        $name = $prop.Name
        $oldH = $old.hashes.components.$name
        $newH = $prop.Value
        if ($oldH -ne $newH) {
            $result.changedComponents += $name
            $result.changed = $true
        }
    }

    function Flatten($obj, $prefix) {
        $out = @{}
        if ($null -eq $obj) { return $out }
        if ($obj -is [System.Collections.IEnumerable] -and -not ($obj -is [string])) {
            $i = 0
            foreach ($item in $obj) {
                $sub = Flatten $item "$prefix[$i]"
                foreach ($k in $sub.Keys) { $out[$k] = $sub[$k] }
                $i++
            }
        } elseif ($obj -is [PSCustomObject]) {
            foreach ($p in $obj.PSObject.Properties) {
                $sub = Flatten $p.Value "$prefix.$($p.Name)"
                foreach ($k in $sub.Keys) { $out[$k] = $sub[$k] }
            }
        } else {
            $out[$prefix] = "$obj"
        }
        return $out
    }

    foreach ($comp in $result.changedComponents) {
        $oldFlat = Flatten $old.$comp $comp
        $newFlat = Flatten $new.$comp $comp
        $keys = ($oldFlat.Keys + $newFlat.Keys) | Sort-Object -Unique
        foreach ($k in $keys) {
            $ov = $oldFlat[$k]; $nv = $newFlat[$k]
            if ($ov -ne $nv) {
                $ovText = if ($null -eq $ov -or $ov -eq "") { "-" } else { "$ov" }
                $nvText = if ($null -eq $nv -or $nv -eq "") { "-" } else { "$nv" }
                $result.details += [ordered]@{
                    component = $comp
                    field     = $k
                    oldValue  = $ovText
                    newValue  = $nvText
                }
            }
        }
    }
    return $result
}

# ---------- HTTP server ----------
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try {
    $listener.Start()
} catch {
    Write-Host "Could not start HWAgent on http://localhost:$Port" -ForegroundColor Red
    Write-Host "The port may already be in use, or Windows denied the local HTTP listener." -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor DarkRed
    Write-Host "Close the older HWAgent window or check the URL reservation, then retry."
    exit 1
}
Write-Host "Agent running: http://localhost:$Port" -ForegroundColor Green
Write-Host "Snapshots dir: $SnapshotDir"
Write-Host "Press Ctrl+C to stop."

function Write-Json($res, $obj) {
    $json  = $obj | ConvertTo-Json -Depth 15 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $res.ContentType = "application/json; charset=utf-8"
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
}

try {
    while ($listener.IsListening) {
        $ctx  = $listener.GetContext()
        $req  = $ctx.Request
        $res  = $ctx.Response
        $path = $req.Url.AbsolutePath

        # The agent UI is served by this same localhost origin. Do not enable
        # wildcard CORS: it would let arbitrary websites read local hardware data.
        if ($req.HttpMethod -eq "OPTIONS") {
            $res.StatusCode = 405
            $res.Close()
            continue
        }

        # Reject browser requests initiated by an unrelated origin. The sync
        # endpoint is state-changing and must carry the exact local UI Origin.
        $origin = $req.Headers["Origin"]
        $allowedOrigins = @("http://localhost:$Port", "http://127.0.0.1:$Port")
        if ($origin -and $origin -notin $allowedOrigins) {
            $res.StatusCode = 403
            Write-Json $res @{ status = "error"; error = "مبدأ درخواست برای این ایجنت مجاز نیست." }
            $res.Close()
            continue
        }
        if ($path -eq "/api/sync-to-itam" -and (
            $req.HttpMethod -ne "POST" -or $origin -notin $allowedOrigins
        )) {
            $res.StatusCode = 403
            Write-Json $res @{ status = "error"; error = "ارسال فقط از رابط محلی HWAgent مجاز است." }
            $res.Close()
            continue
        }

        try {
            switch -Regex ($path) {

                "^/$" {
                    $htmlPath = Join-Path $ScriptDir "index.html"
                    if (Test-Path $htmlPath) {
                        $html  = Get-Content $htmlPath -Raw -Encoding UTF8
                        $bytes = [System.Text.Encoding]::UTF8.GetBytes($html)
                        $res.ContentType = "text/html; charset=utf-8"
                        $res.OutputStream.Write($bytes, 0, $bytes.Length)
                    } else {
                        $res.StatusCode = 404
                    }
                }

                "^/api/snapshot$" {
                    $snap = Get-HardwareSnapshot
                    $file = Save-Snapshot $snap
                    $snap | Add-Member -NotePropertyName savedTo -NotePropertyValue $file -Force
                    Write-Json $res $snap
                }

                "^/api/history$" {
                    $list = @(Get-SnapshotFiles | Select-Object -First 30 | ForEach-Object {
                        [ordered]@{
                            file = $_.Name
                            time = $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
                            size = $_.Length
                        }
                    })
                    Write-Json $res $list
                }

                "^/api/latest$" {
                    $files = @(Get-SnapshotFiles)
                    if ($files.Count -gt 0) {
                        $snap = Load-Snapshot $files[0].FullName
                        Write-Json $res $snap
                    } else {
                        Write-Json $res @{ error = "no snapshot found" }
                    }
                }

                "^/api/sync-to-itam$" {
                    $jsonBody = [System.IO.StreamReader]::new($req.InputStream).ReadToEnd()
                    $cfg = $jsonBody | ConvertFrom-Json
                    $files = @(Get-SnapshotFiles)
                    if ($files.Count -eq 0) {
                        $snap = Get-HardwareSnapshot
                        $file = Save-Snapshot $snap
                    } else {
                        $snap = Load-Snapshot $files[0].FullName
                    }
                    if ($cfg.assetTag) {
                        $snap | Add-Member -NotePropertyName asset_tag -NotePropertyValue "$($cfg.assetTag)" -Force
                    }

                    # خواندن تنظیمات ذخیره‌شده محلی در صورت عدم ارسال از UI
                    $cfgFile = Join-Path $ScriptDir "agent-config.json"
                    $localToken = ""
                    if (Test-Path $cfgFile) {
                        try {
                            $localJson = Get-Content $cfgFile -Raw -Encoding UTF8 | ConvertFrom-Json
                            $localToken = $localJson.agentToken
                        } catch {}
                    }

                    $token = if ($cfg.agentToken) { "$($cfg.agentToken)".Trim() } else { $localToken }
                    if (-not $token) {
                        $res.StatusCode = 401
                        Write-Json $res @{ status = "error"; error = "توکن اختصاصی ایجنت (Agent Token) الزامی است." }
                        break
                    }

                    $baseUrl = if ($cfg.itamUrl) { "$($cfg.itamUrl)".TrimEnd('/') } else { "http://localhost:8000" }
                    $targetUri = $null
                    if (-not [System.Uri]::TryCreate($baseUrl, [System.UriKind]::Absolute, [ref]$targetUri)) {
                        $res.StatusCode = 400
                        Write-Json $res @{ status = "error"; error = "نشانی سرور ITAM معتبر نیست." }
                        break
                    }
                    if ($targetUri.Scheme -ne "https" -and -not [System.Uri]::IsLoopback($targetUri)) {
                        $res.StatusCode = 400
                        Write-Json $res @{ status = "error"; error = "برای سرور راه‌دور استفاده از HTTPS الزامی است." }
                        break
                    }
                    if ($targetUri.UserInfo -or $targetUri.Query -or $targetUri.Fragment) {
                        $res.StatusCode = 400
                        Write-Json $res @{ status = "error"; error = "نشانی سرور نباید اطلاعات ورود، Query یا Fragment داشته باشد." }
                        break
                    }
                    $targetUrl = "$($targetUri.GetLeftPart([System.UriPartial]::Authority).TrimEnd('/'))$($targetUri.AbsolutePath.TrimEnd('/'))/api/v1/hardware/agent-sync/"
                    $payloadJson = $snap | ConvertTo-Json -Depth 15 -Compress

                    $utcTimestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
                    $nonce = [guid]::NewGuid().ToString()

                    $headers = @{
                        "Authorization"    = "Bearer $token"
                        "X-ITAM-Timestamp" = $utcTimestamp
                        "X-ITAM-Nonce"     = $nonce
                    }

                    try {
                        $resp = Invoke-RestMethod -Uri $targetUrl -Method Post -Body $payloadJson -Headers $headers -ContentType "application/json; charset=utf-8"
                        Write-Json $res $resp
                    } catch {
                        $code = 500
                        $serverMessage = $_.Exception.Message
                        if ($_.Exception.Response) {
                            $code = [int]$_.Exception.Response.StatusCode
                            try {
                                $responseStream = $_.Exception.Response.GetResponseStream()
                                if ($responseStream) {
                                    $reader = [System.IO.StreamReader]::new($responseStream)
                                    $responseText = $reader.ReadToEnd()
                                    $reader.Dispose()
                                    if ($responseText) {
                                        try {
                                            $errorPayload = $responseText | ConvertFrom-Json
                                            if ($errorPayload.error) { $serverMessage = "$($errorPayload.error)" }
                                        } catch {
                                            $serverMessage = $responseText
                                        }
                                    }
                                }
                            } catch {}
                        }
                        $res.StatusCode = $code
                        Write-Json $res @{ status = "error"; error = "ارسال به سرور ITAM ناموفق بود (HTTP $code): $serverMessage" }
                    }
                }
                "^/api/compare$" {
                    $files = @(Get-SnapshotFiles)
                    if ($files.Count -lt 2) {
                        Write-Json $res @{ error = "at least two snapshots are required" }
                    } else {
                        $new  = Load-Snapshot $files[0].FullName
                        $old  = Load-Snapshot $files[1].FullName
                        $diff = Compare-Snapshots $old $new
                        Write-Json $res @{
                            oldTime = $old.timestamp
                            newTime = $new.timestamp
                            result  = $diff
                        }
                    }
                }

                default { $res.StatusCode = 404 }
            }
        } catch {
            $res.StatusCode = 500
            Write-Json $res @{ error = "$($_.Exception.Message)" }
        }
        $res.Close()
    }
} finally {
    $listener.Stop()
}