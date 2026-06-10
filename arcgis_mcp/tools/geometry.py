"""ToolSpecs + worker implementations — Category 3: Geometry & Analysis.

Case-sensitivity guard: exact Esri module.function casing throughout —
``arcpy.analysis.Intersect``, ``arcpy.management.Dissolve``,
``arcpy.cartography.SimplifyPolygon``, ``arcpy.analysis.TabulateIntersection``.

Implementation note (documented deviation from the catalog): the catalog
lists ``SelectLayerByAttribute``/``SelectLayerByLocation``, which operate on
transient *layer selections* — meaningless in a stateless worker. They are
materialized instead: ``Select_analysis`` for attribute queries, and a
MakeFeatureLayer -> SelectLayerByLocation -> CopyFeatures pipeline for
spatial queries. Same result, persisted to a real FC.
"""

from __future__ import annotations

from typing import Any

from ..contracts import geometry as c
from ..registry import Category, ToolSpec, register


def _out(inp: Any, **extra: Any) -> dict[str, Any]:
    """Uniform success payload for output-producing tools."""
    return {"output": inp.out_features, **extra}


# ------------------------------------------------------------------- tools --

def _intersect(arcpy: Any, inp: c.IntersectFeaturesInput) -> dict:
    arcpy.analysis.Intersect(inp.in_features, inp.out_features,
                             inp.join_attributes)
    return _out(inp)


def _union(arcpy: Any, inp: c.UnionFeaturesInput) -> dict:
    arcpy.analysis.Union(inp.in_features, inp.out_features)
    return _out(inp)


def _erase(arcpy: Any, inp: c.EraseFeaturesInput) -> dict:
    arcpy.analysis.Erase(inp.in_features, inp.overlay_features, inp.out_features)
    return _out(inp)


def _dissolve(arcpy: Any, inp: c.DissolveFeaturesInput) -> dict:
    arcpy.management.Dissolve(
        inp.in_features, inp.out_features,
        inp.dissolve_fields or None,
        multi_part="MULTI_PART" if inp.multi_part else "SINGLE_PART",
    )
    return _out(inp, dissolve_fields=inp.dissolve_fields)


def _merge(arcpy: Any, inp: c.MergeFeaturesInput) -> dict:
    arcpy.management.Merge(inp.in_features, inp.out_features)
    return _out(inp, merged=len(inp.in_features))


def _select_by_attribute(arcpy: Any, inp: c.SelectByAttributeInput) -> dict:
    arcpy.analysis.Select(inp.in_features, inp.out_features, inp.where_clause)
    count = int(arcpy.management.GetCount(inp.out_features)[0])
    return _out(inp, selected_count=count)


def _select_by_location(arcpy: Any, inp: c.SelectByLocationInput) -> dict:
    lyr = arcpy.management.MakeFeatureLayer(inp.in_features, "sel_lyr")
    try:
        arcpy.management.SelectLayerByLocation(
            in_layer=lyr, overlap_type=inp.relationship,
            select_features=inp.select_features,
            search_distance=inp.search_distance,
            invert_spatial_relationship="INVERT" if inp.invert else "NOT_INVERT",
        )
        arcpy.management.CopyFeatures(lyr, inp.out_features)
    finally:
        arcpy.management.Delete(lyr)
    count = int(arcpy.management.GetCount(inp.out_features)[0])
    return _out(inp, selected_count=count, relationship=inp.relationship)


def _spatial_join(arcpy: Any, inp: c.SpatialJoinInput) -> dict:
    arcpy.analysis.SpatialJoin(
        target_features=inp.target_features, join_features=inp.join_features,
        out_feature_class=inp.out_features,
        join_operation=inp.join_operation, match_option=inp.match_option,
    )
    return _out(inp, join_operation=inp.join_operation)


def _near(arcpy: Any, inp: c.NearAnalysisInput) -> dict:
    if not inp.confirm:
        raise PermissionError(
            "near_analysis mutates in_features (adds NEAR_FID/NEAR_DIST): "
            "set confirm=true to proceed."
        )
    arcpy.analysis.Near(inp.in_features, inp.near_features, inp.search_radius)
    return {"updated": inp.in_features, "fields_added": ["NEAR_FID", "NEAR_DIST"]}


def _generate_near_table(arcpy: Any, inp: c.GenerateNearTableInput) -> dict:
    arcpy.analysis.GenerateNearTable(
        in_features=inp.in_features, near_features=inp.near_features,
        out_table=inp.out_table, search_radius=inp.search_radius,
        closest="ALL", closest_count=inp.closest_count,
    )
    return {"output": inp.out_table, "closest_count": inp.closest_count}


def _minimum_bounding_geometry(
    arcpy: Any, inp: c.MinimumBoundingGeometryInput
) -> dict:
    arcpy.management.MinimumBoundingGeometry(
        inp.in_features, inp.out_features, inp.geometry_type, inp.group_option)
    return _out(inp, geometry_type=inp.geometry_type)


def _feature_to_point(arcpy: Any, inp: c.FeatureToPointInput) -> dict:
    arcpy.management.FeatureToPoint(
        inp.in_features, inp.out_features,
        "INSIDE" if inp.point_location == "INSIDE" else "CENTROID")
    return _out(inp)


def _feature_vertices_to_points(
    arcpy: Any, inp: c.FeatureVerticesToPointsInput
) -> dict:
    arcpy.management.FeatureVerticesToPoints(
        inp.in_features, inp.out_features, inp.point_location)
    return _out(inp)


def _multipart_to_singlepart(
    arcpy: Any, inp: c.MultipartToSinglepartInput
) -> dict:
    arcpy.management.MultipartToSinglepart(inp.in_features, inp.out_features)
    return _out(inp)


def _shape_type(arcpy: Any, dataset: str) -> str:
    return str(arcpy.Describe(dataset).shapeType)


def _simplify(arcpy: Any, inp: c.SimplifyFeaturesInput) -> dict:
    shape = _shape_type(arcpy, inp.in_features)
    if shape == "Polygon":
        arcpy.cartography.SimplifyPolygon(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance)
    elif shape == "Polyline":
        arcpy.cartography.SimplifyLine(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance)
    else:
        raise ValueError(f"simplify_features supports Polygon/Polyline, got {shape}.")
    return _out(inp, shape=shape, algorithm=inp.algorithm)


def _smooth(arcpy: Any, inp: c.SmoothFeaturesInput) -> dict:
    shape = _shape_type(arcpy, inp.in_features)
    if shape == "Polygon":
        arcpy.cartography.SmoothPolygon(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance)
    elif shape == "Polyline":
        arcpy.cartography.SmoothLine(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance)
    else:
        raise ValueError(f"smooth_features supports Polygon/Polyline, got {shape}.")
    return _out(inp, shape=shape, algorithm=inp.algorithm)


def _summarize_within(arcpy: Any, inp: c.SummarizeWithinInput) -> dict:
    arcpy.analysis.SummarizeWithin(
        in_polygons=inp.in_polygons, in_sum_features=inp.in_sum_features,
        out_feature_class=inp.out_features,
        keep_all_polygons="KEEP_ALL" if inp.keep_all_polygons else "ONLY_INTERSECTING",
    )
    return _out(inp)


def _frequency(arcpy: Any, inp: c.FrequencyAnalysisInput) -> dict:
    arcpy.analysis.Frequency(inp.in_table, inp.out_table, inp.frequency_fields)
    return {"output": inp.out_table, "fields": inp.frequency_fields}


def _statistics(arcpy: Any, inp: c.StatisticsAnalysisInput) -> dict:
    arcpy.analysis.Statistics(
        inp.in_table, inp.out_table,
        [[f, s] for f, s in inp.statistics_fields],
        inp.case_field,
    )
    return {"output": inp.out_table, "case_field": inp.case_field}


def _tabulate_intersection(arcpy: Any, inp: c.TabulateIntersectionInput) -> dict:
    arcpy.analysis.TabulateIntersection(
        in_zone_features=inp.in_zone_features, zone_fields=inp.zone_fields,
        in_class_features=inp.in_class_features, out_table=inp.out_table,
    )
    return {"output": inp.out_table}


def _identity(arcpy: Any, inp: c.IdentityFeaturesInput) -> dict:
    arcpy.analysis.Identity(inp.in_features, inp.overlay_features,
                            inp.out_features)
    return _out(inp)


def _sym_diff(arcpy: Any, inp: c.SymmetricalDifferenceInput) -> dict:
    arcpy.analysis.SymDiff(inp.in_features, inp.overlay_features,
                           inp.out_features)
    return _out(inp)


def _create_fishnet(arcpy: Any, inp: c.CreateFishnetInput) -> dict:
    y_axis = inp.y_axis_y if inp.y_axis_y is not None else inp.origin_y + 10.0
    arcpy.management.CreateFishnet(
        out_feature_class=inp.out_features,
        origin_coord=f"{inp.origin_x} {inp.origin_y}",
        y_axis_coord=f"{inp.origin_x} {y_axis}",
        cell_width=inp.cell_width, cell_height=inp.cell_height,
        number_rows=inp.rows, number_columns=inp.columns,
        labels="LABELS" if inp.create_label_points else "NO_LABELS",
        geometry_type=inp.geometry_type,
    )
    return _out(inp, rows=inp.rows, columns=inp.columns)


# -------------------------------------------------------------- registrations

_CAT = Category.GEOMETRY

_SPECS = (
    ("intersect_features", "Geometric intersection of 2+ layers (Intersect).",
     c.IntersectFeaturesInput, _intersect, False),
    ("union_features", "Geometric union of 2+ polygon layers (Union).",
     c.UnionFeaturesInput, _union, False),
    ("erase_features",
     "Remove areas overlapping the overlay layer — cookie-cutter (Erase).",
     c.EraseFeaturesInput, _erase, False),
    ("dissolve_features",
     "Merge geometries sharing attribute values (Dissolve).",
     c.DissolveFeaturesInput, _dissolve, False),
    ("merge_features", "Combine same-schema layers into one FC (Merge).",
     c.MergeFeaturesInput, _merge, False),
    ("select_by_attribute",
     "Materialize a SQL attribute selection into a new FC (Select).",
     c.SelectByAttributeInput, _select_by_attribute, False),
    ("select_by_location",
     "Materialize a spatial-relationship selection into a new FC "
     "(SelectLayerByLocation pipeline).",
     c.SelectByLocationInput, _select_by_location, False),
    ("spatial_join", "Join attributes by spatial relationship (SpatialJoin).",
     c.SpatialJoinInput, _spatial_join, False),
    ("near_analysis",
     "Nearest-neighbor distance per feature; MUTATES input (Near). "
     "Requires confirm=true.",
     c.NearAnalysisInput, _near, True),
    ("generate_near_table",
     "N nearest neighbors as a standalone table (GenerateNearTable).",
     c.GenerateNearTableInput, _generate_near_table, False),
    ("minimum_bounding_geometry",
     "Convex hull / envelope / circle per feature or group "
     "(MinimumBoundingGeometry).",
     c.MinimumBoundingGeometryInput, _minimum_bounding_geometry, False),
    ("feature_to_point", "Polygon/line centroids as points (FeatureToPoint).",
     c.FeatureToPointInput, _feature_to_point, False),
    ("feature_vertices_to_points",
     "Extract vertices as points (FeatureVerticesToPoints).",
     c.FeatureVerticesToPointsInput, _feature_vertices_to_points, False),
    ("multipart_to_singlepart",
     "Explode multipart geometries (MultipartToSinglepart).",
     c.MultipartToSinglepartInput, _multipart_to_singlepart, False),
    ("simplify_features",
     "Simplify polygon/line geometry; auto-detects shape type "
     "(SimplifyPolygon/SimplifyLine).",
     c.SimplifyFeaturesInput, _simplify, False),
    ("smooth_features",
     "Smooth polygon/line corners; auto-detects shape type "
     "(SmoothPolygon/SmoothLine).",
     c.SmoothFeaturesInput, _smooth, False),
    ("summarize_within",
     "Statistics of features falling inside polygons (SummarizeWithin).",
     c.SummarizeWithinInput, _summarize_within, False),
    ("frequency_analysis",
     "Count unique attribute value combinations (Frequency).",
     c.FrequencyAnalysisInput, _frequency, False),
    ("statistics_analysis",
     "SUM/MEAN/MIN/MAX/STD summary table (Statistics).",
     c.StatisticsAnalysisInput, _statistics, False),
    ("tabulate_intersection",
     "Cross-tabulate intersection areas of two layers (TabulateIntersection).",
     c.TabulateIntersectionInput, _tabulate_intersection, False),
    ("identity_features",
     "Overlay keeping source geometry (Identity).",
     c.IdentityFeaturesInput, _identity, False),
    ("symmetrical_difference",
     "Non-overlapping parts of two layers (SymDiff).",
     c.SymmetricalDifferenceInput, _sym_diff, False),
    ("create_fishnet", "Regular grid of cells (CreateFishnet).",
     c.CreateFishnetInput, _create_fishnet, False),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
