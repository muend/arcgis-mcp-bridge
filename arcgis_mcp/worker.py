"""arcgis_mcp.worker — Layer B entrypoint. The ONLY module that imports arcpy.

Runs inside the licensed ``arcgispro-py3``-derived interpreter as a child
process of the MCP server (see ``execution.SubprocessBackend``). Lifecycle:

    stdin  ──► one NDJSON ``WorkerJob`` frame
    stdout ──► one NDJSON ``WorkerResult`` frame (nothing else, ever)
    stderr ──► all diagnostics, GP chatter, warnings, tracebacks

stdout discipline
-----------------
ArcPy and its native ArcObjects layer occasionally print to the process's
stdout. To make that physically harmless, ``main()`` immediately rebinds
``sys.stdout`` to ``sys.stderr`` and keeps a private handle to the real
stdout, used exactly once — to emit the final response frame.

Exit-code semantics
-------------------
0   = a response frame was emitted (even if the frame reports ok=False).
2   = protocol failure before a frame could be built (empty stdin, etc.).
Anything else = uncontrolled termination (native crash) — the parent's
error boundary converts it into a structured failure.

``import arcpy`` is deferred into ``_get_arcpy()`` so this module stays
importable (and unit-testable) in environments without ArcGIS — the import
tax is paid on first use, identically to paying it at module import time
in spawn-per-call mode.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from types import ModuleType
from typing import Any, Callable, Final, TextIO

from pydantic import ValidationError

# Importing the tools package populates the registry (each category module
# registers its ToolSpecs at import time). arcpy is NOT imported by this.
from . import tools as _catalog  # noqa: F401
from .contracts import (
    ExecuteSpatialToolInput,
    ExecuteSpatialToolOutput,
    LayerInfo,
    ListLayersInput,
    ListLayersOutput,
    SpatialToolName,
    WorkerError,
    WorkerJob,
    WorkerResult,
)
from .registry import apply_path_guard, get as registry_get
from .security import PathGuard, PathSecurityError

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.worker")

_EXIT_OK: Final[int] = 0
_EXIT_PROTOCOL: Final[int] = 2


# --------------------------------------------------------------------------- #
# arcpy access (deferred import, single chokepoint)
# --------------------------------------------------------------------------- #

_arcpy_module: ModuleType | None = None


class LicenseUnavailableError(RuntimeError):
    """Raised when arcpy imports but no license can be checked out."""


def _get_arcpy() -> ModuleType:
    """Import arcpy lazily, classifying import-time failures.

    Raises:
        LicenseUnavailableError: license checkout failed.
        ImportError: arcpy genuinely absent (wrong interpreter).
    """
    global _arcpy_module
    if _arcpy_module is not None:
        return _arcpy_module
    LOG.info("Importing arcpy (this can take 10-30 s on a cold start)...")
    t0 = time.perf_counter()
    try:
        import arcpy  # noqa: PLC0415  — deferred by design, see module docstring
    except RuntimeError as exc:
        # Esri signals license problems as RuntimeError at import time.
        raise LicenseUnavailableError(f"ArcGIS license unavailable: {exc}") from exc
    LOG.info("arcpy ready in %.1f s", time.perf_counter() - t0)
    _arcpy_module = arcpy
    return _arcpy_module  # via the ModuleType-typed global: no Any escapes


# --------------------------------------------------------------------------- #
# Legacy Stage 2 tool adapters (Buffer/Clip gateway)
# --------------------------------------------------------------------------- #


def _adapt_buffer(
    arcpy: ModuleType, inp: ExecuteSpatialToolInput, out_path: str
) -> None:
    p = inp.parameters
    arcpy.analysis.Buffer(
        in_features=inp.in_features,
        out_feature_class=out_path,
        buffer_distance_or_field=str(p["buffer_distance_or_field"]),
        line_side=str(p.get("line_side", "FULL")),
        line_end_type=str(p.get("line_end_type", "ROUND")),
        dissolve_option=str(p.get("dissolve_option", "NONE")),
        method=str(p.get("method", "PLANAR")),
    )


def _adapt_clip(arcpy: ModuleType, inp: ExecuteSpatialToolInput, out_path: str) -> None:
    p = inp.parameters
    arcpy.analysis.Clip(
        in_features=inp.in_features,
        clip_features=str(p["clip_features"]),
        out_feature_class=out_path,
        cluster_tolerance=str(p.get("cluster_tolerance", "")),
    )


_TOOL_ADAPTERS: Final[
    dict[SpatialToolName, Callable[[ModuleType, ExecuteSpatialToolInput, str], None]]
] = {
    SpatialToolName.BUFFER: _adapt_buffer,
    SpatialToolName.CLIP: _adapt_clip,
}


# --------------------------------------------------------------------------- #
# Operation handlers
# --------------------------------------------------------------------------- #


def _handle_ping(_: dict[str, Any], __: PathGuard) -> dict[str, Any]:
    """Liveness probe: confirms IPC + interpreter without touching arcpy."""
    return {"pong": True, "python": sys.version.split()[0]}


def _handle_list_layers(payload: dict[str, Any], guard: PathGuard) -> dict[str, Any]:
    """Inspect a geodatabase: enumerate feature classes, tables, rasters."""
    inp = ListLayersInput.model_validate(payload)
    workspace = str(guard.validate_read(inp.workspace))

    arcpy = _get_arcpy()
    t0 = time.perf_counter()
    arcpy.env.workspace = workspace

    layers: list[LayerInfo] = []
    wildcard = inp.dataset_filter

    def _describe_fc(name: str) -> LayerInfo:
        desc = arcpy.Describe(name)
        sr = getattr(desc, "spatialReference", None)
        count: int | None
        try:
            count = int(arcpy.management.GetCount(name)[0])
        except Exception:  # noqa: BLE001 — count is best-effort metadata
            count = None
        return LayerInfo(
            name=name,
            data_type="FeatureClass",
            geometry_type=desc.shapeType,  # validated by Literal
            spatial_reference=(
                f"EPSG:{sr.factoryCode}"
                if sr and sr.factoryCode
                else (sr.name if sr else None)
            ),
            feature_count=count,
        )

    for fc in arcpy.ListFeatureClasses(wildcard) or []:
        layers.append(_describe_fc(fc))
    for tbl in arcpy.ListTables(wildcard) or []:
        try:
            count = int(arcpy.management.GetCount(tbl)[0])
        except Exception:  # noqa: BLE001
            count = None
        layers.append(LayerInfo(name=tbl, data_type="Table", feature_count=count))
    for ras in arcpy.ListRasters(wildcard) or []:
        layers.append(LayerInfo(name=ras, data_type="RasterDataset"))

    out = ListLayersOutput(
        workspace=workspace,
        layers=tuple(layers),
        elapsed_seconds=round(time.perf_counter() - t0, 3),
    )
    return out.model_dump(mode="json")


def _handle_execute_spatial_tool(
    payload: dict[str, Any], guard: PathGuard
) -> dict[str, Any]:
    """Run one allowlisted geoprocessing tool under full guard discipline."""
    inp = ExecuteSpatialToolInput.model_validate(payload)

    # Re-validate paths INSIDE the worker: never trust the parent blindly.
    in_path = str(guard.validate_read(inp.in_features))
    if inp.out_features is None:
        raise PathSecurityError(
            "out_features resolution is the server's responsibility; the "
            "worker requires an explicit, pre-resolved output path."
        )
    out_path = str(guard.validate_write(inp.out_features, overwrite=inp.overwrite))

    # Clip's secondary geometry input is also a path — guard it too.
    if inp.tool is SpatialToolName.CLIP:
        guard.validate_read(str(inp.parameters["clip_features"]))

    arcpy = _get_arcpy()
    arcpy.env.overwriteOutput = inp.overwrite  # mirrors the contract flag exactly

    adapter = _TOOL_ADAPTERS[inp.tool]
    t0 = time.perf_counter()
    try:
        adapter(arcpy, inp.model_copy(update={"in_features": in_path}), out_path)
        messages = tuple(arcpy.GetMessages().splitlines())
        out = ExecuteSpatialToolOutput(
            status="success",
            output_path=out_path,
            messages=messages,
            elapsed_seconds=round(time.perf_counter() - t0, 3),
        )
        return out.model_dump(mode="json")
    except arcpy.ExecuteError as exc:
        # Tool ran and failed: a DOMAIN error, not an infrastructure one.
        raise GeoprocessingFailure(
            message=str(exc).strip() or "Geoprocessing tool failed.",
            gp_messages=tuple(arcpy.GetMessages().splitlines()),
            elapsed_seconds=round(time.perf_counter() - t0, 3),
        ) from exc


class GeoprocessingFailure(RuntimeError):
    """Carrier for arcpy.ExecuteError details across the dispatch boundary."""

    def __init__(
        self,
        message: str,
        gp_messages: tuple[str, ...],
        elapsed_seconds: float,
    ) -> None:
        super().__init__(message)
        self.gp_messages = gp_messages
        self.elapsed_seconds = elapsed_seconds


def _handle_run_tool(payload: dict[str, Any], guard: PathGuard) -> dict[str, Any]:
    """Generic dispatcher for every registry-defined catalog tool.

    One handler serves all 100 tools (DRY): validate against the spec's
    input model, re-enforce the declarative path roles, hand arcpy and the
    sanitized input to the spec's worker function.
    """
    name = str(payload.get("tool", ""))
    spec = registry_get(name)
    if spec is None:
        raise ValueError(f"Unknown catalog tool: {name!r}")

    inp = spec.input_model.model_validate(payload.get("args", {}))
    inp = apply_path_guard(inp, guard)  # Layer-B re-validation: trust no parent

    # Destructive-tool gate BEFORE the expensive arcpy import: an unconfirmed
    # delete must be rejected in milliseconds, not after a 30 s license spin-up.
    if spec.destructive and not getattr(inp, "confirm", False):
        raise PermissionError(
            f"{name} is destructive or mutates its input: "
            "set confirm=true to proceed."
        )

    arcpy = _get_arcpy()
    arcpy.env.overwriteOutput = bool(getattr(inp, "overwrite", False))

    t0 = time.perf_counter()
    try:
        result = spec.worker_fn(arcpy, inp)
    except arcpy.ExecuteError as exc:
        raise GeoprocessingFailure(
            message=str(exc).strip() or f"{name} failed.",
            gp_messages=tuple(arcpy.GetMessages().splitlines()),
            elapsed_seconds=round(time.perf_counter() - t0, 3),
        ) from exc
    result.setdefault("tool", name)
    result.setdefault("elapsed_seconds", round(time.perf_counter() - t0, 3))
    return result


_HANDLERS: Final[dict[str, Callable[[dict[str, Any], PathGuard], dict[str, Any]]]] = {
    "ping": _handle_ping,
    "list_layers": _handle_list_layers,
    "execute_spatial_tool": _handle_execute_spatial_tool,
    "run_tool": _handle_run_tool,
}


# --------------------------------------------------------------------------- #
# Frame processing & entrypoint
# --------------------------------------------------------------------------- #


def _error_result(
    job_id: str, kind: str, message: str, gp_messages: tuple[str, ...] = ()
) -> WorkerResult:
    return WorkerResult(
        job_id=job_id,
        ok=False,
        error=WorkerError(kind=kind, message=message, gp_messages=gp_messages),
    )


def process_frame(raw_line: str, guard: PathGuard) -> WorkerResult:
    """Pure(ish) core: one request line in, one WorkerResult out.

    Factored out of main() so it is unit-testable without real pipes.
    Every failure class maps to a distinct ``WorkerError.kind``.
    """
    try:
        job = WorkerJob.model_validate_json(raw_line)
    except (ValidationError, json.JSONDecodeError) as exc:
        return _error_result("unknown", "validation", f"Malformed job frame: {exc}")

    handler = _HANDLERS.get(job.op)
    if handler is None:  # unreachable while contracts and _HANDLERS agree
        return _error_result(job.job_id, "validation", f"Unknown op: {job.op!r}")

    try:
        result = handler(dict(job.payload), guard)
        return WorkerResult(job_id=job.job_id, ok=True, result=result)
    except (ValidationError, ValueError, LookupError) as exc:
        return _error_result(job.job_id, "validation", str(exc))
    except PathSecurityError as exc:
        return _error_result(job.job_id, "security", str(exc))
    except PermissionError as exc:
        # Confirm-flag guards on destructive tools (delete, remove, near).
        return _error_result(job.job_id, "security", str(exc))
    except LicenseUnavailableError as exc:
        return _error_result(job.job_id, "license", str(exc))
    except GeoprocessingFailure as exc:
        return _error_result(
            job.job_id, "geoprocessing", str(exc), gp_messages=exc.gp_messages
        )
    except Exception as exc:  # noqa: BLE001 — final boundary: nothing escapes
        LOG.exception("job %s: unhandled worker exception", job.job_id)
        return _error_result(
            job.job_id,
            "internal",
            f"Unexpected worker error ({type(exc).__name__}); see server logs.",
        )


def _build_guard() -> PathGuard:
    """Construct PathGuard from the same env contract the server uses."""
    # Imported here to keep worker startup independent of optional config
    # features; Settings validation errors become protocol-level failures.
    from .config import Settings  # noqa: PLC0415

    settings = Settings.from_environment()
    return PathGuard(settings.allowed_roots)


def main() -> int:
    """Read one frame, process, emit one frame. See module docstring."""
    # --- stdout shielding: do this before ANYTHING else can print. ---
    real_stdout: TextIO = sys.stdout
    sys.stdout = sys.stderr

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [worker:%(levelname)s] %(name)s: %(message)s",
    )

    raw_line = sys.stdin.readline()
    if not raw_line.strip():
        LOG.error("No job frame received on stdin.")
        return _EXIT_PROTOCOL

    try:
        guard = _build_guard()
    except Exception as exc:  # noqa: BLE001 — config failure = controlled frame
        frame = _error_result("unknown", "internal", f"Worker config error: {exc}")
        print(frame.model_dump_json(), file=real_stdout, flush=True)
        return _EXIT_OK

    result = process_frame(raw_line, guard)

    # The single sanctioned stdout write in the entire worker lifetime:
    print(result.model_dump_json(), file=real_stdout, flush=True)
    return _EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
