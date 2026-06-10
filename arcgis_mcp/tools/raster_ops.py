"""ToolSpecs + worker implementations — Category 5: Raster Operations (catalog #60-74).

STUB — registration pattern (see map_mgmt/data_mgmt/geometry for live
examples): define _worker_fn(arcpy, inp) -> dict, then
register(ToolSpec(name, _CAT, description, InputModel, _worker_fn)).
Importing this module is what activates its tools (tools/__init__.py).
"""

from __future__ import annotations

from ..registry import Category, ToolSpec, register  # noqa: F401

_CAT = Category.RASTER

# register(ToolSpec(...))  # <- first raster_ops tool goes here
