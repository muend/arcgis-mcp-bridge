"""setup_env.py — Stage 1 administrative bootstrap for the ArcGIS MCP Bridge.

Idempotent automation script that:
  1. Locates the conda executable shipped with ArcGIS Pro.
  2. Verifies whether the dedicated ``arcgis-mcp-env`` environment exists.
  3. Clones the read-only ``arcgispro-py3`` core environment if missing.
  4. Verifies the target interpreter path and confirms ``arcpy`` imports
     inside that interpreter (out-of-process, never in this one).

Design notes
------------
* Idempotency: every mutating step is guarded by an existence check, so the
  script may be re-run safely at any time (e.g., in CI or after a Pro upgrade).
* Isolation: this script NEVER imports arcpy itself. All probing of the GIS
  stack happens in a child process running the target interpreter, mirroring
  the runtime architecture of the MCP server (Layer A / Layer B separation).
* All human-readable output goes to stderr-compatible logging; the script's
  only stdout product is a final machine-readable JSON status line, so it can
  be consumed by other automation.

Usage
-----
    python setup_env.py [--env-name arcgis-mcp-env] [--dry-run]

Exit codes: 0 = ready, 1 = environment error, 2 = conda not found.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.setup")

SOURCE_ENV_NAME: Final[str] = "arcgispro-py3"
DEFAULT_TARGET_ENV: Final[str] = "arcgis-mcp-env"

#: Conventional ArcGIS Pro conda locations, probed in order. The PRO_HOME /
#: explicit-PATH lookups run first, so these are a fallback, not a hard-coding.
_CANDIDATE_CONDA_PATHS: Final[tuple[str, ...]] = (
    r"%PROGRAMFILES%\ArcGIS\Pro\bin\Python\Scripts\conda.exe",
    r"%LOCALAPPDATA%\Programs\ArcGIS\Pro\bin\Python\Scripts\conda.exe",
)

_SUBPROCESS_TIMEOUT_S: Final[int] = 60
_CLONE_TIMEOUT_S: Final[int] = 1800  # full env clone can take 10-20 minutes


class SetupError(RuntimeError):
    """Raised when an unrecoverable setup failure occurs."""


@dataclass(frozen=True)
class EnvReport:
    """Machine-readable result of the audit, emitted as JSON on stdout."""

    conda_exe: str
    env_name: str
    env_path: str
    python_exe: str
    arcpy_ok: bool
    arcpy_version: str | None
    created: bool  # True if this run performed the clone

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)


def _configure_logging() -> None:
    """Route all diagnostics to stderr; stdout is reserved for the JSON report."""
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def _run(cmd: Sequence[str], timeout: int = _SUBPROCESS_TIMEOUT_S) -> str:
    """Run a child process, returning stdout. Raises SetupError on failure."""
    LOG.info("exec: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"Subprocess failed to run: {cmd[0]!r}: {exc}") from exc
    if proc.returncode != 0:
        raise SetupError(
            f"Command {cmd[0]!r} exited {proc.returncode}. "
            f"stderr (truncated): {proc.stderr[:2000]}"
        )
    return proc.stdout


def find_conda() -> Path:
    """Locate conda.exe: explicit env var > PATH > known ArcGIS Pro locations."""
    explicit = os.environ.get("ARCGIS_CONDA_EXE")
    if explicit:
        p = Path(explicit)
        if p.is_file():
            LOG.info("Using conda from ARCGIS_CONDA_EXE: %s", p)
            return p
        raise SetupError(f"ARCGIS_CONDA_EXE is set but not a file: {explicit}")

    on_path = shutil.which("conda")
    if on_path:
        LOG.info("Using conda from PATH: %s", on_path)
        return Path(on_path)

    for raw in _CANDIDATE_CONDA_PATHS:
        candidate = Path(os.path.expandvars(raw))
        if candidate.is_file():
            LOG.info("Using conda from known location: %s", candidate)
            return candidate

    raise SetupError(
        "conda.exe not found. Set ARCGIS_CONDA_EXE to the full path of "
        r"ArcGIS Pro's conda (e.g. C:\Program Files\ArcGIS\Pro\bin\Python"
        r"\Scripts\conda.exe)."
    )


def list_envs(conda_exe: Path) -> dict[str, Path]:
    """Return mapping of environment name -> environment root path."""
    stdout = _run([str(conda_exe), "env", "list", "--json"])
    try:
        payload = json.loads(stdout)
        env_paths = [Path(p) for p in payload["envs"]]
    except (json.JSONDecodeError, KeyError) as exc:
        raise SetupError(f"Could not parse `conda env list --json`: {exc}") from exc
    return {p.name: p for p in env_paths}


def ensure_env(conda_exe: Path, target_env: str, dry_run: bool) -> tuple[Path, bool]:
    """Idempotent core: clone arcgispro-py3 -> target_env only if missing.

    Returns (env_root_path, created_this_run).
    """
    envs = list_envs(conda_exe)

    if SOURCE_ENV_NAME not in envs:
        raise SetupError(
            f"Source environment {SOURCE_ENV_NAME!r} not found. "
            "Is ArcGIS Pro (with its Python distribution) installed?"
        )

    if target_env in envs:
        LOG.info("Environment %r already exists — skipping clone (idempotent).",
                 target_env)
        return envs[target_env], False

    if dry_run:
        LOG.info("[dry-run] Would clone %r -> %r.", SOURCE_ENV_NAME, target_env)
        # Predict the destination next to the source env's parent dir.
        return envs[SOURCE_ENV_NAME].parent / target_env, False

    LOG.info("Cloning %r -> %r (this may take several minutes)...",
             SOURCE_ENV_NAME, target_env)
    _run(
        [str(conda_exe), "create", "--name", target_env,
         "--clone", SOURCE_ENV_NAME, "--yes"],
        timeout=_CLONE_TIMEOUT_S,
    )

    envs = list_envs(conda_exe)  # re-read: trust conda, not our assumption
    if target_env not in envs:
        raise SetupError(f"Clone reported success but {target_env!r} not listed.")
    return envs[target_env], True


def verify_interpreter(env_root: Path) -> Path:
    """Confirm the cloned environment exposes a python.exe and return its path."""
    python_exe = env_root / "python.exe"
    if not python_exe.is_file():
        # POSIX layout fallback (conda on non-Windows hosts / tests).
        alt = env_root / "bin" / "python"
        if alt.is_file():
            return alt
        raise SetupError(f"No Python interpreter found under {env_root}")
    return python_exe


def verify_arcpy(python_exe: Path) -> str:
    """Import arcpy inside the TARGET interpreter and return its version string.

    Runs out-of-process so a native crash or license failure cannot take down
    this script — the same error-boundary pattern the MCP server uses.
    """
    probe = (
        "import json, arcpy; "
        "print(json.dumps({'version': arcpy.GetInstallInfo().get('Version')}))"
    )
    stdout = _run([str(python_exe), "-c", probe], timeout=300)
    try:
        return str(json.loads(stdout.strip().splitlines()[-1])["version"])
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        raise SetupError(f"arcpy probe returned unparseable output: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    _configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-name", default=DEFAULT_TARGET_ENV)
    parser.add_argument("--dry-run", action="store_true",
                        help="Audit only; never mutate conda state.")
    args = parser.parse_args(argv)

    try:
        conda_exe = find_conda()
    except SetupError as exc:
        LOG.error("%s", exc)
        return 2

    try:
        env_root, created = ensure_env(conda_exe, args.env_name, args.dry_run)
        python_exe = verify_interpreter(env_root)
        arcpy_version: str | None = None
        arcpy_ok = False
        try:
            arcpy_version = verify_arcpy(python_exe)
            arcpy_ok = True
            LOG.info("arcpy %s verified in %s", arcpy_version, python_exe)
        except SetupError as exc:
            LOG.warning("arcpy verification failed (license offline?): %s", exc)

        report = EnvReport(
            conda_exe=str(conda_exe),
            env_name=args.env_name,
            env_path=str(env_root),
            python_exe=str(python_exe),
            arcpy_ok=arcpy_ok,
            arcpy_version=arcpy_version,
            created=created,
        )
        print(report.to_json())  # the ONLY stdout output of this script
        LOG.info("Set ARCPY_PYTHON_PATH=%s for the MCP server.", python_exe)
        return 0 if arcpy_ok else 1
    except SetupError as exc:
        LOG.error("Setup failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
