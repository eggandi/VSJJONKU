[CmdletBinding()]
param(
    [string]$RuntimeRoot = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$legacyRuntimeRoot = Join-Path (Split-Path -Parent $projectRoot) "VSJJONKU"
if (-not $RuntimeRoot) {
    if (Test-Path -LiteralPath (Join-Path $legacyRuntimeRoot "tunnel-client\tunnel-client.exe")) {
        $RuntimeRoot = $legacyRuntimeRoot
    } else {
        $RuntimeRoot = Join-Path $env:LOCALAPPDATA "VSJJONKU"
    }
}

$stateFile = Join-Path $RuntimeRoot "vsjjonku-processes.json"
if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) {
    Write-Host "No VS쫀쿠 process state was found."
    exit 0
}

$state = Get-Content -Raw -Encoding utf8 $stateFile | ConvertFrom-Json
foreach ($entry in @($state.processes) | Sort-Object { $_.pid } -Descending) {
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
