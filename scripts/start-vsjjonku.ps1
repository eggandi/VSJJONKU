[CmdletBinding()]
param(
    [string]$WorkspacePath = (Get-Location).Path,
    [string]$TunnelName = "vs-jjonku",
    [string]$RuntimeRoot = "",
    [string]$PolicyPath = "",
    [string]$SessionGatePath = "",
    [string]$TunnelClientPath = "",
    [string]$TunnelProfileDir = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$legacyRuntimeRoot = Join-Path (Split-Path -Parent $projectRoot) "VSJJONKU"

function Resolve-AbsolutePath([string]$Path, [string]$Name) {
    if ($Path -notmatch '^[a-zA-Z]:[\\/]' -and $Path -notmatch '^\\\\[^\\]+\\[^\\]+') {
        throw "$Name must be an absolute Windows or UNC path."
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function Wait-ForPort([int]$Port, [string]$Name) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not open 127.0.0.1:$Port within 30 seconds."
}

function Stop-ExistingVsjjunkuListener([int]$Port, [string]$Marker, [string]$Name) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($null -eq $process -or $process.CommandLine -notmatch [regex]::Escape($Marker)) {
            throw "Port $Port is already used by a process that is not $Name."
        }
        taskkill.exe /PID $listener.OwningProcess /T /F | Out-Null
        Write-Host "Stopped existing $Name."
    }
}

function Stop-ExistingWorkspaceTunnel([string]$Name) {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'code-tunnel.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match [regex]::Escape("--name $Name") }
    foreach ($process in $processes) {
        taskkill.exe /PID $process.ProcessId /T /F | Out-Null
        Write-Host "Stopped existing VS쫀쿠 Tunnel."
    }
}

function Assert-NoOtherWorkspaceTunnel([string]$CodeTunnelPath, [string]$Name) {
    $statusText = & $CodeTunnelPath tunnel status
    if ($LASTEXITCODE -ne 0) {
        return
    }
    try {
        $status = $statusText | ConvertFrom-Json
    } catch {
        return
    }
    $activeName = [string]$status.tunnel.name
    $isConnected = [string]$status.tunnel.tunnel -eq "Connected"
    if ($isConnected -and $activeName -and $activeName -ne $Name) {
        throw "VS Code Tunnel '$activeName' is already active. Turn off VS Code Remote Tunnel Access for that tunnel before starting '$Name'."
    }
}

function Ensure-ManagedSourceLink([string]$WorkspaceRoot, [string]$SourceRoot) {
    if ($WorkspaceRoot.Equals($SourceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $workspaceParent = Split-Path -Parent $WorkspaceRoot
    $sourceParent = Split-Path -Parent $SourceRoot
    if (-not $workspaceParent.Equals($sourceParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkspacePath must be a sibling of the JJONKU source folder to create its managed JJONKU link."
    }
    $linkPath = Join-Path $WorkspaceRoot "JJONKU"
    if (Test-Path -LiteralPath $linkPath) {
        Write-Host "Managed source link already exists: $linkPath"
        return $true
    }
    New-Item -ItemType Junction -Path $linkPath -Target $SourceRoot | Out-Null
    Write-Host "Created managed source link: $linkPath -> $SourceRoot"
    return $true
}

function Ensure-ManagedSourceLinkPolicy([string]$PolicyFile, [bool]$ManagedLinkEnabled) {
    if (-not $ManagedLinkEnabled) {
        return
    }
    try {
        $policy = Get-Content -LiteralPath $PolicyFile -Raw | ConvertFrom-Json
    } catch {
        throw "PolicyPath must contain valid JSON before a managed JJONKU link can be configured."
    }
    $expectedTarget = "../JJONKU"
    $managedLinksProperty = $policy.PSObject.Properties["managedLinks"]
    if ($null -eq $managedLinksProperty) {
        $policy | Add-Member -NotePropertyName "managedLinks" -NotePropertyValue @()
    }
    $existing = @($policy.managedLinks | Where-Object { $_.path -eq "JJONKU" })
    if ($existing.Count -gt 0) {
        if ($existing.Count -ne 1 -or $existing[0].target -ne $expectedTarget) {
            throw "policy.json already declares JJONKU with a different managed link target."
        }
        return
    }
    $policy.managedLinks += [pscustomobject]@{ path = "JJONKU"; target = $expectedTarget }
    $policy | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PolicyFile -Encoding utf8
    Write-Host "Registered managed source link in policy.json."
}

if (-not $RuntimeRoot) {
    $RuntimeRoot = $legacyRuntimeRoot
}

$workspaceRoot = Resolve-AbsolutePath $WorkspacePath "WorkspacePath"
$runtimeDirectory = Resolve-AbsolutePath $RuntimeRoot "RuntimeRoot"
$sourceFolderName = Split-Path -Leaf $projectRoot
if (-not $sourceFolderName.Equals("JJONKU", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The JJONKU source folder must be named JJONKU to create the managed source link."
}
$managedSourceLinkEnabled = Ensure-ManagedSourceLink $workspaceRoot $projectRoot
$bridgeExtensionsDirectory = Join-Path $runtimeDirectory "bridge-extensions"
if (-not $PolicyPath) {
    $PolicyPath = Join-Path $runtimeDirectory "policy.json"
}
if (-not $SessionGatePath) {
    $SessionGatePath = Join-Path $runtimeDirectory "session-gate.json"
}
$policyFile = Resolve-AbsolutePath $PolicyPath "PolicyPath"
$gateFile = Resolve-AbsolutePath $SessionGatePath "SessionGatePath"
$workspacePrefix = $workspaceRoot.TrimEnd('\', '/') + '\'
if ($policyFile.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $gateFile.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "PolicyPath and SessionGatePath must be outside the target Workspace."
}
if (-not $env:VSJJONKU_BRIDGE_TOKEN -or $env:VSJJONKU_BRIDGE_TOKEN.Length -lt 32) {
    throw "VSJJONKU_BRIDGE_TOKEN must contain at least 32 characters."
}
if (-not $env:CONTROL_PLANE_API_KEY) {
    throw "CONTROL_PLANE_API_KEY is required for tunnel-client."
}

if (-not $TunnelClientPath) {
    $TunnelClientPath = Join-Path $runtimeDirectory "tunnel-client\tunnel-client.exe"
}
if (-not $TunnelProfileDir) {
    $TunnelProfileDir = Join-Path $runtimeDirectory "tunnel-client-profile"
}
$clientExecutable = Resolve-AbsolutePath $TunnelClientPath "TunnelClientPath"
$profileDirectory = Resolve-AbsolutePath $TunnelProfileDir "TunnelProfileDir"
if (-not (Test-Path -LiteralPath $clientExecutable -PathType Leaf)) {
    throw "tunnel-client.exe was not found: $clientExecutable"
}
if (-not (Test-Path -LiteralPath (Join-Path $profileDirectory "vsjjonku.yaml") -PathType Leaf)) {
    throw "Tunnel profile vsjjonku.yaml was not found: $profileDirectory"
}

New-Item -ItemType Directory -Force -Path $runtimeDirectory, (Split-Path -Parent $policyFile), (Split-Path -Parent $gateFile) | Out-Null
if (-not (Test-Path -LiteralPath $policyFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "config\vsjjonku-folder-policy.example.json") -Destination $policyFile
}
Ensure-ManagedSourceLinkPolicy $policyFile $managedSourceLinkEnabled

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python virtual environment is missing. Run the installation steps in README.md first."
}
if (-not (Test-Path -LiteralPath $gateFile -PathType Leaf)) {
    & $python -m vsjjonku_gateway.session_gate configure --path $gateFile --minutes 30
} else {
    & $python -m vsjjonku_gateway.session_gate renew --path $gateFile
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$vsix = Get-ChildItem -LiteralPath (Join-Path $projectRoot "vscode-extension") -Filter "*.vsix" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $vsix) {
    throw "VSIX is missing. Build it first: npm ci; npm run compile; npx --yes @vscode/vsce package --allow-missing-repository"
}

$stateFile = Join-Path $runtimeDirectory "vsjjonku-processes.json"
if (Test-Path -LiteralPath $stateFile) {
    throw "VS쫀쿠 may already be running. Run .\scripts\stop-vsjjonku.ps1 first."
}

Stop-ExistingVsjjunkuListener 8000 "vsjjonku_gateway.server" "Gateway"
Stop-ExistingVsjjunkuListener 8091 "tunnel-client" "tunnel-client"
$codeTunnel = (Get-Command code-tunnel -ErrorAction Stop).Source
Stop-ExistingWorkspaceTunnel $TunnelName
Assert-NoOtherWorkspaceTunnel $codeTunnel $TunnelName
$env:VSJJONKU_POLICY_PATH = $policyFile
$codeProcess = Start-Process -FilePath $codeTunnel -ArgumentList @(
    "tunnel", "--name", $TunnelName,
    "--server-data-dir", (Join-Path $runtimeDirectory "server-data"),
    "--extensions-dir", $bridgeExtensionsDirectory,
    "--install-extension", $vsix.FullName,
    "--accept-server-license-terms"
) -PassThru

$gatewayProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $PSScriptRoot "start-gateway.ps1"), "-SessionGatePath", $gateFile
) -PassThru -WindowStyle Hidden
Wait-ForPort 8000 "Gateway"

$clientProcess = Start-Process -FilePath $clientExecutable -ArgumentList @(
    "run", "--profile", "vsjjonku", "--profile-dir", $profileDirectory
) -PassThru -WindowStyle Hidden
Wait-ForPort 8091 "tunnel-client"

[pscustomobject]@{
    version = 1
    workspacePath = $workspaceRoot
    tunnelName = $TunnelName
    processes = @(
        [pscustomobject]@{ name = "code-tunnel"; pid = $codeProcess.Id; marker = "tunnel" },
        [pscustomobject]@{ name = "gateway"; pid = $gatewayProcess.Id; marker = "start-gateway.ps1" },
        [pscustomobject]@{ name = "tunnel-client"; pid = $clientProcess.Id; marker = "tunnel-client" }
    )
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding utf8

$workspaceUrl = "https://vscode.dev/tunnel/$TunnelName/" + ($workspaceRoot -replace '\\', '/')
Write-Host "VS쫀쿠 started."
Write-Host "Open the Workspace in Desktop VS Code: $workspaceUrl"
Write-Host "Stop later with: $PSScriptRoot\stop-vsjjonku.ps1"
