"""Run a safe, reproducible ArcGIS Pro MCP integration benchmark.

The harness uses a dedicated allowed root and an existing scratch geodatabase.
In write-check mode it creates one uniquely named empty point feature class. It
never sends a confirmed delete request, overwrites an output, or reads user data.
Published JSON redacts every configured local path.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = "1.0.0"
REQUIRED_TOOLS = frozenset(
    {
        "health_check",
        "get_spatial_reference",
        "create_feature_class",
        "describe_dataset",
        "get_feature_count",
        "delete_dataset",
    }
)


@dataclass(frozen=True)
class BenchmarkConfig:
    """Validated inputs and declared runtime provenance."""

    arcpy_python: Path
    allowed_root: Path
    scratch_gdb: Path
    output: Path
    source_commit: str
    arcgis_pro_version: str
    expected_tool_count: int = 103
    write_check: bool = False


def validate_config(config: BenchmarkConfig) -> BenchmarkConfig:
    """Resolve paths and reject unsafe or unusable benchmark boundaries."""
    arcpy_python = config.arcpy_python.expanduser().resolve()
    allowed_root = config.allowed_root.expanduser().resolve()
    scratch_gdb = config.scratch_gdb.expanduser().resolve()
    output = config.output.expanduser().resolve()

    if not arcpy_python.is_file():
        raise ValueError(f"ArcPy interpreter does not exist: {arcpy_python}")
    if not allowed_root.is_dir():
        raise ValueError(f"Allowed root does not exist: {allowed_root}")
    if allowed_root == Path(allowed_root.anchor):
        raise ValueError("Allowed root must not be a filesystem root")
    if not scratch_gdb.is_dir() or scratch_gdb.suffix.lower() != ".gdb":
        raise ValueError(f"Scratch geodatabase does not exist: {scratch_gdb}")
    if not scratch_gdb.is_relative_to(allowed_root):
        raise ValueError("Scratch geodatabase must be inside the allowed root")
    if config.expected_tool_count < len(REQUIRED_TOOLS):
        raise ValueError("Expected tool count is smaller than the required surface")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", config.source_commit):
        raise ValueError("Source commit must be a 7-40 character hexadecimal SHA")
    if not config.arcgis_pro_version.strip():
        raise ValueError("ArcGIS Pro version must be declared")

    return BenchmarkConfig(
        arcpy_python=arcpy_python,
        allowed_root=allowed_root,
        scratch_gdb=scratch_gdb,
        output=output,
        source_commit=config.source_commit.lower(),
        arcgis_pro_version=config.arcgis_pro_version.strip(),
        expected_tool_count=config.expected_tool_count,
        write_check=config.write_check,
    )


def outside_root_probe(allowed_root: Path) -> Path:
    """Return an existing parent that a one-root PathGuard must reject."""
    parent = allowed_root.resolve().parent
    if parent == allowed_root or not parent.exists():
        raise ValueError("Cannot derive an existing outside-root probe")
    return parent


def redact(value: Any, replacements: Sequence[tuple[str, str]]) -> Any:
    """Recursively replace local paths without changing evidence structure."""
    if isinstance(value, dict):
        return {key: redact(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, replacements) for item in value]
    if isinstance(value, tuple):
        return [redact(item, replacements) for item in value]
    if not isinstance(value, str):
        return value

    redacted = value
    for source, replacement in sorted(
        replacements, key=lambda pair: len(pair[0]), reverse=True
    ):
        redacted = re.sub(
            re.escape(source), replacement, redacted, flags=re.IGNORECASE
        )
    return redacted


def summarize(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compute transparent pass/fail counts without weighted aggregation."""
    passed = sum(case.get("status") == "pass" for case in cases)
    total = len(cases)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def _result_evidence(result: Any) -> dict[str, Any]:
    payload = getattr(result, "structured_content", None)
    if payload is None:
        payload = getattr(result, "data", None)
    return {
        "is_error": bool(getattr(result, "is_error", False)),
        "payload": payload,
        "messages": [
            getattr(item, "text", str(item))
            for item in getattr(result, "content", [])
        ],
    }


async def _call_case(
    client: Any,
    *,
    case_id: str,
    tool: str,
    arguments: dict[str, Any],
    expect_error: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await client.call_tool(
            tool, arguments, raise_on_error=False, timeout=240
        )
        is_error = bool(getattr(result, "is_error", False))
        passed = is_error if expect_error else not is_error
        evidence = _result_evidence(result)
    except Exception as exc:  # benchmark boundary must preserve partial evidence
        passed = False
        evidence = {
            "is_error": True,
            "exception_type": type(exc).__name__,
            "messages": [str(exc)],
        }
    return {
        "id": case_id,
        "tool": tool,
        "expected": "error" if expect_error else "success",
        "status": "pass" if passed else "fail",
        "wall_seconds": round(time.perf_counter() - started, 3),
        "evidence": evidence,
    }


async def execute(config: BenchmarkConfig) -> dict[str, Any]:
    """Execute the declared benchmark condition and return an unsaved report."""
    benchmark_started = time.perf_counter()
    os.environ["ARCPY_PYTHON_PATH"] = str(config.arcpy_python)
    os.environ["ARCGIS_MCP_ALLOWED_ROOTS"] = str(config.allowed_root)
    os.environ["ARCGIS_MCP_SCRATCH_GDB"] = str(config.scratch_gdb)
    os.environ["ARCGIS_MCP_MAX_WORKERS"] = "1"
    os.environ.setdefault("ARCGIS_MCP_TOOL_TIMEOUT", "180")

    from fastmcp import Client

    from arcgis_mcp.server import mcp

    cases: list[dict[str, Any]] = []
    outside_probe = outside_root_probe(config.allowed_root)
    dataset_name = f"benchmark_point_{uuid.uuid4().hex[:8]}"
    dataset_path = config.scratch_gdb / dataset_name

    replacements = [
        (str(dataset_path), "<SCRATCH_GDB>/<DATASET>"),
        (str(config.scratch_gdb), "<SCRATCH_GDB>"),
        (str(config.arcpy_python), "<ARCPY_PYTHON>"),
        (str(config.allowed_root), "<ALLOWED_ROOT>"),
        (str(outside_probe), "<OUTSIDE_ROOT_PROBE>"),
    ]

    async with Client(mcp) as client:
        started = time.perf_counter()
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        missing = sorted(REQUIRED_TOOLS - tool_names)
        discovered = len(tools)
        cases.append(
            {
                "id": "discover-tool-surface",
                "tool": "tools/list",
                "expected": f"{config.expected_tool_count} tools and required names",
                "status": (
                    "pass"
                    if discovered == config.expected_tool_count and not missing
                    else "fail"
                ),
                "wall_seconds": round(time.perf_counter() - started, 3),
                "evidence": {
                    "discovered_tool_count": discovered,
                    "required_tools": sorted(REQUIRED_TOOLS),
                    "missing_required_tools": missing,
                },
            }
        )

        cases.append(
            await _call_case(
                client,
                case_id="health-check",
                tool="health_check",
                arguments={},
            )
        )
        cases.append(
            await _call_case(
                client,
                case_id="arcpy-spatial-reference",
                tool="get_spatial_reference",
                arguments={"params": {"wkid": 4326}},
            )
        )
        cases.append(
            await _call_case(
                client,
                case_id="outside-root-rejected",
                tool="describe_dataset",
                arguments={"params": {"dataset": str(outside_probe)}},
                expect_error=True,
            )
        )

        if config.write_check:
            cases.append(
                await _call_case(
                    client,
                    case_id="create-empty-feature-class",
                    tool="create_feature_class",
                    arguments={
                        "params": {
                            "out_gdb": str(config.scratch_gdb),
                            "name": dataset_name,
                            "geometry_type": "POINT",
                            "wkid": 4326,
                            "overwrite": False,
                        }
                    },
                )
            )
            cases.append(
                await _call_case(
                    client,
                    case_id="describe-created-dataset",
                    tool="describe_dataset",
                    arguments={"params": {"dataset": str(dataset_path)}},
                )
            )
            cases.append(
                await _call_case(
                    client,
                    case_id="count-created-dataset",
                    tool="get_feature_count",
                    arguments={"params": {"dataset": str(dataset_path)}},
                )
            )
            cases.append(
                await _call_case(
                    client,
                    case_id="unconfirmed-delete-rejected",
                    tool="delete_dataset",
                    arguments={
                        "params": {
                            "dataset": str(dataset_path),
                            "confirm": False,
                        }
                    },
                    expect_error=True,
                )
            )

    cases = redact(cases, replacements)
    summary = summarize(cases)
    summary["wall_seconds"] = round(time.perf_counter() - benchmark_started, 3)
    health_worker_python = next(
        (
            case.get("evidence", {}).get("payload", {}).get("worker_python")
            for case in cases
            if case.get("id") == "health-check"
            and isinstance(case.get("evidence", {}).get("payload"), dict)
        ),
        None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "arcgis-pro-mcp-smoke",
        "condition": "write-safety" if config.write_check else "read-only",
        "status": "pass" if summary["failed"] == 0 else "fail",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "source_commit": config.source_commit,
            "arcgis_mcp_bridge": importlib.metadata.version("arcgis-mcp-bridge"),
            "fastmcp": importlib.metadata.version("fastmcp"),
            "arcgis_pro": config.arcgis_pro_version,
            "host_python": platform.python_version(),
            "worker_python": health_worker_python,
            "platform": platform.system(),
            "expected_tool_count": config.expected_tool_count,
            "max_workers": 1,
        },
        "safety": {
            "allowed_root": "<ALLOWED_ROOT>",
            "scratch_gdb": "<SCRATCH_GDB>",
            "overwrite_requested": False,
            "confirmed_delete_requested": False,
            "created_artifact": (
                "<SCRATCH_GDB>/<DATASET>" if config.write_check else None
            ),
        },
        "summary": summary,
        "cases": cases,
        "limitations": [
            "Single-host integration evidence; not a portability benchmark.",
            "ArcGIS extension-dependent tools are outside this smoke condition.",
            "Case latency includes worker startup and is descriptive, not comparative.",
            "The created empty feature class is retained; no confirmed delete is sent.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arcpy-python", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--scratch-gdb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--arcgis-pro-version", required=True)
    parser.add_argument("--expected-tool-count", type=int, default=103)
    parser.add_argument(
        "--write-check",
        action="store_true",
        help="Create one uniquely named empty point feature class; never delete it.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = validate_config(
            BenchmarkConfig(
                arcpy_python=args.arcpy_python,
                allowed_root=args.allowed_root,
                scratch_gdb=args.scratch_gdb,
                output=args.output,
                source_commit=args.source_commit,
                arcgis_pro_version=args.arcgis_pro_version,
                expected_tool_count=args.expected_tool_count,
                write_check=args.write_check,
            )
        )
        report = asyncio.run(execute(config))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"benchmark configuration/execution failed: {exc}", file=sys.stderr)
        return 2

    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"result: {config.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
