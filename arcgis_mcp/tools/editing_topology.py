"""ToolSpecs + worker implementations — Category 7: Editing & Topology.

Case-sensitivity guard: exact Esri signatures — ``Append``,
``RepairGeometry``, ``CheckGeometry``, ``DetectFeatureChanges``,
``DeleteIdentical``, ``EliminatePolygonPart``, ``ValidateTopology``.

Mutating tools (``append_features``, ``repair_geometry``,
``delete_identical``) are registered ``destructive=True``: the dispatcher
rejects them without ``confirm=true`` BEFORE the arcpy import is paid.
"""

from __future__ import annotations

from typing import Any

from ..contracts import editing_topology as c
from ..registry import Category, ToolSpec, register

# ------------------------------------------------------------------- tools --


def _append_features(arcpy: Any, inp: c.AppendFeaturesInput) -> dict:
    before = int(arcpy.management.GetCount(inp.target)[0])
    arcpy.management.Append(list(inp.inputs), inp.target, inp.schema_type)
    after = int(arcpy.management.GetCount(inp.target)[0])
    return {
        "target": inp.target,
        "rows_appended": after - before,
        "target_count": after,
        "schema_type": inp.schema_type,
    }


def _repair_geometry(arcpy: Any, inp: c.RepairGeometryInput) -> dict:
    arcpy.management.RepairGeometry(
        inp.in_features, "DELETE_NULL" if inp.delete_null else "KEEP_NULL"
    )
    return {
        "repaired": inp.in_features,
        "null_policy": "DELETE_NULL" if inp.delete_null else "KEEP_NULL",
    }


def _check_geometry(arcpy: Any, inp: c.CheckGeometryInput) -> dict:
    arcpy.management.CheckGeometry(inp.in_features, inp.out_table)
    problems = int(arcpy.management.GetCount(inp.out_table)[0])
    return {"report_table": inp.out_table, "problems_found": problems}


def _detect_feature_changes(arcpy: Any, inp: c.DetectFeatureChangesInput) -> dict:
    arcpy.management.DetectFeatureChanges(
        update_features=inp.update_features,
        base_features=inp.base_features,
        out_feature_class=inp.out_features,
        search_distance=inp.search_distance,
    )
    return {"output": inp.out_features, "search_distance": inp.search_distance}


def _delete_identical(arcpy: Any, inp: c.DeleteIdenticalInput) -> dict:
    before = int(arcpy.management.GetCount(inp.dataset)[0])
    arcpy.management.DeleteIdentical(inp.dataset, list(inp.fields), inp.xy_tolerance)
    after = int(arcpy.management.GetCount(inp.dataset)[0])
    return {
        "dataset": inp.dataset,
        "duplicates_deleted": before - after,
        "remaining": after,
        "compared_fields": list(inp.fields),
    }


def _eliminate_polygon_part(arcpy: Any, inp: c.EliminatePolygonPartInput) -> dict:
    arcpy.management.EliminatePolygonPart(
        in_features=inp.in_features,
        out_feature_class=inp.out_features,
        condition=inp.condition,
        part_area=inp.part_area,
        part_area_percent=inp.part_area_percent,
        part_option=("CONTAINED_ONLY" if inp.eliminate_contained_parts_only else "ANY"),
    )
    return {"output": inp.out_features, "condition": inp.condition}


def _topology_check(arcpy: Any, inp: c.TopologyCheckInput) -> dict:
    arcpy.management.ValidateTopology(
        inp.in_topology,
        "Visible_Extent" if inp.visible_extent else "Full_Extent",
    )
    return {
        "validated": inp.in_topology,
        "extent": "Visible_Extent" if inp.visible_extent else "Full_Extent",
        "note": "Inspect the topology's error feature classes for violations.",
    }


# -------------------------------------------------------------- registrations

_CAT = Category.EDITING

_SPECS = (
    (
        "append_features",
        (
            "Append rows from one or more feature classes or tables into an existing "
            "target dataset using ArcPy Append. Use this to load reviewed data, "
            "merge field-compatible updates, or add processed batches into a live "
            "target. This mutates the target dataset by inserting rows, so "
            "confirm=true is required."
        ),
        c.AppendFeaturesInput,
        _append_features,
        True,
    ),
    (
        "repair_geometry",
        (
            "Repair invalid feature geometry in place using ArcPy RepairGeometry. "
            "Use this after check_geometry reports geometry problems or before "
            "overlay, topology, network, or export operations that require valid "
            "shapes. This rewrites geometry and may delete null geometries, so "
            "confirm=true is required."
        ),
        c.RepairGeometryInput,
        _repair_geometry,
        True,
    ),
    (
        "check_geometry",
        (
            "Check a feature class for geometry problems using ArcPy CheckGeometry "
            "and write the findings to an output table. Use this as a non-mutating "
            "QA/QC step before repair_geometry, overlay, topology validation, "
            "conversion, or export. Reads the input features and writes a report "
            "table inside PathGuard allowed roots."
        ),
        c.CheckGeometryInput,
        _check_geometry,
        False,
    ),
    (
        "detect_feature_changes",
        (
            "Detect spatial or attribute changes between updated features and a "
            "reference feature dataset using ArcPy DetectFeatureChanges. Use this "
            "for QA/QC, version comparison, update review, or identifying changed "
            "features within a search tolerance. Reads update_features and "
            "base_features and writes a new out_features change dataset without "
            "mutating the originals."
        ),
        c.DetectFeatureChangesInput,
        _detect_feature_changes,
        False,
    ),
    (
        "delete_identical",
        (
            "Delete duplicate rows from a feature class or table using ArcPy "
            "DeleteIdentical based on selected fields and optional geometry "
            "tolerance. Use this only on an intended working dataset to remove "
            "duplicate records. This operation is irreversible and mutates the "
            "input dataset, so confirm=true is required."
        ),
        c.DeleteIdenticalInput,
        _delete_identical,
        True,
    ),
    (
        "eliminate_polygon_part",
        (
            "Remove small polygon holes or parts using ArcPy EliminatePolygonPart "
            "and write a cleaned output feature class. Use this for cartographic "
            "cleanup, removing sliver holes, or simplifying polygon interiors by "
            "area or percentage thresholds. Reads in_features and writes "
            "out_features without modifying the source dataset."
        ),
        c.EliminatePolygonPartInput,
        _eliminate_polygon_part,
        False,
    ),
    (
        "topology_check",
        (
            "Validate a geodatabase topology using ArcPy ValidateTopology. Use this "
            "to refresh topology rule validation after editing, appending, repair, "
            "or geometry cleanup workflows. Reads the topology dataset and returns "
            "validation metadata; inspect the topology error feature classes in "
            "ArcGIS Pro for rule violations."
        ),
        c.TopologyCheckInput,
        _topology_check,
        False,
    ),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
