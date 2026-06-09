"""arcgis_mcp.contracts — single source of truth for every serialized shape.

Two contract families live here, deliberately in one module (DRY: one
serialization discipline, two enforcement points):

1. **Tool contracts** — the schemas Claude sees via MCP ``tools/list``
   (``ListLayersInput``, ``ExecuteSpatialToolInput``, ...). Validated in the
   server process (Layer A) before anything touches a subprocess.

2. **IPC envelope** — the internal NDJSON frames exchanged between the
   server and the arcpy worker (``WorkerJob`` / ``WorkerResult``).
   Validated again in the worker (Layer B): the worker never trusts that
   the server did its job — defense in depth across the process boundary.

All models are Pydantic v2, ``frozen=True`` (immutable value objects) and
``extra="forbid"`` (unknown keys are a contract violation, not a shrug).
"""

from __future__ import annotations

import enum
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Shared model configuration
# --------------------------------------------------------------------------- #

_STRICT: Final[ConfigDict] = ConfigDict(
    frozen=True,           # value objects: no post-validation mutation
    extra="forbid",        # unknown fields fail loudly (typo = bug, not noise)
    str_strip_whitespace=True,
)

#: JSON-safe scalar for tool parameters (no nested containers by design —
#: every geoprocessing argument ArcPy accepts is expressible as a scalar
#: string/number, and flat payloads keep the IPC frames auditable).
ParameterScalar = Union[str, int, float, bool]


# --------------------------------------------------------------------------- #
# list_layers
# --------------------------------------------------------------------------- #

DataType = Literal["FeatureClass", "Table", "RasterDataset"]
GeometryType = Literal["Point", "Multipoint", "Polyline", "Polygon", "MultiPatch"]


class ListLayersInput(BaseModel):
    """Input contract for the read-only ``list_layers`` tool."""

    model_config = _STRICT

    workspace: str = Field(
        ...,
        min_length=1,
        description="Absolute path to a file geodatabase (.gdb) to inspect.",
    )
    dataset_filter: Optional[str] = Field(
        default=None,
        description="Optional wildcard filter, e.g. 'roads_*'. None = all.",
        max_length=256,
    )


class LayerInfo(BaseModel):
    """One dataset discovered inside a workspace."""

    model_config = _STRICT

    name: str
    data_type: DataType
    geometry_type: Optional[GeometryType] = Field(
        default=None, description="None for non-spatial datasets (tables)."
    )
    spatial_reference: Optional[str] = Field(
        default=None, description="e.g. 'EPSG:5253' or a named CRS string."
    )
    feature_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Row/feature count; None if counting failed or N/A.",
    )


class ListLayersOutput(BaseModel):
    """Result contract for ``list_layers``."""

    model_config = _STRICT

    workspace: str
    layers: tuple[LayerInfo, ...] = Field(default_factory=tuple)
    elapsed_seconds: float = Field(ge=0.0)


# --------------------------------------------------------------------------- #
# execute_spatial_tool
# --------------------------------------------------------------------------- #

class SpatialToolName(str, enum.Enum):
    """Closed allowlist of executable geoprocessing tools.

    Extending this enum is the ONLY way to expose a new tool — there is no
    dynamic ``getattr(arcpy, ...)`` anywhere in the codebase. Each addition
    must ship with a matching parameter spec below and a worker adapter.
    """

    BUFFER = "Buffer_analysis"
    CLIP = "Clip_analysis"


class _ToolParameterSpec(BaseModel):
    """Static description of one tool's accepted parameters."""

    model_config = _STRICT

    required: frozenset[str]
    optional: frozenset[str]


#: Per-tool parameter discipline. Validated at the Layer-A boundary so a
#: malformed request never even spawns a worker process.
TOOL_PARAMETER_SPECS: Final[dict[SpatialToolName, _ToolParameterSpec]] = {
    SpatialToolName.BUFFER: _ToolParameterSpec(
        required=frozenset({"buffer_distance_or_field"}),
        optional=frozenset(
            {"line_side", "line_end_type", "dissolve_option", "method"}
        ),
    ),
    SpatialToolName.CLIP: _ToolParameterSpec(
        required=frozenset({"clip_features"}),
        optional=frozenset({"cluster_tolerance"}),
    ),
}


class ExecuteSpatialToolInput(BaseModel):
    """Input contract for the controlled geoprocessing gateway."""

    model_config = _STRICT

    tool: SpatialToolName
    in_features: str = Field(..., min_length=1, description="Source dataset path.")
    out_features: Optional[str] = Field(
        default=None,
        description="Target path. None = auto-named inside the scratch GDB.",
    )
    parameters: dict[str, ParameterScalar] = Field(
        default_factory=dict,
        description="Tool-specific arguments; keys validated per tool.",
    )
    overwrite: bool = Field(
        default=False,
        description="Explicit opt-in to replace an existing output dataset.",
    )

    @field_validator("parameters")
    @classmethod
    def _no_blank_keys(
        cls, v: dict[str, ParameterScalar]
    ) -> dict[str, ParameterScalar]:
        if any(not k.strip() for k in v):
            raise ValueError("Parameter keys must be non-empty strings.")
        return v

    @model_validator(mode="after")
    def _enforce_tool_parameter_spec(self) -> "ExecuteSpatialToolInput":
        """Cross-field check: parameters must match the tool's static spec."""
        spec = TOOL_PARAMETER_SPECS[self.tool]
        provided = set(self.parameters)
        missing = spec.required - provided
        unknown = provided - spec.required - spec.optional
        if missing:
            raise ValueError(
                f"{self.tool.value}: missing required parameter(s): "
                f"{sorted(missing)}"
            )
        if unknown:
            raise ValueError(
                f"{self.tool.value}: unknown parameter(s): {sorted(unknown)}. "
                f"Accepted: {sorted(spec.required | spec.optional)}"
            )
        return self


class ExecuteSpatialToolOutput(BaseModel):
    """Result contract capturing execution outcome and GP diagnostics."""

    model_config = _STRICT

    status: Literal["success", "error"]
    output_path: Optional[str] = None
    messages: tuple[str, ...] = Field(
        default_factory=tuple,
        description="arcpy.GetMessages() lines — the full GP message stack.",
    )
    elapsed_seconds: float = Field(ge=0.0)
    error: Optional[str] = Field(
        default=None, description="Human-readable failure summary when status=error."
    )


# --------------------------------------------------------------------------- #
# Internal IPC envelope (server <-> worker, NDJSON over pipes)
# --------------------------------------------------------------------------- #

WorkerOp = Literal["list_layers", "execute_spatial_tool", "ping"]


class WorkerJob(BaseModel):
    """One job frame written to the worker's stdin as a single JSON line."""

    model_config = _STRICT

    op: WorkerOp
    payload: dict[str, object] = Field(default_factory=dict)
    job_id: str = Field(..., min_length=1, description="Correlation id for logs.")


class WorkerError(BaseModel):
    """Structured failure description crossing the process boundary."""

    model_config = _STRICT

    kind: Literal[
        "validation",      # payload failed Pydantic re-validation in the worker
        "security",        # PathGuard rejection inside the worker
        "geoprocessing",   # arcpy.ExecuteError — tool ran and failed
        "license",         # license checkout failure
        "internal",        # anything else; details stay in stderr logs
    ]
    message: str
    gp_messages: tuple[str, ...] = Field(default_factory=tuple)


class WorkerResult(BaseModel):
    """One result frame written by the worker to stdout as a single JSON line."""

    model_config = _STRICT

    job_id: str
    ok: bool
    result: Optional[dict[str, object]] = None
    error: Optional[WorkerError] = None

    @model_validator(mode="after")
    def _ok_xor_error(self) -> "WorkerResult":
        if self.ok and self.error is not None:
            raise ValueError("ok=True must not carry an error.")
        if not self.ok and self.error is None:
            raise ValueError("ok=False requires an error.")
        return self


__all__ = [
    "DataType",
    "GeometryType",
    "ParameterScalar",
    "ListLayersInput",
    "LayerInfo",
    "ListLayersOutput",
    "SpatialToolName",
    "TOOL_PARAMETER_SPECS",
    "ExecuteSpatialToolInput",
    "ExecuteSpatialToolOutput",
    "WorkerOp",
    "WorkerJob",
    "WorkerError",
    "WorkerResult",
]
