"""RPC client for communicating with a live Blender session.

Handles the TCP connection to the Blender RPC server injected via
blender_rpc.py, and provides the ability to launch Blender with
the RPC script auto-injected.

Security model: at launch time the client picks a free localhost port
and generates a random session token. Both are handed to the Blender
process via environment variables (DEDAL_RPC_PORT / DEDAL_RPC_TOKEN)
and persisted to ~/.dedal/rpc_session.json so a restarted MCP server
can reconnect to a still-running Blender. Every request carries the
token; the Blender-side server rejects requests without it. A ping
handshake verifies that whatever is listening on the port is actually
our RPC server and not an unrelated local service.

Protocol matches blender_rpc.py: 4-byte big-endian length prefix framing,
JSON payloads with a correlation id.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

RPC_HOST = "127.0.0.1"
RPC_TIMEOUT = 130  # slightly above the 120s server-side timeout
_LENGTH_STRUCT = struct.Struct("!I")

BLENDER_PATH = os.environ.get("BLENDER_PATH", "blender")
# Seconds to wait for Blender to come up after launch (GUI + addons can be slow)
START_TIMEOUT = int(os.environ.get("DEDAL_BLENDER_START_TIMEOUT", "60"))

_SESSION_FILE = Path.home() / ".dedal" / "rpc_session.json"


@dataclass
class RpcResult:
    """Result of a Blender RPC call."""
    output: str
    error: str | None


class BlenderRpcError(Exception):
    """Raised when the RPC communication fails."""


# ── session persistence ──────────────────────────────────────────────

def _load_session() -> dict | None:
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "port" in data and "token" in data:
            return data
    except (OSError, ValueError):
        pass
    return None


def _save_session(port: int, token: str, pid: int) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(
        json.dumps({"port": port, "token": token, "pid": pid}),
        encoding="utf-8",
    )


def _pick_free_port() -> int:
    """Honor a fixed DEDAL_RPC_PORT if set, otherwise let the OS pick one."""
    fixed = os.environ.get("DEDAL_RPC_PORT")
    if fixed:
        return int(fixed)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((RPC_HOST, 0))
        return s.getsockname()[1]


# ── wire protocol ────────────────────────────────────────────────────

def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def _roundtrip(port: int, request: dict, timeout: float) -> dict:
    """Send one length-prefixed JSON request and return the JSON response."""
    payload = json.dumps(request).encode("utf-8")
    with socket.create_connection((RPC_HOST, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(_LENGTH_STRUCT.pack(len(payload)) + payload)
        length_bytes = _recv_exactly(sock, _LENGTH_STRUCT.size)
        response_len = _LENGTH_STRUCT.unpack(length_bytes)[0]
        response_data = _recv_exactly(sock, response_len)
    return json.loads(response_data.decode("utf-8"))


def _ping(port: int, token: str, timeout: float = 2.0) -> bool:
    """True if our RPC server (not some unrelated service) answers on *port*."""
    try:
        response = _roundtrip(
            port,
            {"token": token, "id": str(uuid.uuid4()), "ping": True},
            timeout,
        )
        return response.get("pong") is True and response.get("server") == "dedal-mcp"
    except (OSError, ValueError):
        return False


# ── public API ───────────────────────────────────────────────────────

def is_blender_listening() -> bool:
    """Check whether a live Blender RPC session from this machine is reachable."""
    session = _load_session()
    if session is None:
        return False
    return _ping(session["port"], session["token"])


def launch_blender() -> str:
    """Start Blender GUI with the RPC server injected.

    Picks a free port, generates a session token, launches Blender with
    both in its environment, and polls until the RPC server answers the
    handshake (or START_TIMEOUT elapses).

    Returns a status message.  Raises BlenderRpcError on failure.
    """
    session = _load_session()
    if session is not None and _ping(session["port"], session["token"]):
        return (
            f"Blender RPC is already listening on {RPC_HOST}:{session['port']}. "
            "No new instance started."
        )

    port = _pick_free_port()
    token = secrets.token_hex(16)
    rpc_script = os.path.join(os.path.dirname(__file__), "blender_rpc.py")

    env = dict(os.environ)
    env["DEDAL_RPC_PORT"] = str(port)
    env["DEDAL_RPC_TOKEN"] = token

    try:
        proc = subprocess.Popen(
            [BLENDER_PATH, "--python", rpc_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except FileNotFoundError:
        raise BlenderRpcError(
            f"Blender not found at '{BLENDER_PATH}'. "
            "Set the BLENDER_PATH environment variable."
        )
    except Exception as e:
        raise BlenderRpcError(f"Failed to start Blender: {e}")

    _save_session(port, token, proc.pid)

    # Poll until the RPC server is actually ready, so the first
    # execute_blender_python call never hits "connection refused".
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise BlenderRpcError(
                f"Blender exited immediately (code {proc.returncode}). "
                "Check that BLENDER_PATH points to a working Blender 4.2+ executable."
            )
        if _ping(port, token):
            return (
                f"Blender GUI started, RPC server ready on {RPC_HOST}:{port}."
            )
        time.sleep(0.5)

    return (
        f"Blender was started (pid {proc.pid}) but the RPC server did not "
        f"respond within {START_TIMEOUT}s. It may still be loading — "
        "retry in a few seconds."
    )


def execute_python(code: str) -> RpcResult:
    """Send Python code to the live Blender session and return the result.

    Raises BlenderRpcError if the connection fails.
    """
    session = _load_session()
    if session is None:
        raise BlenderRpcError(
            "No Blender RPC session found. Call start_blender first."
        )

    request = {
        "token": session["token"],
        "id": str(uuid.uuid4()),
        "code": code,
    }

    try:
        response = _roundtrip(session["port"], request, RPC_TIMEOUT)
    except ConnectionRefusedError:
        raise BlenderRpcError(
            "Connection refused. Is Blender running with the RPC server? "
            "Call start_blender first."
        )
    except socket.timeout:
        raise BlenderRpcError("Blender RPC timed out waiting for response.")
    except OSError as e:
        raise BlenderRpcError(f"Cannot connect to Blender RPC: {e}")
    except ValueError as e:
        raise BlenderRpcError(f"Malformed RPC response: {e}")

    error = response.get("error")
    if error == "unauthorized: invalid or missing RPC token":
        raise BlenderRpcError(
            "RPC token rejected. The running Blender belongs to another "
            "session — close it and call start_blender again."
        )
    return RpcResult(output=response.get("output", ""), error=error)
