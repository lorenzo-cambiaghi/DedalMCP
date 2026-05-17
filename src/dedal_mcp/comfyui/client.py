"""Minimal HTTP client for ComfyUI's REST API. Uses only the Python standard
library so DedalMCP keeps a dependency-free footprint.

ComfyUI endpoints used:
    POST /prompt                  submit a workflow, returns {"prompt_id": "..."}
    GET  /history/{prompt_id}     check completion status + result metadata
    POST /upload/image            multipart upload, returns {"name": "...", "subfolder": "..."}
    GET  /view?filename=...&subfolder=...&type=output    fetch a generated image
"""

from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


DEFAULT_SERVER = os.environ.get("DEDAL_COMFYUI_URL", "http://localhost:8188")


class ComfyError(RuntimeError):
    """Raised on any ComfyUI client failure (network, server, timeout)."""


def _http_request(method: str, url: str, data: bytes | None = None, headers: dict | None = None,
                  timeout: float = 30.0) -> bytes:
    """Wrap urllib with friendly error messages."""
    try:
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    except ValueError as e:
        # urllib raises ValueError on malformed URL (e.g. missing scheme)
        raise ComfyError(f"Invalid ComfyUI URL {url!r}: {e}") from e
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise ComfyError(f"ComfyUI HTTP {e.code} on {method} {url}: {body[:300]}") from e
    except urllib.error.URLError as e:
        raise ComfyError(f"Cannot reach ComfyUI at {url}: {e.reason}") from e
    except ValueError as e:
        # urlopen also raises ValueError for unknown URL types ("not-a-url")
        raise ComfyError(f"Invalid ComfyUI URL {url!r}: {e}") from e
    except (TimeoutError, OSError) as e:
        raise ComfyError(f"ComfyUI request to {url} failed: {e}") from e


def submit_prompt(workflow: dict, server: str = DEFAULT_SERVER, client_id: str | None = None) -> str:
    """POST a workflow to /prompt. Returns the prompt_id."""
    payload = {
        "prompt": workflow,
        "client_id": client_id or str(uuid.uuid4()),
    }
    body = json.dumps(payload).encode("utf-8")
    raw = _http_request(
        "POST", f"{server}/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ComfyError(f"Invalid JSON in /prompt response: {raw[:200]!r}") from e
    if "prompt_id" not in resp:
        raise ComfyError(f"/prompt response missing 'prompt_id': {resp}")
    return resp["prompt_id"]


def poll_history(prompt_id: str, server: str = DEFAULT_SERVER, timeout: int = 1800,
                 interval: float = 1.0) -> dict:
    """Poll /history/{prompt_id} until the entry appears with status info.
    Returns the prompt's history record (dict). Raises ComfyError on timeout."""
    deadline = time.monotonic() + timeout
    url = f"{server}/history/{urllib.parse.quote(prompt_id)}"
    while time.monotonic() < deadline:
        raw = _http_request("GET", url, timeout=10)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ComfyError(f"Invalid JSON in /history response: {raw[:200]!r}") from e
        if prompt_id in data and data[prompt_id].get("status", {}).get("completed", False):
            return data[prompt_id]
        # Some ComfyUI versions return without 'completed' until done; entry simply absent until then.
        time.sleep(interval)
    raise ComfyError(
        f"Workflow {prompt_id!r} did not complete within {timeout}s "
        f"(may still be running on the server)"
    )


def upload_image(image_path: str | Path, server: str = DEFAULT_SERVER,
                 subfolder: str = "", overwrite: bool = True) -> dict:
    """POST /upload/image multipart. Returns {"name": "...", "subfolder": "...", "type": "input"}."""
    path = Path(image_path)
    if not path.is_file():
        raise ComfyError(f"Image not found: {path}")

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    boundary = "----DedalMCP" + uuid.uuid4().hex
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    def add_file(name: str, filename: str, content: bytes, content_type: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")

    add_field("type", "input")
    if subfolder:
        add_field("subfolder", subfolder)
    if overwrite:
        add_field("overwrite", "true")
    add_file("image", path.name, path.read_bytes(), mime)
    body.extend(f"--{boundary}--\r\n".encode())

    raw = _http_request(
        "POST", f"{server}/upload/image",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=60,
    )
    try:
        resp = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ComfyError(f"Invalid JSON in /upload/image response: {raw[:200]!r}") from e
    return {
        "name": resp.get("name", path.name),
        "subfolder": resp.get("subfolder", subfolder),
        "type": resp.get("type", "input"),
    }


def fetch_output(filename: str, subfolder: str, type_: str, dest: str | Path,
                 server: str = DEFAULT_SERVER) -> Path:
    """GET /view?filename=&subfolder=&type= → write content to *dest*."""
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
    url = f"{server}/view?{qs}"
    content = _http_request("GET", url, timeout=120)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)
    return dest_path
