"""arcgis_mcp.registry — declarative ToolSpec registry (the scale mechanism).

One hundred tools cannot mean one hundred FastMCP wrappers plus one hundred
worker handlers. Instead each tool is a single declarative ``ToolSpec``;
``server.py`` materializes MCP endpoints from the registry with ONE generic
proxy factory, and ``worker.py`` dispatches with ONE generic handler. Adding
a tool therefore touches exactly two places: its input model (contracts/)
and its spec + worker function (tools/) — Open/Closed at package scale.

Security floor: ``apply_path_guard()`` is the shared, generic enforcement
of ``ToolInput.path_fields`` declarations. It runs in Layer A (precheck,
fail before spawn) AND in Layer B (re-validation, never trust the parent) —
one implementation, two enforcement points (DRY).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Any, Callable, Final, Iterator

from .contracts.base import ToolInput
from .security import PathGuard, PathSecurityError

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.registry")


class Category(str, enum.Enum):
    """The ten catalog verticals (arcgis_mcp_tool_catalog.md)."""

    MAP_MGMT = "map_layer_management"
    DATA_MGMT = "data_management"
    GEOMETRY = "geometry_analysis"
    PROJECTION = "coordinate_reference_projection"
    RASTER = "raster_operations"
    EXPORT_LAYOUT = "export_layout"
    EDITING = "editing_topology"
    NETWORK = "network_analysis"
    SPATIAL_STATS = "spatial_statistics"
    VISION = "vision_analytics"


#: Worker-side implementation signature: (arcpy module, validated input) ->
#: JSON-safe result dict. Receives arcpy as a parameter so tools/ modules
#: never import it (Layer B exclusivity is preserved by construction).
#: The input is typed Any rather than ToolInput: each worker function takes
#: its own concrete model, and Callable parameters are contravariant — the
#: specific-input functions could never satisfy a ToolInput-typed alias.
#: Runtime pairing is guaranteed by the dispatcher, which validates the
#: payload against spec.input_model before invoking spec.worker_fn.
WorkerFn = Callable[[Any, Any], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    """Complete declarative description of one catalog tool."""

    name: str  # MCP tool name, snake_case (catalog col 2)
    category: Category
    description: str  # surfaced to Claude via tools/list
    input_model: type[ToolInput]
    worker_fn: WorkerFn
    destructive: bool = False  # True => input model must carry confirm flag


_REGISTRY: Final[dict[str, ToolSpec]] = {}


def register(spec: ToolSpec) -> ToolSpec:
    """Add a spec to the global registry. Duplicate names are a build error."""
    if spec.name in _REGISTRY:
        raise ValueError(f"Duplicate tool registration: {spec.name!r}")
    if spec.destructive and "confirm" not in spec.input_model.model_fields:
        raise ValueError(
            f"{spec.name!r} is destructive but its input model has no "
            "'confirm' field — refusing to register."
        )
    _REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def all_specs() -> Iterator[ToolSpec]:
    """Iterate specs in deterministic (registration) order."""
    yield from _REGISTRY.values()


def count() -> int:
    return len(_REGISTRY)


def apply_path_guard(inp: ToolInput, guard: PathGuard) -> ToolInput:
    """Generically enforce a model's ``path_fields`` declarations.

    Returns a copy of the input with every guarded field replaced by its
    fully resolved form, so downstream code only ever sees sanitized paths.
    ``write`` roles honor the model's ``overwrite`` field when present
    (absent => False: the conservative default).

    Raises:
        PathSecurityError: on any boundary or overwrite-discipline violation.
    """
    updates: dict[str, Any] = {}
    overwrite = bool(getattr(inp, "overwrite", False))

    for field, role in type(inp).path_fields.items():
        value = getattr(inp, field)
        if value is None:
            continue
        if role == "read":
            updates[field] = str(guard.validate_read(str(value)))
        elif role == "write":
            updates[field] = str(guard.validate_write(str(value), overwrite=overwrite))
        elif role == "read_list":
            if not isinstance(value, (list, tuple)):
                raise PathSecurityError(
                    f"{field!r} declared read_list but is not a sequence."
                )
            updates[field] = [str(guard.validate_read(str(v))) for v in value]
        else:  # unreachable while PathRole stays closed
            raise PathSecurityError(f"Unknown path role {role!r} on {field!r}.")

    return inp.model_copy(update=updates) if updates else inp


__all__ = [
    "Category",
    "ToolSpec",
    "WorkerFn",
    "all_specs",
    "apply_path_guard",
    "count",
    "get",
    "register",
]
