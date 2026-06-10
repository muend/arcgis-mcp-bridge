"""ToolSpecs + worker implementations — Category 9: Spatial Statistics.

Case-sensitivity guard: ``arcpy.stats.MeanCenter``,
``arcpy.stats.DirectionalDistribution``, ``arcpy.sa.KernelDensity``,
``arcpy.stats.HotSpots``, ``arcpy.stats.SpatialAutocorrelation`` match
Esri signatures exactly. KernelDensity is the one Spatial Analyst tool in
this vertical and runs inside the shared license guard.

Catalog note: the source catalog lists six candidates (#95-100); the
mandated 100-tool census allocates five to this vertical, so
``cluster_outlier`` (Anselin Local Moran's I) is deferred — it slots in
later as one ToolSpec without touching any runtime code.
"""

from __future__ import annotations

from typing import Any

from ..contracts import spatial_stats as c
from ..registry import Category, ToolSpec, register
from ._licensing import extension

# ------------------------------------------------------------------- tools --


def _mean_center(arcpy: Any, inp: c.MeanCenterInput) -> dict:
    arcpy.stats.MeanCenter(
        inp.in_features, inp.out_features, inp.weight_field, inp.case_field
    )
    return {"output": inp.out_features, "weight_field": inp.weight_field}


def _directional_distribution(arcpy: Any, inp: c.DirectionalDistributionInput) -> dict:
    arcpy.stats.DirectionalDistribution(
        inp.in_features, inp.out_features, inp.ellipse_size, inp.weight_field
    )
    return {"output": inp.out_features, "ellipse_size": inp.ellipse_size}


def _kernel_density(arcpy: Any, inp: c.KernelDensityInput) -> dict:
    with extension(arcpy, "Spatial"):
        result = arcpy.sa.KernelDensity(
            inp.in_features,
            inp.population_field,
            inp.cell_size,
            inp.search_radius,
        )
        result.save(inp.out_raster)
    return {
        "output": inp.out_raster,
        "population_field": inp.population_field,
        "search_radius": inp.search_radius,
    }


def _hotspot_analysis(arcpy: Any, inp: c.HotspotAnalysisInput) -> dict:
    arcpy.stats.HotSpots(
        Input_Feature_Class=inp.in_features,
        Input_Field=inp.input_field,
        Output_Feature_Class=inp.out_features,
        Conceptualization_of_Spatial_Relationships=inp.conceptualization,
        Distance_Method=inp.distance_method,
        Standardization="NONE",
        Distance_Band_or_Threshold_Distance=inp.distance_band,
    )
    return {
        "output": inp.out_features,
        "statistic": "Getis-Ord Gi*",
        "fields_added": ["GiZScore", "GiPValue", "Gi_Bin"],
    }


def _spatial_autocorrelation(arcpy: Any, inp: c.SpatialAutocorrelationInput) -> dict:
    result = arcpy.stats.SpatialAutocorrelation(
        Input_Feature_Class=inp.in_features,
        Input_Field=inp.input_field,
        Generate_Report="NO_REPORT",
        Conceptualization_of_Spatial_Relationships=inp.conceptualization,
        Distance_Method=inp.distance_method,
        Standardization=inp.standardization,
        Distance_Band_or_Threshold_Distance=inp.distance_band,
    )

    # Derived outputs: 0=Moran's Index, 1=ZScore, 2=PValue (Esri ordering).
    def _out(i: int) -> float | None:
        try:
            return float(result.getOutput(i))
        except (ValueError, TypeError, IndexError, RuntimeError):
            return None

    return {
        "statistic": "Global Moran's I",
        "morans_index": _out(0),
        "z_score": _out(1),
        "p_value": _out(2),
        "messages": str(arcpy.GetMessages()).splitlines()[-5:],
    }


# -------------------------------------------------------------- registrations

_CAT = Category.SPATIAL_STATS

_SPECS = (
    (
        "mean_center",
        "Geometric mean center of features, optionally weighted (MeanCenter).",
        c.MeanCenterInput,
        _mean_center,
    ),
    (
        "directional_distribution",
        "Standard deviational ellipse of a point distribution "
        "(DirectionalDistribution).",
        c.DirectionalDistributionInput,
        _directional_distribution,
    ),
    (
        "kernel_density",
        "Kernel density surface from points/lines (sa.KernelDensity). "
        "Requires Spatial Analyst.",
        c.KernelDensityInput,
        _kernel_density,
    ),
    (
        "hotspot_analysis",
        "Getis-Ord Gi* hot/cold spot clustering (HotSpots).",
        c.HotspotAnalysisInput,
        _hotspot_analysis,
    ),
    (
        "spatial_autocorrelation",
        "Global Moran's I index, z-score and p-value (SpatialAutocorrelation).",
        c.SpatialAutocorrelationInput,
        _spatial_autocorrelation,
    ),
)

for _name, _desc, _model, _fn in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn))
