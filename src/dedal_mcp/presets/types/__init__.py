"""Type registry for preset interpreters.

Each preset JSON declares a ``type`` + ``version`` pair. The loader looks up
the matching interpreter here and delegates parsing/validation to it.

To register a new type, create a module that calls ``register(...)`` at import
time and import it from this package's ``__init__``.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple

# An interpreter takes the parsed JSON dict and returns a preset entry:
#   {"description": str, "default_colors": dict, "category": str,
#    "builder": Callable[[str, dict, dict], str]}
Interpreter = Callable[[dict], dict]


class UnknownTypeError(KeyError):
    """Raised when a preset declares a (type, version) we don't know."""


_REGISTRY: Dict[Tuple[str, int], Interpreter] = {}


def register(type_name: str, version: int, interpreter: Interpreter) -> None:
    key = (type_name, version)
    if key in _REGISTRY:
        raise ValueError(f"Type {type_name} v{version} already registered")
    _REGISTRY[key] = interpreter


def get(type_name: str, version: int) -> Interpreter:
    try:
        return _REGISTRY[(type_name, version)]
    except KeyError:
        known = sorted(f"{t}/v{v}" for t, v in _REGISTRY)
        raise UnknownTypeError(
            f"Unknown preset type {type_name!r} v{version}. Known: {', '.join(known)}"
        )


def known_types() -> list[tuple[str, int]]:
    return sorted(_REGISTRY)


# Built-in types — importing the modules triggers self-registration.
from dedal_mcp.presets.types import composite as _composite  # noqa: F401,E402
from dedal_mcp.presets.types import script_template as _script_template  # noqa: F401,E402
from dedal_mcp.presets.types import mesh_data as _mesh_data  # noqa: F401,E402
from dedal_mcp.presets.types import geometry_nodes as _geometry_nodes  # noqa: F401,E402
