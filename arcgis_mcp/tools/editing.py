"""ToolSpecs + worker implementations — Category 7: Editing & Topology (catalog #84-90).

STUB — registration pattern (see map_mgmt/data_mgmt/geometry for live
examples): define _worker_fn(arcpy, inp) -> dict, then
register(ToolSpec(name, _CAT, description, InputModel, _worker_fn)).
Importing this module is what activates its tools (tools/__init__.py).
"""

from __future__ import annotations

from ..registry import Category, ToolSpec, register  # noqa: F401

_CAT = Category.EDITING

# register(ToolSpec(...))  # <- first editing tool goes here
