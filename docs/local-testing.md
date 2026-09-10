# Local wrapper verification

## Prerequisites

Run from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Push-Location vscode-extension
npm install
npm run compile
Pop-Location
```

## Extension Bridge

Launch a VS Code Extension Development Host with this repository as its only
workspace. The Bridge listens on `127.0.0.1` and defaults to port `38991`.
Set one 32+ character Bridge token in the environment before launching VS Code.

```powershell
$env:VSJJONKU_BRIDGE_TOKEN = "replace-with-a-32-character-minimum-token"
$env:VSJJONKU_POLICY_PATH = "C:\outside-workspace\policy.json"
code --new-window `
  --extensionDevelopmentPath "$PWD\vscode-extension" `
  "$PWD"
```

Check it only from the same machine:

```powershell
curl.exe -H "Authorization: Bearer $env:VSJJONKU_BRIDGE_TOKEN" http://127.0.0.1:38991/health
```

For a parallel test host, set `vsjjonku.bridgePort` in that host's VS Code
settings (the verification host uses port `38993`).

## Gateway and MCP smoke test

Point the Gateway at the matching local Bridge and start it:

```powershell
$env:VSJJONKU_BRIDGE_URL = "http://127.0.0.1:38991/rpc"
$env:VSJJONKU_BRIDGE_TOKEN = "replace-with-the-same-token"
$env:VSJJONKU_MCP_PORT = "8000"
.\.venv\Scripts\python.exe -m vsjjonku_gateway.server
```

The MCP endpoint is `http://127.0.0.1:$env:VSJJONKU_MCP_PORT/mcp`. It remains
loopback-only; do not expose it directly on the network.

## Completed on 2026-09-10

- `npm run compile` passed.
- Python Bridge client unit tests passed (`2 passed`).
- A VS Code Extension Development Host returned successful `list_directory`,
  `read_file`, and `search_code` Bridge responses.
- An MCP `tools/call` request for `search_code` returned the matching files via
  the Bridge.
- A `../` path was rejected with `Path traversal is not allowed.`
- Unauthenticated Bridge requests returned HTTP 401; `.env` requests were
  rejected through the MCP path.
