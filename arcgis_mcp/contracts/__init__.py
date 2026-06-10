"""arcgis_mcp.contracts — schema package, split by catalog vertical.

``base.py`` holds the IPC envelope, shared model config, the ``ToolInput``
root class and the legacy Stage 2 models. Category modules hold the input
models for each catalog vertical.

Everything from ``base`` is re-exported here so existing imports
(``from .contracts import WorkerJob``) keep working unchanged after the
module->package conversion (Open/Closed: extension without breakage).
"""

from __future__ import annotations

from .base import (  # noqa: F401 — deliberate re-export surface
    DataType,
    ExecuteSpatialToolInput,
    ExecuteSpatialToolOutput,
    GeometryType,
    LayerInfo,
    ListLayersInput,
    ListLayersOutput,
    ParameterScalar,
    PathRole,
    SpatialToolName,
    TOOL_PARAMETER_SPECS,
    ToolInput,
    WorkerError,
    WorkerJob,
    WorkerOp,
    WorkerResult,
)

__all__ = [
    "DataType",
    "ExecuteSpatialToolInput",
    "ExecuteSpatialToolOutput",
    "GeometryType",
    "LayerInfo",
    "ListLayersInput",
    "ListLayersOutput",
    "ParameterScalar",
    "PathRole",
    "SpatialToolName",
    "TOOL_PARAMETER_SPECS",
    "ToolInput",
    "WorkerError",
    "WorkerJob",
    "WorkerOp",
    "WorkerResult",
]
