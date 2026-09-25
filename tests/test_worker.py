"""tests/test_worker.py — worker.process_frame error-boundary mapping.

process_frame turns one request line into exactly one WorkerResult, and every
failure class must map to a distinct WorkerError.kind. Most branches never
reach arcpy; the arcpy-touching ones use the session MagicMock (conftest) with
`ExecuteError` swapped for a real exception class so the handler's
`except arcpy.ExecuteError` clause is well-formed.

main() is exercised in a real subprocess to prove that native writes to fd 1
never reach the protocol stream.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import arcgis_mcp.registry as reg
import arcgis_mcp.worker as wk
from arcgis_mcp.contracts import WorkerJob, WorkerResult
from arcgis_mcp.contracts.base import ToolInput
from arcgis_mcp.registry import Category, ToolSpec
from arcgis_mcp.security import PathGuard
from arcgis_mcp.worker import (
    GeoprocessingFailure,
    LicenseUnavailableError,
    process_frame,
)

# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


class _PlainTool(ToolInput):
    """No fields, no path roles — model_validate({}) succeeds."""


class _ConfirmTool(ToolInput):
    confirm: bool = False


def _ok_worker(_arcpy: object, _inp: object) -> dict:
    return {}


def _frame(op: str, payload: dict, job_id: str = "j1") -> str:
    return WorkerJob(op=op, payload=payload, job_id=job_id).model_dump_json()


@pytest.fixture
def guard_root(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    return PathGuard(allowed_roots=[root]), root


@pytest.fixture
def real_execute_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the mock arcpy a real ExceptError class so `except` clauses bind."""
    arcpy = sys.modules["arcpy"]
    monkeypatch.setattr(
        arcpy, "ExecuteError", type("ExecuteError", (Exception,), {}), raising=False
    )


def _register_one(monkeypatch: pytest.MonkeyPatch, spec: ToolSpec) -> None:
    monkeypatch.setattr(reg, "_REGISTRY", {spec.name: spec})


# --------------------------------------------------------------------------- #
# Non-arcpy branches
# --------------------------------------------------------------------------- #


def test_ping_maps_to_ok(guard_root) -> None:
    guard, _ = guard_root
    res = process_frame(_frame("ping", {}), guard)
    assert res.ok is True
    assert res.result is not None and res.result["pong"] is True


def test_malformed_frame_maps_to_validation(guard_root) -> None:
    guard, _ = guard_root
    res = process_frame("{ not valid json", guard)
    assert res.ok is False
    assert res.error is not None and res.error.kind == "validation"


def test_run_tool_unknown_maps_to_validation(guard_root) -> None:
    guard, _ = guard_root
    res = process_frame(_frame("run_tool", {"tool": "does_not_exist", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "validation"


def test_execute_missing_output_maps_to_security(guard_root) -> None:
    guard, root = guard_root
    payload = {
        "tool": "Buffer_analysis",
        "in_features": str(root / "in.shp"),
        "out_features": None,
        "parameters": {"buffer_distance_or_field": "1 Meters"},
    }
    res = process_frame(_frame("execute_spatial_tool", payload), guard)
    assert res.error is not None and res.error.kind == "security"


def test_list_layers_outside_root_maps_to_security(guard_root, tmp_path) -> None:
    guard, _ = guard_root
    payload = {"workspace": str(tmp_path / "outside" / "x.gdb")}
    res = process_frame(_frame("list_layers", payload), guard)
    assert res.error is not None and res.error.kind == "security"


def test_destructive_without_confirm_maps_to_security(
    guard_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = guard_root
    spec = ToolSpec(
        name="t_del",
        category=Category.EDITING,
        description="d",
        input_model=_ConfirmTool,
        worker_fn=_ok_worker,
        destructive=True,
    )
    _register_one(monkeypatch, spec)
    res = process_frame(_frame("run_tool", {"tool": "t_del", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "security"


# --------------------------------------------------------------------------- #
# arcpy-touching branches (mock arcpy via conftest)
# --------------------------------------------------------------------------- #


def test_destructive_with_confirm_runs(
    guard_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = guard_root
    spec = ToolSpec(
        name="t_del_ok",
        category=Category.EDITING,
        description="d",
        input_model=_ConfirmTool,
        worker_fn=_ok_worker,
        destructive=True,
    )
    _register_one(monkeypatch, spec)
    res = process_frame(
        _frame("run_tool", {"tool": "t_del_ok", "args": {"confirm": True}}), guard
    )
    assert res.ok is True
    assert res.result is not None and res.result["tool"] == "t_del_ok"


def test_license_failure_maps_to_license(
    guard_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = guard_root
    spec = ToolSpec(
        name="t_lic",
        category=Category.DATA_MGMT,
        description="d",
        input_model=_PlainTool,
        worker_fn=_ok_worker,
    )
    _register_one(monkeypatch, spec)

    def _raise_license() -> object:
        raise LicenseUnavailableError("no seat")

    monkeypatch.setattr(wk, "_get_arcpy", _raise_license)
    res = process_frame(_frame("run_tool", {"tool": "t_lic", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "license"


def test_geoprocessing_failure_maps_to_geoprocessing(
    guard_root, monkeypatch: pytest.MonkeyPatch, real_execute_error: None
) -> None:
    guard, _ = guard_root

    def _boom(_arcpy: object, _inp: object) -> dict:
        raise GeoprocessingFailure(
            message="gp failed", gp_messages=("ERROR 000123",), elapsed_seconds=0.0
        )

    spec = ToolSpec(
        name="t_gp",
        category=Category.GEOMETRY,
        description="d",
        input_model=_PlainTool,
        worker_fn=_boom,
    )
    _register_one(monkeypatch, spec)
    res = process_frame(_frame("run_tool", {"tool": "t_gp", "args": {}}), guard)
    assert res.error is not None
    assert res.error.kind == "geoprocessing"
    assert "ERROR 000123" in res.error.gp_messages


def test_unexpected_error_maps_to_internal(
    guard_root, monkeypatch: pytest.MonkeyPatch, real_execute_error: None
) -> None:
    guard, _ = guard_root

    def _boom(_arcpy: object, _inp: object) -> dict:
        raise RuntimeError("kaboom")

    spec = ToolSpec(
        name="t_int",
        category=Category.DATA_MGMT,
        description="d",
        input_model=_PlainTool,
        worker_fn=_boom,
    )
    _register_one(monkeypatch, spec)
    res = process_frame(_frame("run_tool", {"tool": "t_int", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "internal"


# --------------------------------------------------------------------------- #
# main() stdout discipline — real subprocess, real pipes (issue #23)
# --------------------------------------------------------------------------- #

# Stands in for ArcPy's native layer: writes to fd 1 and, on Windows, to the
# Win32 standard output handle — both bypass sys.stdout entirely.
_NOISY_WORKER = textwrap.dedent(
    """
    import os
    import sys

    import arcgis_mcp.worker as wk


    def _noisy_ping(payload, guard):
        os.write(1, b"WARNING 000635: fd-1 noise\\n")
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetStdHandle.restype = wintypes.HANDLE
            k32.WriteFile.argtypes = [
                wintypes.HANDLE,
                ctypes.c_char_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ]
            msg = b"WARNING win32-handle noise\\n"
            written = wintypes.DWORD()
            k32.WriteFile(k32.GetStdHandle(-11), msg, len(msg), written, None)
        print("python-level noise")
        return {"pong": True}


    wk._HANDLERS["ping"] = _noisy_ping
    raise SystemExit(wk.main())
    """
)


def test_main_keeps_native_stdout_noise_off_the_protocol_stream(tmp_path) -> None:
    root = tmp_path / "ws"
    (root / "scratch.gdb").mkdir(parents=True)
    env = {
        **os.environ,
        "ARCPY_PYTHON_PATH": sys.executable,
        "ARCGIS_MCP_ALLOWED_ROOTS": str(root),
    }
    env.pop("ARCGIS_MCP_SCRATCH_GDB", None)

    proc = subprocess.run(
        [sys.executable, "-u", "-c", _NOISY_WORKER],
        input=_frame("ping", {}, job_id="fd1") + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stderr
    frames = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(frames) == 1, proc.stdout
    result = WorkerResult.model_validate_json(frames[0])
    assert result.ok is True and result.job_id == "fd1"
    assert "fd-1 noise" in proc.stderr
    assert "python-level noise" in proc.stderr
    if sys.platform == "win32":
        assert "win32-handle noise" in proc.stderr
