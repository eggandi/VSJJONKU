# Security boundary

## Trust boundaries

```text
ChatGPT / MCP client
  -> OpenAI Secure MCP Tunnel (next phase)
  -> MCP Gateway, 127.0.0.1 only
  -> authenticated loopback Bridge
  -> VS Code Workspace Extension
  -> one opened Workspace
```

The VS Code Remote Tunnel transports the VS Code session. It is not used as an
arbitrary SSH endpoint or as the MCP exposure mechanism.

## Implemented controls

- The MCP Gateway binds only to `127.0.0.1`; `VSJJONKU_MCP_PORT` is restricted
  to TCP ports 1024–65535.
- The Python Gateway accepts only an `http://127.0.0.1` Bridge endpoint.
- The Gateway and Workspace Extension require the same
  `VSJJONKU_BRIDGE_TOKEN` value of at least 32 characters. The Extension
  rejects every unauthenticated Bridge request, including health checks.
- Exactly one Workspace folder must be open.
- A folder policy is mandatory and must be stored outside the Workspace. It
  grants `read`, `write`, `change`, `delete`, and `exec` independently; details
  are in `folder-policy.md`.
- Paths must be relative, and traversal (`..`), sensitive path components, and
  symbolic links are rejected. A policy can declare only a direct `JJONKU`
  link to one configured sibling directory; the Bridge resolves and verifies
  that target on every RPC. The link root itself cannot be replaced or deleted.
- `.env` and `.env.*`, SSH key names, `credentials*`, `.ssh`, `.aws`, `.gnupg`,
  and common private-key suffixes are excluded from listing, reading, and code
  search.
- File reads, writes, and Git command output have a 1 MiB limit. Git operations
  use a 10 second timeout and only fixed read-only arguments.
- File creation cannot overwrite an existing file. File modification cannot
  create a new file. Deletion is limited to one non-symlink file; recursive
  deletion is not implemented.
- When started with `-SessionGatePath`, the Gateway requires a locally renewed
  30- or 60-minute session-key lease. On expiry it terminates and stops serving
  MCP requests. See `session-gate.md`.

## Explicitly not implemented

- build, test, and generic `exec` tools;
- external MCP exposure or ChatGPT account authorization;
- multi-workspace operation;
- a policy exception mechanism for a normally denied file.

The next external-facing layer must use OpenAI Secure MCP Tunnel or an
equivalent authenticated MCP transport. It must not bind this Gateway to a
non-loopback interface.
