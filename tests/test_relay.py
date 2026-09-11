from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from vsjjonku_gateway.relay import (
    PortalStore,
    PortalSession,
    RelaySettings,
    RelayStore,
    create_app,
    portal_directory_entries,
    portal_read_command,
)
from vsjjonku_gateway.session_gate import SessionGate


class RelayStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_is_dispatched_and_completed_for_its_agent(self) -> None:
        store = RelayStore()
        command = await store.enqueue("desktop", "list_directory", {"path": "."})

        dispatched = await store.poll("desktop", timeout_seconds=1)

        self.assertIsNotNone(dispatched)
        assert dispatched is not None
        self.assertEqual(dispatched.request_id, command.request_id)
        self.assertEqual(dispatched.status, "dispatched")

        completed = await store.complete(
            "desktop", command.request_id, {"ok": True, "result": []}
        )

        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.result, {"ok": True, "result": []})

    async def test_other_agent_cannot_complete_a_command(self) -> None:
        store = RelayStore()
        command = await store.enqueue("desktop", "git_status", {})

        with self.assertRaises(KeyError):
            await store.complete("other", command.request_id, {"ok": True, "result": {}})

    async def test_portal_read_waits_for_the_workspace_extension_result(self) -> None:
        store = RelayStore()
        session = PortalSession("capability", "desktop", expires_at=9_999_999_999)
        read = asyncio.create_task(
            portal_read_command(
                store,
                SessionGate(None),
                session,
                "read_file",
                {"path": "README.md"},
            )
        )
        command = await store.poll("desktop", timeout_seconds=1)
        assert command is not None
        await store.complete("desktop", command.request_id, {"ok": True, "result": {"content": "hello"}})
        self.assertEqual(await read, {"content": "hello"})


class RelayApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = RelayStore()
        self.client = TestClient(create_app(RelaySettings("w" * 32, "a" * 32), self.store))

    def test_web_command_requires_token_and_returns_agent_result(self) -> None:
        payload = {"agentId": "desktop", "method": "list_directory", "params": {"path": "."}}
        self.assertEqual(self.client.post("/api/commands", json=payload).status_code, 401)

        queued = self.client.post(
            "/api/commands",
            json=payload,
            headers={"X-VSJJONKU-Web-Token": "w" * 32},
        )
        self.assertEqual(queued.status_code, 200)
        request_id = queued.json()["requestId"]

        command = asyncio.run(self.store.poll("desktop", timeout_seconds=1))
        assert command is not None
        completed = self.client.post(
            f"/api/agents/desktop/results/{request_id}",
            json={"ok": True, "result": [{"name": "README.md"}]},
            headers={"X-VSJJONKU-Agent-Token": "a" * 32},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["result"]["ok"], True)

    def test_destructive_command_requires_explicit_confirmation(self) -> None:
        response = self.client.post(
            "/api/commands",
            json={"agentId": "desktop", "method": "delete_file", "params": {"path": "a.txt"}},
            headers={"X-VSJJONKU-Web-Token": "w" * 32},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm", response.json()["detail"])

    def test_portal_creation_requires_web_token_and_is_read_capability_only(self) -> None:
        payload = {"agentId": "desktop", "minutes": 5}
        self.assertEqual(self.client.post("/api/portals", json=payload).status_code, 401)
        created = self.client.post(
            "/api/portals",
            json=payload,
            headers={"X-VSJJONKU-Web-Token": "w" * 32},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["agentId"], "desktop")
        self.assertTrue(created.json()["path"].startswith("/r/"))
        self.assertNotIn("write", created.json())

    def test_portal_directory_is_no_store_html_with_workspace_links(self) -> None:
        created = self.client.post(
            "/api/portals",
            json={"agentId": "desktop", "minutes": 5},
            headers={"X-VSJJONKU-Web-Token": "w" * 32},
        )
        with patch("vsjjonku_gateway.relay.portal_read_command", new=AsyncMock(return_value=[
            {"name": "src", "type": "directory"},
            {"name": "README.md", "type": "file"},
        ])):
            response = self.client.get(created.json()["path"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("README.md", response.text)
        self.assertIn("/d/src", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")


class PortalStoreTests(unittest.TestCase):
    def test_capability_has_a_bounded_request_budget(self) -> None:
        store = PortalStore()
        session = store.create("desktop", 1)
        used = store.use(session.capability)
        self.assertEqual(used.requests_remaining, 199)

    def test_directory_html_skips_unknown_entry_types(self) -> None:
        html = portal_directory_entries(
            "capability",
            ".",
            [
                {"name": "src", "type": "directory"},
                {"name": "README.md", "type": "file"},
                {"name": "socket", "type": "other"},
            ],
        )
        self.assertIn("src/", html)
        self.assertIn("README.md", html)
        self.assertNotIn("socket", html)
