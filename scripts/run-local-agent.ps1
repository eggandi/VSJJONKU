[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Task,
    [string]$RuntimeRoot = "",
    [string]$ModelBaseUrl = "http://127.0.0.1:1234/v1",
    [string]$Model = "NousResearch/Hermes-3-Llama-3.2-3B",
    [ValidateRange(1, 20)]
    [int]$MaxSteps = 8
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "local-relay-common.ps1")

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path (Split-Path -Parent $projectRoot) "VSJJONKU"
}
$runtimeDirectory = Resolve-VSJJONKUAbsolutePath $RuntimeRoot "RuntimeRoot"
$stateFile = Join-Path $runtimeDirectory "local-relay-processes.json"
if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) {
    throw "Local Relay is not running. Start scripts\start-local-relay.ps1 first."
}
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$relayUrl = [string]$state.relayUrl
if (-not $relayUrl) { throw "Local Relay state is invalid." }

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python virtual environment is missing."
}
$secrets = Get-VSJJONKULocalRelaySecrets $runtimeDirectory
$env:VSJJONKU_RELAY_WEB_TOKEN = $secrets.webToken
$env:VSJJONKU_RELAY_URL = $relayUrl

& $python -m vsjjonku_gateway.local_agent `
    --task $Task `
    --model-base-url $ModelBaseUrl `
    --model $Model `
    --relay-url $relayUrl `
    --max-steps $MaxSteps
exit $LASTEXITCODE
