function Resolve-VSJJONKUAbsolutePath([string]$Path, [string]$Name) {
    if ($Path -notmatch '^[a-zA-Z]:[\\/]' -and $Path -notmatch '^\\\\[^\\]+\\[^\\]+') {
        throw "$Name must be an absolute Windows or UNC path."
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function New-VSJJONKURelayToken {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

function ConvertFrom-VSJJONKUSecureString([System.Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-VSJJONKULocalRelaySecrets([string]$RuntimeRoot) {
    $secretPath = Join-Path $RuntimeRoot "local-relay-secrets.json"
    if (-not (Test-Path -LiteralPath $secretPath -PathType Leaf)) {
        $webToken = New-VSJJONKURelayToken
        $agentToken = New-VSJJONKURelayToken
        [pscustomobject]@{
            version = 1
            webToken = ConvertFrom-SecureString (ConvertTo-SecureString $webToken -AsPlainText -Force)
            agentToken = ConvertFrom-SecureString (ConvertTo-SecureString $agentToken -AsPlainText -Force)
        } | ConvertTo-Json | Set-Content -LiteralPath $secretPath -Encoding utf8
        return [pscustomobject]@{ webToken = $webToken; agentToken = $agentToken; path = $secretPath }
    }
    try {
        $stored = Get-Content -LiteralPath $secretPath -Raw | ConvertFrom-Json
        if ($stored.version -ne 1 -or -not $stored.webToken -or -not $stored.agentToken) {
            throw "invalid secret file"
        }
        $webToken = ConvertFrom-VSJJONKUSecureString (ConvertTo-SecureString ([string]$stored.webToken))
        $agentToken = ConvertFrom-VSJJONKUSecureString (ConvertTo-SecureString ([string]$stored.agentToken))
    } catch {
        throw "Local Relay secrets cannot be read for the current Windows user: $secretPath"
    }
    if ($webToken.Length -lt 32 -or $agentToken.Length -lt 32) {
        throw "Local Relay secrets are invalid: $secretPath"
    }
    return [pscustomobject]@{ webToken = $webToken; agentToken = $agentToken; path = $secretPath }
}

function Test-VSJJONKULocalPort([int]$Port, [string]$Name) {
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet) {
        throw "$Name port $Port is already in use. Stop the existing local Relay first."
    }
}

function Wait-VSJJONKULocalPort([int]$Port, [string]$Name) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not open 127.0.0.1:$Port within 30 seconds."
}
