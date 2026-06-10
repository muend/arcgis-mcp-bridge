"""ToolSpecs + worker implementations — Category 5: Raster Operations & DEM.

Case-sensitivity guard: exact Esri signatures — ``arcpy.sa.ExtractByMask``,
``arcpy.sa.RasterCalculator``, ``arcpy.management.Resample``,
``arcpy.management.MosaicToNewRaster``, ``arcpy.conversion.RasterToPolygon``,
``arcpy.conversion.PolygonToRaster``, ``arcpy.sa.ZonalStatistics``,
``arcpy.sa.ZonalStatisticsAsTable``, ``arcpy.sa.Slope``, ``arcpy.sa.Aspect``,
``arcpy.sa.Hillshade``, ``arcpy.sa.Contour``, ``arcpy.sa.FlowDirection``,
``arcpy.sa.Fill``, ``arcpy.management.Clip``.

License discipline
------------------
Every ``arcpy.sa`` call runs inside the ``_extension()`` context manager:
checkout is verified BEFORE the tool executes, and ``CheckInExtension``
runs in ``finally`` so a geoprocessing crash can never leave the Spatial
Analyst seat locked. An unavailable extension raises
``ExtensionLicenseError`` — a structured frame, not a process drop.

Lazy import discipline: ``arcpy.sa`` raster objects are reached lazily via
the passed ``arcpy`` module only inside worker functions; this module adds
zero import weight to Layer A.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from ..contracts import raster_ops as c
from ..registry import Category, ToolSpec, register


class ExtensionLicenseError(ValueError):
    """Required Esri extension license is not available on this machine."""


@contextmanager
def _extension(arcpy: Any, name: str) -> Iterator[None]:
    """Checkout/checkin guard for licensed extensions ('Spatial', '3D')."""
    if arcpy.CheckExtension(name) != "Available":
        raise ExtensionLicenseError(
            f"The {name} Analyst extension license is not available. "
            "Enable it in ArcGIS Pro (Settings > Licensing) and retry."
        )
    arcpy.CheckOutExtension(name)
    try:
        yield
    finally:
        arcpy.CheckInExtension(name)  # never leave the seat locked


def _save(result_raster: Any, out_path: str) -> dict[str, Any]:
    """Persist an in-memory sa Raster result; uniform success payload."""
    result_raster.save(out_path)
    return {"output": out_path}


# ----------------------------------------------------------- Spatial Analyst


def _extract_by_mask(arcpy: Any, inp: c.ExtractByMaskInput) -> dict:
    with _extension(arcpy, "Spatial"):
        return _save(arcpy.sa.ExtractByMask(inp.in_raster, inp.mask), inp.out_raster)


def _raster_calculator(arcpy: Any, inp: c.RasterCalculatorInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.RasterCalculator(
            rasters=list(inp.rasters),
            input_names=list(inp.variable_names),
            expression=inp.expression,
        )
        out = _save(result, inp.out_raster)
    out["expression"] = inp.expression
    return out


def _zonal_statistics(arcpy: Any, inp: c.ZonalStatisticsInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.ZonalStatistics(
            inp.in_zone_data, inp.zone_field, inp.in_value_raster, inp.statistics_type
        )
        out = _save(result, inp.out_raster)
    out["statistic"] = inp.statistics_type
    return out


def _zonal_statistics_as_table(arcpy: Any, inp: c.ZonalStatisticsAsTableInput) -> dict:
    with _extension(arcpy, "Spatial"):
        arcpy.sa.ZonalStatisticsAsTable(
            inp.in_zone_data,
            inp.zone_field,
            inp.in_value_raster,
            inp.out_table,
            "DATA",
            inp.statistics_type,
        )
    return {"output": inp.out_table, "statistic": inp.statistics_type}


def _slope(arcpy: Any, inp: c.SlopeAnalysisInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.Slope(inp.in_raster, inp.output_measurement, inp.z_factor)
        out = _save(result, inp.out_raster)
    out["measurement"] = inp.output_measurement
    return out


def _aspect(arcpy: Any, inp: c.AspectAnalysisInput) -> dict:
    with _extension(arcpy, "Spatial"):
        return _save(arcpy.sa.Aspect(inp.in_raster), inp.out_raster)


def _hillshade(arcpy: Any, inp: c.HillshadeInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.Hillshade(
            inp.in_raster,
            inp.azimuth,
            inp.altitude,
            "SHADOWS" if inp.model_shadows else "NO_SHADOWS",
            inp.z_factor,
        )
        out = _save(result, inp.out_raster)
    out.update(azimuth=inp.azimuth, altitude=inp.altitude)
    return out


def _contour_lines(arcpy: Any, inp: c.ContourLinesInput) -> dict:
    with _extension(arcpy, "Spatial"):
        arcpy.sa.Contour(
            inp.in_dem,
            inp.out_features,
            inp.contour_interval,
            inp.base_contour,
            inp.z_factor,
        )
    return {"output": inp.out_features, "interval": inp.contour_interval}


def _flow_direction(arcpy: Any, inp: c.FlowDirectionInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.FlowDirection(
            inp.in_raster, "FORCE" if inp.force_flow else "NORMAL"
        )
        return _save(result, inp.out_raster)


def _fill_sinks(arcpy: Any, inp: c.FillSinksInput) -> dict:
    with _extension(arcpy, "Spatial"):
        result = arcpy.sa.Fill(inp.in_raster, inp.z_limit)
        out = _save(result, inp.out_raster)
    out["z_limit"] = inp.z_limit
    return out


# ------------------------------------------------- unlicensed core tools --


def _resample_raster(arcpy: Any, inp: c.ResampleRasterInput) -> dict:
    arcpy.management.Resample(
        inp.in_raster, inp.out_raster, str(inp.cell_size), inp.resampling_type
    )
    return {
        "output": inp.out_raster,
        "cell_size": inp.cell_size,
        "resampling_type": inp.resampling_type,
    }


def _mosaic_to_new_raster(arcpy: Any, inp: c.MosaicToNewRasterInput) -> dict:
    arcpy.management.MosaicToNewRaster(
        input_rasters=list(inp.rasters),
        output_location=inp.output_location,
        raster_dataset_name_with_extension=inp.raster_name,
        pixel_type=inp.pixel_type,
        cellsize=inp.cell_size,
        number_of_bands=inp.number_of_bands,
        mosaic_method=inp.mosaic_method,
    )
    return {
        "output": f"{inp.output_location}/{inp.raster_name}",
        "inputs_merged": len(inp.rasters),
        "mosaic_method": inp.mosaic_method,
    }


def _raster_to_polygon(arcpy: Any, inp: c.RasterToPolygonInput) -> dict:
    arcpy.conversion.RasterToPolygon(
        inp.in_raster,
        inp.out_features,
        "SIMPLIFY" if inp.simplify else "NO_SIMPLIFY",
        inp.raster_field,
    )
    return {"output": inp.out_features}


def _polygon_to_raster(arcpy: Any, inp: c.PolygonToRasterInput) -> dict:
    arcpy.conversion.PolygonToRaster(
        inp.in_features,
        inp.value_field,
        inp.out_raster,
        inp.cell_assignment,
        cellsize=inp.cell_size,
    )
    return {"output": inp.out_raster, "value_field": inp.value_field}


def _clip_raster(arcpy: Any, inp: c.ClipRasterInput) -> dict:
    rectangle = (
        f"{inp.xmin} {inp.ymin} {inp.xmax} {inp.ymax}" if inp.xmin is not None else "#"
    )
    arcpy.management.Clip(
        in_raster=inp.in_raster,
        rectangle=rectangle,
        out_raster=inp.out_raster,
        in_template_dataset=inp.template_dataset,
        nodata_value=inp.nodata_value,
        clipping_geometry=("ClippingGeometry" if inp.use_clipping_geometry else "NONE"),
    )
    return {
        "output": inp.out_raster,
        "rectangle": rectangle,
        "template": inp.template_dataset,
    }


# -------------------------------------------------------------- registrations

_CAT = Category.RASTER

_SPECS = (
    (
        "extract_by_mask",
        "Clip a raster by a polygon/raster mask (sa.ExtractByMask). "
        "Requires Spatial Analyst.",
        c.ExtractByMaskInput,
        _extract_by_mask,
    ),
    (
        "raster_calculator",
        "Map algebra over named raster variables, e.g. NDVI = (nir-red)/(nir+red) "
        "(sa.RasterCalculator). Requires Spatial Analyst.",
        c.RasterCalculatorInput,
        _raster_calculator,
    ),
    (
        "resample_raster",
        "Change raster cell size with NEAREST/BILINEAR/CUBIC/MAJORITY (Resample).",
        c.ResampleRasterInput,
        _resample_raster,
    ),
    (
        "mosaic_to_new_raster",
        "Merge multiple rasters into one dataset (MosaicToNewRaster).",
        c.MosaicToNewRasterInput,
        _mosaic_to_new_raster,
    ),
    (
        "raster_to_polygon",
        "Vectorize a classified raster (conversion.RasterToPolygon).",
        c.RasterToPolygonInput,
        _raster_to_polygon,
    ),
    (
        "polygon_to_raster",
        "Rasterize polygons by a value field (conversion.PolygonToRaster).",
        c.PolygonToRasterInput,
        _polygon_to_raster,
    ),
    (
        "zonal_statistics",
        "Per-zone raster statistic as a raster (sa.ZonalStatistics). "
        "Requires Spatial Analyst.",
        c.ZonalStatisticsInput,
        _zonal_statistics,
    ),
    (
        "zonal_statistics_as_table",
        "Per-zone raster statistics as a table (sa.ZonalStatisticsAsTable). "
        "Requires Spatial Analyst.",
        c.ZonalStatisticsAsTableInput,
        _zonal_statistics_as_table,
    ),
    (
        "slope_analysis",
        "Slope (degrees or percent rise) from a DEM (sa.Slope). "
        "Requires Spatial Analyst.",
        c.SlopeAnalysisInput,
        _slope,
    ),
    (
        "aspect_analysis",
        "Aspect (downslope direction) from a DEM (sa.Aspect). "
        "Requires Spatial Analyst.",
        c.AspectAnalysisInput,
        _aspect,
    ),
    (
        "hillshade",
        "Illumination shading from a DEM with sun azimuth/altitude "
        "(sa.Hillshade). Requires Spatial Analyst.",
        c.HillshadeInput,
        _hillshade,
    ),
    (
        "contour_lines",
        "Vector elevation isolines from a DEM (sa.Contour). "
        "Requires Spatial Analyst.",
        c.ContourLinesInput,
        _contour_lines,
    ),
    (
        "flow_direction",
        "D8 hydrological flow direction raster (sa.FlowDirection). "
        "Requires Spatial Analyst.",
        c.FlowDirectionInput,
        _flow_direction,
    ),
    (
        "fill_sinks",
        "Fill DEM sinks for hydrological conditioning (sa.Fill). "
        "Requires Spatial Analyst.",
        c.FillSinksInput,
        _fill_sinks,
    ),
    (
        "clip_raster",
        "Clip a raster by rectangle and/or template geometry (management.Clip).",
        c.ClipRasterInput,
        _clip_raster,
    ),
)

for _name, _desc, _model, _fn in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn))
