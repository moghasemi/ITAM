# Validate the trusted reverse-proxy addresses before an operational install.
function Assert-ItamTrustedProxyEntries {
    [CmdletBinding()]
    param([AllowNull()][string]$Value)

    $entries = @($Value -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($entries.Count -eq 0) {
        throw "ITAM_TRUSTED_PROXY_IPS must contain the exact reverse-proxy IP or CIDR."
    }

    foreach ($entry in $entries) {
        if ($entry -match "REPLACE|CHANGE_ME|\*") {
            throw "ITAM_TRUSTED_PROXY_IPS contains a placeholder or wildcard."
        }

        $parts = $entry.Split("/")
        if ($parts.Count -gt 2) {
            throw "Invalid trusted proxy entry: $entry"
        }

        try {
            $address = [System.Net.IPAddress]::Parse($parts[0])
        }
        catch {
            throw "Invalid IP address in ITAM_TRUSTED_PROXY_IPS: $entry"
        }

        if ($address.Equals([System.Net.IPAddress]::Any) -or $address.Equals([System.Net.IPAddress]::IPv6Any)) {
            throw "Unspecified IP addresses cannot be trusted proxies: $entry"
        }

        if ($parts.Count -eq 2) {
            $prefix = 0
            if (-not [int]::TryParse($parts[1], [ref]$prefix)) {
                throw "Invalid CIDR prefix in ITAM_TRUSTED_PROXY_IPS: $entry"
            }

            $isIpv4 = $address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
            $maxPrefix = if ($isIpv4) { 32 } else { 128 }
            $minimumPrefix = if ($isIpv4) { 16 } else { 48 }
            if ($prefix -lt $minimumPrefix -or $prefix -gt $maxPrefix) {
                throw "Trusted proxy CIDR is too broad or invalid: $entry"
            }
        }
    }

    return $true
}
