"""arcgis_mcp.security — PathGuard: workspace path sanitization & containment.

Threat model
------------
Tool arguments arrive from an LLM host and may be influenced by prompt
injection (e.g., a malicious string embedded in a document Claude read).
A crafted ``in_features`` like ``C:\\data\\..\\..\\Windows\\System32`` or a
UNC path to an attacker share must never reach ArcPy. PathGuard is the
single chokepoint (SRP) every filesystem-touching argument passes through.

Guarantees
----------
* Paths are fully resolved (symlinks, ``..``, relative segments collapsed)
  BEFORE the boundary check — never compare unresolved strings.
* The resolved path must be equal to, or a descendant of, one of the
  configured allowed roots.
* Geodatabase-internal references (``...\\data.gdb\\roads``) are supported:
  containment is checked on the filesystem-resolvable prefix.
* Write targets get stricter rules than read sources (overwrite opt-in).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Final, Iterable, Literal

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.security")

#: Windows device/reserved names that must never appear as a path component.
_RESERVED_COMPONENTS: Final[frozenset[str]] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Dataset name rule for things we are asked to CREATE inside a GDB:
#: ArcGIS-legal = letters, digits, underscore; must not start with a digit.
_VALID_DATASET_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_MAX_PATH_LENGTH: Final[int] = 4096


class PathSecurityError(PermissionError):
    """Raised when a path fails validation.

    Subclasses PermissionError so callers can distinguish policy rejections
    from ordinary I/O errors. Messages are safe to return to the MCP host:
    they name the rule violated, not internal directory listings.
    """


class PathGuard:
    """Validates and normalizes every filesystem path the server touches.

    Instantiated once from ``Settings.allowed_roots`` and injected into the
    tool layer (dependency inversion: tools depend on this abstraction, not
    on ``os.path`` calls scattered through the codebase).
    """

    def __init__(self, allowed_roots: Iterable[Path]) -> None:
        """Resolve and store the boundary roots.

        Raises:
            ValueError: if no usable roots are provided.
        """
        resolved: list[Path] = []
        for root in allowed_roots:
            try:
                resolved.append(Path(root).expanduser().resolve(strict=True))
            except OSError as exc:
                raise ValueError(f"Allowed root is not resolvable: {root}") from exc
        if not resolved:
            raise ValueError("PathGuard requires at least one allowed root.")
        self._roots: tuple[Path, ...] = tuple(resolved)
        LOG.info("PathGuard active with %d allowed root(s).", len(self._roots))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def validate_read(self, raw: str) -> Path:
        """Validate a path used as an INPUT (must exist, at least as a prefix).

        Args:
            raw: untrusted path string, possibly a GDB-internal reference.

        Returns:
            The fully resolved path (GDB-internal tail re-appended verbatim).

        Raises:
            PathSecurityError: on any policy violation.
        """
        resolved, tail = self._resolve(raw)
        self._assert_contained(resolved)
        if not resolved.exists():
            raise PathSecurityError(f"Input path does not exist on disk: {resolved}")
        return self._rejoin(resolved, tail)

    def validate_write(
        self,
        raw: str,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Validate a path used as an OUTPUT target.

        Stricter than reads: the parent container must exist inside the
        boundary, the leaf dataset name must be ArcGIS-legal, and clobbering
        an existing dataset requires the explicit ``overwrite`` flag
        (idempotency guard — a blind retry can never silently destroy data).

        Raises:
            PathSecurityError: on any policy violation.
        """
        resolved, tail = self._resolve(raw)
        self._assert_contained(resolved)

        leaf = tail[-1] if tail else resolved.name
        dataset_name = leaf.rsplit(".", 1)[0]  # tolerate shapefile suffixes
        if not _VALID_DATASET_NAME.match(dataset_name):
            raise PathSecurityError(
                f"Output dataset name {leaf!r} is not a valid ArcGIS name "
                "(letters, digits, underscore; must not start with a digit)."
            )

        full = self._rejoin(resolved, tail)
        if not overwrite and self._dataset_exists(resolved, tail):
            raise PathSecurityError(
                f"Output already exists and overwrite=False: {full}. "
                "Pass overwrite=true to replace it explicitly."
            )
        return full

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _resolve(self, raw: str) -> tuple[Path, list[str]]:
        """Normalize an untrusted string into (resolved fs prefix, gdb tail).

        A path like ``C:\\data\\city.gdb\\roads`` has a filesystem-resolvable
        prefix (``city.gdb`` is a real directory) and a logical tail
        (``roads``) that only ArcPy understands. We resolve the deepest
        prefix that exists; remaining components become the tail and are
        validated as dataset names (they can't smuggle traversal sequences).
        """
        candidate = (raw or "").strip().strip('"')
        if not candidate:
            raise PathSecurityError("Empty path is not permitted.")
        if len(candidate) > _MAX_PATH_LENGTH:
            raise PathSecurityError("Path exceeds maximum permitted length.")
        if "\x00" in candidate:
            raise PathSecurityError("Path contains a NUL byte.")
        if candidate.startswith(("\\\\", "//")):
            raise PathSecurityError("UNC / network share paths are not permitted.")

        path = Path(candidate).expanduser()
        if not path.is_absolute():
            raise PathSecurityError(
                f"Relative paths are not permitted: {candidate!r}. "
                "Provide an absolute path inside an allowed workspace."
            )

        for component in path.parts:
            stem = component.split(".")[0].upper()
            if stem in _RESERVED_COMPONENTS:
                raise PathSecurityError(f"Reserved device name in path: {component!r}")

        # Walk upward to find the deepest existing prefix.
        tail: list[str] = []
        prefix = path
        while not prefix.exists() and prefix != prefix.parent:
            tail.insert(0, prefix.name)
            prefix = prefix.parent

        try:
            resolved_prefix = prefix.resolve(strict=False)
        except OSError as exc:  # exotic FS errors still must not escape
            raise PathSecurityError(f"Path could not be resolved: {exc}") from exc

        # Tail components are logical (GDB-internal or to-be-created): they
        # must be plain names, never traversal or separators.
        for name in tail:
            if name in {".", ".."} or os.sep in name or "/" in name:
                raise PathSecurityError(
                    f"Illegal path component after resolution: {name!r}"
                )

        return resolved_prefix, tail

    def _assert_contained(self, resolved: Path) -> None:
        """Boundary check: resolved must sit under one allowed root."""
        for root in self._roots:
            if resolved == root or resolved.is_relative_to(root):
                return
        LOG.warning("Boundary rejection: %s", resolved)
        raise PathSecurityError(
            f"Path {resolved} is outside every allowed workspace root."
        )

    @staticmethod
    def _rejoin(prefix: Path, tail: list[str]) -> Path:
        return prefix.joinpath(*tail) if tail else prefix

    @staticmethod
    def _dataset_exists(prefix: Path, tail: list[str]) -> bool:
        """Best-effort existence check without importing arcpy.

        If the target is GDB-internal (non-empty tail under an existing
        ``.gdb``), true existence is only knowable via arcpy. We return
        False here and let the worker enforce ``arcpy.env.overwriteOutput``
        accordingly — the conservative default still blocks plain-file
        clobbering, which is the case we can decide locally.
        """
        if tail:
            return False
        return prefix.exists()


__all__: Final[tuple[str, ...]] = ("PathGuard", "PathSecurityError")

# Re-export type alias for tool-layer signatures.
AccessMode = Literal["read", "write"]
