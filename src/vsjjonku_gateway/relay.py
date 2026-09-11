"""Private web relay for commands executed by a VSJJONKU Workspace Extension."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import escape
import os
import re
import secrets
import time
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from .session_gate import SessionGate, SessionGateError


AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
REQUEST_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
SUPPORTED_METHODS = frozenset(
    {
        "list_directory",
        "read_file",
        "search_code",
        "git_status",
        "git_diff",
        "write_file",
        "create_directory",
        "change_file",
        "delete_file",
        "delete_directory",
    }
)
DESTRUCTIVE_METHODS = frozenset({"change_file", "delete_file", "delete_directory"})
PORTAL_METHODS = frozenset({"list_directory", "read_file"})
PORTAL_MAX_MINUTES = 60
PORTAL_MAX_REQUESTS = 200
PORTAL_COMMAND_TIMEOUT_SECONDS = 35


@dataclass(frozen=True)
class RelaySettings:
    web_token: str
    agent_token: str

    @classmethod
    def from_environment(cls) -> "RelaySettings":
        web_token = os.environ.get("VSJJONKU_RELAY_WEB_TOKEN", "")
        agent_token = os.environ.get("VSJJONKU_RELAY_AGENT_TOKEN", "")
        if len(web_token) < 32 or len(agent_token) < 32:
            raise ValueError(
                "VSJJONKU_RELAY_WEB_TOKEN and VSJJONKU_RELAY_AGENT_TOKEN must contain at least 32 characters."
            )
        return cls(web_token=web_token, agent_token=agent_token)


@dataclass
class RelayCommand:
    request_id: str
    agent_id: str
    method: str
    params: dict[str, Any]
    created_at: float
    status: str = "queued"
    result: dict[str, Any] | None = None


@dataclass
class PortalSession:
    capability: str
    agent_id: str
    expires_at: float
    requests_remaining: int = PORTAL_MAX_REQUESTS


class RelayStore:
    """In-memory, per-agent FIFO queue for one private relay process."""

    def __init__(self) -> None:
        self._commands: dict[str, RelayCommand] = {}
        self._queues: dict[str, list[str]] = {}
        self._condition = asyncio.Condition()

    async def enqueue(self, agent_id: str, method: str, params: dict[str, Any]) -> RelayCommand:
        command = RelayCommand(
            request_id=secrets.token_hex(16),
            agent_id=agent_id,
            method=method,
            params=params,
            created_at=time.time(),
        )
        async with self._condition:
            self._commands[command.request_id] = command
            self._queues.setdefault(agent_id, []).append(command.request_id)
            self._condition.notify_all()
        return command

    async def poll(self, agent_id: str, timeout_seconds: int) -> RelayCommand | None:
        async with self._condition:
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: bool(self._queues.get(agent_id))),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                return None
            command = self._commands[self._queues[agent_id].pop(0)]
            command.status = "dispatched"
            return command

    async def complete(
        self, agent_id: str, request_id: str, result: dict[str, Any]
    ) -> RelayCommand:
        async with self._condition:
            command = self._commands.get(request_id)
            if command is None or command.agent_id != agent_id:
                raise KeyError(request_id)
            command.status = "completed"
            command.result = result
            self._condition.notify_all()
            return command

    async def get(self, request_id: str) -> RelayCommand | None:
        async with self._condition:
            return self._commands.get(request_id)

    async def wait_for_result(
        self, request_id: str, timeout_seconds: float
    ) -> RelayCommand | None:
        async with self._condition:
            command = self._commands.get(request_id)
            if command is None:
                return None
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(
                        lambda: (current := self._commands.get(request_id)) is None
                        or current.result is not None
                    ),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                return None
            return self._commands.get(request_id)


class PortalStore:
    """Short-lived public read capability sessions kept only in relay memory."""

    def __init__(self) -> None:
        self._sessions: dict[str, PortalSession] = {}

    def create(self, agent_id: str, minutes: int) -> PortalSession:
        self._purge_expired()
        session = PortalSession(
            capability=secrets.token_urlsafe(32),
            agent_id=agent_id,
            expires_at=time.time() + (minutes * 60),
        )
        self._sessions[session.capability] = session
        return session

    def use(self, capability: str) -> PortalSession:
        self._purge_expired()
        session = self._sessions.get(capability)
        if session is None:
            raise KeyError(capability)
        if session.requests_remaining <= 0:
            self._sessions.pop(capability, None)
            raise KeyError(capability)
        session.requests_remaining -= 1
        return session

    def _purge_expired(self) -> None:
        now = time.time()
        for capability, session in list(self._sessions.items()):
            if session.expires_at <= now:
                self._sessions.pop(capability, None)


def create_app(
    settings: RelaySettings | None = None,
    store: RelayStore | None = None,
    session_gate: SessionGate | None = None,
    portal_store: PortalStore | None = None,
) -> FastAPI:
    settings = settings or RelaySettings.from_environment()
    store = store or RelayStore()
    session_gate = session_gate or SessionGate(None)
    portal_store = portal_store or PortalStore()
    app = FastAPI(title="VSJJONKU Relay", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def control_page() -> str:
        return CONTROL_PAGE

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/commands")
    async def enqueue_command(
        payload: dict[str, Any],
        x_vsjjonku_web_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_vsjjonku_web_token, settings.web_token)
        require_active_session(session_gate)
        agent_id = validate_agent_id(payload.get("agentId"))
        method = validate_method(payload.get("method"))
        params = payload.get("params", {})
        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="params must be an object.")
        if method in DESTRUCTIVE_METHODS and payload.get("confirm") is not True:
            raise HTTPException(status_code=400, detail="Destructive commands require confirm: true.")
        return command_view(await store.enqueue(agent_id, method, params))

    @app.get("/api/commands/{request_id}")
    async def command_status(
        request_id: str,
        x_vsjjonku_web_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_vsjjonku_web_token, settings.web_token)
        validate_request_id(request_id)
        command = await store.get(request_id)
        if command is None:
            raise HTTPException(status_code=404, detail="Command was not found.")
        return command_view(command)

    @app.post("/api/agents/{agent_id}/poll")
    async def poll_agent(
        agent_id: str,
        payload: dict[str, Any],
        x_vsjjonku_agent_token: str | None = Header(default=None),
    ) -> dict[str, Any] | None:
        require_token(x_vsjjonku_agent_token, settings.agent_token)
        validate_agent_id(agent_id)
        timeout_seconds = payload.get("timeoutSeconds", 20)
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 25:
            raise HTTPException(status_code=400, detail="timeoutSeconds must be an integer from 1 to 25.")
        command = await store.poll(agent_id, timeout_seconds)
        return None if command is None else command_view(command)

    @app.post("/api/agents/{agent_id}/results/{request_id}")
    async def submit_result(
        agent_id: str,
        request_id: str,
        payload: dict[str, Any],
        x_vsjjonku_agent_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_vsjjonku_agent_token, settings.agent_token)
        validate_agent_id(agent_id)
        validate_request_id(request_id)
        ok = payload.get("ok")
        if not isinstance(ok, bool):
            raise HTTPException(status_code=400, detail="Result must contain boolean ok.")
        if ok:
            result = {"ok": True, "result": payload.get("result")}
        else:
            error = payload.get("error")
            if not isinstance(error, str) or not error:
                raise HTTPException(status_code=400, detail="Failed result must contain error.")
            result = {"ok": False, "error": error}
        try:
            return command_view(await store.complete(agent_id, request_id, result))
        except KeyError:
            raise HTTPException(status_code=404, detail="Command was not found.") from None

    @app.post("/api/portals")
    async def create_portal(
        payload: dict[str, Any],
        x_vsjjonku_web_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_vsjjonku_web_token, settings.web_token)
        require_active_session(session_gate)
        agent_id = validate_agent_id(payload.get("agentId"))
        minutes = payload.get("minutes", 15)
        if not isinstance(minutes, int) or not 1 <= minutes <= PORTAL_MAX_MINUTES:
            raise HTTPException(
                status_code=400,
                detail=f"minutes must be an integer from 1 to {PORTAL_MAX_MINUTES}.",
            )
        return portal_view(portal_store.create(agent_id, minutes))

    @app.get("/r/{capability}/", response_class=HTMLResponse)
    async def portal_root(capability: str) -> HTMLResponse:
        return await portal_directory_response(capability, ".")

    @app.get("/r/{capability}/d/{path:path}", response_class=HTMLResponse)
    async def portal_directory(capability: str, path: str) -> HTMLResponse:
        return await portal_directory_response(capability, path)

    @app.get("/r/{capability}/f/{path:path}", response_class=HTMLResponse)
    async def portal_file(capability: str, path: str) -> HTMLResponse:
        try:
            session = portal_store.use(capability)
            safe_path = validate_portal_path(path)
            result = await portal_read_command(
                store, session_gate, session, "read_file", {"path": safe_path}
            )
            if not isinstance(result, dict) or not isinstance(result.get("content"), str):
                raise HTTPException(status_code=502, detail="Workspace returned an invalid file response.")
            parent = parent_portal_path(safe_path)
            body = (
                f'<p><a href="{portal_directory_href(capability, parent)}">Up</a></p>'
                f"<pre>{escape(result['content'])}</pre>"
            )
            return portal_html_response(f"VSJJONKU file: {safe_path}", body)
        except KeyError:
            raise HTTPException(status_code=404, detail="Portal capability is unavailable.") from None

    async def portal_directory_response(capability: str, path: str) -> HTMLResponse:
        try:
            session = portal_store.use(capability)
            safe_path = validate_portal_path(path)
            result = await portal_read_command(
                store, session_gate, session, "list_directory", {"path": safe_path}
            )
            if not isinstance(result, list):
                raise HTTPException(status_code=502, detail="Workspace returned an invalid directory response.")
            entries = portal_directory_entries(capability, safe_path, result)
            up = "" if safe_path == "." else f'<p><a href="{portal_directory_href(capability, parent_portal_path(safe_path))}">Up</a></p>'
            body = f"{up}<ul>{entries}</ul>"
            return portal_html_response(f"VSJJONKU directory: {safe_path}", body)
        except KeyError:
            raise HTTPException(status_code=404, detail="Portal capability is unavailable.") from None

    return app


def require_token(received: str | None, expected: str) -> None:
    if received is None or not secrets.compare_digest(received, expected):
        raise HTTPException(status_code=401, detail="Unauthorized.")


def require_active_session(session_gate: SessionGate) -> None:
    try:
        session_gate.require_active()
    except SessionGateError:
        raise HTTPException(status_code=403, detail="Local session gate is inactive.") from None


async def portal_read_command(
    store: RelayStore,
    session_gate: SessionGate,
    session: PortalSession,
    method: str,
    params: dict[str, str],
) -> Any:
    if method not in PORTAL_METHODS:
        raise RuntimeError("Portal attempted an unsupported Workspace method.")
    require_active_session(session_gate)
    command = await store.enqueue(session.agent_id, method, params)
    completed = await store.wait_for_result(command.request_id, PORTAL_COMMAND_TIMEOUT_SECONDS)
    if completed is None or completed.result is None:
        raise HTTPException(status_code=504, detail="Workspace did not answer before the portal request timed out.")
    if completed.result.get("ok") is not True:
        error = completed.result.get("error", "Workspace read failed.")
        raise HTTPException(status_code=502, detail=str(error))
    return completed.result.get("result")


def validate_portal_path(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise HTTPException(status_code=400, detail="Portal path must be Workspace-relative.")
    parts = [part for part in value.replace("\\", "/").split("/") if part and part != "."]
    if any(part == ".." or "\x00" in part for part in parts):
        raise HTTPException(status_code=400, detail="Portal path traversal is not allowed.")
    return "." if not parts else "/".join(parts)


def parent_portal_path(path: str) -> str:
    if path == "." or "/" not in path:
        return "."
    return path.rsplit("/", 1)[0]


def portal_directory_href(capability: str, path: str) -> str:
    if path == ".":
        return f"/r/{quote(capability, safe='')}/"
    return f"/r/{quote(capability, safe='')}/d/{quote(path, safe='/')}"


def portal_directory_entries(capability: str, parent: str, entries: list[Any]) -> str:
    links: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        entry_type = entry.get("type")
        if not isinstance(name, str) or not isinstance(entry_type, str):
            continue
        try:
            child_path = validate_portal_path(name if parent == "." else f"{parent}/{name}")
        except HTTPException:
            continue
        if entry_type == "directory":
            href = portal_directory_href(capability, child_path)
            label = f"{name}/"
        elif entry_type == "file":
            href = f"/r/{quote(capability, safe='')}/f/{quote(child_path, safe='/')}"
            label = name
        else:
            continue
        links.append(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>')
    return "".join(links)


def portal_html_response(title: str, body: str) -> HTMLResponse:
    document = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"robots\" content=\"noindex\">"
        f"<title>{escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:70rem}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#0645ad}</style>"
        f"</head><body><h1>{escape(title)}</h1>{body}</body></html>"
    )
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        },
    )


def validate_agent_id(value: object) -> str:
    if not isinstance(value, str) or not AGENT_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid agent id.")
    return value


def validate_request_id(value: object) -> str:
    if not isinstance(value, str) or not REQUEST_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid request id.")
    return value


def validate_method(value: object) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_METHODS:
        raise HTTPException(status_code=400, detail="Unsupported Workspace method.")
    return value


def command_view(command: RelayCommand) -> dict[str, Any]:
    return {
        "requestId": command.request_id,
        "agentId": command.agent_id,
        "method": command.method,
        "params": command.params,
        "createdAt": command.created_at,
        "status": command.status,
        "result": command.result,
    }


def portal_view(session: PortalSession) -> dict[str, Any]:
    return {
        "capability": session.capability,
        "agentId": session.agent_id,
        "expiresAt": session.expires_at,
        "requestsRemaining": session.requests_remaining,
        "path": f"/r/{session.capability}/",
    }


def main() -> None:
    host = os.environ.get("VSJJONKU_RELAY_BIND_HOST", "127.0.0.1")
    port_text = os.environ.get("VSJJONKU_RELAY_PORT", "8787")
    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("VSJJONKU_RELAY_PORT must be a valid TCP port.") from error
    if not 1024 <= port <= 65535:
        raise ValueError("VSJJONKU_RELAY_PORT must be a valid TCP port.")
    session_gate = SessionGate.from_environment()
    session_gate.start()
    uvicorn.run(create_app(session_gate=session_gate), host=host, port=port, log_level="info")


CONTROL_PAGE = """<!doctype html><meta charset="utf-8"><title>VSJJONKU Relay</title>
<h1>VSJJONKU Relay</h1><p>Private Workspace command queue.</p>
<label>Web token <input id="token" type="password"></label><br>
<label>Agent ID <input id="agent" value="default"></label><br>
<label>Method <select id="method"><option>list_directory</option><option>read_file</option><option>search_code</option><option>git_status</option><option>git_diff</option><option>write_file</option><option>create_directory</option><option>change_file</option><option>delete_file</option><option>delete_directory</option></select></label><br>
<label>Params JSON<br><textarea id="params" rows="10" cols="80">{"path":"."}</textarea></label><br>
<label><input id="confirm" type="checkbox"> Confirm destructive command</label><br><button id="send">Send</button><pre id="output"></pre>
<script>const $=id=>document.getElementById(id);const headers=()=>({'X-VSJJONKU-Web-Token':$('token').value});$('send').onclick=async()=>{try{const body={agentId:$('agent').value,method:$('method').value,params:JSON.parse($('params').value),confirm:$('confirm').checked};let r=await fetch('/api/commands',{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify(body)});let x=await r.json();if(!r.ok)throw new Error(x.detail||'Request failed');const id=x.requestId;const timer=setInterval(async()=>{r=await fetch('/api/commands/'+id,{headers:headers()});x=await r.json();$('output').textContent=JSON.stringify(x,null,2);if(x.result)clearInterval(timer)},1000)}catch(e){$('output').textContent=e.message}};</script>"""


if __name__ == "__main__":
    main()
