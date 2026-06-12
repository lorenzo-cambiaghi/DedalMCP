"""Blender RPC server — injected into Blender at startup via --python.

This script runs inside the Blender process. It starts a TCP server on a
background thread that receives JSON requests containing Python code, then
dispatches execution to Blender's main thread via bpy.app.timers.

Protocol (per connection):
  1. Client connects to 127.0.0.1:PORT
  2. Client sends a 4-byte big-endian length prefix, then the JSON payload:
     {"token": str, "id": str, "code": str}  — execute code
     {"token": str, "id": str, "ping": true} — handshake / liveness check
  3. Server validates the token, executes the code on the main thread
  4. Server sends a 4-byte big-endian length prefix, then the JSON response:
     {"id": str, "output": str, "error": str|null}        — for code
     {"id": str, "pong": true, "server": "dedal-mcp"}     — for ping
  5. Connection is closed by the server

Port and auth token are passed by the launching client via the
DEDAL_RPC_PORT / DEDAL_RPC_TOKEN environment variables. If no token is
set (e.g. manual launch with `blender --python blender_rpc.py`), auth is
disabled and a warning is printed.

The length-prefix framing avoids the need for shutdown(SHUT_WR) which
caused half-closed socket issues. Request/response pairs carry a
correlation id so a response that arrives after the client gave up
(execution timeout) is discarded instead of being delivered to the
next request.
"""

import bpy
import os
import threading
import queue
import socket
import struct
import json
import sys
import io

RPC_HOST = "127.0.0.1"
RPC_PORT = int(os.environ.get("DEDAL_RPC_PORT", "8081"))
RPC_TOKEN = os.environ.get("DEDAL_RPC_TOKEN", "")
EXEC_TIMEOUT = 120  # seconds the TCP thread waits for the main thread

_LENGTH_STRUCT = struct.Struct("!I")  # 4-byte big-endian unsigned int

_request_queue: queue.Queue = queue.Queue()
_response_queue: queue.Queue = queue.Queue()

# Persistent namespace for executed scripts. Isolated from this module's
# globals so user code can't clobber the RPC machinery, while variables
# still persist between execute_blender_python calls.
_SESSION_NS: dict = {"__name__": "__main__", "bpy": bpy}


def _recv_exactly(conn: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *conn*, or raise ConnectionError."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def _send_response(conn: socket.socket, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    conn.sendall(_LENGTH_STRUCT.pack(len(data)) + data)


def _wait_for_result(request_id: str, timeout: float) -> dict:
    """Wait for the main-thread result matching *request_id*.

    Results with a different id are stale (a previous request that timed
    out client-side and completed later) and are discarded.
    """
    import time
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"output": "", "error": f"Execution timed out ({timeout:.0f}s)"}
        try:
            rid, result = _response_queue.get(timeout=remaining)
        except queue.Empty:
            return {"output": "", "error": f"Execution timed out ({timeout:.0f}s)"}
        if rid == request_id:
            return result
        # stale result from an earlier timed-out request — drop it


def _tcp_server_loop() -> None:
    """Background thread: accept connections, enqueue code, return results."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((RPC_HOST, RPC_PORT))
        server.listen(1)
        print(f"DedalMCP Blender RPC listening on {RPC_HOST}:{RPC_PORT}...")
        if not RPC_TOKEN:
            print("DedalMCP RPC WARNING: no DEDAL_RPC_TOKEN set — "
                  "authentication disabled, any local process can connect.")
    except Exception as e:
        print(f"DedalMCP RPC: failed to bind port {RPC_PORT}: {e}")
        return

    while True:
        conn = None
        try:
            conn, _addr = server.accept()

            # --- read length-prefixed request ---
            length_bytes = _recv_exactly(conn, _LENGTH_STRUCT.size)
            payload_len = _LENGTH_STRUCT.unpack(length_bytes)[0]
            payload = _recv_exactly(conn, payload_len)
            request = json.loads(payload.decode("utf-8"))
            request_id = str(request.get("id", ""))

            # --- auth ---
            if RPC_TOKEN and request.get("token") != RPC_TOKEN:
                _send_response(conn, {
                    "id": request_id,
                    "output": "",
                    "error": "unauthorized: invalid or missing RPC token",
                })
                continue

            # --- handshake ---
            if request.get("ping"):
                _send_response(conn, {
                    "id": request_id,
                    "pong": True,
                    "server": "dedal-mcp",
                })
                continue

            # --- execute on main thread ---
            _request_queue.put((request_id, request["code"]))
            result = _wait_for_result(request_id, EXEC_TIMEOUT)
            _send_response(conn, {"id": request_id, **result})

        except Exception as e:
            print(f"DedalMCP RPC error: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass


def _main_thread_dispatcher() -> float:
    """Called on Blender's main thread via bpy.app.timers.

    Drains one request from the queue, executes it, and puts the result
    back on the response queue.  Returns 0.1 to be called again in 100 ms.
    """
    try:
        request_id, code = _request_queue.get_nowait()
    except queue.Empty:
        return 0.1

    old_stdout = sys.stdout
    captured = sys.stdout = io.StringIO()

    error = None
    try:
        exec(code, _SESSION_NS)  # noqa: S102 — intentional dynamic execution
    except Exception:
        import traceback
        error = traceback.format_exc()
    finally:
        sys.stdout = old_stdout

    _response_queue.put((request_id, {
        "output": captured.getvalue(),
        "error": error,
    }))

    return 0.1


# ── bootstrap ────────────────────────────────────────────────────────
_thread = threading.Thread(target=_tcp_server_loop, daemon=True)
_thread.start()

if not bpy.app.timers.is_registered(_main_thread_dispatcher):
    bpy.app.timers.register(_main_thread_dispatcher)
