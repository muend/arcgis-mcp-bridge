"""tests/test_config.py — Settings.from_environment validation, including the
#7 fail-fast on a missing scratch geodatabase.

Each test runs with a cleaned environment (autouse fixture) so ambient
ARCGIS_MCP_* / ARCPY_PYTHON_PATH values on the developer machine can't leak in.
"""

from pathlib import Path

import pytest

from arcgis_mcp.config import ConfigError, Settings

_ENV_VARS = (
    "ARCPY_PYTHON_PATH",
    "ARCGIS_MCP_ALLOWED_ROOTS",
    "ARCGIS_MCP_SCRATCH_GDB",
    "ARCGIS_MCP_LOG_LEVEL",
    "ARCGIS_MCP_TOOL_TIMEOUT",
    "ARCGIS_MCP_MAX_WORKERS",
    "ARCGIS_MCP_LOG_FILE",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _set_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, make_scratch: bool = True
) -> Path:
    """Set a minimally valid ARCPY_PYTHON_PATH + ALLOWED_ROOTS; return the root."""
    py = tmp_path / "python.exe"
    py.write_text("")  # a real file => passes is_file()
    root = tmp_path / "ws"
    root.mkdir()
    if make_scratch:
        (root / "scratch.gdb").mkdir()
    monkeypatch.setenv("ARCPY_PYTHON_PATH", str(py))
    monkeypatch.setenv("ARCGIS_MCP_ALLOWED_ROOTS", str(root))
    return root


# --------------------------------------------------------------------------- #
# #7 — scratch geodatabase fail-fast
# --------------------------------------------------------------------------- #


def test_missing_scratch_gdb_fails_fast(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_base(monkeypatch, tmp_path, make_scratch=False)
    with pytest.raises(ConfigError, match="Scratch geodatabase does not exist"):
        Settings.from_environment()


def test_present_scratch_gdb_builds_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _set_base(monkeypatch, tmp_path, make_scratch=True)
    settings = Settings.from_environment()
    assert settings.scratch_gdb.name == "scratch.gdb"
    assert settings.allowed_roots[0] == root.resolve()


def test_explicit_scratch_gdb_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_base(monkeypatch, tmp_path, make_scratch=False)
    custom = tmp_path / "custom.gdb"
    custom.mkdir()
    monkeypatch.setenv("ARCGIS_MCP_SCRATCH_GDB", str(custom))
    settings = Settings.from_environment()
    assert settings.scratch_gdb == custom.resolve()


# --------------------------------------------------------------------------- #
# Required / structural validation
# --------------------------------------------------------------------------- #


def test_missing_arcpy_python_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARCGIS_MCP_ALLOWED_ROOTS", str(tmp_path))
    with pytest.raises(ConfigError, match="ARCPY_PYTHON_PATH"):
        Settings.from_environment()


def test_arcpy_python_path_not_a_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARCPY_PYTHON_PATH", str(tmp_path / "nope.exe"))
    monkeypatch.setenv("ARCGIS_MCP_ALLOWED_ROOTS", str(tmp_path))
    with pytest.raises(ConfigError, match="existing file"):
        Settings.from_environment()


def test_allowed_root_not_a_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    py = tmp_path / "python.exe"
    py.write_text("")
    monkeypatch.setenv("ARCPY_PYTHON_PATH", str(py))
    monkeypatch.setenv("ARCGIS_MCP_ALLOWED_ROOTS", str(tmp_path / "ghost"))
    with pytest.raises(ConfigError, match="not an existing directory"):
        Settings.from_environment()


def test_allowed_roots_unset_uses_home_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    py = tmp_path / "python.exe"
    py.write_text("")
    home = tmp_path / "home"
    projects = home / "Documents" / "ArcGIS" / "Projects"
    projects.mkdir(parents=True)
    (projects / "scratch.gdb").mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("ARCPY_PYTHON_PATH", str(py))
    settings = Settings.from_environment()  # ALLOWED_ROOTS intentionally unset
    assert settings.allowed_roots[0] == projects.resolve()


@pytest.mark.parametrize("level", ["BOGUS", "verbose", "42x"])
def test_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, level: str
) -> None:
    _set_base(monkeypatch, tmp_path)
    monkeypatch.setenv("ARCGIS_MCP_LOG_LEVEL", level)
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        Settings.from_environment()


@pytest.mark.parametrize("bad", ["0", "-5", "abc"])
def test_invalid_tool_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
) -> None:
    _set_base(monkeypatch, tmp_path)
    monkeypatch.setenv("ARCGIS_MCP_TOOL_TIMEOUT", bad)
    with pytest.raises(ConfigError, match="positive integer"):
        Settings.from_environment()


@pytest.mark.parametrize("bad", ["0", "abc"])
def test_invalid_max_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
) -> None:
    _set_base(monkeypatch, tmp_path)
    monkeypatch.setenv("ARCGIS_MCP_MAX_WORKERS", bad)
    with pytest.raises(ConfigError, match="positive integer"):
        Settings.from_environment()
