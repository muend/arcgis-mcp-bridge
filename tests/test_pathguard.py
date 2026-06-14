"""tests/test_pathguard.py — deep PathGuard containment, normalization, and
write-discipline coverage (complements the smoke set in test_security.py).

Pure unit tests: PathGuard never imports arcpy, so nothing here is mocked.
"""

from pathlib import Path

import pytest

from arcgis_mcp.security import PathGuard, PathSecurityError


@pytest.fixture
def guard_root(tmp_path: Path) -> tuple[PathGuard, Path]:
    """A PathGuard with a single, real, resolved allowed root."""
    root = tmp_path / "workspace"
    root.mkdir()
    return PathGuard(allowed_roots=[root]), root


# --------------------------------------------------------------------------- #
# __init__
# --------------------------------------------------------------------------- #


def test_init_rejects_empty_roots() -> None:
    with pytest.raises(ValueError, match="at least one allowed root"):
        PathGuard(allowed_roots=[])


def test_init_rejects_unresolvable_root(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="not resolvable"):
        PathGuard(allowed_roots=[missing])


# --------------------------------------------------------------------------- #
# validate_read — acceptance
# --------------------------------------------------------------------------- #


def test_read_allows_path_inside_root(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    target = root / "Layers" / "roads.shp"  # need not exist on disk
    resolved = guard.validate_read(str(target))
    assert isinstance(resolved, Path)
    assert resolved.is_relative_to(root)


def test_read_preserves_gdb_internal_tail(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    (root / "city.gdb").mkdir()  # the filesystem-resolvable prefix exists
    resolved = guard.validate_read(str(root / "city.gdb" / "roads"))
    assert resolved.name == "roads"
    assert resolved.parent.name == "city.gdb"


def test_read_strips_surrounding_quotes(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    resolved = guard.validate_read(f'"{root}"')
    assert resolved == root


# --------------------------------------------------------------------------- #
# validate_read — rejection
# --------------------------------------------------------------------------- #


def test_read_rejects_path_outside_all_roots(
    guard_root: tuple[PathGuard, Path], tmp_path: Path
) -> None:
    guard, _ = guard_root
    outside = tmp_path / "elsewhere" / "secret.gdb"
    with pytest.raises(PathSecurityError, match="outside every allowed"):
        guard.validate_read(str(outside))


def test_read_rejects_directory_traversal(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, root = guard_root
    with pytest.raises(PathSecurityError):
        guard.validate_read(str(root / ".." / ".." / "Windows" / "System32"))


@pytest.mark.parametrize(
    "bad",
    [
        r"\\server\share\data.gdb",  # UNC backslash
        "//server/share/data.gdb",  # UNC forward-slash
        "relative/path.shp",  # not absolute
        "   ",  # empty after strip
    ],
)
def test_read_rejects_malformed_paths(
    guard_root: tuple[PathGuard, Path], bad: str
) -> None:
    guard, _ = guard_root
    with pytest.raises(PathSecurityError):
        guard.validate_read(bad)


def test_read_rejects_nul_byte(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    with pytest.raises(PathSecurityError, match="NUL"):
        guard.validate_read(f"{root}\x00evil")


def test_read_rejects_overlong_path(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    with pytest.raises(PathSecurityError, match="maximum permitted length"):
        guard.validate_read(f"{root}\\" + "a" * 5000)


@pytest.mark.parametrize("device", ["CON", "PRN", "AUX", "NUL", "COM1", "LPT9"])
def test_read_rejects_reserved_device_names(
    guard_root: tuple[PathGuard, Path], device: str
) -> None:
    guard, root = guard_root
    with pytest.raises(PathSecurityError, match="Reserved device name"):
        guard.validate_read(str(root / device / "data.shp"))


# --------------------------------------------------------------------------- #
# validate_write — dataset-name rules + overwrite discipline
# --------------------------------------------------------------------------- #


def test_write_allows_valid_new_target(guard_root: tuple[PathGuard, Path]) -> None:
    guard, root = guard_root
    out = guard.validate_write(str(root / "Outputs" / "result.gdb"), overwrite=False)
    assert out.is_relative_to(root)


@pytest.mark.parametrize("bad_leaf", ["9roads", "bad-name", "has space"])
def test_write_rejects_illegal_dataset_name(
    guard_root: tuple[PathGuard, Path], bad_leaf: str
) -> None:
    guard, root = guard_root
    with pytest.raises(PathSecurityError, match="not a valid ArcGIS name"):
        guard.validate_write(str(root / bad_leaf), overwrite=True)


def test_write_tolerates_shapefile_suffix(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, root = guard_root
    out = guard.validate_write(str(root / "roads.shp"), overwrite=True)
    assert out.name == "roads.shp"


def test_write_blocks_existing_without_overwrite(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, root = guard_root
    existing = root / "out.gdb"
    existing.mkdir()  # a real, on-disk dataset (empty tail => existence is decidable)
    with pytest.raises(PathSecurityError, match="overwrite=False"):
        guard.validate_write(str(existing), overwrite=False)


def test_write_allows_existing_with_overwrite(
    guard_root: tuple[PathGuard, Path]
) -> None:
    guard, root = guard_root
    existing = root / "out.gdb"
    existing.mkdir()
    out = guard.validate_write(str(existing), overwrite=True)
    assert out == existing
