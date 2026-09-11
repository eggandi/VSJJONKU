from __future__ import annotations

import asyncio
import unittest

from fastapi.testclient import TestClient

from vsjjonku_gateway.relay import RelaySettings, RelayStore, create_app


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
