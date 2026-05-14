"""Blender RPC server — injected into Blender at startup via --python.

This script runs inside the Blender process. It starts a TCP server on a
background thread that receives JSON requests containing Python code, then
dispatches execution to Blender's main thread via bpy.app.timers.

Protocol (per connection):
  1. Client connects to localhost:PORT
  2. Client sends a 4-byte big-endian length prefix, then the JSON payload
  3. Server executes the code on the main thread
  4. Server sends a 4-byte big-endian length prefix, then the JSON response
  5. Connection is closed by the server

The length-prefix framing avoids the need for shutdown(SHUT_WR) which
caused half-closed socket issues.
"""

import bpy
import threading
import queue
import socket
import struct
import json
import sys
import io

RPC_PORT = 8081
_LENGTH_STRUCT = struct.Struct("!I")  # 4-byte big-endian unsigned int

_request_queue: queue.Queue = queue.Queue()
_response_queue: queue.Queue = queue.Queue()


def _recv_exactly(conn: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *conn*, or raise ConnectionError."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def _tcp_server_loop() -> None:
    """Background thread: accept connections, enqueue code, return results."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("localhost", RPC_PORT))
        server.listen(1)
        print(f"DedalMCP Blender RPC listening on localhost:{RPC_PORT}...")
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

            # Enqueue for main-thread execution
            _request_queue.put(request["code"])

            # Block until main thread finishes (with timeout)
            try:
                result = _response_queue.get(timeout=120)
            except queue.Empty:
                result = {"output": "", "error": "Execution timed out (120s)"}

            # --- send length-prefixed response ---
            response_bytes = json.dumps(result).encode("utf-8")
            conn.sendall(_LENGTH_STRUCT.pack(len(response_bytes)) + response_bytes)

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
        code = _request_queue.get_nowait()
    except queue.Empty:
        return 0.1

    old_stdout = sys.stdout
    captured = sys.stdout = io.StringIO()

    error = None
    try:
        exec(code, globals())  # noqa: S102 — intentional dynamic execution
    except Exception:
        import traceback
        error = traceback.format_exc()
    finally:
        sys.stdout = old_stdout

    _response_queue.put({
        "output": captured.getvalue(),
        "error": error,
    })

    return 0.1


# ── bootstrap ────────────────────────────────────────────────────────
_thread = threading.Thread(target=_tcp_server_loop, daemon=True)
_thread.start()

if not bpy.app.timers.is_registered(_main_thread_dispatcher):
    bpy.app.timers.register(_main_thread_dispatcher)
