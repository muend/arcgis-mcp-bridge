"""arcgis_mcp.tools — tool definitions grouped by catalog vertical.

Importing this package populates the global registry: each category module
registers its ToolSpecs at import time. ``server.py`` (Layer A) and
``worker.py`` (Layer B) both import it, so the tool surface and the
dispatch table can never diverge — they are read from the same registry.

To activate a new category, implement its module and ensure it is listed
here. Order = registration order = tools/list order.
"""

from __future__ import annotations

from . import (  # noqa: F401 — imports ARE the registrations
    map_mgmt,
    data_mgmt,
    geometry,
    projection,
    raster_ops,
    export_layout,
    editing,
    network,
    spatial_stats,
    vision_analytics,
)

from ..registry import all_specs, count  # noqa: F401 — convenience re-export
