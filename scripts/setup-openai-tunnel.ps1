[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$McpPort = 8000,
    [string]$Profile = "vsjjonku"
)

if (-not (Get-Command tunnel-client -ErrorAction SilentlyContinue)) {
    throw "tunnel-client is not installed. Download it through OpenAI Platform tunnel settings."
}
if (-not $env:CONTROL_PLANE_API_KEY) {
    throw "CONTROL_PLANE_API_KEY is required. Use an OpenAI runtime API key with Tunnels Read + Use."
}
if (-not $env:VSJJONKU_TUNNEL_ID) {
    throw "VSJJONKU_TUNNEL_ID is required. Create or select the OpenAI tunnel first."
}

$mcpUrl = "http://127.0.0.1:$McpPort/mcp"
& tunnel-client init `
    --profile $Profile `
    --tunnel-id $env:VSJJONKU_TUNNEL_ID `
    --mcp-server-url $mcpUrl
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& tunnel-client doctor --profile $Profile --explain
exit $LASTEXITCODE
