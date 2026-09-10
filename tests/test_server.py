from __future__ import annotations

import unittest

from vsjjonku_gateway.server import server


class ServerToolAnnotationTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_annotations_match_workspace_capabilities(self) -> None:
        tools = {tool.name: tool for tool in await server.list_tools()}

        for name in ("list_directory", "read_file", "search_code", "git_status", "git_diff"):
            annotations = tools[name].annotations
            self.assertTrue(annotations.read_only_hint)
            self.assertFalse(annotations.destructive_hint)
            self.assertFalse(annotations.open_world_hint)

        self.assertFalse(tools["write_file"].annotations.read_only_hint)
        self.assertFalse(tools["write_file"].annotations.destructive_hint)
        for name in ("change_file", "delete_file"):
            annotations = tools[name].annotations
            self.assertFalse(annotations.read_only_hint)
            self.assertTrue(annotations.destructive_hint)

