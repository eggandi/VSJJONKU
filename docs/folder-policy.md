# Folder permission policy

VS쫀쿠 permission checks operate on folders, not individual files. The only
file-level exceptions are the fixed sensitive-path denials in `security.md`.

## Capabilities

- `read`: list, read, search, and Git read-only tools.
- `write`: create a new file through `write_file`; overwriting is refused.
- `change`: replace an existing file through `change_file`. Move and rename are
  not exposed.
- `delete`: remove exactly one file through `delete_file`. Directory and
  recursive deletion are not exposed.
- `exec`: run an allowlisted command. Not exposed yet and will remain
  Workspace-scoped rather than folder-scoped.

## Policy file

Store the JSON policy **outside** the Workspace and set its absolute path in
the VS Code Server process environment:

```powershell
$env:VSJJONKU_POLICY_PATH = "D:\VSJJONKU\policy.json"
```

The Bridge refuses to start without this value or when the policy is inside the
Workspace. This prevents a future `change` operation from modifying its own
access policy.

Use [the example](../config/vsjjonku-folder-policy.example.json) as a starting
point. A rule path must name an existing relative folder. A path cannot name a
file, use `..`, or be absolute.

```json
{
  "version": 1,
  "rules": [
    { "path": ".", "permissions": { "read": true } },
    { "path": "src", "permissions": { "write": true, "change": true } },
    { "path": "docs", "permissions": { "delete": false } }
  ]
}
```

Permissions are inherited from the nearest ancestor that defines that specific
capability. Absent permissions are denied. Therefore, `src` inherits `read`
from `.`, adds `write` and `change`, and `docs` explicitly denies `delete`.

`read`, `write`, `change`, and `delete` are enforced by their corresponding
MCP tools. `exec` remains a reserved capability until an allowlisted command
registry is implemented.
