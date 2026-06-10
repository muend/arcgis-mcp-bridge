"""Input models — Category 3: Geometry & Analysis (catalog #33-55)."""

from __future__ import annotations

from typing import ClassVar, List, Literal, Optional, Tuple

from pydantic import Field

from .base import PathRole, ToolInput
from .data_mgmt import InOutInput


class MultiInputOverlay(ToolInput):
    """Shared base: N input layers -> one output (Intersect, Union, Merge)."""

    in_features: List[str] = Field(..., min_length=2, max_length=20)
    out_features: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read_list",
        "out_features": "write",
    }


class TwoLayerOverlay(ToolInput):
    """Shared base: primary + secondary layer -> output (Erase, Identity...)."""

    in_features: str
    overlay_features: str
    out_features: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "overlay_features": "read",
        "out_features": "write",
    }


class IntersectFeaturesInput(MultiInputOverlay):
    join_attributes: Literal["ALL", "NO_FID", "ONLY_FID"] = "ALL"


class UnionFeaturesInput(MultiInputOverlay):
    pass


class EraseFeaturesInput(TwoLayerOverlay):
    pass


class DissolveFeaturesInput(InOutInput):
    dissolve_fields: List[str] = Field(default_factory=list, max_length=20)
    multi_part: bool = True


class MergeFeaturesInput(MultiInputOverlay):
    pass


class SelectByAttributeInput(InOutInput):
    where_clause: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description='SQL expression, e.g. "POP > 1000".',
    )


SpatialRelationship = Literal[
    "INTERSECT",
    "WITHIN_A_DISTANCE",
    "CONTAINS",
    "WITHIN",
    "COMPLETELY_CONTAINS",
    "COMPLETELY_WITHIN",
    "HAVE_THEIR_CENTER_IN",
    "BOUNDARY_TOUCHES",
    "SHARE_A_LINE_SEGMENT_WITH",
    "CROSSED_BY_THE_OUTLINE_OF",
]


class SelectByLocationInput(ToolInput):
    in_features: str
    select_features: str
    out_features: str
    relationship: SpatialRelationship = "INTERSECT"
    search_distance: Optional[str] = Field(
        default=None, description="e.g. '500 Meters' (WITHIN_A_DISTANCE only)."
    )
    invert: bool = Field(default=False, description="True = NOT relationship.")
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "select_features": "read",
        "out_features": "write",
    }


class SpatialJoinInput(ToolInput):
    target_features: str
    join_features: str
    out_features: str
    join_operation: Literal["JOIN_ONE_TO_ONE", "JOIN_ONE_TO_MANY"] = "JOIN_ONE_TO_ONE"
    match_option: SpatialRelationship = "INTERSECT"
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "target_features": "read",
        "join_features": "read",
        "out_features": "write",
    }


class NearAnalysisInput(ToolInput):
    in_features: str = Field(..., description="MODIFIED in place: NEAR_* fields added.")
    near_features: str
    search_radius: Optional[str] = Field(
        default=None, description="e.g. '1 Kilometers'"
    )
    confirm: bool = Field(
        default=False, description="Must be true: mutates the input dataset."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "near_features": "read",
    }


class GenerateNearTableInput(ToolInput):
    in_features: str
    near_features: str
    out_table: str
    closest_count: int = Field(default=1, ge=1, le=100)
    search_radius: Optional[str] = None
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "near_features": "read",
        "out_table": "write",
    }


class MinimumBoundingGeometryInput(InOutInput):
    geometry_type: Literal[
        "RECTANGLE_BY_AREA",
        "RECTANGLE_BY_WIDTH",
        "CONVEX_HULL",
        "CIRCLE",
        "ENVELOPE",
    ] = "CONVEX_HULL"
    group_option: Literal["NONE", "ALL"] = "NONE"


class FeatureToPointInput(InOutInput):
    point_location: Literal["CENTROID", "INSIDE"] = "CENTROID"


class FeatureVerticesToPointsInput(InOutInput):
    point_location: Literal["ALL", "MID", "START", "END", "BOTH_ENDS"] = "ALL"


class MultipartToSinglepartInput(InOutInput):
    pass


class SimplifyFeaturesInput(InOutInput):
    algorithm: Literal["POINT_REMOVE", "BEND_SIMPLIFY", "WEIGHTED_AREA"] = (
        "POINT_REMOVE"
    )
    tolerance: str = Field(..., description="e.g. '10 Meters'")


class SmoothFeaturesInput(InOutInput):
    algorithm: Literal["PAEK", "BEZIER_INTERPOLATION"] = "PAEK"
    tolerance: str = Field(
        ..., description="PAEK smoothing tolerance, e.g. '100 Meters'"
    )


class SummarizeWithinInput(ToolInput):
    in_polygons: str
    in_sum_features: str
    out_features: str
    keep_all_polygons: bool = True
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_polygons": "read",
        "in_sum_features": "read",
        "out_features": "write",
    }


class FrequencyAnalysisInput(ToolInput):
    in_table: str
    out_table: str
    frequency_fields: List[str] = Field(..., min_length=1, max_length=20)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_table": "read",
        "out_table": "write",
    }


StatType = Literal[
    "SUM",
    "MEAN",
    "MIN",
    "MAX",
    "STD",
    "COUNT",
    "FIRST",
    "LAST",
    "RANGE",
    "MEDIAN",
    "VARIANCE",
    "UNIQUE",
]


class StatisticsAnalysisInput(ToolInput):
    in_table: str
    out_table: str
    statistics_fields: List[Tuple[str, StatType]] = Field(
        ..., min_length=1, description="[[field, SUM|MEAN|...], ...]"
    )
    case_field: Optional[str] = None
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_table": "read",
        "out_table": "write",
    }


class TabulateIntersectionInput(ToolInput):
    in_zone_features: str
    zone_fields: List[str] = Field(..., min_length=1)
    in_class_features: str
    out_table: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_zone_features": "read",
        "in_class_features": "read",
        "out_table": "write",
    }


class IdentityFeaturesInput(TwoLayerOverlay):
    pass


class SymmetricalDifferenceInput(TwoLayerOverlay):
    pass


class CreateFishnetInput(ToolInput):
    out_features: str
    origin_x: float
    origin_y: float
    y_axis_y: Optional[float] = Field(
        default=None, description="Y of the orientation point; default origin_y+10."
    )
    cell_width: float = Field(..., gt=0)
    cell_height: float = Field(..., gt=0)
    rows: int = Field(..., ge=1, le=10000)
    columns: int = Field(..., ge=1, le=10000)
    geometry_type: Literal["POLYLINE", "POLYGON"] = "POLYGON"
    create_label_points: bool = False
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {"out_features": "write"}
