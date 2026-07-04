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
    arcpy.analysis.Intersect(inp.in_features, inp.out_features, inp.join_attributes)
    return _out(inp)


def _union(arcpy: Any, inp: c.UnionFeaturesInput) -> dict:
    arcpy.analysis.Union(inp.in_features, inp.out_features)
    return _out(inp)


def _erase(arcpy: Any, inp: c.EraseFeaturesInput) -> dict:
    arcpy.analysis.Erase(inp.in_features, inp.overlay_features, inp.out_features)
    return _out(inp)


def _dissolve(arcpy: Any, inp: c.DissolveFeaturesInput) -> dict:
    arcpy.management.Dissolve(
        inp.in_features,
        inp.out_features,
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
            in_layer=lyr,
            overlap_type=inp.relationship,
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
        target_features=inp.target_features,
        join_features=inp.join_features,
        out_feature_class=inp.out_features,
        join_operation=inp.join_operation,
        match_option=inp.match_option,
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
        in_features=inp.in_features,
        near_features=inp.near_features,
        out_table=inp.out_table,
        search_radius=inp.search_radius,
        closest="ALL",
        closest_count=inp.closest_count,
    )
    return {"output": inp.out_table, "closest_count": inp.closest_count}


def _minimum_bounding_geometry(arcpy: Any, inp: c.MinimumBoundingGeometryInput) -> dict:
    arcpy.management.MinimumBoundingGeometry(
        inp.in_features, inp.out_features, inp.geometry_type, inp.group_option
    )
    return _out(inp, geometry_type=inp.geometry_type)


def _feature_to_point(arcpy: Any, inp: c.FeatureToPointInput) -> dict:
    arcpy.management.FeatureToPoint(
        inp.in_features,
        inp.out_features,
        "INSIDE" if inp.point_location == "INSIDE" else "CENTROID",
    )
    return _out(inp)


def _feature_vertices_to_points(
    arcpy: Any, inp: c.FeatureVerticesToPointsInput
) -> dict:
    arcpy.management.FeatureVerticesToPoints(
        inp.in_features, inp.out_features, inp.point_location
    )
    return _out(inp)


def _multipart_to_singlepart(arcpy: Any, inp: c.MultipartToSinglepartInput) -> dict:
    arcpy.management.MultipartToSinglepart(inp.in_features, inp.out_features)
    return _out(inp)


def _shape_type(arcpy: Any, dataset: str) -> str:
    return str(arcpy.Describe(dataset).shapeType)


def _simplify(arcpy: Any, inp: c.SimplifyFeaturesInput) -> dict:
    shape = _shape_type(arcpy, inp.in_features)
    if shape == "Polygon":
        arcpy.cartography.SimplifyPolygon(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance
        )
    elif shape == "Polyline":
        arcpy.cartography.SimplifyLine(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance
        )
    else:
        raise ValueError(f"simplify_features supports Polygon/Polyline, got {shape}.")
    return _out(inp, shape=shape, algorithm=inp.algorithm)


def _smooth(arcpy: Any, inp: c.SmoothFeaturesInput) -> dict:
    shape = _shape_type(arcpy, inp.in_features)
    if shape == "Polygon":
        arcpy.cartography.SmoothPolygon(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance
        )
    elif shape == "Polyline":
        arcpy.cartography.SmoothLine(
            inp.in_features, inp.out_features, inp.algorithm, inp.tolerance
        )
    else:
        raise ValueError(f"smooth_features supports Polygon/Polyline, got {shape}.")
    return _out(inp, shape=shape, algorithm=inp.algorithm)


def _summarize_within(arcpy: Any, inp: c.SummarizeWithinInput) -> dict:
    arcpy.analysis.SummarizeWithin(
        in_polygons=inp.in_polygons,
        in_sum_features=inp.in_sum_features,
        out_feature_class=inp.out_features,
        keep_all_polygons="KEEP_ALL" if inp.keep_all_polygons else "ONLY_INTERSECTING",
    )
    return _out(inp)


def _frequency(arcpy: Any, inp: c.FrequencyAnalysisInput) -> dict:
    arcpy.analysis.Frequency(inp.in_table, inp.out_table, inp.frequency_fields)
    return {"output": inp.out_table, "fields": inp.frequency_fields}


def _statistics(arcpy: Any, inp: c.StatisticsAnalysisInput) -> dict:
    arcpy.analysis.Statistics(
        inp.in_table,
        inp.out_table,
        [[f, s] for f, s in inp.statistics_fields],
        inp.case_field,
    )
    return {"output": inp.out_table, "case_field": inp.case_field}


def _tabulate_intersection(arcpy: Any, inp: c.TabulateIntersectionInput) -> dict:
    arcpy.analysis.TabulateIntersection(
        in_zone_features=inp.in_zone_features,
        zone_fields=inp.zone_fields,
        in_class_features=inp.in_class_features,
        out_table=inp.out_table,
    )
    return {"output": inp.out_table}


def _identity(arcpy: Any, inp: c.IdentityFeaturesInput) -> dict:
    arcpy.analysis.Identity(inp.in_features, inp.overlay_features, inp.out_features)
    return _out(inp)


def _sym_diff(arcpy: Any, inp: c.SymmetricalDifferenceInput) -> dict:
    arcpy.analysis.SymDiff(inp.in_features, inp.overlay_features, inp.out_features)
    return _out(inp)


def _create_fishnet(arcpy: Any, inp: c.CreateFishnetInput) -> dict:
    y_axis = inp.y_axis_y if inp.y_axis_y is not None else inp.origin_y + 10.0
    arcpy.management.CreateFishnet(
        out_feature_class=inp.out_features,
        origin_coord=f"{inp.origin_x} {inp.origin_y}",
        y_axis_coord=f"{inp.origin_x} {y_axis}",
        cell_width=inp.cell_width,
        cell_height=inp.cell_height,
        number_rows=inp.rows,
        number_columns=inp.columns,
        labels="LABELS" if inp.create_label_points else "NO_LABELS",
        geometry_type=inp.geometry_type,
    )
    return _out(inp, rows=inp.rows, columns=inp.columns)


# -------------------------------------------------------------- registrations

_CAT = Category.GEOMETRY

_SPECS = (
    (
        "intersect_features",
        (
            "Overlay two or more feature layers using ArcPy Intersect and write "
            "only the shared geometry to a new output feature class. Use this "
            "to find areas, lines, or points common to multiple datasets while "
            "preserving selected attributes. Reads all input feature paths and "
            "writes out_features inside PathGuard allowed roots."
        ),
        c.IntersectFeaturesInput,
        _intersect,
        False,
    ),
    (
        "union_features",
        (
            "Overlay two or more polygon feature layers using ArcPy Union and "
            "write a new polygon feature class containing all combined areas. "
            "Use this to compare zoning, land-use, administrative, or planning "
            "layers while retaining attributes from each input. Reads input "
            "features and writes out_features inside PathGuard allowed roots."
        ),
        c.UnionFeaturesInput,
        _union,
        False,
    ),
    (
        "erase_features",
        (
            "Remove portions of input features that overlap an erase layer using "
            "ArcPy Erase. Use this for exclusion zones, masking restricted areas, "
            "or subtracting one geography from another. Reads the input and "
            "overlay feature paths and writes a new output feature class without "
            "modifying the source datasets."
        ),
        c.EraseFeaturesInput,
        _erase,
        False,
    ),
    (
        "dissolve_features",
        (
            "Merge adjacent or overlapping features that share attribute values "
            "using ArcPy Dissolve. Use this to generalize boundaries, aggregate "
            "parcels, zones, roads, or other features by one or more dissolve "
            "fields. Reads in_features and writes a new dissolved output feature "
            "class inside PathGuard allowed roots."
        ),
        c.DissolveFeaturesInput,
        _dissolve,
        False,
    ),
    (
        "merge_features",
        (
            "Combine multiple compatible feature classes or layers into one output "
            "feature class using ArcPy Merge. Use this to assemble same-schema "
            "datasets from multiple sources, tiles, districts, or processing "
            "batches. Reads all input feature paths and writes one new output "
            "inside PathGuard allowed roots."
        ),
        c.MergeFeaturesInput,
        _merge,
        False,
    ),
    (
        "select_by_attribute",
        (
            "Materialize a SQL attribute query into a new feature class using "
            "ArcPy Select. Use this when a stateless MCP workflow needs a saved "
            "subset rather than an in-memory layer selection. Reads in_features, "
            "applies where_clause, and writes the selected rows to out_features."
        ),
        c.SelectByAttributeInput,
        _select_by_attribute,
        False,
    ),
    (
        "select_by_location",
        (
            "Materialize a spatial relationship selection into a new feature class "
            "using a MakeFeatureLayer, SelectLayerByLocation, and CopyFeatures "
            "pipeline. Use this to persist features that intersect, contain, are "
            "within, or are near another dataset. Writes the selected result to "
            "out_features and removes the temporary layer."
        ),
        c.SelectByLocationInput,
        _select_by_location,
        False,
    ),
    (
        "spatial_join",
        (
            "Join attributes from one feature layer to another based on spatial "
            "relationships using ArcPy SpatialJoin. Use this to count, summarize, "
            "or transfer nearby, contained, intersecting, or matching feature "
            "attributes into a new output feature class. Reads target_features "
            "and join_features and writes out_features inside PathGuard roots."
        ),
        c.SpatialJoinInput,
        _spatial_join,
        False,
    ),
    (
        "near_analysis",
        (
            "Calculate nearest-neighbor distance from each input feature to nearby "
            "features using ArcPy Near. This mutates the input dataset by adding "
            "or updating NEAR_FID and NEAR_DIST fields, so confirm=true is "
            "required. Use a copied working dataset when exposing this workflow "
            "to an LLM or automated agent."
        ),
        c.NearAnalysisInput,
        _near,
        True,
    ),
    (
        "generate_near_table",
        (
            "Create a standalone proximity table between input features and near "
            "features using ArcPy GenerateNearTable. Use this to record nearest "
            "neighbors, distances, and candidate matches without modifying the "
            "source datasets. Reads input and near feature paths and writes a new "
            "out_table inside PathGuard allowed roots."
        ),
        c.GenerateNearTableInput,
        _generate_near_table,
        False,
    ),
    (
        "minimum_bounding_geometry",
        (
            "Create bounding geometries around input features using ArcPy "
            "MinimumBoundingGeometry. Use this to generate convex hulls, envelopes, "
            "circles, or other summary shapes for features or groups. Reads "
            "in_features and writes a new output feature class with the requested "
            "geometry_type and grouping behavior."
        ),
        c.MinimumBoundingGeometryInput,
        _minimum_bounding_geometry,
        False,
    ),
    (
        "feature_to_point",
        (
            "Create representative point features from polygons or lines using "
            "ArcPy FeatureToPoint. Use this to produce centroids or guaranteed "
            "inside points for labeling, joins, sampling, or simplified analysis. "
            "Reads in_features and writes a new point feature class to out_features."
        ),
        c.FeatureToPointInput,
        _feature_to_point,
        False,
    ),
    (
        "feature_vertices_to_points",
        (
            "Convert feature vertices to point features using ArcPy "
            "FeatureVerticesToPoints. Use this to extract endpoints, all vertices, "
            "midpoints, or dangle points from line or polygon geometry for QA/QC, "
            "network checks, and geometry inspection. Reads in_features and "
            "creates out_features inside PathGuard allowed roots."
        ),
        c.FeatureVerticesToPointsInput,
        _feature_vertices_to_points,
        False,
    ),
    (
        "multipart_to_singlepart",
        (
            "Split multipart features into singlepart features using ArcPy "
            "MultipartToSinglepart. Use this before per-feature editing, counting, "
            "topology checks, joins, or analysis that requires one geometry part "
            "per row. Reads in_features and creates out_features without modifying "
            "the source dataset."
        ),
        c.MultipartToSinglepartInput,
        _multipart_to_singlepart,
        False,
    ),
    (
        "simplify_features",
        (
            "Simplify polygon or polyline geometry using ArcPy SimplifyPolygon or "
            "SimplifyLine after detecting the input shape type. Use this to reduce "
            "vertex density for cartography, web export, performance, or scale-"
            "appropriate analysis. Writes a simplified output feature class and "
            "does not mutate the source features."
        ),
        c.SimplifyFeaturesInput,
        _simplify,
        False,
    ),
    (
        "smooth_features",
        (
            "Smooth polygon or polyline geometry using ArcPy SmoothPolygon or "
            "SmoothLine after detecting the input shape type. Use this for "
            "cartographic cleanup where angular boundaries or lines need a more "
            "generalized appearance. Writes a new smoothed output feature class "
            "without modifying the source dataset."
        ),
        c.SmoothFeaturesInput,
        _smooth,
        False,
    ),
    (
        "summarize_within",
        (
            "Summarize features that fall within polygon areas using ArcPy "
            "SummarizeWithin. Use this to count or aggregate points, lines, or "
            "polygons by administrative zones, grid cells, parcels, buffers, or "
            "service areas. Reads boundary polygons and summary features, then "
            "writes a new summarized output feature class."
        ),
        c.SummarizeWithinInput,
        _summarize_within,
        False,
    ),
    (
        "frequency_analysis",
        (
            "Count unique combinations of attribute values using ArcPy Frequency. "
            "Use this to profile categorical fields, detect duplicates, summarize "
            "classes, or prepare simple frequency tables for QA/QC and reporting. "
            "Reads an input table and writes a new output table inside PathGuard "
            "allowed roots."
        ),
        c.FrequencyAnalysisInput,
        _frequency,
        False,
    ),
    (
        "statistics_analysis",
        (
            "Calculate summary statistics for numeric or categorical fields using "
            "ArcPy Statistics. Use this to aggregate counts, sums, means, minima, "
            "maxima, standard deviations, or grouped statistics before reporting "
            "or joining results back to features. Reads an input table and writes "
            "a new output table."
        ),
        c.StatisticsAnalysisInput,
        _statistics,
        False,
    ),
    (
        "tabulate_intersection",
        (
            "Cross-tabulate intersections between zone features and class features "
            "using ArcPy TabulateIntersection. Use this to quantify how much of "
            "each class falls inside each zone, such as land-use area by district "
            "or habitat type by planning unit. Writes a standalone output table."
        ),
        c.TabulateIntersectionInput,
        _tabulate_intersection,
        False,
    ),
    (
        "identity_features",
        (
            "Overlay input features with identity features using ArcPy Identity. "
            "Use this to transfer polygon or line attributes onto another feature "
            "layer while preserving the input geometry where applicable. Reads "
            "both input datasets and writes a new output feature class inside "
            "PathGuard allowed roots."
        ),
        c.IdentityFeaturesInput,
        _identity,
        False,
    ),
    (
        "symmetrical_difference",
        (
            "Create the non-overlapping parts of two feature layers using ArcPy "
            "SymmetricalDifference. Use this to compare boundaries, detect areas "
            "present in only one of two datasets, or isolate disagreement between "
            "two polygon/line sources. Writes a new output feature class and does "
            "not modify the inputs."
        ),
        c.SymmetricalDifferenceInput,
        _sym_diff,
        False,
    ),
    (
        "create_fishnet",
        (
            "Create a rectangular fishnet or grid feature class using ArcPy "
            "CreateFishnet from explicit origin coordinates, optional Y-axis "
            "orientation, cell width, cell height, row count, column count, label "
            "point option, and output geometry type. Use this to generate sampling "
            "grids, planning units, analysis zones, index maps, polygon tiles, or "
            "polyline grid overlays before spatial join, summarize-within, raster "
            "conversion, QA/QC, or map production. Writes out_features inside a "
            "PathGuard allowed root; existing outputs require overwrite=true."
        ),
        c.CreateFishnetInput,
        _create_fishnet,
        False,
    ),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
