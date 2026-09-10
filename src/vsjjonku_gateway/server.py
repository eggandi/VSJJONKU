"""Read-only MCP server backed by the VS Code Workspace Bridge."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .bridge_client import BridgeClient
from .session_gate import SessionGate


def _mcp_port() -> int:
    value = os.environ.get("VSJJONKU_MCP_PORT", "8000")
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("VSJJONKU_MCP_PORT must be a valid TCP port.") from error
    if not 1024 <= port <= 65535:
        raise ValueError("VSJJONKU_MCP_PORT must be a valid TCP port.")
    return port


server = MCPServer(
    "VS쫀쿠",
    instructions=(
        "Use read-only Workspace tools before proposing changes. "
        "All paths are relative to the Workspace root."
    ),
)

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_CREATE_FILE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
_MODIFY_FILE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
_session_gate = SessionGate.from_environment()


def _bridge() -> BridgeClient:
    _session_gate.require_active()
    token = os.environ.get("VSJJONKU_BRIDGE_TOKEN", "")
    return BridgeClient(
        endpoint=os.environ.get("VSJJONKU_BRIDGE_URL", "http://127.0.0.1:38991/rpc"),
        token=token,
    )


@server.tool(annotations=_READ_ONLY)
def list_directory(path: str = ".") -> Any:
    """List a Workspace directory. Use before reading an unknown path."""

    return _bridge().call("list_directory", {"path": path})


@server.tool(annotations=_READ_ONLY)
def read_file(path: str) -> Any:
    """Read a UTF-8 text file inside the Workspace."""

    return _bridge().call("read_file", {"path": path})


@server.tool(annotations=_READ_ONLY)
def search_code(query: str, path: str = ".") -> Any:
    """Search literal text in Workspace files under a relative directory."""

    return _bridge().call("search_code", {"query": query, "path": path})


@server.tool(annotations=_CREATE_FILE)
def write_file(path: str, content: str) -> Any:
    """Create a new UTF-8 file. Refuses to overwrite an existing file."""

    return _bridge().call("write_file", {"path": path, "content": content})


@server.tool(annotations=_CREATE_FILE)
def create_directory(path: str) -> Any:
    """Create one new Workspace directory. Its parent directory must already exist."""

    return _bridge().call("create_directory", {"path": path})


@server.tool(annotations=_MODIFY_FILE)
def change_file(path: str, content: str) -> Any:
    """Replace one existing UTF-8 file after the folder's change permission is granted."""

    return _bridge().call("change_file", {"path": path, "content": content})


@server.tool(annotations=_MODIFY_FILE)
def delete_file(path: str) -> Any:
    """Delete exactly one file after the folder's delete permission is granted."""

    return _bridge().call("delete_file", {"path": path})


@server.tool(annotations=_MODIFY_FILE)
def delete_directory(path: str) -> Any:
    """Delete one empty directory after the parent folder's delete permission is granted."""

    return _bridge().call("delete_directory", {"path": path})


@server.tool(annotations=_READ_ONLY)
def git_status() -> Any:
    """Return the current Workspace Git status without modifying it."""

    return _bridge().call("git_status")


@server.tool(annotations=_READ_ONLY)
def git_diff() -> Any:
    """Return the current Workspace Git diff without modifying it."""

    return _bridge().call("git_diff")


def main() -> None:
    """Run a local Streamable HTTP MCP endpoint."""

    _bridge()
    _session_gate.start()
    server.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=_mcp_port(),
    )


if __name__ == "__main__":
    main()
