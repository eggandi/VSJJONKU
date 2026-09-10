"""Client for the loopback Bridge hosted by the VS Code Workspace Extension."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BridgeError(RuntimeError):
    """The VS Code Bridge rejected a request or could not be reached."""


@dataclass(frozen=True)
class BridgeClient:
    """Call the local, read-only Workspace Bridge over HTTP."""

    endpoint: str = "http://127.0.0.1:38991/rpc"
    token: str = ""
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
            raise ValueError("Bridge endpoint must use http://127.0.0.1.")
        if len(self.token) < 32:
            raise ValueError("Bridge token must contain at least 32 characters.")

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = json.dumps(
            {"method": method, "params": params or {}}, separators=(",", ":")
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as error:
            raise BridgeError(f"Bridge request failed with HTTP {error.code}.") from error
        except URLError as error:
            raise BridgeError("VS Code Bridge is unavailable.") from error

        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BridgeError("Bridge returned an invalid response.") from error

        if not isinstance(decoded, dict) or decoded.get("ok") is not True:
            message = decoded.get("error", "Bridge rejected the request.") if isinstance(decoded, dict) else "Bridge rejected the request."
            raise BridgeError(str(message))

        return decoded.get("result")
