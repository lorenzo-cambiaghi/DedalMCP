"""Render config schema + discovery.

A ``render_config/v1`` JSON declares a Blender render job: source scene
(.blend or live RPC), camera, resolution/samples/engine overrides, list of
passes, output directory.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


_VALID_PASSES = {
    "combined", "depth", "normal", "mist", "ao",
    "position", "object_id", "edges",
}
_VALID_ENGINES = {"CYCLES", "EEVEE_NEXT", "WORKBENCH"}
_BLEND_FILENAME_RE = re.compile(r"^[\w.\-]+\.blend$")

_USER_HOME_DIR = Path.home() / ".dedal" / "renders"
_LOCAL_DIR = Path.cwd() / "dedal_renders"


class RenderConfigError(ValueError):
    """Raised when a render_config/v1 JSON is malformed."""


@dataclass
class RenderConfig:
    name: str
    passes: list[str]
    description: str = ""
    scene: str | None = None          # None → use live RPC session
    camera: str | None = None
    resolution: tuple[int, int] | None = None
    samples: int | None = None
    engine: str | None = None
    denoise: bool | None = None
    output_dir: str = "renders/"
    frame: int | None = None
    _source: str | None = field(default=None, repr=False)

    def merged_with(self, overrides: dict) -> "RenderConfig":
        """Return a copy with the given overrides applied (only known fields)."""
        data = self.__dict__.copy()
        data.pop("_source", None)
        for k, v in overrides.items():
            if k in data and v is not None:
                if k == "resolution" and isinstance(v, list):
                    v = tuple(v)
                data[k] = v
        # Re-validate the merged config
        return _validate_dict({
            **{k: v for k, v in data.items() if v is not None},
            "type": "render_config",
            "version": 1,
        })


def _paths_from_env(var: str) -> list[Path]:
    raw = os.environ.get(var)
    if not raw:
        return []
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def _discover() -> Iterable[tuple[str, Path]]:
    """Yield (source_tag, file_path) for every render_config JSON discovered."""
    seen: set[Path] = set()
    dirs: list[Path] = []
    dirs.extend(_paths_from_env("DEDAL_RENDERS_PATH"))
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


def _validate_dict(data: dict) -> RenderConfig:
    if not isinstance(data, dict):
        raise RenderConfigError("render config must be a JSON object")

    for f in ("type", "version", "name", "passes"):
        if f not in data:
            raise RenderConfigError(f"missing required field {f!r}")
    if data["type"] != "render_config":
        raise RenderConfigError(f"expected type 'render_config', got {data['type']!r}")
    if int(data["version"]) != 1:
        raise RenderConfigError(f"unknown version {data['version']!r} (only 1 supported)")

    passes = data["passes"]
    if not isinstance(passes, list) or not passes:
        raise RenderConfigError("'passes' must be a non-empty list")
    unknown = set(passes) - _VALID_PASSES
    if unknown:
        raise RenderConfigError(
            f"unknown passes {sorted(unknown)}. Valid: {sorted(_VALID_PASSES)}"
        )

    scene = data.get("scene")
    if scene is not None:
        if not isinstance(scene, str) or not _BLEND_FILENAME_RE.match(scene):
            raise RenderConfigError(
                f"'scene' must be a bare .blend filename (no path/spaces), got {scene!r}"
            )

    res = data.get("resolution")
    if res is not None:
        if not (isinstance(res, (list, tuple)) and len(res) == 2 and all(isinstance(x, int) and x > 0 for x in res)):
            raise RenderConfigError(f"'resolution' must be [width, height] of positive ints, got {res!r}")

    eng = data.get("engine")
    if eng is not None and eng not in _VALID_ENGINES:
        raise RenderConfigError(f"'engine' must be one of {sorted(_VALID_ENGINES)}, got {eng!r}")

    samples = data.get("samples")
    if samples is not None and (not isinstance(samples, int) or samples <= 0):
        raise RenderConfigError(f"'samples' must be a positive int, got {samples!r}")

    frame = data.get("frame")
    if frame is not None and not isinstance(frame, int):
        raise RenderConfigError(f"'frame' must be an int, got {frame!r}")

    denoise = data.get("denoise")
    if denoise is not None and not isinstance(denoise, bool):
        raise RenderConfigError(f"'denoise' must be bool, got {denoise!r}")

    output_dir = data.get("output_dir", "renders/")
    if not isinstance(output_dir, str):
        raise RenderConfigError(f"'output_dir' must be a string")

    return RenderConfig(
        name=str(data["name"]).lower(),
        passes=list(passes),
        description=data.get("description", ""),
        scene=scene,
        camera=data.get("camera"),
        resolution=tuple(res) if res else None,
        samples=samples,
        engine=eng,
        denoise=denoise,
        output_dir=output_dir,
        frame=frame,
    )


_CACHE: dict[str, RenderConfig] | None = None


def _load_all() -> dict[str, RenderConfig]:
    out: dict[str, RenderConfig] = {}
    for _src, path in _discover():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cfg = _validate_dict(data)
            cfg._source = str(path)
            if cfg.name in out:
                print(
                    f"DedalMCP: render config {cfg.name!r} from {path} overrides {out[cfg.name]._source}",
                    file=sys.stderr,
                )
            out[cfg.name] = cfg
        except Exception as e:
            print(
                f"DedalMCP: Failed to load render config {path}: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
    return out


def load_render_config(name_or_inline) -> RenderConfig:
    """Resolve a render config from name (looks up in discovery dirs) or inline dict.

    Discovery is cached on first call; pass an inline dict to bypass.
    """
    if isinstance(name_or_inline, dict):
        return _validate_dict(name_or_inline)

    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    name = str(name_or_inline).lower()
    if name not in _CACHE:
        known = sorted(_CACHE)
        raise RenderConfigError(
            f"Unknown render config {name!r}. Known: {known or '[]'}"
        )
    return _CACHE[name]


def list_render_configs() -> list[dict]:
    """Return a summary list of all discovered render configs."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    return [
        {
            "name": cfg.name,
            "description": cfg.description,
            "passes": cfg.passes,
            "scene": cfg.scene or "<live>",
        }
        for cfg in _CACHE.values()
    ]


def _reset_cache() -> None:
    """Test helper: clear the discovery cache so env var changes take effect."""
    global _CACHE
    _CACHE = None
