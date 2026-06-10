"""ToolSpecs + worker implementations — Category 4: Coordinate Reference & Projection.

Case-sensitivity guard: exact Esri signatures — ``DefineProjection``,
``Project``, ``ProjectRaster``, ``SpatialReference``.

A WKID is resolved into a live ``arcpy.SpatialReference`` through ONE
helper (`_sr`), which converts Esri's opaque "invalid code" RuntimeError
into a clear validation message (DRY: one resolution path, one error shape).
"""

from __future__ import annotations

from typing import Any

from ..contracts import projection as c
from ..registry import Category, ToolSpec, register


def _sr(arcpy: Any, wkid: int) -> Any:
    """Resolve a WKID to a SpatialReference with a structured failure."""
    try:
        return arcpy.SpatialReference(wkid)
    except (RuntimeError, ValueError) as exc:
        raise ValueError(
            f"WKID {wkid} is not a valid EPSG/Esri factory code: {exc}"
        ) from exc


def _sr_info(sr: Any) -> dict[str, Any]:
    """Uniform serialization of a SpatialReference object."""
    return {
        "factory_code": int(sr.factoryCode),
        "name": sr.name,
        "type": sr.type,                       # 'Projected' | 'Geographic'
        "linear_unit": getattr(sr, "linearUnitName", None) or None,
        "angular_unit": getattr(sr, "angularUnitName", None) or None,
        "datum": getattr(sr, "datumName", None) or None,
    }


# ------------------------------------------------------------------- tools --

def _define_projection(arcpy: Any, inp: c.DefineProjectionInput) -> dict:
    sr = _sr(arcpy, inp.wkid)
    arcpy.management.DefineProjection(inp.dataset, sr)
    return {"dataset": inp.dataset, "defined": _sr_info(sr),
            "note": "Metadata-only operation: coordinates were NOT transformed."}


def _project_features(arcpy: Any, inp: c.ProjectFeaturesInput) -> dict:
    sr = _sr(arcpy, inp.out_wkid)
    arcpy.management.Project(
        in_dataset=inp.in_features,
        out_dataset=inp.out_features,
        out_coor_system=sr,
        transform_method=inp.transform_method,
    )
    return {"output": inp.out_features, "crs": _sr_info(sr),
            "transform_method": inp.transform_method}


def _get_spatial_reference(arcpy: Any, inp: c.GetSpatialReferenceInput) -> dict:
    return _sr_info(_sr(arcpy, inp.wkid))


def _project_raster(arcpy: Any, inp: c.ProjectRasterInput) -> dict:
    sr = _sr(arcpy, inp.out_wkid)
    arcpy.management.ProjectRaster(
        in_raster=inp.in_raster,
        out_raster=inp.out_raster,
        out_coor_system=sr,
        resampling_type=inp.resampling_type,
        cell_size=inp.cell_size,
    )
    return {"output": inp.out_raster, "crs": _sr_info(sr),
            "resampling_type": inp.resampling_type}


# -------------------------------------------------------------- registrations

_CAT = Category.PROJECTION

register(ToolSpec(
    "define_projection", _CAT,
    "Assign a CRS (by WKID/EPSG) to a dataset with an unknown spatial "
    "reference (DefineProjection). Metadata-only; requires confirm=true.",
    c.DefineProjectionInput, _define_projection, destructive=True))
register(ToolSpec(
    "project_features", _CAT,
    "Transform a vector dataset into another CRS/datum (Project).",
    c.ProjectFeaturesInput, _project_features))
register(ToolSpec(
    "get_spatial_reference", _CAT,
    "Look up a CRS by WKID: name, type, linear/angular units, datum.",
    c.GetSpatialReferenceInput, _get_spatial_reference))
register(ToolSpec(
    "project_raster", _CAT,
    "Reproject a raster with NEAREST/BILINEAR/CUBIC/MAJORITY resampling "
    "(ProjectRaster).",
    c.ProjectRasterInput, _project_raster))
