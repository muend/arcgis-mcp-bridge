"""Input models — Category 7: Editing & Topology (catalog #84-90)."""

from __future__ import annotations

from typing import ClassVar, List, Literal, Optional

from pydantic import Field

from .base import PathRole, ToolInput


class AppendFeaturesInput(ToolInput):
    """Append rows from one or more FCs into an existing target (mutates it)."""

    inputs: List[str] = Field(..., min_length=1, max_length=20)
    target: str = Field(..., description="Existing FC that receives the rows.")
    schema_type: Literal["TEST", "NO_TEST"] = Field(
        default="TEST",
        description="TEST = schemas must match; NO_TEST = best-effort mapping.",
    )
    confirm: bool = Field(
        default=False, description="Must be true: appends into live data."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "inputs": "read_list",
        "target": "read",
    }


class RepairGeometryInput(ToolInput):
    """Repair invalid geometries IN PLACE (RepairGeometry)."""

    in_features: str
    delete_null: bool = Field(
        default=True, description="True deletes features with null geometry."
    )
    confirm: bool = Field(
        default=False, description="Must be true: rewrites geometries in place."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"in_features": "read"}


class CheckGeometryInput(ToolInput):
    """Report (not fix) geometry problems into a table (CheckGeometry)."""

    in_features: str
    out_table: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_table": "write",
    }


class DetectFeatureChangesInput(ToolInput):
    update_features: str = Field(..., description="The newer dataset.")
    base_features: str = Field(..., description="The reference dataset.")
    out_features: str
    search_distance: str = Field(..., description="Match tolerance, e.g. '5 Meters'.")
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "update_features": "read",
        "base_features": "read",
        "out_features": "write",
    }


class DeleteIdenticalInput(ToolInput):
    """Delete duplicate rows IN PLACE by field/geometry equality."""

    dataset: str
    fields: List[str] = Field(
        ...,
        min_length=1,
        description="Comparison fields; use 'Shape' for geometry equality.",
    )
    xy_tolerance: Optional[str] = Field(
        default=None, description="e.g. '0.01 Meters' (geometry comparisons)."
    )
    confirm: bool = Field(
        default=False, description="Must be true: deletes rows irreversibly."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class EliminatePolygonPartInput(ToolInput):
    in_features: str
    out_features: str
    condition: Literal["AREA", "PERCENT", "AREA_OR_PERCENT", "AREA_AND_PERCENT"] = (
        "AREA"
    )
    part_area: float = Field(default=0.0, ge=0.0, description="Map-unit area.")
    part_area_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    eliminate_contained_parts_only: bool = True
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class TopologyCheckInput(ToolInput):
    """Validate a geodatabase topology (ValidateTopology)."""

    in_topology: str = Field(..., description="Path to the GDB topology.")
    visible_extent: bool = Field(
        default=False, description="False validates the full extent."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"in_topology": "read"}


__all__ = [
    "AppendFeaturesInput",
    "CheckGeometryInput",
    "DeleteIdenticalInput",
    "DetectFeatureChangesInput",
    "EliminatePolygonPartInput",
    "RepairGeometryInput",
    "TopologyCheckInput",
]
