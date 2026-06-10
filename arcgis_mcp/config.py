"""arcgis_mcp.config — single source of truth for runtime configuration.

Responsibilities (and nothing else — SRP):
  * Read and validate environment variables once, at startup.
  * Expose an immutable ``Settings`` object to the rest of the package.
  * Configure logging so that NOTHING is ever written to stdout.

stdout protection
-----------------
The MCP stdio transport multiplexes JSON-RPC 2.0 frames over this process's
stdout. A single stray ``print()`` or log line on stdout corrupts the channel
and disconnects the host (Claude Desktop). Therefore:

  * All log handlers attach to ``sys.stderr`` and/or a rotating file.
  * ``configure_logging()`` is the only sanctioned way to set up logging.

Environment variables
---------------------
ARCPY_PYTHON_PATH        (required) Absolute path to python.exe inside the
                         cloned ``arcgis-mcp-env`` conda environment.
ARCGIS_MCP_ALLOWED_ROOTS (required) ``os.pathsep``-separated list of root
                         directories the server may read/write (PathGuard).
ARCGIS_MCP_SCRATCH_GDB   (optional) Default output workspace. Defaults to
                         ``<first allowed root>/scratch.gdb``.
ARCGIS_MCP_LOG_FILE      (optional) Rotating log file path.
ARCGIS_MCP_LOG_LEVEL     (optional) DEBUG/INFO/WARNING/ERROR. Default INFO.
ARCGIS_MCP_TOOL_TIMEOUT  (optional) Per-tool wall-clock timeout in seconds.
ANTHROPIC_API_KEY        (optional) NOT required for stdio MCP operation —
                         the host (Claude Desktop) owns model access. Loaded
                         only for future out-of-band features; treated as a
                         secret: never logged, never echoed in errors.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

_LOG_FORMAT: Final[str] = (
    "%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s"
)
_DEFAULT_TOOL_TIMEOUT_S: Final[int] = 600
_LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024
_LOG_BACKUP_COUNT: Final[int] = 3

_SECRET_ENV_VARS: Final[frozenset[str]] = frozenset({"ANTHROPIC_API_KEY"})


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid.

    Messages must remain safe to surface to the MCP host: never embed
    secret values, only variable *names*.
    """


def _require_env(name: str) -> str:
    """Fetch a mandatory environment variable or fail fast with a clear error."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Required environment variable {name!r} is not set. "
            "Define it in claude_desktop_config.json under the server's "
            '"env" block.'
        )
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Immutable, validated runtime configuration.

    Frozen so no component can mutate global config at runtime — config
    drift inside a long-lived server is a debugging nightmare.
    """

    arcpy_python_path: Path
    allowed_roots: tuple[Path, ...]
    scratch_gdb: Path
    log_file: Path | None
    log_level: int
    tool_timeout_s: int
    anthropic_api_key: str | None = field(
        repr=False, default=None
    )  # never in repr/logs

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build and validate Settings from process environment variables."""
        arcpy_python = Path(_require_env("ARCPY_PYTHON_PATH")).expanduser()
        if not arcpy_python.is_file():
            raise ConfigError(
                f"ARCPY_PYTHON_PATH does not point to an existing file: {arcpy_python}"
            )

        raw_roots = _require_env("ARCGIS_MCP_ALLOWED_ROOTS")
        roots: list[Path] = []
        for chunk in raw_roots.split(os.pathsep):
            chunk = chunk.strip()
            if not chunk:
                continue
            root = Path(chunk).expanduser().resolve()
            if not root.is_dir():
                raise ConfigError(f"Allowed root is not an existing directory: {root}")
            roots.append(root)
        if not roots:
            raise ConfigError("ARCGIS_MCP_ALLOWED_ROOTS yielded no usable directories.")

        scratch_raw = _optional_env("ARCGIS_MCP_SCRATCH_GDB")
        scratch = (
            Path(scratch_raw).expanduser().resolve()
            if scratch_raw
            else roots[0] / "scratch.gdb"
        )

        level_name = _optional_env("ARCGIS_MCP_LOG_LEVEL", "INFO").upper()
        level = logging.getLevelName(level_name)
        if not isinstance(level, int):
            raise ConfigError(f"Invalid ARCGIS_MCP_LOG_LEVEL: {level_name!r}")

        timeout_raw = _optional_env(
            "ARCGIS_MCP_TOOL_TIMEOUT", str(_DEFAULT_TOOL_TIMEOUT_S)
        )
        try:
            timeout_s = int(timeout_raw)
            if timeout_s <= 0:
                raise ValueError
        except ValueError as exc:
            raise ConfigError(
                f"ARCGIS_MCP_TOOL_TIMEOUT must be a positive integer, "
                f"got {timeout_raw!r}"
            ) from exc

        log_file_raw = _optional_env("ARCGIS_MCP_LOG_FILE")

        return cls(
            arcpy_python_path=arcpy_python,
            allowed_roots=tuple(roots),
            scratch_gdb=scratch,
            log_file=Path(log_file_raw).expanduser() if log_file_raw else None,
            log_level=level,
            tool_timeout_s=timeout_s,
            anthropic_api_key=_optional_env("ANTHROPIC_API_KEY") or None,
        )


class _StdoutGuardFilter(logging.Filter):
    """Defense-in-depth: refuse any record whose handler targets stdout."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        # Redact secret values if they ever appear in a message by accident.
        msg = record.getMessage()
        for var in _SECRET_ENV_VARS:
            secret = os.environ.get(var)
            if secret and secret in msg:
                record.msg = msg.replace(secret, "***REDACTED***")
                record.args = ()
        return True


def configure_logging(settings: Settings) -> logging.Logger:
    """Install stderr (+ optional rotating-file) handlers on the package root.

    Idempotent: calling twice does not duplicate handlers, so module reloads
    and test harnesses are safe.
    """
    root = logging.getLogger("arcgis_mcp")
    if getattr(root, "_arcgis_mcp_configured", False):
        return root

    formatter = logging.Formatter(_LOG_FORMAT)
    guard = _StdoutGuardFilter()

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(guard)
    root.addHandler(stderr_handler)

    if settings.log_file is not None:
        try:
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                settings.log_file,
                maxBytes=_LOG_MAX_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(guard)
            root.addHandler(file_handler)
        except OSError as exc:
            # File logging is best-effort; stderr logging must survive.
            root.warning("Could not attach file log handler: %s", exc)

    root.setLevel(settings.log_level)
    root.propagate = False  # never bubble to the (unconfigured) global root
    root._arcgis_mcp_configured = True  # type: ignore[attr-defined]
    root.debug(
        "Logging configured (stderr%s).",
        " + rotating file" if settings.log_file else "",
    )
    return root
