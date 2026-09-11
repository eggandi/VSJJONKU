[CmdletBinding()]
param(
    [string]$WorkspacePath = (Get-Location).Path,
    [string]$RuntimeRoot = "",
    [string]$PolicyPath = "",
    [string]$SessionGatePath = "",
    [ValidateRange(1024, 65535)]
    [int]$RelayPort = 8787
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "local-relay-common.ps1")

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $RuntimeRoot) {
    $RuntimeRoot = Join-Path (Split-Path -Parent $projectRoot) "VSJJONKU"
}
$workspaceRoot = Resolve-VSJJONKUAbsolutePath $WorkspacePath "WorkspacePath"
$runtimeDirectory = Resolve-VSJJONKUAbsolutePath $RuntimeRoot "RuntimeRoot"
if (-not $PolicyPath) { $PolicyPath = Join-Path $runtimeDirectory "local-policy.json" }
if (-not $SessionGatePath) { $SessionGatePath = Join-Path $runtimeDirectory "local-session-gate.json" }
$policyFile = Resolve-VSJJONKUAbsolutePath $PolicyPath "PolicyPath"
$gateFile = Resolve-VSJJONKUAbsolutePath $SessionGatePath "SessionGatePath"
$workspacePrefix = $workspaceRoot.TrimEnd('\\', '/') + '\\'
if ($policyFile.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $gateFile.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "PolicyPath and SessionGatePath must be outside the target Workspace."
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python virtual environment is missing. Run the README installation first."
}
$vsix = Get-ChildItem -LiteralPath (Join-Path $projectRoot "vscode-extension") -Filter "*.vsix" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $vsix) {
    throw "VSIX is missing. Build it first: npm ci; npm run compile; npx --yes @vscode/vsce package --allow-missing-repository"
}
$code = (Get-Command code -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path $runtimeDirectory, (Split-Path -Parent $policyFile), (Split-Path -Parent $gateFile) | Out-Null
if (-not (Test-Path -LiteralPath $policyFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "config\vsjjonku-local-folder-policy.example.json") -Destination $policyFile
}
if (Test-Path -LiteralPath $gateFile -PathType Leaf) {
    & $python -m vsjjonku_gateway.session_gate status --path $gateFile | Out-Null
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $gateFile -PathType Leaf)) {
    & $python -m vsjjonku_gateway.session_gate configure --path $gateFile --minutes 30
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$stateFile = Join-Path $runtimeDirectory "local-relay-processes.json"
if (Test-Path -LiteralPath $stateFile) {
    throw "Local Relay may already be running. Run scripts\stop-local-relay.ps1 first."
}
Test-VSJJONKULocalPort $RelayPort "Local Relay"
$secrets = Get-VSJJONKULocalRelaySecrets $runtimeDirectory
$env:VSJJONKU_RELAY_WEB_TOKEN = $secrets.webToken
$env:VSJJONKU_RELAY_AGENT_TOKEN = $secrets.agentToken
$env:VSJJONKU_RELAY_BIND_HOST = "127.0.0.1"
$env:VSJJONKU_RELAY_PORT = $RelayPort.ToString()
$env:VSJJONKU_SESSION_GATE_PATH = $gateFile
$env:VSJJONKU_POLICY_PATH = $policyFile
$env:VSJJONKU_RELAY_URL = "http://127.0.0.1:$RelayPort"
$env:VSJJONKU_RELAY_AGENT_ID = "default"

$relayProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $PSScriptRoot "start-relay.ps1"), "-SessionGatePath", $gateFile
) -PassThru -WindowStyle Hidden
Wait-VSJJONKULocalPort $RelayPort "Local Relay"

$localProfile = Join-Path $runtimeDirectory "local-vscode-profile"
$localExtensions = Join-Path $runtimeDirectory "local-vscode-extensions"
Start-Process -FilePath $code -ArgumentList @(
    "--user-data-dir", $localProfile,
    "--extensions-dir", $localExtensions,
    "--install-extension", $vsix.FullName,
    "--new-window", $workspaceRoot
) | Out-Null

[pscustomobject]@{
    version = 1
    mode = "local-relay"
    workspacePath = $workspaceRoot
    relayUrl = $env:VSJJONKU_RELAY_URL
    processes = @(
        [pscustomobject]@{ name = "relay"; pid = $relayProcess.Id; marker = "start-relay.ps1" }
    )
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding utf8

Write-Host "VSJJONKU local Relay started."
Write-Host "Open Workspace trust in the dedicated local VS Code window."
Write-Host "Browser Relay web token (paste into the browser extension): $($secrets.webToken)"
Write-Host "Run local model tasks with: $PSScriptRoot\run-local-agent.ps1 -Task '<task>'"
