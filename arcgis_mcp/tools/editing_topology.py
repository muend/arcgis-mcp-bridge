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
        "Append rows from FCs into an existing target (Append). Mutates the "
        "target; requires confirm=true.",
        c.AppendFeaturesInput,
        _append_features,
        True,
    ),
    (
        "repair_geometry",
        "Fix invalid geometries in place (RepairGeometry). Requires confirm=true.",
        c.RepairGeometryInput,
        _repair_geometry,
        True,
    ),
    (
        "check_geometry",
        "Report geometry problems into a table without fixing (CheckGeometry).",
        c.CheckGeometryInput,
        _check_geometry,
        False,
    ),
    (
        "detect_feature_changes",
        "Diff two line FCs spatially/attributively (DetectFeatureChanges).",
        c.DetectFeatureChangesInput,
        _detect_feature_changes,
        False,
    ),
    (
        "delete_identical",
        "Delete duplicate rows by field/geometry equality (DeleteIdentical). "
        "Irreversible; requires confirm=true.",
        c.DeleteIdenticalInput,
        _delete_identical,
        True,
    ),
    (
        "eliminate_polygon_part",
        "Merge small polygon parts into neighbors (EliminatePolygonPart).",
        c.EliminatePolygonPartInput,
        _eliminate_polygon_part,
        False,
    ),
    (
        "topology_check",
        "Validate a geodatabase topology's rules (ValidateTopology).",
        c.TopologyCheckInput,
        _topology_check,
        False,
    ),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
