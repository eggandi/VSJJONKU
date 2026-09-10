[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$McpPort = 8000,
    [Parameter(Mandatory = $true)]
    [string]$SessionGatePath
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment is missing. Run the setup steps in docs/local-testing.md."
}
if (-not $env:VSJJONKU_BRIDGE_TOKEN -or $env:VSJJONKU_BRIDGE_TOKEN.Length -lt 32) {
    throw "VSJJONKU_BRIDGE_TOKEN must contain at least 32 characters."
}

$env:VSJJONKU_MCP_PORT = $McpPort.ToString()
$isDriveAbsolutePath = $SessionGatePath -match '^[a-zA-Z]:[\\/]'
$isUncAbsolutePath = $SessionGatePath -match '^\\\\[^\\]+\\[^\\]+'
if (-not ($isDriveAbsolutePath -or $isUncAbsolutePath)) {
    throw "SessionGatePath must be an absolute Windows or UNC path."
}
$resolvedGatePath = [System.IO.Path]::GetFullPath($SessionGatePath)
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
$workspacePrefix = $resolvedProjectRoot.TrimEnd('\', '/') + '\'
if ($resolvedGatePath.Equals($resolvedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $resolvedGatePath.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "SessionGatePath must be outside the Workspace."
}
if (-not (Test-Path -LiteralPath $resolvedGatePath -PathType Leaf)) {
    throw "Session gate configuration is missing. Run python -m vsjjonku_gateway.session_gate configure first."
}
$env:VSJJONKU_SESSION_GATE_PATH = $resolvedGatePath
& $python -m vsjjonku_gateway.server
exit $LASTEXITCODE
