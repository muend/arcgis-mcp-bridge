"""arcgis_mcp.execution — asynchronous process-isolation bridge (Layer A side).

Defines the ``ExecutionBackend`` Protocol and its first concrete
implementation, ``SubprocessBackend``: spawn-per-call execution of
``arcgis_mcp.worker`` inside the cloned conda interpreter.

Why a Protocol (structural typing) instead of an ABC?
-----------------------------------------------------
The server layer should depend on a *capability* ("something that can run a
WorkerJob"), not on an inheritance tree (Dependency Inversion). A future
``WarmPoolBackend`` (persistent pre-imported arcpy worker) or a
``FakeBackend`` used in unit tests satisfies the Protocol simply by having
the right method shape — no registration, no base-class import.

Failure philosophy
------------------
This module NEVER lets a worker failure propagate as an unhandled exception
into the stdio event loop. Every failure mode — timeout, crash, garbage
output, non-zero exit — is converted into a structured ``WorkerResult`` with
``ok=False``. The JSON-RPC channel stays alive no matter what arcpy does.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from pydantic import ValidationError

from .contracts import WorkerError, WorkerJob, WorkerResult

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.execution")

#: Hard ceiling on bytes we will buffer from a worker's stdout/stderr.
#: A runaway GP message stack must not exhaust server memory.
_MAX_STREAM_BYTES: Final[int] = 8 * 1024 * 1024

#: Grace period between SIGTERM-equivalent kill() and giving up on wait().
_KILL_GRACE_S: Final[float] = 10.0


@runtime_checkable
class ExecutionBackend(Protocol):
    """Structural contract: anything that can execute a WorkerJob.

    Implementations MUST be total functions over their failure domain:
    they return a WorkerResult for every input and never raise for
    worker-side problems (server-side programming errors may still raise).
    """

    async def run_job(self, job: WorkerJob, *, timeout_s: int) -> WorkerResult:
        """Execute one job and return its structured result."""
        ...


def _failure(job_id: str, kind: str, message: str) -> WorkerResult:
    """Build a structured failure frame (single construction point — DRY)."""
    return WorkerResult(
        job_id=job_id,
        ok=False,
        error=WorkerError(kind=kind, message=message),
    )


class SubprocessBackend:
    """Spawn-per-call backend: one worker process per job, full isolation.

    Trade-off (documented in the Stage 2 blueprint): maximum crash isolation
    and zero state leakage between jobs, at the cost of paying the
    ``import arcpy`` tax (~10-30 s) on every call. The warm-pool variant
    will live behind the same Protocol when latency matters.
    """

    def __init__(
        self,
        arcpy_python: Path,
        project_root: Path,
        max_workers: int = 2,
    ) -> None:
        """Configure the bridge.

        Args:
            arcpy_python: Interpreter inside ``arcgis-mcp-env``
                (``Settings.arcpy_python_path``).
            project_root: Directory containing the ``arcgis_mcp`` package.
                Set as the worker subprocess's ``cwd`` (below), so
                ``python -m arcgis_mcp.worker`` resolves the package via
                ``sys.path[0]`` without mutating ``PYTHONPATH``.
            max_workers: Concurrency ceiling for simultaneously live worker
                subprocesses (``ARCGIS_MCP_MAX_WORKERS``). Each worker pays
                a full ``import arcpy`` (hundreds of MB) and may check out
                finite Esri extension license seats, so parallel agent
                fan-out without a bound is an OOM / ``ExtensionLicenseError``
                stampede. Excess requests queue FIFO on the semaphore.
        """
        if not arcpy_python.is_file():
            raise FileNotFoundError(f"Worker interpreter not found: {arcpy_python}")
        if not (project_root / "arcgis_mcp" / "worker.py").is_file():
            raise FileNotFoundError(
                f"arcgis_mcp package not found under: {project_root}"
            )
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {max_workers}")
        self._python: Final[Path] = arcpy_python
        self._root: Final[Path] = project_root
        #: Orchestration-boundary gate: bounds live subprocesses, not queued
        #: requests — callers await their turn instead of stampeding arcpy.
        self._gate: Final[asyncio.Semaphore] = asyncio.Semaphore(max_workers)

    # ------------------------------------------------------------------ #
    # ExecutionBackend implementation
    # ------------------------------------------------------------------ #

    async def run_job(self, job: WorkerJob, *, timeout_s: int) -> WorkerResult:
        """Acquire a worker slot, then spawn/feed/await one NDJSON exchange.

        Concurrency discipline: the semaphore is held for the worker's full
        lifetime (spawn → communicate → reap), so at most ``max_workers``
        arcpy interpreters exist at any instant. Queue wait time does NOT
        count against ``timeout_s`` — the timeout measures geoprocessing,
        not orchestration backpressure.

        Every exit path returns a WorkerResult; nothing worker-related
        escapes as an exception (error-boundary guarantee).
        """
        async with self._gate:
            return await self._run_one(job, timeout_s=timeout_s)

    async def _run_one(self, job: WorkerJob, *, timeout_s: int) -> WorkerResult:
        """Spawn the worker, feed one NDJSON frame, await one NDJSON frame."""
        frame = job.model_dump_json() + "\n"
        LOG.info("job %s: dispatch op=%s", job.job_id, job.op)

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self._python),
                "-u",  # unbuffered pipes: no half-written frames
                "-m",
                "arcgis_mcp.worker",
                cwd=str(self._root),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_MAX_STREAM_BYTES,
            )
        except OSError as exc:
            LOG.error("job %s: failed to spawn worker: %s", job.job_id, exc)
            return _failure(job.job_id, "internal", f"Could not spawn worker: {exc}")

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=frame.encode("utf-8")),
                timeout=float(timeout_s),
            )
        except asyncio.TimeoutError:
            await self._terminate(proc, job.job_id)
            return _failure(
                job.job_id,
                "internal",
                f"Worker exceeded the {timeout_s}s timeout and was terminated. "
                "Partial geoprocessing output may exist in the scratch GDB.",
            )
        except (OSError, asyncio.LimitOverrunError) as exc:
            await self._terminate(proc, job.job_id)
            return _failure(job.job_id, "internal", f"IPC pipe failure: {exc}")

        self._log_worker_stderr(job.job_id, stderr_b)

        if proc.returncode != 0:
            # Native crash, license hard-failure, unhandled worker exception.
            LOG.error(
                "job %s: worker exited %s (native crash boundary engaged)",
                job.job_id,
                proc.returncode,
            )
            return _failure(
                job.job_id,
                "internal",
                f"Worker process exited with code {proc.returncode}. "
                "The geoprocessing runtime may have crashed; see server logs.",
            )

        return self._parse_response(job.job_id, stdout_b)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _parse_response(self, job_id: str, stdout_b: bytes) -> WorkerResult:
        """Extract and validate the single response frame from worker stdout.

        Defense in depth: even though the worker shields its stdout, we only
        trust the LAST non-empty line — any stray native-library noise that
        slipped through is ignored rather than fatal.
        """
        lines = [
            ln
            for ln in stdout_b.decode("utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        if not lines:
            return _failure(job_id, "internal", "Worker produced no response frame.")
        try:
            result = WorkerResult.model_validate_json(lines[-1])
        except (ValidationError, json.JSONDecodeError) as exc:
            LOG.error("job %s: unparseable worker frame: %s", job_id, exc)
            return _failure(
                job_id, "internal", "Worker returned a malformed response frame."
            )
        if result.job_id != job_id:
            return _failure(
                job_id,
                "internal",
                f"Correlation mismatch: expected {job_id}, got {result.job_id}.",
            )
        return result

    @staticmethod
    async def _terminate(proc: asyncio.subprocess.Process, job_id: str) -> None:
        """Kill a misbehaving worker and reap it (no zombie processes)."""
        if proc.returncode is not None:
            return
        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE_S)
        except (ProcessLookupError, asyncio.TimeoutError) as exc:
            LOG.warning("job %s: worker reaping issue: %s", job_id, exc)

    @staticmethod
    def _log_worker_stderr(job_id: str, stderr_b: bytes) -> None:
        """Relay worker diagnostics into the server log (stderr/file only)."""
        text = stderr_b.decode("utf-8", errors="replace").strip()
        if text:
            for line in text.splitlines()[-200:]:  # cap relay volume
                LOG.debug("job %s [worker] %s", job_id, line)


def new_job_id() -> str:
    """Generate a short correlation id for one tool invocation."""
    return uuid.uuid4().hex[:12]


__all__ = ["ExecutionBackend", "SubprocessBackend", "new_job_id"]
