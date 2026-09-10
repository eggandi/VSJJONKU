# Session-key expiry gate

This local gate requires someone at the computer hosting VSJJONKU to re-enter
a session key every 30 or 60 minutes. When the lease expires, the Gateway
process exits. The tunnel client can remain running, but no MCP tools work
until an operator renews the lease and starts the Gateway again.

The key never crosses MCP, the Secure MCP Tunnel, or the VS Code Bridge. The
configuration stores an `scrypt` hash and random salt, not the key itself.

## Configure

Choose a path outside the Workspace, then create a 30- or 60-minute lease:

```powershell
$gate = "C:\workspace\onedrive\Research\VSJJONKU\session-gate.json"
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate configure --path $gate --minutes 30
```

The command prompts for an exactly four-digit numeric key twice. This is a
local operating check, not a high-entropy credential or a replacement for the
Bridge token and OpenAI authentication.

## Start and renew

```powershell
.\scripts\start-gateway.ps1 -McpPort 8000 -SessionGatePath $gate
```

Renew it locally before expiry without restarting the Gateway:

```powershell
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate renew --path $gate
```

`status` shows the deadline without exposing the key:

```powershell
.\.venv\Scripts\python.exe -m vsjjonku_gateway.session_gate status --path $gate
```

This is an operational session boundary, not a defense against someone who
already controls the local Windows account.
