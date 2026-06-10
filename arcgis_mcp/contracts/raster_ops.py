"""Input models — Category 5: Raster Operations & DEM Processing (catalog #60-74)."""

from __future__ import annotations

import re
from typing import ClassVar, List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from .base import PathRole, ToolInput
from .projection import RasterResampling  # shared Literal — single definition

ZonalStatType = Literal[
    "MEAN", "SUM", "MIN", "MAX", "RANGE", "STD", "MEDIAN",
    "MAJORITY", "MINORITY", "VARIETY", "ALL",
]
PixelType = Literal[
    "1_BIT", "8_BIT_UNSIGNED", "8_BIT_SIGNED", "16_BIT_UNSIGNED",
    "16_BIT_SIGNED", "32_BIT_UNSIGNED", "32_BIT_SIGNED", "32_BIT_FLOAT",
    "64_BIT",
]
MosaicMethod = Literal["FIRST", "LAST", "BLEND", "MEAN", "MINIMUM", "MAXIMUM"]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RasterInOut(ToolInput):
    """Shared base: one input raster, one output raster."""

    in_raster: str = Field(..., min_length=1)
    out_raster: str = Field(..., min_length=1)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "out_raster": "write",
    }


class DemDerivative(RasterInOut):
    """Shared base: DEM-derived surfaces with a vertical exaggeration factor."""

    z_factor: float = Field(
        default=1.0, gt=0,
        description="Vertical unit conversion (e.g. 0.3048 if Z is in feet "
                    "and XY in meters).",
    )


class ExtractByMaskInput(RasterInOut):
    mask: str = Field(..., description="Polygon FC or raster acting as the mask.")
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "mask": "read",
        "out_raster": "write",
    }


class RasterCalculatorInput(ToolInput):
    """Map algebra over named raster variables.

    The expression references rasters strictly through the declared
    ``variable_names`` (e.g. ``(nir - red) / (nir + red)`` for NDVI) — no
    inline paths, no Python execution in our code: Esri's map-algebra
    parser receives the expression verbatim.
    """

    rasters: List[str] = Field(..., min_length=1, max_length=10)
    variable_names: List[str] = Field(..., min_length=1, max_length=10)
    expression: str = Field(..., min_length=1, max_length=2000)
    out_raster: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "rasters": "read_list",
        "out_raster": "write",
    }

    @field_validator("variable_names")
    @classmethod
    def _names_are_identifiers(cls, v: List[str]) -> List[str]:
        bad = [n for n in v if not _IDENTIFIER.match(n)]
        if bad:
            raise ValueError(f"Variable names must be identifiers: {bad}")
        return v

    @model_validator(mode="after")
    def _names_match_rasters(self) -> "RasterCalculatorInput":
        if len(self.rasters) != len(self.variable_names):
            raise ValueError(
                f"{len(self.rasters)} raster(s) but "
                f"{len(self.variable_names)} variable name(s)."
            )
        return self


class ResampleRasterInput(RasterInOut):
    cell_size: float = Field(..., gt=0, description="Target cell size (map units).")
    resampling_type: RasterResampling = "NEAREST"


class MosaicToNewRasterInput(ToolInput):
    rasters: List[str] = Field(..., min_length=2, max_length=50)
    output_location: str = Field(..., description="Existing folder or GDB.")
    raster_name: str = Field(..., min_length=1, max_length=128,
                             description="Output name (with .tif etc. if folder).")
    number_of_bands: int = Field(..., ge=1, le=400)
    pixel_type: PixelType = "32_BIT_FLOAT"
    mosaic_method: MosaicMethod = "LAST"
    cell_size: Optional[float] = Field(default=None, gt=0)
    path_fields: ClassVar[dict[str, PathRole]] = {
        "rasters": "read_list",
        "output_location": "read",
    }


class RasterToPolygonInput(ToolInput):
    in_raster: str
    out_features: str
    simplify: bool = Field(default=True, description="Smooth cell-edge stairsteps.")
    raster_field: str = Field(default="Value", max_length=64)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "out_features": "write",
    }


class PolygonToRasterInput(ToolInput):
    in_features: str
    value_field: str = Field(..., min_length=1, max_length=64)
    out_raster: str
    cell_assignment: Literal[
        "CELL_CENTER", "MAXIMUM_AREA", "MAXIMUM_COMBINED_AREA"
    ] = "CELL_CENTER"
    cell_size: float = Field(..., gt=0)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_raster": "write",
    }


class ZonalStatisticsInput(ToolInput):
    in_zone_data: str = Field(..., description="Polygon FC or zone raster.")
    zone_field: str = Field(..., min_length=1, max_length=64)
    in_value_raster: str
    out_raster: str
    statistics_type: ZonalStatType = "MEAN"
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_zone_data": "read",
        "in_value_raster": "read",
        "out_raster": "write",
    }

    @model_validator(mode="after")
    def _no_all_for_raster_output(self) -> "ZonalStatisticsInput":
        if self.statistics_type == "ALL":
            raise ValueError(
                "statistics_type='ALL' is only valid for "
                "zonal_statistics_as_table (a raster holds one statistic)."
            )
        return self


class ZonalStatisticsAsTableInput(ToolInput):
    in_zone_data: str
    zone_field: str = Field(..., min_length=1, max_length=64)
    in_value_raster: str
    out_table: str
    statistics_type: ZonalStatType = "ALL"
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_zone_data": "read",
        "in_value_raster": "read",
        "out_table": "write",
    }


class SlopeAnalysisInput(DemDerivative):
    output_measurement: Literal["DEGREE", "PERCENT_RISE"] = "DEGREE"


class AspectAnalysisInput(DemDerivative):
    pass


class HillshadeInput(DemDerivative):
    azimuth: float = Field(default=315.0, ge=0.0, le=360.0)
    altitude: float = Field(default=45.0, ge=0.0, le=90.0)
    model_shadows: bool = False


class ContourLinesInput(ToolInput):
    in_dem: str
    out_features: str = Field(..., description="Output polyline FC of isolines.")
    contour_interval: float = Field(..., gt=0)
    base_contour: float = 0.0
    z_factor: float = Field(default=1.0, gt=0)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_dem": "read",
        "out_features": "write",
    }


class FlowDirectionInput(RasterInOut):
    force_flow: bool = Field(
        default=False,
        description="True forces edge cells to flow outward (FORCE).",
    )


class FillSinksInput(RasterInOut):
    z_limit: Optional[float] = Field(
        default=None, gt=0,
        description="Max sink depth to fill; None fills all sinks.",
    )


class ClipRasterInput(RasterInOut):
    """Clip by explicit rectangle and/or template dataset geometry."""

    xmin: Optional[float] = None
    ymin: Optional[float] = None
    xmax: Optional[float] = None
    ymax: Optional[float] = None
    template_dataset: Optional[str] = Field(
        default=None, description="FC/raster whose extent (or geometry) clips.")
    use_clipping_geometry: bool = Field(
        default=False, description="Clip to template polygon geometry, not extent.")
    nodata_value: Optional[str] = None
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "template_dataset": "read",
        "out_raster": "write",
    }

    @model_validator(mode="after")
    def _rectangle_or_template(self) -> "ClipRasterInput":
        coords = (self.xmin, self.ymin, self.xmax, self.ymax)
        has_rect = all(v is not None for v in coords)
        some_rect = any(v is not None for v in coords)
        if some_rect and not has_rect:
            raise ValueError("Provide all four of xmin/ymin/xmax/ymax or none.")
        if not has_rect and self.template_dataset is None:
            raise ValueError("Provide a rectangle or a template_dataset.")
        if has_rect and not (self.xmax > self.xmin and self.ymax > self.ymin):
            raise ValueError("Rectangle must satisfy xmax > xmin and ymax > ymin.")
        if self.use_clipping_geometry and self.template_dataset is None:
            raise ValueError("use_clipping_geometry requires template_dataset.")
        return self


__all__ = [
    "ZonalStatType", "PixelType", "MosaicMethod",
    "RasterInOut", "DemDerivative",
    "ExtractByMaskInput", "RasterCalculatorInput", "ResampleRasterInput",
    "MosaicToNewRasterInput", "RasterToPolygonInput", "PolygonToRasterInput",
    "ZonalStatisticsInput", "ZonalStatisticsAsTableInput",
    "SlopeAnalysisInput", "AspectAnalysisInput", "HillshadeInput",
    "ContourLinesInput", "FlowDirectionInput", "FillSinksInput",
    "ClipRasterInput",
]
