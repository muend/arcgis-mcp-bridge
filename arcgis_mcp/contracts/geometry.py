"""Input models â€” Category 3: Geometry & Analysis (catalog #33-55)."""

from __future__ import annotations

from typing import ClassVar, List, Literal, Optional, Tuple

from pydantic import Field

from .base import PathRole, ToolInput
from .data_mgmt import InOutInput


class MultiInputOverlay(ToolInput):
    """Shared base for overlay tools that read multiple inputs and write one output."""

    in_features: List[str] = Field(
        ...,
        min_length=2,
        max_length=20,
        description=(
            "Absolute paths to two or more existing input feature classes or "
            "layers. Every path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create from the overlay result. "
            "The path must be inside a configured PathGuard allowed root; existing "
            "outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read_list",
        "out_features": "write",
    }


class TwoLayerOverlay(ToolInput):
    """Shared base for tools that overlay one primary layer with one secondary layer."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the primary input feature class or layer. The path "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    overlay_features: str = Field(
        ...,
        description=(
            "Absolute path to the secondary overlay feature class or layer. The "
            "path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create. The path must be inside "
            "a configured PathGuard allowed root; existing outputs require "
            "overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "overlay_features": "read",
        "out_features": "write",
    }


class IntersectFeaturesInput(MultiInputOverlay):
    """Input contract for creating the shared geometry of multiple feature layers."""

    join_attributes: Literal["ALL", "NO_FID", "ONLY_FID"] = Field(
        default="ALL",
        description=(
            "Attribute transfer mode for ArcPy Intersect. ALL keeps all input "
            "attributes, NO_FID drops feature ID fields, and ONLY_FID keeps only "
            "feature ID fields."
        ),
    )


class UnionFeaturesInput(MultiInputOverlay):
    """Input contract for polygon union overlay."""


class EraseFeaturesInput(TwoLayerOverlay):
    """Input contract for subtracting overlay features from primary features."""


class DissolveFeaturesInput(InOutInput):
    """Input contract for dissolving features by shared attribute values."""

    dissolve_fields: List[str] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Optional field names used to group features before dissolving. Use an "
            "empty list to dissolve all input features into one multipart or "
            "singlepart output."
        ),
    )
    multi_part: bool = Field(
        default=True,
        description=(
            "When true, allow multipart output features. When false, force "
            "singlepart output where ArcPy supports it."
        ),
    )


class MergeFeaturesInput(MultiInputOverlay):
    """Input contract for merging multiple compatible feature layers."""


class SelectByAttributeInput(InOutInput):
    """Input contract for materializing a SQL attribute selection."""

    where_clause: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description=(
            'SQL expression used to select rows, for example "POP > 1000". '
            "The expression is passed to ArcPy Select and should match the input "
            "workspace SQL dialect."
        ),
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
    """Input contract for materializing a spatial relationship selection."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class or layer from which features "
            "will be selected. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    select_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class or layer used as the spatial "
            "selector. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path containing the selected features. "
            "Existing outputs require overwrite=true."
        ),
    )
    relationship: SpatialRelationship = Field(
        default="INTERSECT",
        description=(
            "Spatial relationship used for the selection, such as INTERSECT, "
            "WITHIN, CONTAINS, or WITHIN_A_DISTANCE."
        ),
    )
    search_distance: Optional[str] = Field(
        default=None,
        description=(
            "Optional search distance such as '500 Meters'. Primarily used with "
            "WITHIN_A_DISTANCE; leave None for relationships that do not require "
            "a distance."
        ),
    )
    invert: bool = Field(
        default=False,
        description=(
            "When true, select features that do not satisfy the requested spatial "
            "relationship."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "select_features": "read",
        "out_features": "write",
    }


class SpatialJoinInput(ToolInput):
    """Input contract for joining attributes by spatial relationship."""

    target_features: str = Field(
        ...,
        description=(
            "Absolute path to the target feature class or layer that will receive "
            "joined attributes. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    join_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class or layer whose attributes will be "
            "joined to the target features. The path must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create with the spatial join "
            "result. Existing outputs require overwrite=true."
        ),
    )
    join_operation: Literal["JOIN_ONE_TO_ONE", "JOIN_ONE_TO_MANY"] = Field(
        default="JOIN_ONE_TO_ONE",
        description=(
            "Join cardinality. JOIN_ONE_TO_ONE aggregates matching join features "
            "onto each target feature; JOIN_ONE_TO_MANY creates one output row per "
            "target/join match."
        ),
    )
    match_option: SpatialRelationship = Field(
        default="INTERSECT",
        description=(
            "Spatial match rule used to relate target and join features, such as "
            "INTERSECT, WITHIN, CONTAINS, or WITHIN_A_DISTANCE."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "target_features": "read",
        "join_features": "read",
        "out_features": "write",
    }


class NearAnalysisInput(ToolInput):
    """Input contract for ArcPy Near, which mutates the input dataset."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class that will be modified in "
            "place. ArcPy Near adds or updates NEAR_FID and NEAR_DIST fields, so "
            "use a copied working dataset when possible."
        ),
    )
    near_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class used to find nearest features. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    search_radius: Optional[str] = Field(
        default=None,
        description=(
            "Optional maximum search radius, for example '1 Kilometers'. Use None "
            "to let ArcPy search for the nearest feature without a radius limit."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. near_analysis mutates the input dataset by adding or "
            "updating NEAR_* fields."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "near_features": "read",
    }


class GenerateNearTableInput(ToolInput):
    """Input contract for writing nearest-neighbor relationships to a table."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class whose nearby features will "
            "be measured. The path must be inside a configured PathGuard allowed root."
        ),
    )
    near_features: str = Field(
        ...,
        description=(
            "Absolute path to the feature class searched for near candidates. The "
            "path must be inside a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path to create with near-feature relationships "
            "and distances. Existing outputs require overwrite=true."
        ),
    )
    closest_count: int = Field(
        default=1,
        ge=1,
        le=100,
        description=(
            "Maximum number of nearest candidates to write per input feature. "
            "Use 1 for nearest-only workflows."
        ),
    )
    search_radius: Optional[str] = Field(
        default=None,
        description=(
            "Optional maximum search radius, for example '500 Meters'. Use None "
            "to allow ArcPy to search without a radius limit."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "near_features": "read",
        "out_table": "write",
    }


class MinimumBoundingGeometryInput(InOutInput):
    """Input contract for creating bounding geometry around features."""

    geometry_type: Literal[
        "RECTANGLE_BY_AREA",
        "RECTANGLE_BY_WIDTH",
        "CONVEX_HULL",
        "CIRCLE",
        "ENVELOPE",
    ] = Field(
        default="CONVEX_HULL",
        description=(
            "Bounding geometry type to create, such as CONVEX_HULL, ENVELOPE, "
            "CIRCLE, RECTANGLE_BY_AREA, or RECTANGLE_BY_WIDTH."
        ),
    )
    group_option: Literal["NONE", "ALL"] = Field(
        default="NONE",
        description=(
            "Grouping behavior for bounding geometry creation. NONE creates "
            "bounding geometry per feature; ALL creates one geometry for all inputs."
        ),
    )


class FeatureToPointInput(InOutInput):
    """Input contract for converting features to representative points."""

    point_location: Literal["CENTROID", "INSIDE"] = Field(
        default="CENTROID",
        description=(
            "Point placement method. CENTROID uses the geometric centroid; INSIDE "
            "places the point inside the input feature when possible."
        ),
    )


class FeatureVerticesToPointsInput(InOutInput):
    """Input contract for extracting vertices from features as points."""

    point_location: Literal["ALL", "MID", "START", "END", "BOTH_ENDS"] = Field(
        default="ALL",
        description=(
            "Which vertices to extract as points: ALL vertices, MID points, START "
            "vertices, END vertices, or BOTH_ENDS for line endpoints."
        ),
    )


class MultipartToSinglepartInput(InOutInput):
    """Input contract for splitting multipart features into singlepart features."""


class SimplifyFeaturesInput(InOutInput):
    """Input contract for simplifying polygon or polyline geometry."""

    algorithm: Literal["POINT_REMOVE", "BEND_SIMPLIFY", "WEIGHTED_AREA"] = Field(
        default="POINT_REMOVE",
        description=(
            "Simplification algorithm passed to ArcPy. POINT_REMOVE is general "
            "purpose, BEND_SIMPLIFY preserves major bends, and WEIGHTED_AREA is "
            "commonly used for polygon simplification."
        ),
    )
    tolerance: str = Field(
        ...,
        description=(
            "Simplification tolerance with units, for example '10 Meters'. Larger "
            "values remove more detail."
        ),
    )


class SmoothFeaturesInput(InOutInput):
    """Input contract for smoothing polygon or polyline geometry."""

    algorithm: Literal["PAEK", "BEZIER_INTERPOLATION"] = Field(
        default="PAEK",
        description=(
            "Smoothing algorithm passed to ArcPy. PAEK uses a tolerance distance; "
            "BEZIER_INTERPOLATION creates smoother curves without a tolerance in "
            "some ArcPy workflows."
        ),
    )
    tolerance: str = Field(
        ...,
        description=(
            "PAEK smoothing tolerance with units, for example '100 Meters'. "
            "Required by the current worker implementation."
        ),
    )


class SummarizeWithinInput(ToolInput):
    """Input contract for summarizing features inside polygon areas."""

    in_polygons: str = Field(
        ...,
        description=(
            "Absolute path to polygon features that define summary areas, such as "
            "districts, parcels, buffers, or grid cells. The path must be inside "
            "a configured PathGuard allowed root."
        ),
    )
    in_sum_features: str = Field(
        ...,
        description=(
            "Absolute path to point, line, or polygon features to summarize within "
            "each polygon. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create with summary attributes. "
            "Existing outputs require overwrite=true."
        ),
    )
    keep_all_polygons: bool = Field(
        default=True,
        description=(
            "When true, keep all input polygons even if no summary features fall "
            "inside them. When false, keep only polygons with intersecting summaries."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_polygons": "read",
        "in_sum_features": "read",
        "out_features": "write",
    }


class FrequencyAnalysisInput(ToolInput):
    """Input contract for counting unique attribute value combinations."""

    in_table: str = Field(
        ...,
        description=(
            "Absolute path to the input table or feature class whose attribute "
            "frequencies will be counted. The path must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path to create with frequency counts. Existing "
            "outputs require overwrite=true."
        ),
    )
    frequency_fields: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description=(
            "Field names used to define unique combinations for frequency counts."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
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
    """Input contract for writing summary statistics to a table."""

    in_table: str = Field(
        ...,
        description=(
            "Absolute path to the input table or feature class whose fields will "
            "be summarized. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path to create with summary statistics. "
            "Existing outputs require overwrite=true."
        ),
    )
    statistics_fields: List[Tuple[str, StatType]] = Field(
        ...,
        min_length=1,
        description=(
            "List of [field_name, statistic_type] pairs, such as "
            "[['POP', 'SUM'], ['AREA', 'MEAN']]. Statistic type may be SUM, "
            "MEAN, MIN, MAX, STD, COUNT, FIRST, LAST, RANGE, MEDIAN, VARIANCE, "
            "or UNIQUE."
        ),
    )
    case_field: Optional[str] = Field(
        default=None,
        description=(
            "Optional field used to group statistics. Use None to calculate one "
            "summary row for all input records."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_table": "read",
        "out_table": "write",
    }


class TabulateIntersectionInput(ToolInput):
    """Input contract for cross-tabulating class features inside zones."""

    in_zone_features: str = Field(
        ...,
        description=(
            "Absolute path to polygon zone features, such as districts, parcels, "
            "or planning units. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    zone_fields: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "One or more zone identifier fields used to group intersection results."
        ),
    )
    in_class_features: str = Field(
        ...,
        description=(
            "Absolute path to class features whose overlap with each zone will be "
            "tabulated. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path to create with tabulated intersection "
            "results. Existing outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_zone_features": "read",
        "in_class_features": "read",
        "out_table": "write",
    }


class IdentityFeaturesInput(TwoLayerOverlay):
    """Input contract for identity overlay analysis."""


class SymmetricalDifferenceInput(TwoLayerOverlay):
    """Input contract for extracting non-overlapping parts of two feature layers."""


class CreateFishnetInput(ToolInput):
    """Input contract for creating a rectangular fishnet or analysis grid."""

    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path for the generated fishnet grid. "
            "Use a geodatabase feature class path for project analysis outputs. "
            "The path must be inside a configured PathGuard allowed root; existing "
            "outputs require overwrite=true."
        ),
    )
    origin_x: float = Field(
        ...,
        description=(
            "X coordinate of the fishnet origin point, usually the lower-left "
            "corner of the grid in the output coordinate system."
        ),
    )
    origin_y: float = Field(
        ...,
        description=(
            "Y coordinate of the fishnet origin point, usually the lower-left "
            "corner of the grid in the output coordinate system."
        ),
    )
    y_axis_y: Optional[float] = Field(
        default=None,
        description=(
            "Y coordinate of the orientation point used with origin_x to define "
            "the fishnet Y-axis direction. Leave None to use origin_y + 10, which "
            "creates a north-oriented grid in typical projected coordinate systems."
        ),
    )
    cell_width: float = Field(
        ...,
        gt=0,
        description=(
            "Width of each fishnet cell in output coordinate system units. For "
            "projected data this is usually meters or feet."
        ),
    )
    cell_height: float = Field(
        ...,
        gt=0,
        description=(
            "Height of each fishnet cell in output coordinate system units. Use "
            "the same value as cell_width for square cells."
        ),
    )
    rows: int = Field(
        ...,
        ge=1,
        le=10000,
        description=(
            "Number of fishnet rows to create. Combined with cell_height, this "
            "controls the total grid height."
        ),
    )
    columns: int = Field(
        ...,
        ge=1,
        le=10000,
        description=(
            "Number of fishnet columns to create. Combined with cell_width, this "
            "controls the total grid width."
        ),
    )
    geometry_type: Literal["POLYLINE", "POLYGON"] = Field(
        default="POLYGON",
        description=(
            "Output grid geometry type. Use POLYGON when cells should be analysis "
            "zones, sampling units, planning units, or overlay features. Use "
            "POLYLINE when only grid lines are needed for indexing or cartography."
        ),
    )
    create_label_points: bool = Field(
        default=False,
        description=(
            "When true, ask ArcPy CreateFishnet to create label points for grid "
            "cells where supported. Use this when cell centers are needed for "
            "labels, sampling points, or downstream joins."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing fishnet output feature class "
            "is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"out_features": "write"}
