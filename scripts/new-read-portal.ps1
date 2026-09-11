[CmdletBinding()]
param(
    [ValidateRange(1, 60)]
    [int]$Minutes = 15,
    [string]$RuntimeRoot = "",
    [string]$RelayUrl = "http://127.0.0.1:8787",
    [string]$PublicBaseUrl = "",
    [string]$AgentId = "default"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "local-relay-common.ps1")

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path (Split-Path -Parent $projectRoot) "VSJJONKU"
}
$runtimeDirectory = Resolve-VSJJONKUAbsolutePath $RuntimeRoot "RuntimeRoot"
$relayUri = [Uri]$RelayUrl
if ($relayUri.Scheme -ne "http" -or $relayUri.Host -notin @("127.0.0.1", "localhost")) {
    throw "RelayUrl must use local http://127.0.0.1 or http://localhost."
}
if ($PublicBaseUrl) {
    $publicUri = [Uri]$PublicBaseUrl
    if ($publicUri.Scheme -ne "https" -or $publicUri.Query -or $publicUri.Fragment) {
        throw "PublicBaseUrl must be an HTTPS origin without a query or fragment."
    }
    $publicOrigin = $publicUri.GetLeftPart([System.UriPartial]::Authority)
} else {
    $publicOrigin = $relayUri.GetLeftPart([System.UriPartial]::Authority)
}

$secrets = Get-VSJJONKULocalRelaySecrets $runtimeDirectory
$body = @{ agentId = $AgentId; minutes = $Minutes } | ConvertTo-Json -Compress
$response = Invoke-RestMethod -Method Post -Uri ($relayUri.GetLeftPart([System.UriPartial]::Authority) + "/api/portals") `
    -ContentType "application/json" `
    -Headers @{ "X-VSJJONKU-Web-Token" = $secrets.webToken } `
    -Body $body

Write-Host "Read-only Portal URL (expires at $([DateTimeOffset]::FromUnixTimeSeconds([int64]$response.expiresAt).ToLocalTime())):"
Write-Host ($publicOrigin.TrimEnd('/') + [string]$response.path)
