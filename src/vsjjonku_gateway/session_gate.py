"""Local, time-limited session-key gate for the MCP Gateway."""

from __future__ import annotations

import argparse
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from threading import Event, Lock, Thread
from time import time
from typing import Callable
import re


ALLOWED_LEASE_SECONDS = frozenset({30 * 60, 60 * 60})
SESSION_KEY_PATTERN = re.compile(r"^[0-9]{4}$")


class SessionGateError(RuntimeError):
    """The local session-key gate is unavailable, expired, or rejected a key."""


@dataclass(frozen=True)
class LeaseConfig:
    """Persisted non-secret configuration for a local session-key lease."""

    salt: bytes
    key_hash: bytes
    lease_seconds: int
    expires_at: float

    @classmethod
    def load(cls, path: Path) -> "LeaseConfig":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SessionGateError("Session gate configuration is unavailable.") from error

        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise SessionGateError("Session gate configuration is invalid.")
        try:
            salt = b64decode(raw["salt"], validate=True)
            key_hash = b64decode(raw["key_hash"], validate=True)
            lease_seconds = int(raw["lease_seconds"])
            expires_at = float(raw["expires_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise SessionGateError("Session gate configuration is invalid.") from error
        if len(salt) != 16 or len(key_hash) != 32 or lease_seconds not in ALLOWED_LEASE_SECONDS:
            raise SessionGateError("Session gate configuration is invalid.")
        return cls(salt=salt, key_hash=key_hash, lease_seconds=lease_seconds, expires_at=expires_at)

    def with_expiry(self, now: float) -> "LeaseConfig":
        return LeaseConfig(
            salt=self.salt,
            key_hash=self.key_hash,
            lease_seconds=self.lease_seconds,
            expires_at=now + self.lease_seconds,
        )

    def to_json(self) -> bytes:
        return json.dumps(
            {
                "version": 1,
                "salt": b64encode(self.salt).decode("ascii"),
                "key_hash": b64encode(self.key_hash).decode("ascii"),
                "lease_seconds": self.lease_seconds,
                "expires_at": self.expires_at,
            },
            separators=(",", ":"),
        ).encode("utf-8")


def _derive_key_hash(key: str, salt: bytes) -> bytes:
    return hashlib.scrypt(key.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _require_session_key(key: str) -> None:
    if not SESSION_KEY_PATTERN.fullmatch(key):
        raise SessionGateError("Session key must be exactly four digits.")


def _write_config(path: Path, config: LeaseConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    try:
        handle.write(config.to_json())
        handle.flush()
        handle.close()
        os.replace(handle.name, path)
    finally:
        if not handle.closed:
            handle.close()
        temporary_path = Path(handle.name)
        if temporary_path.exists():
            temporary_path.unlink()


def configure_lease(path: Path, key: str, lease_seconds: int, now: float | None = None) -> LeaseConfig:
    """Create a new gate configuration and issue its first lease."""

    if lease_seconds not in ALLOWED_LEASE_SECONDS:
        raise SessionGateError("Lease duration must be 1800 or 3600 seconds.")
    _require_session_key(key)
    now = time() if now is None else now
    salt = secrets.token_bytes(16)
    config = LeaseConfig(salt, _derive_key_hash(key, salt), lease_seconds, now + lease_seconds)
    _write_config(path, config)
    return config


def renew_lease(path: Path, key: str, now: float | None = None) -> LeaseConfig:
    """Verify a local key and extend the existing gateway lease."""

    config = LeaseConfig.load(path)
    candidate = _derive_key_hash(key, config.salt)
    if not hmac.compare_digest(candidate, config.key_hash):
        raise SessionGateError("Session key was rejected.")
    renewed = config.with_expiry(time() if now is None else now)
    _write_config(path, renewed)
    return renewed


def _format_expiry(expires_at: float) -> str:
    return datetime.fromtimestamp(expires_at, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


class SessionGate:
    """Watch an optional local lease file and terminate the Gateway at expiry."""

    def __init__(self, config_path: Path | None, *, now: Callable[[], float] = time, on_expire: Callable[[], None] | None = None) -> None:
        self._config_path = config_path
        self._now = now
        self._on_expire = on_expire or (lambda: os._exit(75))
        self._expired = Event()
        self._stopped = Event()
        self._lock = Lock()

    @classmethod
    def from_environment(cls) -> "SessionGate":
        value = os.environ.get("VSJJONKU_SESSION_GATE_PATH", "")
        if not value:
            return cls(None)
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("VSJJONKU_SESSION_GATE_PATH must be an absolute path.")
        return cls(path)

    @property
    def enabled(self) -> bool:
        return self._config_path is not None

    def is_active(self) -> bool:
        if not self.enabled:
            return True
        if self._expired.is_set():
            return False
        return LeaseConfig.load(self._config_path).expires_at > self._now()

    def require_active(self) -> None:
        if not self.is_active():
            self._expire()
            raise SessionGateError("Session key lease expired; Gateway is shutting down.")

    def start(self) -> None:
        if not self.enabled:
            return
        self.require_active()
        Thread(target=self._watch, name="vsjjonku-session-gate", daemon=True).start()

    def stop(self) -> None:
        self._stopped.set()

    def poll_once(self) -> None:
        if self.enabled and not self.is_active():
            self._expire()

    def _watch(self) -> None:
        while not self._stopped.is_set() and not self._expired.is_set():
            self.poll_once()
            self._stopped.wait(timeout=1.0)

    def _expire(self) -> None:
        with self._lock:
            if self._expired.is_set():
                return
            self._expired.set()
            self._on_expire()


def _absolute_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("Path must be absolute.")
    return path


def _read_new_key() -> str:
    key = getpass("Set session key: ")
    if key != getpass("Confirm session key: "):
        raise SessionGateError("Session key confirmation does not match.")
    return key


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a VSJJONKU local session-key lease.")
    commands = parser.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure", help="Create a 30 or 60 minute session-key lease.")
    configure.add_argument("--path", required=True, type=_absolute_path)
    configure.add_argument("--minutes", required=True, type=int, choices=(30, 60))
    renew = commands.add_parser("renew", help="Re-enter the key and renew the lease.")
    renew.add_argument("--path", required=True, type=_absolute_path)
    status = commands.add_parser("status", help="Show lease state without revealing the key.")
    status.add_argument("--path", required=True, type=_absolute_path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    try:
        if args.command == "configure":
            config = configure_lease(args.path, _read_new_key(), args.minutes * 60)
            print(f"Session gate configured; it expires at {_format_expiry(config.expires_at)}.")
        elif args.command == "renew":
            config = renew_lease(args.path, getpass("Session key: "))
            print(f"Session gate renewed; it expires at {_format_expiry(config.expires_at)}.")
        else:
            config = LeaseConfig.load(args.path)
            status = "active" if config.expires_at > time() else "expired"
            print(f"Session gate is {status}; expiry {_format_expiry(config.expires_at)}.")
    except SessionGateError as error:
        print(f"Session gate error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
