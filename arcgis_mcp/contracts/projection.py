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
    """Assign CRS metadata to a dataset whose spatial reference is unknown.

    DefineProjection rewrites metadata only — it does NOT transform
    coordinates. Defining the wrong CRS silently corrupts every downstream
    analysis, hence the confirm gate.
    """

    dataset: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to the dataset whose coordinate reference metadata will "
            "be assigned. The path must be inside a configured PathGuard allowed "
            "root. This does not transform coordinates; it only defines metadata."
        ),
    )
    wkid: int = Field(
        ...,
        ge=_WKID_MIN,
        le=_WKID_MAX,
        description=(
            "EPSG or Esri WKID to assign as the dataset spatial reference, for "
            "example 5258 for TUREF/TM or 32635 for WGS 84 / UTM zone 35N."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. define_projection rewrites CRS metadata in place and "
            "can make downstream analysis incorrect if the WKID does not match the "
            "dataset's actual coordinate system."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class ProjectFeaturesInput(ToolInput):
    """Transform a vector feature dataset into a different coordinate system."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class or layer to reproject. The "
            "path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create in the target coordinate "
            "system. The path must be inside a configured PathGuard allowed root; "
            "existing outputs require overwrite=true."
        ),
    )
    out_wkid: int = Field(
        ...,
        ge=_WKID_MIN,
        le=_WKID_MAX,
        description=(
            "Target EPSG or Esri WKID for the output feature class. Coordinates "
            "are transformed into this spatial reference using ArcPy Project."
        ),
    )
    transform_method: Optional[str] = Field(
        default=None,
        description=(
            "Optional named geographic transformation used when source and target "
            "datums differ, for example 'ITRF_2014_To_ETRF_2014'. Use None to let "
            "ArcPy choose where possible."
        ),
        max_length=120,
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing projected output feature "
            "class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class GetSpatialReferenceInput(ToolInput):
    """Inspect a spatial reference definition by WKID without touching files."""

    wkid: int = Field(
        ...,
        ge=_WKID_MIN,
        le=_WKID_MAX,
        description=(
            "EPSG or Esri WKID to inspect. This is a pure spatial-reference lookup "
            "and has no filesystem input or output."
        ),
    )
    # No path_fields: this tool has no filesystem surface at all.


class ProjectRasterInput(ToolInput):
    """Reproject a raster dataset into a different coordinate system."""

    in_raster: str = Field(
        ...,
        description=(
            "Absolute path to the input raster dataset to reproject. The path must "
            "be inside a configured PathGuard allowed root."
        ),
    )
    out_raster: str = Field(
        ...,
        description=(
            "Absolute output raster path to create in the target coordinate system. "
            "The path must be inside a configured PathGuard allowed root; existing "
            "outputs require overwrite=true."
        ),
    )
    out_wkid: int = Field(
        ...,
        ge=_WKID_MIN,
        le=_WKID_MAX,
        description=(
            "Target EPSG or Esri WKID for the output raster. Raster cells are "
            "projected into this spatial reference using ArcPy ProjectRaster."
        ),
    )
    resampling_type: RasterResampling = Field(
        default="NEAREST",
        description=(
            "Resampling method used while projecting raster cells. Use NEAREST for "
            "categorical rasters such as land cover or zones; use BILINEAR or "
            "CUBIC for continuous surfaces such as DEMs or imagery; use MAJORITY "
            "for classified rasters where appropriate."
        ),
    )
    cell_size: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional output cell size in target map units. Use None to let ArcPy "
            "derive an appropriate cell size from the input raster and projection."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output raster is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "out_raster": "write",
    }


__all__ = [
    "DefineProjectionInput",
    "GetSpatialReferenceInput",
    "ProjectFeaturesInput",
    "ProjectRasterInput",
    "RasterResampling",
]
