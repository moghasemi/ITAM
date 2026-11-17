. (Join-Path $PSScriptRoot "..\proxy_validation.ps1")

$valid = @(
    "127.0.0.1",
    "10.20.30.0/24",
    "2001:db8::1",
    "fd00:1234::/64"
)
foreach ($value in $valid) {
    if (-not (Assert-ItamTrustedProxyEntries -Value $value)) {
        throw "Expected trusted proxy value to pass: $value"
    }
}

$invalid = @(
    "",
    "REPLACE_WITH_PROXY_IP_OR_CIDR",
    "0.0.0.0/0",
    "::/0",
    "10.0.0.0/8",
    "2001:db8::/32",
    "not-an-ip",
    "10.0.0.1/33"
)
foreach ($value in $invalid) {
    $rejected = $false
    try {
        Assert-ItamTrustedProxyEntries -Value $value | Out-Null
    }
    catch {
        $rejected = $true
    }
    if (-not $rejected) {
        throw "Expected trusted proxy value to be rejected: '$value'"
    }
}

Write-Host "Trusted proxy configuration tests passed."
