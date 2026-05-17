"""Load ComfyUI API-format workflows and inject AI-provided inputs by node title.

Convention: the user renames target nodes in ComfyUI before exporting (right
click → Properties → Title):

    LoadImage         titled  DEDAL_INPUT_IMAGE  (or DEDAL_INPUT_DEPTH, …)
    CLIPTextEncode    titled  DEDAL_PROMPT       (or DEDAL_PROMPT_NEGATIVE, …)
    KSampler          titled  DEDAL_SEED
    SaveImage         titled  DEDAL_OUTPUT       (or DEDAL_OUTPUT_*)

This module does not assume the structure of any specific workflow — it just
walks the node dict looking for these titles, then writes into the matching
input field (chosen based on the node's ``class_type``).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterable

_USER_HOME_DIR = Path.home() / ".dedal" / "workflows"
_LOCAL_DIR = Path.cwd() / "dedal_workflows"


# Maps node class_type → list of field names that hold the writable value(s)
# for each well-known input type. Used to translate a DEDAL_* title into the
# right input slot on the node.
_CLASS_TO_FIELD = {
    "LoadImage":      ["image"],
    "CLIPTextEncode": ["text"],
    "KSampler":       ["seed"],
    "KSamplerAdvanced": ["noise_seed"],
}


class WorkflowError(ValueError):
    """Raised on workflow load / structure errors."""


def _paths_from_env(var: str) -> list[Path]:
    raw = os.environ.get(var)
    if not raw:
        return []
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def _discover() -> Iterable[tuple[str, Path]]:
    seen: set[Path] = set()
    dirs: list[Path] = []
    dirs.extend(_paths_from_env("DEDAL_WORKFLOWS_PATH"))
    dirs.append(_USER_HOME_DIR)
    dirs.append(_LOCAL_DIR)
    for d in dirs:
        try:
            r = d.resolve()
        except OSError:
            continue
        if r in seen or not r.is_dir():
            continue
        seen.add(r)
        for path in sorted(r.glob("*.json")):
            yield "user", path


_CACHE: dict[str, dict] | None = None


def _node_title(node: dict) -> str | None:
    """Return the user-set title for a node, or None if it has only the default."""
    meta = node.get("_meta")
    if isinstance(meta, dict):
        title = meta.get("title")
        if title and isinstance(title, str):
            return title
    return None


def _load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for _src, path in _discover():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise WorkflowError("workflow must be a JSON object (API format)")
            # ComfyUI API workflow: top-level keys are stringified node IDs
            # with values like {"class_type": "...", "inputs": {...}, "_meta": {"title": "..."}}
            for nid, node in data.items():
                if not isinstance(node, dict) or "class_type" not in node:
                    raise WorkflowError(
                        f"node {nid!r} doesn't look like an API-format workflow node "
                        f"(missing 'class_type'). Did you export as 'API Format'?"
                    )
            name = path.stem.lower()
            if name in out:
                print(
                    f"DedalMCP: workflow {name!r} from {path} overrides earlier definition",
                    file=sys.stderr,
                )
            out[name] = data
        except Exception as e:
            print(
                f"DedalMCP: Failed to load workflow {path}: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
    return out


def load_workflow(name_or_inline) -> dict:
    """Return a workflow dict; ``name_or_inline`` is either a discovered name or a literal dict.

    The returned dict is a deep-copy-safe representation suitable for mutation
    via ``inject_inputs``.
    """
    if isinstance(name_or_inline, dict):
        # Caller may want to mutate without affecting the registry — copy via JSON roundtrip
        return json.loads(json.dumps(name_or_inline))

    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    key = str(name_or_inline).lower()
    if key not in _CACHE:
        known = sorted(_CACHE)
        raise WorkflowError(f"Unknown workflow {key!r}. Known: {known or '[]'}")
    return json.loads(json.dumps(_CACHE[key]))


def list_workflows() -> list[dict]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    return [
        {
            "name": name,
            "nodes": len(wf),
            "dedal_titles": sorted({_node_title(n) for n in wf.values()
                                     if (_node_title(n) or "").startswith("DEDAL_")}),
        }
        for name, wf in _CACHE.items()
    ]


def inject_inputs(workflow: dict, inputs: dict[str, object]) -> list[str]:
    """Mutate *workflow* in place: for each (title → value) pair in *inputs*,
    find a node with that title and write the value into its primary input field.

    Returns a list of warnings (titles not found, etc.).
    """
    warnings: list[str] = []
    titles_to_nodes: dict[str, list[tuple[str, dict]]] = {}
    for nid, node in workflow.items():
        t = _node_title(node)
        if t:
            titles_to_nodes.setdefault(t, []).append((nid, node))

    for title, value in inputs.items():
        nodes = titles_to_nodes.get(title)
        if not nodes:
            warnings.append(f"No node found with title {title!r}")
            continue
        if len(nodes) > 1:
            warnings.append(f"Multiple nodes have title {title!r}; updating all")
        for nid, node in nodes:
            class_type = node.get("class_type")
            fields = _CLASS_TO_FIELD.get(class_type)
            if not fields:
                warnings.append(
                    f"Node {nid!r} (title {title!r}) has unsupported class_type {class_type!r}; "
                    f"known types: {sorted(_CLASS_TO_FIELD)}"
                )
                continue
            node.setdefault("inputs", {})
            # Image inputs from upload come as {"name": "...", "subfolder": "...", "type": "input"}
            # ComfyUI expects either just the filename or "subfolder/filename" for LoadImage
            if class_type == "LoadImage" and isinstance(value, dict) and "name" in value:
                sub = value.get("subfolder") or ""
                fn = value["name"]
                node["inputs"][fields[0]] = f"{sub}/{fn}" if sub else fn
            else:
                node["inputs"][fields[0]] = value
    return warnings


def find_output_nodes(workflow: dict) -> list[tuple[str, dict]]:
    """Return (node_id, node) for every node titled DEDAL_OUTPUT* (or class SaveImage)."""
    out: list[tuple[str, dict]] = []
    for nid, node in workflow.items():
        title = _node_title(node) or ""
        if title.startswith("DEDAL_OUTPUT") or node.get("class_type") == "SaveImage":
            out.append((nid, node))
    return out


def _reset_cache() -> None:
    """Test helper."""
    global _CACHE
    _CACHE = None
