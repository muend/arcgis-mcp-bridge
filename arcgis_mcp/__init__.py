"""arcgis_mcp — MCP bridge between Claude (JSON-RPC over stdio) and ArcPy.

Layer A (protocol) lives in ``server.py``; Layer B (execution) in
``worker.py``. ``arcpy`` must never be imported anywhere else.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    # Single source of truth: the version is read from installed package
    # metadata, which setuptools-scm stamps from the git tag at build time —
    # so __init__, pyproject and the published artifact can never drift.
    __version__ = version("arcgis-mcp-bridge")
except PackageNotFoundError:  # raw source tree that was never installed
    __version__ = "0.0.0+unknown"
