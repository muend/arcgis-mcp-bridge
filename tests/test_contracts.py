"""tests/test_contracts.py — Pydantic contract enforcement: per-tool parameter
specs, cross-field validators, frozen/extra-forbid discipline, and the
ok-xor-error invariant on the IPC result envelope.

Pure unit tests: contracts import no arcpy.
"""

import pytest
from pydantic import ValidationError

from arcgis_mcp.contracts import (
    ExecuteSpatialToolInput,
    ListLayersInput,
    SpatialToolName,
    WorkerError,
    WorkerJob,
    WorkerResult,
)

# --------------------------------------------------------------------------- #
# ExecuteSpatialToolInput — per-tool parameter discipline
# --------------------------------------------------------------------------- #


def test_buffer_accepts_required_parameter() -> None:
    inp = ExecuteSpatialToolInput(
        tool=SpatialToolName.BUFFER,
        in_features="C:/data/in.gdb/roads",
        parameters={"buffer_distance_or_field": "100 Meters"},
    )
    assert inp.tool is SpatialToolName.BUFFER
    assert inp.overwrite is False  # default


def test_clip_accepts_required_and_optional() -> None:
    inp = ExecuteSpatialToolInput(
        tool=SpatialToolName.CLIP,
        in_features="C:/data/in.gdb/roads",
        parameters={"clip_features": "C:/data/in.gdb/aoi", "cluster_tolerance": "1"},
    )
    assert inp.tool is SpatialToolName.CLIP


def test_missing_required_parameter_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing required parameter"):
        ExecuteSpatialToolInput(
            tool=SpatialToolName.BUFFER,
            in_features="C:/data/in.gdb/roads",
            parameters={},
        )


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown parameter"):
        ExecuteSpatialToolInput(
            tool=SpatialToolName.BUFFER,
            in_features="C:/data/in.gdb/roads",
            parameters={"buffer_distance_or_field": "1", "bogus": "x"},
        )


def test_blank_parameter_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        ExecuteSpatialToolInput(
            tool=SpatialToolName.BUFFER,
            in_features="C:/data/in.gdb/roads",
            parameters={"buffer_distance_or_field": "1", "  ": "x"},
        )


def test_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        ExecuteSpatialToolInput(
            tool=SpatialToolName.BUFFER,
            in_features="C:/data/in.gdb/roads",
            parameters={"buffer_distance_or_field": "1"},
            unexpected_field=5,
        )


def test_input_model_is_frozen() -> None:
    inp = ExecuteSpatialToolInput(
        tool=SpatialToolName.BUFFER,
        in_features="C:/data/in.gdb/roads",
        parameters={"buffer_distance_or_field": "1"},
    )
    with pytest.raises(ValidationError):
        inp.in_features = "C:/data/in.gdb/other"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# ListLayersInput
# --------------------------------------------------------------------------- #


def test_list_layers_rejects_empty_workspace() -> None:
    with pytest.raises(ValidationError):
        ListLayersInput(workspace="")


def test_list_layers_strips_whitespace() -> None:
    inp = ListLayersInput(workspace="  C:/data/city.gdb  ")
    assert inp.workspace == "C:/data/city.gdb"


# --------------------------------------------------------------------------- #
# IPC envelope — WorkerJob / WorkerResult invariants
# --------------------------------------------------------------------------- #


def test_worker_job_rejects_unknown_op() -> None:
    with pytest.raises(ValidationError):
        WorkerJob(op="not_an_op", job_id="j1")


def test_worker_job_requires_job_id() -> None:
    with pytest.raises(ValidationError):
        WorkerJob(op="ping", job_id="")


def test_worker_result_ok_path_is_valid() -> None:
    res = WorkerResult(job_id="j1", ok=True, result={"pong": True})
    assert res.ok is True
    assert res.error is None


def test_worker_result_error_path_is_valid() -> None:
    res = WorkerResult(
        job_id="j1",
        ok=False,
        error=WorkerError(kind="security", message="blocked"),
    )
    assert res.ok is False
    assert res.error is not None


def test_worker_result_ok_with_error_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not carry an error"):
        WorkerResult(
            job_id="j1",
            ok=True,
            error=WorkerError(kind="internal", message="x"),
        )


def test_worker_result_not_ok_without_error_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires an error"):
        WorkerResult(job_id="j1", ok=False)
