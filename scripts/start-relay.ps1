[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionGatePath
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python virtual environment is missing. Run the installation steps in README.md first."
}
if (-not $env:VSJJONKU_RELAY_WEB_TOKEN -or $env:VSJJONKU_RELAY_WEB_TOKEN.Length -lt 32) {
    throw "VSJJONKU_RELAY_WEB_TOKEN must contain at least 32 characters."
}
if (-not $env:VSJJONKU_RELAY_AGENT_TOKEN -or $env:VSJJONKU_RELAY_AGENT_TOKEN.Length -lt 32) {
    throw "VSJJONKU_RELAY_AGENT_TOKEN must contain at least 32 characters."
}
$isDriveAbsolutePath = $SessionGatePath -match '^[a-zA-Z]:[\\/]'
$isUncAbsolutePath = $SessionGatePath -match '^\\\\[^\\]+\\[^\\]+'
if (-not ($isDriveAbsolutePath -or $isUncAbsolutePath)) {
    throw "SessionGatePath must be an absolute Windows or UNC path."
}
$env:VSJJONKU_SESSION_GATE_PATH = [System.IO.Path]::GetFullPath($SessionGatePath)

& $python -m vsjjonku_gateway.relay
exit $LASTEXITCODE
