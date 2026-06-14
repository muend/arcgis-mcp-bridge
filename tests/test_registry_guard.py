"""tests/test_registry_guard.py — generic path-guard enforcement
(`apply_path_guard`) and registration invariants (`register`).

The registration tests run against an ISOLATED registry (monkeypatched empty
dict) so they never pollute or collide with the real catalog populated by
importing arcgis_mcp.tools elsewhere in the session.
"""

from pathlib import Path
from typing import ClassVar

import pytest

import arcgis_mcp.registry as reg
from arcgis_mcp.contracts.base import ToolInput
from arcgis_mcp.registry import Category, ToolSpec, apply_path_guard, get, register
from arcgis_mcp.security import PathGuard, PathSecurityError

# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


class _GuardModel(ToolInput):
    """A ToolInput exercising all three path roles."""

    src: str | None = None
    dst: str | None = None
    srcs: list[str] | None = None
    overwrite: bool = False
    path_fields: ClassVar[dict[str, str]] = {
        "src": "read",
        "dst": "write",
        "srcs": "read_list",
    }


class _PlainInput(ToolInput):
    """No confirm field — invalid for a destructive spec."""


class _ConfirmInput(ToolInput):
    confirm: bool = False


def _dummy_worker(_arcpy: object, _inp: object) -> dict:
    return {}


@pytest.fixture
def guard_root(tmp_path: Path) -> tuple[PathGuard, Path]:
    root = tmp_path / "ws"
    root.mkdir()
    return PathGuard(allowed_roots=[root]), root


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the module-global registry for a fresh, auto-restored dict."""
    monkeypatch.setattr(reg, "_REGISTRY", {})


# --------------------------------------------------------------------------- #
# apply_path_guard
# --------------------------------------------------------------------------- #


def test_guard_resolves_read_field(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    model = _GuardModel(src=str(root / "in.shp"))
    out = apply_path_guard(model, guard)
    assert out.src is not None
    assert Path(out.src).is_relative_to(root)


def test_guard_resolves_read_list(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    model = _GuardModel(srcs=[str(root / "a.shp"), str(root / "b.shp")])
    out = apply_path_guard(model, guard)
    assert out.srcs is not None
    assert len(out.srcs) == 2
    assert all(Path(p).is_relative_to(root) for p in out.srcs)


def test_guard_write_honors_overwrite_flag(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, root = guard_root
    existing = root / "out.gdb"
    existing.mkdir()
    blocked = _GuardModel(dst=str(existing), overwrite=False)
    with pytest.raises(PathSecurityError, match="overwrite=False"):
        apply_path_guard(blocked, guard)

    allowed = _GuardModel(dst=str(existing), overwrite=True)
    out = apply_path_guard(allowed, guard)
    assert out.dst is not None and Path(out.dst) == existing


def test_guard_skips_none_fields_and_returns_same_instance(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, _ = guard_root
    model = _GuardModel()  # all guarded fields None
    out = apply_path_guard(model, guard)
    assert out is model  # no updates => no copy


def test_guard_rejects_path_outside_root(
    guard_root: tuple[PathGuard, Path], tmp_path: Path
) -> None:
    guard, _ = guard_root
    model = _GuardModel(src=str(tmp_path / "outside" / "x.shp"))
    with pytest.raises(PathSecurityError):
        apply_path_guard(model, guard)


# --------------------------------------------------------------------------- #
# register
# --------------------------------------------------------------------------- #


def test_register_and_retrieve(clean_registry: None) -> None:
    spec = ToolSpec(
        name="_t_ok",
        category=Category.DATA_MGMT,
        description="d",
        input_model=_PlainInput,
        worker_fn=_dummy_worker,
    )
    assert register(spec) is spec
    assert get("_t_ok") is spec


def test_register_rejects_duplicate_name(clean_registry: None) -> None:
    spec = ToolSpec(
        name="_t_dup",
        category=Category.DATA_MGMT,
        description="d",
        input_model=_PlainInput,
        worker_fn=_dummy_worker,
    )
    register(spec)
    with pytest.raises(ValueError, match="Duplicate"):
        register(spec)


def test_register_rejects_destructive_without_confirm(clean_registry: None) -> None:
    spec = ToolSpec(
        name="_t_del",
        category=Category.EDITING,
        description="d",
        input_model=_PlainInput,
        worker_fn=_dummy_worker,
        destructive=True,
    )
    with pytest.raises(ValueError, match="confirm"):
        register(spec)


def test_register_accepts_destructive_with_confirm(clean_registry: None) -> None:
    spec = ToolSpec(
        name="_t_del_ok",
        category=Category.EDITING,
        description="d",
        input_model=_ConfirmInput,
        worker_fn=_dummy_worker,
        destructive=True,
    )
    assert register(spec).destructive is True
