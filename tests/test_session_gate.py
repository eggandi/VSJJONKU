from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vsjjonku_gateway.session_gate import SessionGate, SessionGateError, configure_lease, renew_lease


class SessionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "session-gate.json"
        self.key = "0427"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_renewal_extends_the_selected_lease(self) -> None:
        configured = configure_lease(self.path, self.key, 1800, now=100.0)
        renewed = renew_lease(self.path, self.key, now=500.0)
        self.assertEqual(configured.expires_at, 1900.0)
        self.assertEqual(renewed.expires_at, 2300.0)
        self.assertEqual(renewed.lease_seconds, 1800)

    def test_rejects_an_incorrect_key(self) -> None:
        configure_lease(self.path, self.key, 3600, now=100.0)
        with self.assertRaisesRegex(SessionGateError, "rejected"):
            renew_lease(self.path, "9999", now=200.0)

    def test_rejects_a_non_numeric_or_non_four_digit_key(self) -> None:
        with self.assertRaisesRegex(SessionGateError, "four digits"):
            configure_lease(self.path, "123", 1800, now=100.0)
        with self.assertRaisesRegex(SessionGateError, "four digits"):
            configure_lease(self.path, "12ab", 1800, now=100.0)

    def test_expiration_invokes_the_shutdown_callback(self) -> None:
        configure_lease(self.path, self.key, 1800, now=100.0)
        expired: list[bool] = []
        gate = SessionGate(self.path, now=lambda: 1900.0, on_expire=lambda: expired.append(True))
        gate.poll_once()
        self.assertEqual(expired, [True])
        self.assertFalse(gate.is_active())
