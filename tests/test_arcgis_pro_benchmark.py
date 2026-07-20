"""License-free tests for the real-runtime benchmark harness."""

import json
import re
from pathlib import Path

import pytest
from benchmarks.arcgis_pro_smoke import (
    BenchmarkConfig,
    outside_root_probe,
    redact,
    summarize,
    validate_config,
)


def _config(tmp_path: Path) -> BenchmarkConfig:
    arcpy_python = tmp_path / "python.exe"
    arcpy_python.touch()
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    scratch_gdb = allowed_root / "scratch.gdb"
    scratch_gdb.mkdir()
    return BenchmarkConfig(
        arcpy_python=arcpy_python,
        allowed_root=allowed_root,
        scratch_gdb=scratch_gdb,
        output=tmp_path / "result.json",
        source_commit="c4415d8",
        arcgis_pro_version="3.7",
        write_check=True,
    )


def test_validate_config_resolves_safe_paths(tmp_path: Path) -> None:
    result = validate_config(_config(tmp_path))
    assert result.allowed_root.is_absolute()
    assert result.scratch_gdb.is_relative_to(result.allowed_root)


def test_validate_config_rejects_scratch_outside_root(tmp_path: Path) -> None:
    config = _config(tmp_path)
    outside_gdb = tmp_path / "outside.gdb"
    outside_gdb.mkdir()
    with pytest.raises(ValueError, match="inside the allowed root"):
        validate_config(
            BenchmarkConfig(
                **{
                    **config.__dict__,
                    "scratch_gdb": outside_gdb,
                }
            )
        )


def test_outside_probe_and_redaction_are_boundary_safe(tmp_path: Path) -> None:
    config = validate_config(_config(tmp_path))
    probe = outside_root_probe(config.allowed_root)
    assert probe.exists()
    assert not probe.is_relative_to(config.allowed_root)

    secret = str(config.scratch_gdb / "FeatureA")
    escaped_secret = secret.replace("\\", "\\\\")
    value = {
        "path": secret.upper(),
        "message": f'{{"created": "{escaped_secret}"}}; rejected {probe}',
        "dataset": "benchmark_point_deadbeef",
    }
    result = redact(
        value,
        [
            (secret, "<SCRATCH_GDB>/<DATASET>"),
            (str(probe), "<OUTSIDE_ROOT_PROBE>"),
            ("benchmark_point_deadbeef", "<DATASET>"),
        ],
    )
    serialized = json.dumps(result)
    assert str(tmp_path).lower() not in serialized.lower()
    assert "<SCRATCH_GDB>/<DATASET>" in serialized
    assert "<OUTSIDE_ROOT_PROBE>" in serialized
    assert "<DATASET>" in serialized


def test_summarize_uses_unweighted_case_counts() -> None:
    result = summarize([{"status": "pass"}, {"status": "fail"}])
    assert result == {"total": 2, "passed": 1, "failed": 1, "pass_rate": 0.5}


def test_published_result_is_sanitized_and_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    result_path = (
        root
        / "benchmarks"
        / "results"
        / "arcgis-pro-3.7-windows-2026-07-20.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    cases = result["cases"]
    summary = result["summary"]

    assert result["schema_version"] == "1.0.0"
    assert result["benchmark"] == "arcgis-pro-mcp-smoke"
    assert result["condition"] == "write-safety"
    assert result["status"] == "pass"
    assert re.fullmatch(r"[0-9a-f]{40}", result["environment"]["source_commit"])
    assert summary["total"] == len(cases) == 8
    assert summary["passed"] == 8
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 1.0
    assert all(case["status"] == "pass" for case in cases)

    serialized = json.dumps(result).lower()
    forbidden = (
        "c:\\\\",
        "users",
        "program files",
        "geoai-arcgis",
        "benchmark_point_",
    )
    assert not any(token in serialized for token in forbidden)
