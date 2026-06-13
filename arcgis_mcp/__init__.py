"""arcgis_mcp — MCP bridge between Claude (JSON-RPC over stdio) and ArcPy.

Layer A (protocol) lives in ``server.py``; Layer B (execution) in
``worker.py``. ``arcpy`` must never be imported anywhere else.
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.5.1"
