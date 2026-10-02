"""tests/test_input_existence.py — missing inputs are classified, not crashes.

Issue #27: a dataset that does not exist used to surface as
``internal: Unexpected worker error (OSError); see server logs`` for some tools
and as a geoprocessing error for others. Every read-role input is now checked
before the tool runs and reported as ``not_found`` with the offending path;
OSError from non-GP arcpy calls keeps ArcPy's message, and a truly unexpected
error carries its text instead of pointing at logs a model cannot read.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
from pydantic import Field

import arcgis_mcp.registry as reg
from arcgis_mcp.contracts import WorkerJob
from arcgis_mcp.contracts.base import PathRole, ToolInput
from arcgis_mcp.registry import (
    Category,
    InputNotFoundError,
    ToolSpec,
    require_inputs_exist,
)
from arcgis_mcp.security import PathGuard
from arcgis_mcp.tools.data_mgmt import _get_extent
from arcgis_mcp.tools.geometry import _shape_type
from arcgis_mcp.worker import process_frame


class _Roles(ToolInput):
    src: str
    srcs: list[str] = Field(default_factory=list)
    dst: str | None = None
    opt: str | None = None
    path_fields: ClassVar[dict[str, PathRole]] = {
        "src": "read",
        "srcs": "read_list",
        "dst": "write",
        "opt": "read",
    }


def _frame(op: str, payload: dict) -> str:
    return WorkerJob(op=op, payload=payload, job_id="j1").model_dump_json()


@pytest.fixture
def ws(tmp_path: Path) -> tuple[PathGuard, Path]:
    root = tmp_path / "ws"
    (root / "scratch.gdb").mkdir(parents=True)
    return PathGuard(allowed_roots=[root]), root


@pytest.fixture
def arcpy_exists(monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """Make the mock arcpy.Exists answer from a set the test controls."""
    known: set[str] = set()
    monkeypatch.setattr(sys.modules["arcpy"], "Exists", lambda p: p in known)
    return known


@pytest.fixture
def real_execute_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys.modules["arcpy"],
        "ExecuteError",
        type("ExecuteError", (Exception,), {}),
        raising=False,
    )


# --------------------------------------------------------------------------- #
# require_inputs_exist
# --------------------------------------------------------------------------- #


def test_all_present_passes() -> None:
    inp = _Roles(src="a", srcs=["b", "c"], dst="missing-output")
    require_inputs_exist(inp, lambda p: p in {"a", "b", "c"})


def test_missing_read_names_field_and_path() -> None:
    with pytest.raises(InputNotFoundError) as info:
        require_inputs_exist(_Roles(src="a"), lambda p: False)
    assert info.value.field == "src" and info.value.path == "a"
    assert "does not exist: a" in str(info.value)


def test_missing_member_of_read_list() -> None:
    inp = _Roles(src="a", srcs=["b", "gone"])
    with pytest.raises(InputNotFoundError, match=r"'srcs'.*gone"):
        require_inputs_exist(inp, lambda p: p != "gone")


def test_write_and_unset_optional_paths_are_not_checked() -> None:
    checked: list[str] = []
    require_inputs_exist(_Roles(src="a", dst="d"), lambda p: checked.append(p) or True)
    assert checked == ["a"]


# --------------------------------------------------------------------------- #
# Issue #27 reproduction: the four read-only metadata tools
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tool", ["get_extent", "describe_dataset", "get_field_info", "get_feature_count"]
)
def test_missing_dataset_is_not_found_for_metadata_tools(
    ws: tuple[PathGuard, Path], arcpy_exists: set[str], tool: str
) -> None:
    guard, root = ws
    missing = str(root / "scratch.gdb" / "this_dataset_never_existed")

    res = process_frame(_frame("run_tool", {"tool": tool, "args": {"dataset": missing}}), guard)

    assert res.ok is False and res.error is not None
    assert res.error.kind == "not_found"
    assert "this_dataset_never_existed" in res.error.message


def test_gdb_internal_dataset_known_to_arcpy_runs(
    ws: tuple[PathGuard, Path], arcpy_exists: set[str]
) -> None:
    guard, root = ws
    present = str(root / "scratch.gdb" / "roads")
    arcpy_exists.add(present)

    res = process_frame(
        _frame("run_tool", {"tool": "get_feature_count", "args": {"dataset": present}}),
        guard,
    )
    assert res.ok is True


def test_file_on_disk_needs_no_arcpy_lookup(
    ws: tuple[PathGuard, Path], arcpy_exists: set[str]
) -> None:
    guard, root = ws
    shp = root / "roads.shp"
    shp.write_bytes(b"")  # exists on disk; arcpy_exists stays empty

    res = process_frame(
        _frame("run_tool", {"tool": "get_feature_count", "args": {"dataset": str(shp)}}),
        guard,
    )
    assert res.ok is True


def test_missing_list_layers_workspace_is_not_found(
    ws: tuple[PathGuard, Path], arcpy_exists: set[str]
) -> None:
    guard, root = ws
    res = process_frame(_frame("list_layers", {"workspace": str(root / "nope.gdb")}), guard)
    assert res.error is not None and res.error.kind == "not_found"


def test_missing_clip_features_is_not_found(
    ws: tuple[PathGuard, Path], arcpy_exists: set[str]
) -> None:
    guard, root = ws
    present = str(root / "scratch.gdb" / "roads")
    arcpy_exists.add(present)
    payload = {
        "tool": "Clip_analysis",
        "in_features": present,
        "out_features": str(root / "scratch.gdb" / "clipped"),
        "parameters": {"clip_features": str(root / "scratch.gdb" / "aoi")},
    }
    res = process_frame(_frame("execute_spatial_tool", payload), guard)
    assert res.error is not None and res.error.kind == "not_found"
    assert "clip_features" in res.error.message


# --------------------------------------------------------------------------- #
# Error boundary: OSError, PermissionError, unexpected errors
# --------------------------------------------------------------------------- #


class _NoPaths(ToolInput):
    pass


def _register_raising(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _boom(_arcpy: object, _inp: object) -> dict:
        raise exc

    spec = ToolSpec("t_raise", Category.DATA_MGMT, "d", _NoPaths, _boom)
    monkeypatch.setattr(reg, "_REGISTRY", {spec.name: spec})


@pytest.mark.usefixtures("real_execute_error")
def test_arcpy_oserror_keeps_its_message(
    ws: tuple[PathGuard, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = ws
    _register_raising(monkeypatch, OSError('"C:\\x.gdb\\fc" does not exist'))
    res = process_frame(_frame("run_tool", {"tool": "t_raise", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "geoprocessing"
    assert "does not exist" in res.error.message


@pytest.mark.usefixtures("real_execute_error")
def test_permission_error_inside_tool_stays_security(
    ws: tuple[PathGuard, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = ws
    _register_raising(monkeypatch, PermissionError("set confirm=true"))
    res = process_frame(_frame("run_tool", {"tool": "t_raise", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "security"


@pytest.mark.usefixtures("real_execute_error")
def test_internal_error_carries_exception_text(
    ws: tuple[PathGuard, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    guard, _ = ws
    _register_raising(monkeypatch, RuntimeError("layer   has\nno data source"))
    res = process_frame(_frame("run_tool", {"tool": "t_raise", "args": {}}), guard)
    assert res.error is not None and res.error.kind == "internal"
    assert res.error.message == (
        "Unexpected worker error (RuntimeError): layer has no data source"
    )


# --------------------------------------------------------------------------- #
# Non-spatial data passed to spatial-only tools
# --------------------------------------------------------------------------- #


class _FakeArcpy:
    def __init__(self, desc: object) -> None:
        self._desc = desc

    def Describe(self, _path: str) -> object:  # mirrors arcpy
        return self._desc


def test_get_extent_on_table_is_a_clear_error() -> None:
    from arcgis_mcp.contracts.data_mgmt import GetExtentInput

    arcpy = _FakeArcpy(SimpleNamespace(dataType="Table"))
    with pytest.raises(ValueError, match=r"no spatial extent.*Table"):
        _get_extent(arcpy, GetExtentInput(dataset="C:/d.gdb/t"))


def test_shape_type_of_table_is_reported_not_raised() -> None:
    assert _shape_type(_FakeArcpy(SimpleNamespace(dataType="Table")), "t") == (
        "no geometry"
    )
