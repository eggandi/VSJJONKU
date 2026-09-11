[CmdletBinding()]
param(
    [string]$RuntimeRoot = ""
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
    Write-Host "No local Relay process state was found."
    exit 0
}

$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($entry in @($state.processes)) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.pid)" -ErrorAction SilentlyContinue
    if ($null -eq $process) { continue }
    if ($process.CommandLine -notmatch [regex]::Escape([string]$entry.marker)) {
        Write-Warning "Skipping PID $($entry.pid): expected $($entry.name) marker is absent."
        continue
    }
    taskkill.exe /PID $entry.pid /T /F | Out-Null
    Write-Host "Stopped $($entry.name)."
}
Remove-Item -LiteralPath $stateFile -Force
