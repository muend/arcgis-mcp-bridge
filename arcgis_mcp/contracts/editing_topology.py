"""Input models — Category 7: Editing & Topology (catalog #84-90)."""

from __future__ import annotations

from typing import ClassVar, List, Literal, Optional

from pydantic import Field

from .base import PathRole, ToolInput


class AppendFeaturesInput(ToolInput):
    """Append rows from one or more feature classes into an existing target."""

    inputs: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description=(
            "Absolute paths to one or more input feature classes or tables whose "
            "rows will be appended. Every path must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    target: str = Field(
        ...,
        description=(
            "Absolute path to the existing target feature class or table that "
            "will receive the appended rows. This dataset is modified in place "
            "and must be inside a configured PathGuard allowed root."
        ),
    )
    schema_type: Literal["TEST", "NO_TEST"] = Field(
        default="TEST",
        description=(
            "Schema validation mode for ArcPy Append. TEST requires compatible "
            "schemas; NO_TEST allows best-effort field mapping where ArcPy supports it."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. append_features mutates the target dataset by inserting "
            "rows from the input datasets."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "inputs": "read_list",
        "target": "read",
    }


class RepairGeometryInput(ToolInput):
    """Repair invalid geometries in place using ArcPy RepairGeometry."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class whose invalid geometries will be "
            "repaired in place. Use a copied working dataset when possible."
        ),
    )
    delete_null: bool = Field(
        default=True,
        description=(
            "When true, delete features with null geometry during repair. When "
            "false, keep null-geometry features where ArcPy allows it."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. repair_geometry rewrites feature geometries in the "
            "input dataset and may delete null-geometry rows."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"in_features": "read"}


class CheckGeometryInput(ToolInput):
    """Report geometry problems to an output table without modifying features."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class whose geometry will be checked. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path where geometry problems will be written. "
            "Existing outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_table": "write",
    }


class DetectFeatureChangesInput(ToolInput):
    """Detect changed features by comparing a newer dataset against a reference."""

    update_features: str = Field(
        ...,
        description=(
            "Absolute path to the newer or updated feature dataset being compared. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    base_features: str = Field(
        ...,
        description=(
            "Absolute path to the reference or baseline feature dataset. The path "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create with detected feature "
            "changes. Existing outputs require overwrite=true."
        ),
    )
    search_distance: str = Field(
        ...,
        description=(
            "Feature matching tolerance with units, for example '5 Meters'. Use "
            "a value appropriate to the dataset precision and expected geometry shift."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output change dataset is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "update_features": "read",
        "base_features": "read",
        "out_features": "write",
    }


class DeleteIdenticalInput(ToolInput):
    """Delete duplicate rows in place by field or geometry equality."""

    dataset: str = Field(
        ...,
        description=(
            "Absolute path to the feature class or table where duplicate rows "
            "will be removed in place. Use a copied working dataset when possible."
        ),
    )
    fields: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Comparison fields used to identify duplicate rows. Use 'Shape' when "
            "geometry equality should be part of the duplicate test."
        ),
    )
    xy_tolerance: Optional[str] = Field(
        default=None,
        description=(
            "Optional XY tolerance for geometry comparisons, for example "
            "'0.01 Meters'. Use None to let ArcPy use its default tolerance."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. delete_identical irreversibly removes duplicate rows "
            "from the input dataset."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class EliminatePolygonPartInput(ToolInput):
    """Remove small polygon holes or parts and write a cleaned output feature class."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input polygon feature class to clean. The path "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output polygon feature class path to create after eliminating "
            "small parts. Existing outputs require overwrite=true."
        ),
    )
    condition: Literal["AREA", "PERCENT", "AREA_OR_PERCENT", "AREA_AND_PERCENT"] = (
        Field(
            default="AREA",
            description=(
                "Rule used to decide which polygon parts are eliminated. AREA uses "
                "part_area, PERCENT uses part_area_percent, and combined options "
                "apply either or both thresholds."
            ),
        )
    )
    part_area: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Area threshold in map units. Polygon parts smaller than this threshold "
            "may be eliminated depending on condition."
        ),
    )
    part_area_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description=(
            "Percentage threshold from 0 to 100. Polygon parts below this percentage "
            "may be eliminated depending on condition."
        ),
    )
    eliminate_contained_parts_only: bool = Field(
        default=True,
        description=(
            "When true, eliminate only contained polygon parts such as holes. When "
            "false, allow ArcPy to eliminate qualifying parts more broadly."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing cleaned output feature class "
            "is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class TopologyCheckInput(ToolInput):
    """Validate a geodatabase topology using ArcPy ValidateTopology."""

    in_topology: str = Field(
        ...,
        description=(
            "Absolute path to the geodatabase topology to validate. The topology "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    visible_extent: bool = Field(
        default=False,
        description=(
            "When false, validate the full topology extent. When true, request "
            "visible-extent validation where the ArcPy topology context supports it."
        ),
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
