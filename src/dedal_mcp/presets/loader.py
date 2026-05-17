"""Preset discovery and loading.

Scans built-in JSONs bundled with the package, then user directories. Each
file declares ``type`` + ``version``; the loader dispatches to the matching
interpreter registered in ``presets.types``. Custom presets override built-ins
when names collide.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path
from typing import Iterable

from dedal_mcp.presets import types as _types

_BUILTIN_DIR = Path(__file__).parent / "data"
_USER_HOME_DIR = Path.home() / ".dedal" / "presets"
_LOCAL_DIR = Path.cwd() / "dedal_presets"

# Blend file discovery (for geometry_nodes/v1)
_USER_HOME_BLEND_DIR = Path.home() / ".dedal" / "blends"
_LOCAL_BLEND_DIR = Path.cwd() / "dedal_blends"


def _paths_from_env(var: str) -> list[Path]:
    raw = os.environ.get(var)
    if not raw:
        return []
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def _user_paths_from_env() -> list[Path]:
    return _paths_from_env("DEDAL_PRESETS_PATH")


def blend_search_dirs() -> list[Path]:
    """Directories to search for .blend files, in order.
    First match wins (DEDAL_BLENDS_PATH > ~/.dedal/blends/ > ./dedal_blends/)."""
    dirs: list[Path] = []
    dirs.extend(_paths_from_env("DEDAL_BLENDS_PATH"))
    dirs.append(_USER_HOME_BLEND_DIR)
    dirs.append(_LOCAL_BLEND_DIR)
    return dirs


def resolve_blend_path(filename: str) -> Path:
    """Find *filename* (basename only) among the blend search directories.

    Raises FileNotFoundError with a clear message listing where we looked.
    The schema already enforces that *filename* contains no path separators,
    so this is a pure basename lookup — no traversal risk here.
    """
    candidates: list[Path] = []
    for d in blend_search_dirs():
        candidate = d / filename
        candidates.append(candidate)
        if candidate.is_file():
            return candidate
    searched = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Blend file {filename!r} not found. Searched:\n  {searched}"
    )


def _discover() -> Iterable[tuple[str, Path]]:
    """Yield (source_tag, file_path) for every preset JSON discovered.

    Order matters: later entries override earlier ones on name collision.
    """
    seen: set[Path] = set()

    if _BUILTIN_DIR.is_dir():
        try:
            seen.add(_BUILTIN_DIR.resolve())
        except OSError:
            pass
        for path in sorted(_BUILTIN_DIR.glob("*.json")):
            yield "builtin", path

    user_dirs: list[Path] = []
    user_dirs.extend(_user_paths_from_env())
    user_dirs.append(_USER_HOME_DIR)
    user_dirs.append(_LOCAL_DIR)

    for d in user_dirs:
        try:
            d_resolved = d.resolve()
        except OSError:
            continue
        if d_resolved in seen or not d_resolved.is_dir():
            continue
        seen.add(d_resolved)
        for path in sorted(d_resolved.glob("*.json")):
            yield "user", path


def _load_one(path: Path) -> tuple[str, dict]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("preset file must contain a JSON object at the top level")
    for field in ("type", "version", "name"):
        if field not in data:
            raise ValueError(f"missing required field {field!r}")

    interpreter = _types.get(data["type"], int(data["version"]))
    entry = interpreter(data)
    entry["_source"] = str(path)
    return data["name"].lower(), entry


def load_all() -> dict[str, dict]:
    """Discover, parse, and validate all available presets.

    Built-in failures are fatal (they indicate a broken release).
    User-preset failures are warnings (one bad file shouldn't break the server).
    """
    presets: dict[str, dict] = {}
    for source, path in _discover():
        try:
            name, entry = _load_one(path)
        except Exception as e:
            msg = f"Failed to load preset {path}: {type(e).__name__}: {e}"
            if source == "builtin":
                raise RuntimeError(msg) from e
            print(f"DedalMCP: {msg}", file=sys.stderr)
            continue

        if name in presets:
            warnings.warn(
                f"Preset {name!r} from {path} overrides {presets[name]['_source']}",
                stacklevel=2,
            )
        presets[name] = entry

    return presets
