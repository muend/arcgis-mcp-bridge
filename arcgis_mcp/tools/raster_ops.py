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

from typing import Any

from ..contracts import raster_ops as c
from ..registry import Category, ToolSpec, register
from ._licensing import ExtensionLicenseError, extension as _extension

__all__ = ["ExtensionLicenseError", "_extension"]  # back-compat re-export


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
        (
            "Extract raster cells inside a polygon or raster mask using ArcPy "
            "Spatial Analyst ExtractByMask. Use this to clip elevation, imagery, "
            "land-cover, suitability, or other raster data to a study area before "
            "analysis. Requires a Spatial Analyst license; reads in_raster and "
            "mask inside PathGuard roots and writes out_raster."
        ),
        c.ExtractByMaskInput,
        _extract_by_mask,
    ),
    (
        "raster_calculator",
        (
            "Run Spatial Analyst map algebra over explicitly named raster "
            "variables using ArcPy RasterCalculator. Use this for NDVI, suitability "
            "models, binary masks, raster normalization, and cell-by-cell formulas. "
            "Requires a Spatial Analyst license; expressions may reference only "
            "declared variable_names and validated map-algebra syntax."
        ),
        c.RasterCalculatorInput,
        _raster_calculator,
    ),
    (
        "resample_raster",
        (
            "Change raster cell size using ArcPy Resample. Use this to align "
            "resolution before overlay, modeling, visualization, or export. Reads "
            "one input raster and writes out_raster inside PathGuard roots; choose "
            "a resampling method appropriate for categorical or continuous data."
        ),
        c.ResampleRasterInput,
        _resample_raster,
    ),
    (
        "mosaic_to_new_raster",
        (
            "Merge multiple raster datasets into one new raster using ArcPy "
            "MosaicToNewRaster. Use this to combine tiles, scenes, DEM sheets, or "
            "image bands into a single dataset. Reads two or more input rasters "
            "and writes a named raster into an existing folder or geodatabase."
        ),
        c.MosaicToNewRasterInput,
        _mosaic_to_new_raster,
    ),
    (
        "raster_to_polygon",
        (
            "Convert raster zones or classes to polygon features using ArcPy "
            "RasterToPolygon. Use this to vectorize classified rasters, suitability "
            "classes, land-cover codes, or cell regions for GIS editing, overlay, "
            "and cartographic workflows. Reads in_raster and writes out_features."
        ),
        c.RasterToPolygonInput,
        _raster_to_polygon,
    ),
    (
        "polygon_to_raster",
        (
            "Convert polygon features to a raster dataset using ArcPy "
            "PolygonToRaster. Use this when vector zones, classes, parcels, or "
            "planning units need to become raster cells for map algebra, "
            "suitability modeling, or raster overlay. Reads polygon features and "
            "writes out_raster using value_field, cell_assignment, and cell_size."
        ),
        c.PolygonToRasterInput,
        _polygon_to_raster,
    ),
    (
        "zonal_statistics",
        (
            "Calculate one raster statistic per zone and write the result as a "
            "raster using ArcPy Spatial Analyst ZonalStatistics. Use this when "
            "each zone should receive a MEAN, SUM, MIN, MAX, or similar value "
            "from an input value raster. Requires a Spatial Analyst license."
        ),
        c.ZonalStatisticsInput,
        _zonal_statistics,
    ),
    (
        "zonal_statistics_as_table",
        (
            "Calculate zonal statistics and write the results to a standalone "
            "table using ArcPy Spatial Analyst ZonalStatisticsAsTable. Use this "
            "to summarize raster values by districts, parcels, watersheds, grid "
            "cells, or other zone datasets. Requires a Spatial Analyst license."
        ),
        c.ZonalStatisticsAsTableInput,
        _zonal_statistics_as_table,
    ),
    (
        "slope_analysis",
        (
            "Derive slope from an elevation raster using ArcPy Spatial Analyst "
            "Slope. Use this in terrain, hydrology, accessibility, hazard, and "
            "site suitability workflows. Requires a Spatial Analyst license; "
            "writes a slope raster in degrees or percent rise using z_factor."
        ),
        c.SlopeAnalysisInput,
        _slope,
    ),
    (
        "aspect_analysis",
        (
            "Derive downslope aspect direction from an elevation raster using "
            "ArcPy Spatial Analyst Aspect. Use this for terrain interpretation, "
            "solar exposure, ecological modeling, hydrology, and site suitability. "
            "Requires a Spatial Analyst license and writes a new aspect raster."
        ),
        c.AspectAnalysisInput,
        _aspect,
    ),
    (
        "hillshade",
        (
            "Create shaded relief from an elevation raster using ArcPy Spatial "
            "Analyst Hillshade. Use this for terrain visualization, map backdrops, "
            "and DEM QA/QC with controlled sun azimuth, altitude, shadow modeling, "
            "and z_factor. Requires a Spatial Analyst license."
        ),
        c.HillshadeInput,
        _hillshade,
    ),
    (
        "contour_lines",
        (
            "Create vector elevation isolines from a DEM raster using ArcPy "
            "Spatial Analyst Contour. Use this to generate cartographic contours, "
            "terrain analysis inputs, or elevation reference lines. Requires a "
            "Spatial Analyst license and writes a polyline feature class."
        ),
        c.ContourLinesInput,
        _contour_lines,
    ),
    (
        "flow_direction",
        (
            "Derive a hydrologic flow-direction raster from an elevation or "
            "surface raster using ArcPy Spatial Analyst FlowDirection. Use this "
            "before flow accumulation, watershed delineation, drainage modeling, "
            "or stream extraction. Requires a Spatial Analyst license; writes "
            "out_raster and can optionally force edge cells to flow outward."
        ),
        c.FlowDirectionInput,
        _flow_direction,
    ),
    (
        "fill_sinks",
        (
            "Fill sinks or depressions in an elevation raster using ArcPy Spatial "
            "Analyst Fill. Use this to hydrologically condition DEMs before flow "
            "direction, flow accumulation, watershed, or stream network analysis. "
            "Requires a Spatial Analyst license; optional z_limit controls maximum "
            "sink depth to fill."
        ),
        c.FillSinksInput,
        _fill_sinks,
    ),
    (
        "clip_raster",
        (
            "Clip a raster by rectangle, template extent, or template polygon "
            "geometry using ArcPy management Clip. Use this to crop imagery, DEMs, "
            "or classified rasters to a study area without requiring Spatial "
            "Analyst. Reads in_raster and optional template_dataset and writes "
            "out_raster inside PathGuard roots."
        ),
        c.ClipRasterInput,
        _clip_raster,
    ),
)

for _name, _desc, _model, _fn in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn))
