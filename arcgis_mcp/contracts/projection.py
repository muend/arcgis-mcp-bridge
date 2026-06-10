"""Input models — Category 4: Coordinate Reference & Projection (catalog #56-59)."""

from __future__ import annotations

from typing import ClassVar, Literal, Optional

from pydantic import Field

from .base import PathRole, ToolInput

#: Valid EPSG/WKID window: 1024 is the lowest EPSG code; ~200000+ are the
#: Esri factory codes (e.g., 102100 Web Mercator Aux Sphere legacy).
_WKID_MIN, _WKID_MAX = 1024, 300000

RasterResampling = Literal["NEAREST", "BILINEAR", "CUBIC", "MAJORITY"]


class DefineProjectionInput(ToolInput):
    """Assign a CRS to a dataset whose spatial reference is unknown.

    DefineProjection rewrites metadata only — it does NOT transform
    coordinates. Defining the wrong CRS silently corrupts every downstream
    analysis, hence the confirm gate.
    """

    dataset: str = Field(..., min_length=1)
    wkid: int = Field(..., ge=_WKID_MIN, le=_WKID_MAX,
                      description="EPSG/WKID, e.g. 5258 (TUREF) or 32635.")
    confirm: bool = Field(
        default=False,
        description="Must be true: redefining a CRS rewrites dataset metadata.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class ProjectFeaturesInput(ToolInput):
    """Transform a vector dataset into a different CRS (Project)."""

    in_features: str
    out_features: str
    out_wkid: int = Field(..., ge=_WKID_MIN, le=_WKID_MAX)
    transform_method: Optional[str] = Field(
        default=None,
        description="Named geographic transformation when datums differ, "
                    "e.g. 'ITRF_2014_To_ETRF_2014'. None lets arcpy choose.",
        max_length=120,
    )
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class GetSpatialReferenceInput(ToolInput):
    """Inspect a CRS definition by WKID. Pure lookup — touches no files."""

    wkid: int = Field(..., ge=_WKID_MIN, le=_WKID_MAX)
    # No path_fields: this tool has no filesystem surface at all.


class ProjectRasterInput(ToolInput):
    """Reproject a raster dataset (ProjectRaster)."""

    in_raster: str
    out_raster: str
    out_wkid: int = Field(..., ge=_WKID_MIN, le=_WKID_MAX)
    resampling_type: RasterResampling = Field(
        default="NEAREST",
        description="NEAREST for categorical rasters; BILINEAR/CUBIC for "
                    "continuous surfaces (DEM, imagery).",
    )
    cell_size: Optional[float] = Field(default=None, gt=0)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "out_raster": "write",
    }


__all__ = [
    "DefineProjectionInput",
    "ProjectFeaturesInput",
    "GetSpatialReferenceInput",
    "ProjectRasterInput",
    "RasterResampling",
]
