"""arcgis_mcp.server — Layer A: the MCP stdio endpoint (FastMCP).

Responsibilities (strictly protocol-side — SRP):
  * Build the runtime object graph LAZILY via ``get_runtime()`` — a
    memoized composition root (``functools.lru_cache(maxsize=1)``).
    Importing this module performs NO environment validation and NEVER
    raises ``SystemExit``: unit-test suites and static tooling can import
    it on machines with no ArcGIS installation. Environment resolution is
    deferred to the first tool invocation (or ``main()``, which resolves
    it eagerly so a misconfigured server still dies before the handshake).
  * Register the tool surface (``list_layers``, ``execute_spatial_tool``,
    ``health_check``) with contract-validated inputs.
  * Translate ``WorkerResult`` frames into MCP tool results.

What this module must NEVER do:
  * import arcpy (Layer B exclusivity),
  * print to stdout (JSON-RPC channel),
  * re-parse environment variables. ``Settings.from_environment()`` is the
    single configuration parser; duplicating ``os.environ`` reads here is
    exactly how Layer A and the Stage 1 contracts drifted apart, which is
    the class of bug this revision eliminates.

Settings field contract (all lowercase, frozen):
    arcpy_python_path : Path  — worker interpreter (arcgis-mcp-env)
    allowed_roots     : tuple[Path, ...] — PathGuard boundary
    scratch_gdb       : Path  — default output workspace
    log_file          : Path | None — optional rotating log target
    log_level         : int   — stdlib logging level
    tool_timeout_s    : int   — per-job wall-clock ceiling
    max_workers       : int   — concurrent arcpy worker ceiling (semaphore)
"""

from __future__ import annotations

import functools
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional

try:  # official SDK packaging
    from mcp.server.fastmcp import FastMCP
except ImportError:  # standalone fastmcp 2.x packaging
    from fastmcp import FastMCP  # type: ignore[assignment]

from pydantic import ValidationError

# Importing the tools package populates the registry with all catalog
# verticals (each category module registers its ToolSpecs at import time).
from . import tools as _catalog  # noqa: F401
from .config import ConfigError, Settings, configure_logging
from .contracts import (
    ExecuteSpatialToolInput,
    ListLayersInput,
    ParameterScalar,
    WorkerJob,
    WorkerResult,
)
from .execution import ExecutionBackend, SubprocessBackend, new_job_id
from .registry import ToolSpec, all_specs, apply_path_guard, count as registry_count
from .security import PathGuard, PathSecurityError

#: Repository root (parent of the ``arcgis_mcp`` package directory).
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

#: Module logger — safe at import time: emits nothing until
#: ``configure_logging()`` (called inside ``get_runtime()``) attaches
#: handlers to the package root.
LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.server")


# --------------------------------------------------------------------------- #
# Composition root — LAZY and memoized, fail-fast on first resolution.
# Importing this module never touches the environment (testability); a
# misconfigured server still dies with an actionable stderr message on the
# first ``get_runtime()`` call — which ``main()`` performs BEFORE accepting
# the handshake, never limping into half-initialized tool calls.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Runtime:
    """The fully wired object graph: one instance per server process."""

    settings: Settings
    guard: PathGuard
    backend: ExecutionBackend
    log: logging.Logger


def _bootstrap() -> Runtime:
    """Build the object graph from validated configuration.

    Wrapped in a function (rather than bare top-level statements) so the
    failure path is testable and the dependency order stays explicit:
    Settings -> logging -> PathGuard -> backend.
    """
    try:
        settings = Settings.from_environment()
    except ConfigError as exc:
        # stderr is safe; stdout belongs to JSON-RPC even pre-handshake.
        print(f"[arcgis-mcp] FATAL configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    log = configure_logging(settings)

    try:
        guard = PathGuard(settings.allowed_roots)
        backend: ExecutionBackend = SubprocessBackend(
            arcpy_python=settings.arcpy_python_path,
            project_root=_PROJECT_ROOT,
            max_workers=settings.max_workers,
        )
    except (ValueError, FileNotFoundError) as exc:
        log.critical("Bootstrap failed: %s", exc)
        raise SystemExit(1) from exc

    log.info(
        "Bootstrap complete: interpreter=%s, roots=%d, scratch=%s, "
        "timeout=%ss, max_workers=%d",
        settings.arcpy_python_path,
        len(settings.allowed_roots),
        settings.scratch_gdb,
        settings.tool_timeout_s,
        settings.max_workers,
    )
    return Runtime(settings=settings, guard=guard, backend=backend, log=log)


@functools.lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    """Lazy, memoized accessor for the composition root.

    The first caller pays environment resolution; every subsequent call
    returns the same frozen ``Runtime``. Tests may call
    ``get_runtime.cache_clear()`` to re-resolve under a patched environment.
    """
    return _bootstrap()


mcp: Final[FastMCP] = FastMCP("arcgis-pro-bridge")


# --------------------------------------------------------------------------- #
# Result translation helpers
# --------------------------------------------------------------------------- #


class ToolExecutionError(RuntimeError):
    """Raised to surface a structured failure to the MCP host.

    FastMCP converts raised exceptions into ``isError`` tool results; we
    raise with a message assembled from the WorkerError so Claude receives
    the actionable diagnostic (GP message stack included) instead of a
    generic stack trace.
    """


def _unwrap(result: WorkerResult) -> dict[str, Any]:
    """Return the payload of a successful frame or raise ToolExecutionError."""
    if result.ok and result.result is not None:
        return result.result
    error = result.error
    if error is None:  # defensive: contract invariant makes this unreachable
        raise ToolExecutionError("Worker returned an empty failure frame.")
    detail = f"[{error.kind}] {error.message}"
    if error.gp_messages:
        detail += "\nGeoprocessing messages:\n" + "\n".join(error.gp_messages)
    raise ToolExecutionError(detail)


def _default_output_path(settings: Settings, tool_value: str, job_id: str) -> str:
    """Deterministic auto-name inside the configured scratch GDB."""
    safe_tool = tool_value.split("_", 1)[0].lower()  # 'Buffer_analysis' -> 'buffer'
    return str(settings.scratch_gdb / f"{safe_tool}_{job_id}")


# --------------------------------------------------------------------------- #
# Tool surface
# --------------------------------------------------------------------------- #


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Verify the full execution pipeline: server -> conda worker -> back.

    Spawns a real worker process (without importing arcpy) and reports the
    interpreter version plus configuration summary. Use this first when
    diagnosing connectivity.
    """
    rt = get_runtime()
    job = WorkerJob(op="ping", payload={}, job_id=new_job_id())
    result = await rt.backend.run_job(
        job, timeout_s=min(rt.settings.tool_timeout_s, 120)
    )
    payload = _unwrap(result)
    return {
        "server": "ok",
        "worker_python": payload.get("python"),
        "worker_interpreter": str(rt.settings.arcpy_python_path),
        "allowed_roots": [str(r) for r in rt.settings.allowed_roots],
        "scratch_gdb": str(rt.settings.scratch_gdb),
        "tool_timeout_s": rt.settings.tool_timeout_s,
        "max_workers": rt.settings.max_workers,
    }


@mcp.tool()
async def list_layers(
    workspace: str,
    dataset_filter: Optional[str] = None,
) -> dict[str, Any]:
    """List feature classes, tables and rasters inside a file geodatabase.

    Args:
        workspace: Absolute path to a .gdb inside an allowed workspace root.
        dataset_filter: Optional wildcard (e.g. 'roads_*'); None lists all.

    Returns:
        ListLayersOutput as JSON: workspace, layers[], elapsed_seconds.
    """
    rt = get_runtime()
    try:
        inp = ListLayersInput(workspace=workspace, dataset_filter=dataset_filter)
        rt.guard.validate_read(inp.workspace)  # Layer-A precheck: fail before spawn
    except (ValidationError, PathSecurityError) as exc:
        raise ToolExecutionError(f"[validation] {exc}") from exc

    job = WorkerJob(
        op="list_layers",
        payload=inp.model_dump(mode="json"),
        job_id=new_job_id(),
    )
    rt.log.info("list_layers %s: workspace=%s", job.job_id, inp.workspace)
    result = await rt.backend.run_job(job, timeout_s=rt.settings.tool_timeout_s)
    return _unwrap(result)


@mcp.tool()
async def execute_spatial_tool(
    tool: str,
    in_features: str,
    parameters: dict[str, ParameterScalar],
    out_features: Optional[str] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Execute one allowlisted geoprocessing tool (Buffer_analysis, Clip_analysis).

    Args:
        tool: Allowlisted tool name, e.g. 'Buffer_analysis'.
        in_features: Absolute path to the source dataset (inside allowed roots).
        parameters: Tool-specific arguments. Buffer requires
            'buffer_distance_or_field' (e.g. '100 Meters'); Clip requires
            'clip_features' (a dataset path).
        out_features: Output path. Omit to auto-name inside the scratch GDB.
        overwrite: Must be true to replace an existing output (explicit opt-in).

    Returns:
        ExecuteSpatialToolOutput as JSON: status, output_path, messages,
        elapsed_seconds.
    """
    try:
        inp = ExecuteSpatialToolInput(
            tool=tool,  # str -> enum coercion; non-allowlisted names rejected
            in_features=in_features,
            out_features=out_features,
            parameters=parameters,
            overwrite=overwrite,
        )
    except (ValidationError, ValueError) as exc:
        raise ToolExecutionError(f"[validation] {exc}") from exc

    rt = get_runtime()
    job_id = new_job_id()
    try:
        # Layer-A path discipline: resolve + authorize BEFORE spawning.
        rt.guard.validate_read(inp.in_features)
        resolved_out = str(
            rt.guard.validate_write(
                inp.out_features
                if inp.out_features is not None
                else _default_output_path(rt.settings, inp.tool.value, job_id),
                overwrite=inp.overwrite,
            )
        )
    except PathSecurityError as exc:
        raise ToolExecutionError(f"[security] {exc}") from exc

    # Ship the RESOLVED output path; the worker re-validates but never invents.
    payload = inp.model_copy(update={"out_features": resolved_out}).model_dump(
        mode="json"
    )
    job = WorkerJob(op="execute_spatial_tool", payload=payload, job_id=job_id)
    rt.log.info(
        "execute_spatial_tool %s: tool=%s in=%s out=%s overwrite=%s",
        job_id,
        inp.tool.value,
        inp.in_features,
        resolved_out,
        inp.overwrite,
    )
    result = await rt.backend.run_job(job, timeout_s=rt.settings.tool_timeout_s)
    return _unwrap(result)


# --------------------------------------------------------------------------- #
# Catalog tool surface — generated from the registry (one proxy factory
# serves every vertical; adding a tool never touches this file)
# --------------------------------------------------------------------------- #


def _make_catalog_proxy(spec: ToolSpec) -> Any:
    """Build the async MCP endpoint for one ToolSpec.

    The proxy's ``params`` annotation is the spec's Pydantic model, so
    FastMCP derives the full JSON schema (types, Literals, defaults,
    descriptions) that Claude sees — schema and validation come from the
    same class, by construction.
    """

    async def _proxy(params: Any) -> dict[str, Any]:  # real schema set below
        rt = get_runtime()
        try:
            inp = spec.input_model.model_validate(
                params if isinstance(params, dict) else params.model_dump()
            )
            apply_path_guard(inp, rt.guard)  # Layer-A precheck: fail before spawn
        except (ValidationError, PathSecurityError) as exc:
            raise ToolExecutionError(f"[validation] {exc}") from exc

        job = WorkerJob(
            op="run_tool",
            payload={"tool": spec.name, "args": inp.model_dump(mode="json")},
            job_id=new_job_id(),
        )
        rt.log.info("%s %s: dispatch (%s)", spec.name, job.job_id, spec.category.value)
        return _unwrap(
            await rt.backend.run_job(job, timeout_s=rt.settings.tool_timeout_s)
        )

    _proxy.__name__ = spec.name
    _proxy.__doc__ = spec.description
    _proxy.__annotations__ = {"params": spec.input_model, "return": dict[str, Any]}
    return _proxy


def _register_catalog_tools() -> None:
    """Materialize every registered ToolSpec as an MCP tool endpoint."""
    for spec in all_specs():
        mcp.tool(name=spec.name, description=spec.description)(
            _make_catalog_proxy(spec)
        )
    LOG.info("Catalog tools registered: %d (plus 3 core tools).", registry_count())


_register_catalog_tools()


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def main() -> None:
    """Run the stdio server. Blocking; owns the process from here on.

    Resolves the runtime EAGERLY: a misconfigured deployment must die with
    an actionable stderr message before the MCP handshake, while imports
    (tests, tooling) stay side-effect free.
    """
    rt = get_runtime()
    rt.log.info("arcgis-pro-bridge starting on stdio transport.")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
