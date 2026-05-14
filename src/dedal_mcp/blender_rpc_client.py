"""RPC client for communicating with a live Blender session.

Handles the TCP connection to the Blender RPC server injected via
blender_rpc.py, and provides the ability to launch Blender with
the RPC script auto-injected.

Protocol matches blender_rpc.py: 4-byte big-endian length prefix framing.
"""

from __future__ import annotations

import os
import socket
import struct
import json
import subprocess
from dataclasses import dataclass

RPC_HOST = "localhost"
RPC_PORT = 8081
RPC_TIMEOUT = 130  # slightly above the 120s server-side timeout
_LENGTH_STRUCT = struct.Struct("!I")

BLENDER_PATH = os.environ.get("BLENDER_PATH", "blender")


@dataclass
class RpcResult:
    """Result of a Blender RPC call."""
    output: str
    error: str | None


class BlenderRpcError(Exception):
    """Raised when the RPC communication fails."""


def launch_blender() -> str:
    """Start Blender GUI with the RPC server injected.

    Returns a status message.  Raises BlenderRpcError on failure.
    """
    # Guard against launching when already listening
    if is_blender_listening():
        return (
            f"Blender RPC is already listening on {RPC_HOST}:{RPC_PORT}. "
            "No new instance started."
        )

    rpc_script = os.path.join(os.path.dirname(__file__), "blender_rpc.py")

    try:
        subprocess.Popen(
            [BLENDER_PATH, "--python", rpc_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise BlenderRpcError(
            f"Blender not found at '{BLENDER_PATH}'. "
            "Set the BLENDER_PATH environment variable."
        )
    except Exception as e:
        raise BlenderRpcError(f"Failed to start Blender: {e}")

    return (
        f"Blender GUI started with RPC server on {RPC_HOST}:{RPC_PORT}. "
        "Wait a few seconds for Blender to finish loading before sending commands."
    )


def is_blender_listening() -> bool:
    """Check whether the Blender RPC port is reachable."""
    try:
        with socket.create_connection((RPC_HOST, RPC_PORT), timeout=1):
            return True
    except OSError:
        return False


def execute_python(code: str) -> RpcResult:
    """Send Python code to the live Blender session and return the result.

    Raises BlenderRpcError if the connection fails.
    """
    payload = json.dumps({"code": code}).encode("utf-8")

    try:
        sock = socket.create_connection((RPC_HOST, RPC_PORT), timeout=RPC_TIMEOUT)
    except ConnectionRefusedError:
        raise BlenderRpcError(
            "Connection refused. Is Blender running with the RPC server? "
            "Call start_blender first."
        )
    except OSError as e:
        raise BlenderRpcError(f"Cannot connect to Blender RPC: {e}")

    try:
        sock.settimeout(RPC_TIMEOUT)

        # Send length-prefixed request
        sock.sendall(_LENGTH_STRUCT.pack(len(payload)) + payload)

        # Receive length-prefixed response
        length_bytes = _recv_exactly(sock, _LENGTH_STRUCT.size)
        response_len = _LENGTH_STRUCT.unpack(length_bytes)[0]
        response_data = _recv_exactly(sock, response_len)

        result = json.loads(response_data.decode("utf-8"))
        return RpcResult(output=result.get("output", ""), error=result.get("error"))

    except socket.timeout:
        raise BlenderRpcError("Blender RPC timed out waiting for response.")
    except Exception as e:
        raise BlenderRpcError(f"RPC communication error: {e}")
    finally:
        sock.close()


def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)
