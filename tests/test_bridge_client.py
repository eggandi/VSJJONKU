from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import unittest

from vsjjonku_gateway.bridge_client import BridgeClient, BridgeError


TEST_TOKEN = "t" * 32


class _BridgeHandler(BaseHTTPRequestHandler):
    response: dict[str, object] = {"ok": True, "result": {"ready": True}}
    last_request: dict[str, object] | None = None
    last_authorization: str | None = None

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers["Content-Length"])
        type(self).last_request = json.loads(self.rfile.read(size))
        type(self).last_authorization = self.headers.get("Authorization")
        encoded = json.dumps(type(self).response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


class BridgeClientTests(unittest.TestCase):
    def setUp(self) -> None:
        _BridgeHandler.response = {"ok": True, "result": {"ready": True}}
        _BridgeHandler.last_request = None
        _BridgeHandler.last_authorization = None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.client = BridgeClient(
            endpoint=f"http://127.0.0.1:{self.httpd.server_port}/rpc",
            token=TEST_TOKEN,
        )

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.thread.join()
        self.httpd.server_close()

    def test_call_serializes_method_and_params(self) -> None:
        self.assertEqual(self.client.call("read_file", {"path": "README.md"}), {"ready": True})
        self.assertEqual(
            _BridgeHandler.last_request,
            {"method": "read_file", "params": {"path": "README.md"}},
        )
        self.assertEqual(_BridgeHandler.last_authorization, f"Bearer {TEST_TOKEN}")

    def test_call_raises_for_rejected_request(self) -> None:
        _BridgeHandler.response = {"ok": False, "error": "outside workspace"}
        with self.assertRaisesRegex(BridgeError, "outside workspace"):
            self.client.call("read_file", {"path": "../secret"})

    def test_client_rejects_insecure_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            BridgeClient(endpoint="http://gateway.invalid/rpc", token=TEST_TOKEN)
        with self.assertRaisesRegex(ValueError, "32 characters"):
            BridgeClient(endpoint="http://127.0.0.1/rpc", token="short")
