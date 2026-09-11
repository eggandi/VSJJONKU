from __future__ import annotations

import unittest

from vsjjonku_gateway.local_agent import (
    CommandDecision,
    FinalDecision,
    LocalAgentError,
    parse_decision,
    require_loopback_base_url,
    run_task,
)


class FakeModel:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = iter(outputs)

    def complete(self, _messages: list[dict[str, str]]) -> str:
        return next(self.outputs)


class FakeRelay:
    def __init__(self) -> None:
        self.commands: list[tuple[CommandDecision, bool]] = []

    def enqueue(self, decision: CommandDecision, *, confirm: bool) -> dict[str, str]:
        self.commands.append((decision, confirm))
        return {"requestId": "a" * 32}

    def get_command(self, _request_id: str) -> dict[str, object]:
        return {"result": {"ok": True, "result": [{"name": "README.md"}]}}


class LocalAgentTests(unittest.TestCase):
    def test_parses_only_supported_commands_or_final_response(self) -> None:
        command = parse_decision('{"method":"read_file","params":{"path":"README.md"}}')
        self.assertEqual(command, CommandDecision("read_file", {"path": "README.md"}))
        self.assertEqual(parse_decision('{"final":"Done"}'), FinalDecision("Done"))
        with self.assertRaises(LocalAgentError):
            parse_decision('{"method":"exec","params":{}}')

    def test_rejects_non_loopback_services(self) -> None:
        self.assertEqual(require_loopback_base_url("http://localhost:1234/v1", "Model"), "http://localhost:1234/v1")
        with self.assertRaises(ValueError):
            require_loopback_base_url("https://example.com/v1", "Model")

    def test_runs_one_safe_command_then_returns_final_response(self) -> None:
        relay = FakeRelay()
        output: list[str] = []
        result = run_task(
            "Inspect the project.",
            FakeModel([
                '{"method":"list_directory","params":{"path":"."}}',
                '{"final":"Workspace inspected."}',
            ]),
            relay,
            confirm=lambda _command: False,
            output=output.append,
        )
        self.assertEqual(result, "Workspace inspected.")
        self.assertEqual(relay.commands, [(CommandDecision("list_directory", {"path": "."}), False)])

    def test_requires_local_confirmation_for_destructive_commands(self) -> None:
        with self.assertRaisesRegex(LocalAgentError, "declined"):
            run_task(
                "Delete a file.",
                FakeModel(['{"method":"delete_file","params":{"path":"old.txt"}}']),
                FakeRelay(),
                confirm=lambda _command: False,
                output=lambda _text: None,
            )
