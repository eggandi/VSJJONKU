# OpenAI Secure MCP Tunnel

This is the external transport for VS쫀쿠. VS Code Remote Tunnel continues to
serve the VS Code session; it does not expose the MCP Gateway.

```text
ChatGPT developer-mode app
  -> OpenAI-hosted MCP tunnel
  -> tunnel-client (outbound HTTPS)
  -> VS쫀쿠 MCP Gateway at 127.0.0.1
  -> authenticated VS Code Extension Bridge at 127.0.0.1
  -> Workspace
```

## Required account setup

1. Create an OpenAI-hosted tunnel and save its ID in the current shell as
   `VSJJONKU_TUNNEL_ID`.
2. Create a runtime API key with **Tunnels Read + Use**, and place it only in
   the current shell as `CONTROL_PLANE_API_KEY`.
3. Associate the tunnel with the intended ChatGPT workspace as well as the
   Platform organization.
4. Enable ChatGPT developer mode for that workspace.
5. Download the official `tunnel-client` from OpenAI Platform tunnel settings.

Do not place either the runtime API key or Bridge token in this repository.

## Local startup

Use the same Bridge token for the VS Code Extension process and Gateway:

```powershell
$env:VSJJONKU_BRIDGE_TOKEN = "a-new-32-character-minimum-secret"
$env:VSJJONKU_POLICY_PATH = "D:\VSJJONKU\policy.json"
```

For the Extension Development Host, compile and package the extension:

```powershell
Push-Location .\vscode-extension
npm run compile
npx --yes @vscode/vsce package --allow-missing-repository
Pop-Location
```

Install the resulting VSIX into the VS Code Server that owns the Remote Tunnel,
then restart that VS Code Server with `VSJJONKU_BRIDGE_TOKEN` in its process
environment. A development-host install proves the Bridge only; it is not the
Remote Tunnel deployment.

Configure a local 30- or 60-minute session-key lease outside the Workspace,
then start the Gateway in a second terminal:

```powershell
$gate = "C:\workspace\onedrive\Research\VSJJONKU\session-gate.json"
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate configure --path $gate --minutes 30
.\scripts\start-gateway.ps1 -McpPort 8000 -SessionGatePath $gate
```

Configure and validate the tunnel once:

```powershell
$env:VSJJONKU_TUNNEL_ID = "tunnel_..."
$env:CONTROL_PLANE_API_KEY = "sk-..."
.\scripts\setup-openai-tunnel.ps1 -McpPort 8000
```

Then keep the client running:

```powershell
.\scripts\run-openai-tunnel.ps1
```

## ChatGPT test

In ChatGPT developer mode, create an app, select **Tunnel** as the connection
type, and select or paste `VSJJONKU_TUNNEL_ID`. Confirm the five read-only
tools appear, then test `list_directory` and `search_code` first.

If the tunnel is not listed, check the workspace association and the caller's
**Tunnels Read + Use** permission. If tool discovery fails, run
`tunnel-client doctor --profile vsjjonku --explain` while the client remains
running.
