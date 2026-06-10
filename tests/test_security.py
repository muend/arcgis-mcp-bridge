"""Tests/test_security.py - PathGuard boundary and sandbox escape unit tests."""

from pathlib import Path

import pytest

from arcgis_mcp.security import PathGuard, PathSecurityError


# Pytest Fixture: Her test için izole, geçici ve fiziksel olarak var olan
# sanal çalışma alanları (sandbox) kurgular.
@pytest.fixture
def sandbox_setup(tmp_path: Path) -> tuple[PathGuard, Path, Path]:
    """Sets up real existing temporary directories for deterministic testing."""
    root1 = tmp_path / "Arcgis_Pro_MCP_Server"
    root2 = tmp_path / "GIS_Data_Workspace"

    # Sınıfın strict=True kuralını tatmin etmek için klasörleri diskte oluştur
    root1.mkdir()
    root2.mkdir()

    # Sınıf başlatıcısı (__init__) bir Path listesi/iterable bekler
    guard = PathGuard(allowed_roots=[root1, root2])
    return guard, root1, root2


def test_path_guard_allows_valid_read(sandbox_setup) -> None:
    """Ensures that valid read paths strictly inside the allowed roots pass validation."""
    guard, _, root2 = sandbox_setup
    valid_vector_path = root2 / "Layers" / "highways.shp"

    # Doğrulama: validate_read metodu ham string alır ve geriye Path nesnesi döner
    resolved_path = guard.validate_read(str(valid_vector_path))
    assert isinstance(resolved_path, Path)


def test_path_guard_allows_valid_write(sandbox_setup) -> None:
    """Ensures that valid write paths strictly inside the allowed roots pass validation."""
    guard, _, root2 = sandbox_setup
    valid_output_path = root2 / "Outputs" / "analysis_result.gdb"

    # Doğrulama: validate_write metodu ham string ve opsiyonel overwrite bayrağı alır
    resolved_path = guard.validate_write(str(valid_output_path), overwrite=True)
    assert isinstance(resolved_path, Path)


def test_path_guard_blocks_directory_traversal(sandbox_setup) -> None:
    """Ensures malicious dot-dot-slash attempts are aggressively blocked during reads."""
    guard, _, root2 = sandbox_setup
    malicious_traversal = root2 / ".." / ".." / "Windows" / "System32"

    # Kısıt Kontrolü: Sistem dışına sızma girişiminde PathSecurityError fırlatılmalıdır
    with pytest.raises(PathSecurityError):
        guard.validate_read(str(malicious_traversal))


def test_path_guard_blocks_unauthorized_roots(sandbox_setup, tmp_path: Path) -> None:
    """Ensures completely outside system paths are strictly blocked from being accessed."""
    guard, _, _ = sandbox_setup
    unauthorized_dir = tmp_path / "Unauthorized_Dir"
    unauthorized_dir.mkdir()
    unauthorized_path = unauthorized_dir / "secret_blueprint.gdb"

    with pytest.raises(PathSecurityError):
        guard.validate_read(str(unauthorized_path))
