"""Input models — Category 5: Raster Operations & DEM Processing (catalog #60-74)."""

from __future__ import annotations

import re
from typing import ClassVar, List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from .base import PathRole, ToolInput
from .projection import RasterResampling  # shared Literal — single definition

ZonalStatType = Literal[
    "MEAN",
    "SUM",
    "MIN",
    "MAX",
    "RANGE",
    "STD",
    "MEDIAN",
    "MAJORITY",
    "MINORITY",
    "VARIETY",
    "ALL",
]
PixelType = Literal[
    "1_BIT",
    "8_BIT_UNSIGNED",
    "8_BIT_SIGNED",
    "16_BIT_UNSIGNED",
    "16_BIT_SIGNED",
    "32_BIT_UNSIGNED",
    "32_BIT_SIGNED",
    "32_BIT_FLOAT",
    "64_BIT",
]
MosaicMethod = Literal["FIRST", "LAST", "BLEND", "MEAN", "MINIMUM", "MAXIMUM"]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Map-algebra expression whitelist: identifiers, numbers, arithmetic,
#: comparisons, boolean/bitwise operators, parentheses and commas. No
#: quotes, no attribute access beyond what sa functions need, so a
#: prompt-injected ``__import__('os')``-style payload cannot be expressed.
_MAP_ALGEBRA_CHARS = re.compile(r"^[A-Za-z0-9_+\-*/().,%<>=!&|~^ \t]+$")


class RasterInOut(ToolInput):
    """Shared base for tools that read one raster and create one raster output."""

    in_raster: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to the existing input raster dataset. The path must "
            "be inside a configured PathGuard allowed root."
        ),
    )
    out_raster: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute output raster path to create. The path must be inside a "
            "configured PathGuard allowed root; existing outputs require "
            "overwrite=true."
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


class DemDerivative(RasterInOut):
    """Shared base for DEM-derived raster surfaces."""

    z_factor: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Vertical unit conversion or exaggeration factor. Use 1.0 when XY "
            "and Z units already match; for example use 0.3048 when elevation "
            "Z values are in feet and XY units are meters."
        ),
    )


class ExtractByMaskInput(RasterInOut):
    """Input contract for extracting raster cells inside a mask."""

    mask: str = Field(
        ...,
        description=(
            "Absolute path to a polygon feature class or raster dataset used as "
            "the extraction mask. The mask must be inside a configured PathGuard "
            "allowed root."
        ),
    )
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

    rasters: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Absolute paths to input raster datasets used by the map-algebra "
            "expression. Each path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    variable_names: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Identifier names used inside the expression to reference the rasters. "
            "The list length must match rasters, and each name must be a valid "
            "identifier such as red, nir, or elevation."
        ),
    )
    expression: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Map-algebra expression using only declared variable_names, numbers, "
            "operators, comparisons, parentheses, commas, and supported Spatial "
            "Analyst functions. Inline file paths, quotes, and dunder access are "
            "rejected."
        ),
    )
    out_raster: str = Field(
        ...,
        description=(
            "Absolute output raster path to create from the map-algebra result. "
            "Existing outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output raster is intended.",
    )
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

    @field_validator("expression")
    @classmethod
    def _expression_is_pure_map_algebra(cls, v: str) -> str:
        """Constrain the free-form channel to the map-algebra grammar.

        The expression string ultimately reaches an evaluation context in
        the worker; restricting it to identifiers/numbers/operators (no
        quotes, no dunder access) means only declared raster variables and
        sa functions are reachable — never the interpreter's builtins.
        """
        if not _MAP_ALGEBRA_CHARS.match(v):
            raise ValueError(
                "Expression contains characters outside the map-algebra "
                "grammar (identifiers, numbers, + - * / % ( ) , comparison "
                "and boolean operators)."
            )
        if "__" in v:
            raise ValueError("Dunder sequences are not valid map algebra.")
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
    """Input contract for changing raster cell size and resampling method."""

    cell_size: float = Field(
        ...,
        gt=0,
        description=(
            "Target output cell size in map units. Larger values produce coarser "
            "rasters; smaller values produce finer rasters."
        ),
    )
    resampling_type: RasterResampling = Field(
        default="NEAREST",
        description=(
            "Resampling method used when creating the output raster. Use NEAREST "
            "for categorical rasters and bilinear/cubic-style methods for "
            "continuous rasters when available."
        ),
    )


class MosaicToNewRasterInput(ToolInput):
    """Input contract for mosaicking multiple rasters into a new raster dataset."""

    rasters: List[str] = Field(
        ...,
        min_length=2,
        max_length=50,
        description=(
            "Absolute paths to two or more input raster datasets to mosaic. Each "
            "path must be inside a configured PathGuard allowed root."
        ),
    )
    output_location: str = Field(
        ...,
        description=(
            "Absolute path to an existing folder or geodatabase where the mosaic "
            "output raster will be created. Must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    raster_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description=(
            "Name of the output raster. Include an extension such as .tif when "
            "writing to a folder; use a geodatabase raster name when writing to a GDB."
        ),
    )
    number_of_bands: int = Field(
        ...,
        ge=1,
        le=400,
        description="Number of bands in the output raster dataset.",
    )
    pixel_type: PixelType = Field(
        default="32_BIT_FLOAT",
        description=(
            "Pixel depth and numeric type for the output raster, such as "
            "8_BIT_UNSIGNED, 16_BIT_SIGNED, or 32_BIT_FLOAT."
        ),
    )
    mosaic_method: MosaicMethod = Field(
        default="LAST",
        description=(
            "Method used to resolve overlapping raster cells, such as FIRST, LAST, "
            "BLEND, MEAN, MINIMUM, or MAXIMUM."
        ),
    )
    cell_size: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional output cell size in map units. Use None to let ArcPy choose "
            "from the input rasters."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "rasters": "read_list",
        "output_location": "read",
    }


class RasterToPolygonInput(ToolInput):
    """Input contract for converting raster zones or classes to polygons."""

    in_raster: str = Field(
        ...,
        description=(
            "Absolute path to the input raster dataset to convert to polygons. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output polygon feature class path to create. Existing "
            "outputs require overwrite=true."
        ),
    )
    simplify: bool = Field(
        default=True,
        description=(
            "When true, smooth polygon boundaries to reduce cell-edge stair steps. "
            "When false, preserve exact raster cell edges."
        ),
    )
    raster_field: str = Field(
        default="Value",
        max_length=64,
        description=(
            "Raster attribute field used to assign polygon values. The default "
            "Value field is appropriate for most classified rasters."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output polygon feature "
            "class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "out_features": "write",
    }


class PolygonToRasterInput(ToolInput):
    """Input contract for converting polygon features to raster cells."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input polygon feature class. The path must be "
            "inside a configured PathGuard allowed root."
        ),
    )
    value_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Attribute field whose values will be burned into output raster cells."
        ),
    )
    out_raster: str = Field(
        ...,
        description=(
            "Absolute output raster path to create. Existing outputs require "
            "overwrite=true."
        ),
    )
    cell_assignment: Literal["CELL_CENTER", "MAXIMUM_AREA", "MAXIMUM_COMBINED_AREA"] = (
        Field(
            default="CELL_CENTER",
            description=(
                "Rule used to assign polygon values to raster cells. CELL_CENTER "
                "uses the polygon covering the cell center; MAXIMUM_AREA uses the "
                "polygon occupying the largest cell area; MAXIMUM_COMBINED_AREA "
                "combines areas by value."
            ),
        )
    )
    cell_size: float = Field(
        ...,
        gt=0,
        description="Output raster cell size in map units.",
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output raster is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_raster": "write",
    }


class ZonalStatisticsInput(ToolInput):
    """Input contract for calculating one zonal statistic as a raster output."""

    in_zone_data: str = Field(
        ...,
        description=(
            "Absolute path to polygon zone features or a zone raster. The path "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    zone_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Zone identifier field used to group value raster cells for statistics."
        ),
    )
    in_value_raster: str = Field(
        ...,
        description=(
            "Absolute path to the raster containing values to summarize within "
            "each zone. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_raster: str = Field(
        ...,
        description=(
            "Absolute output raster path to create with one statistic value per "
            "zone. Existing outputs require overwrite=true."
        ),
    )
    statistics_type: ZonalStatType = Field(
        default="MEAN",
        description=(
            "Statistic to calculate for each zone, such as MEAN, SUM, MIN, MAX, "
            "RANGE, STD, MEDIAN, MAJORITY, MINORITY, or VARIETY. ALL is rejected "
            "for raster output."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output raster is intended.",
    )
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
    """Input contract for writing zonal statistics to a standalone table."""

    in_zone_data: str = Field(
        ...,
        description=(
            "Absolute path to polygon zone features or a zone raster. The path "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    zone_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Zone identifier field used to group value raster cells for statistics."
        ),
    )
    in_value_raster: str = Field(
        ...,
        description=(
            "Absolute path to the raster containing values to summarize within "
            "each zone. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output table path to create with zonal statistics. Existing "
            "outputs require overwrite=true."
        ),
    )
    statistics_type: ZonalStatType = Field(
        default="ALL",
        description=(
            "Statistic or statistic set to calculate. ALL writes the full supported "
            "statistics set to the output table."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output table is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_zone_data": "read",
        "in_value_raster": "read",
        "out_table": "write",
    }


class SlopeAnalysisInput(DemDerivative):
    """Input contract for deriving slope from an elevation raster."""

    output_measurement: Literal["DEGREE", "PERCENT_RISE"] = Field(
        default="DEGREE",
        description=(
            "Slope output unit. DEGREE returns slope angle in degrees; "
            "PERCENT_RISE returns rise over run as a percentage."
        ),
    )


class AspectAnalysisInput(DemDerivative):
    """Input contract for deriving aspect direction from an elevation raster."""


class HillshadeInput(DemDerivative):
    """Input contract for deriving shaded relief from an elevation raster."""

    azimuth: float = Field(
        default=315.0,
        ge=0.0,
        le=360.0,
        description=(
            "Illumination azimuth in degrees clockwise from north. The default "
            "315 degrees represents northwest light."
        ),
    )
    altitude: float = Field(
        default=45.0,
        ge=0.0,
        le=90.0,
        description=(
            "Illumination altitude angle in degrees above the horizon. Higher "
            "values create more overhead lighting."
        ),
    )
    model_shadows: bool = Field(
        default=False,
        description=(
            "When true, model terrain shadows where supported by ArcPy hillshade."
        ),
    )


class ContourLinesInput(ToolInput):
    """Input contract for deriving contour isolines from a DEM raster."""

    in_dem: str = Field(
        ...,
        description=(
            "Absolute path to the input elevation raster. The path must be inside "
            "a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output polyline feature class path for contour isolines. "
            "Existing outputs require overwrite=true."
        ),
    )
    contour_interval: float = Field(
        ...,
        gt=0,
        description="Elevation interval between contour lines in DEM vertical units.",
    )
    base_contour: float = Field(
        default=0.0,
        description="Base contour value from which intervals are calculated.",
    )
    z_factor: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Vertical unit conversion or exaggeration factor applied before "
            "contour generation."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output contour feature "
            "class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_dem": "read",
        "out_features": "write",
    }


class FlowDirectionInput(RasterInOut):
    """Input contract for deriving hydrologic flow direction from a surface raster."""

    force_flow: bool = Field(
        default=False,
        description=(
            "When true, force edge cells to flow outward using ArcPy FORCE "
            "behavior. When false, use the default NORMAL behavior."
        ),
    )


class FillSinksInput(RasterInOut):
    """Input contract for filling sinks in an elevation raster."""

    z_limit: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Maximum sink depth to fill. Use None to fill all sinks detected by "
            "ArcPy; use a positive value to limit filling to shallow sinks."
        ),
    )


class ClipRasterInput(RasterInOut):
    """Input contract for clipping a raster by rectangle or template dataset."""

    xmin: Optional[float] = Field(
        default=None,
        description=(
            "Minimum X coordinate of the clipping rectangle. Provide all four "
            "rectangle bounds together, or leave all bounds None and use "
            "template_dataset."
        ),
    )
    ymin: Optional[float] = Field(
        default=None,
        description=(
            "Minimum Y coordinate of the clipping rectangle. Provide all four "
            "rectangle bounds together, or leave all bounds None and use "
            "template_dataset."
        ),
    )
    xmax: Optional[float] = Field(
        default=None,
        description=(
            "Maximum X coordinate of the clipping rectangle. Must be greater than "
            "xmin when rectangle clipping is used."
        ),
    )
    ymax: Optional[float] = Field(
        default=None,
        description=(
            "Maximum Y coordinate of the clipping rectangle. Must be greater than "
            "ymin when rectangle clipping is used."
        ),
    )
    template_dataset: Optional[str] = Field(
        default=None,
        description=(
            "Optional feature class or raster whose extent, or polygon geometry "
            "when use_clipping_geometry=true, defines the clipping area."
        ),
    )
    use_clipping_geometry: bool = Field(
        default=False,
        description=(
            "When true, clip to the template polygon geometry instead of only the "
            "template extent. Requires template_dataset."
        ),
    )
    nodata_value: Optional[str] = Field(
        default=None,
        description=(
            "Optional NoData value assigned outside the clipping area where ArcPy "
            "supports it."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_raster": "read",
        "template_dataset": "read",
        "out_raster": "write",
    }

    @model_validator(mode="after")
    def _rectangle_or_template(self) -> "ClipRasterInput":
        # Explicit per-field narrowing (mypy cannot narrow through all()/any()).
        if (
            self.xmin is not None
            and self.ymin is not None
            and self.xmax is not None
            and self.ymax is not None
        ):
            if not (self.xmax > self.xmin and self.ymax > self.ymin):
                raise ValueError("Rectangle must satisfy xmax > xmin and ymax > ymin.")
        elif any(v is not None for v in (self.xmin, self.ymin, self.xmax, self.ymax)):
            raise ValueError("Provide all four of xmin/ymin/xmax/ymax or none.")
        elif self.template_dataset is None:
            raise ValueError("Provide a rectangle or a template_dataset.")
        if self.use_clipping_geometry and self.template_dataset is None:
            raise ValueError("use_clipping_geometry requires template_dataset.")
        return self


__all__ = [
    "AspectAnalysisInput",
    "ClipRasterInput",
    "ContourLinesInput",
    "DemDerivative",
    "ExtractByMaskInput",
    "FillSinksInput",
    "FlowDirectionInput",
    "HillshadeInput",
    "MosaicMethod",
    "MosaicToNewRasterInput",
    "PixelType",
    "PolygonToRasterInput",
    "RasterCalculatorInput",
    "RasterInOut",
    "RasterToPolygonInput",
    "ResampleRasterInput",
    "SlopeAnalysisInput",
    "ZonalStatType",
    "ZonalStatisticsAsTableInput",
    "ZonalStatisticsInput",
]
