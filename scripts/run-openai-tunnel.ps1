[CmdletBinding()]
param(
    [string]$Profile = "vsjjonku"
)

if (-not (Get-Command tunnel-client -ErrorAction SilentlyContinue)) {
    throw "tunnel-client is not installed."
}
if (-not $env:CONTROL_PLANE_API_KEY) {
    throw "CONTROL_PLANE_API_KEY is required."
}

& tunnel-client run --profile $Profile
exit $LASTEXITCODE
