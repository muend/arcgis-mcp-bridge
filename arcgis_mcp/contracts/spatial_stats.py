"""Input models — Category 9: Spatial Statistics (catalog #95-100)."""

from __future__ import annotations

from typing import ClassVar, Literal, Optional

from pydantic import Field

from .base import PathRole, ToolInput

Conceptualization = Literal[
    "INVERSE_DISTANCE",
    "INVERSE_DISTANCE_SQUARED",
    "FIXED_DISTANCE_BAND",
    "ZONE_OF_INDIFFERENCE",
    "K_NEAREST_NEIGHBORS",
    "CONTIGUITY_EDGES_ONLY",
    "CONTIGUITY_EDGES_CORNERS",
]
DistanceMethod = Literal["EUCLIDEAN_DISTANCE", "MANHATTAN_DISTANCE"]


class StatsInOut(ToolInput):
    """Shared base for spatial statistics tools that read features and write features."""

    in_features: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to the input feature class used for spatial statistics. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute output feature class path to create with statistical results. "
            "The path must be inside a configured PathGuard allowed root; existing "
            "outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing spatial statistics output "
            "feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class MeanCenterInput(StatsInOut):
    """Input contract for calculating the geographic mean center of features."""

    weight_field: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Optional numeric field used to weight features when calculating the "
            "mean center. Use None when every feature should contribute equally."
        ),
    )
    case_field: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Optional field used to group features and calculate one mean center "
            "per group. Use None to calculate one mean center for all features."
        ),
    )


class DirectionalDistributionInput(StatsInOut):
    """Input contract for creating standard deviational ellipse features."""

    ellipse_size: Literal[
        "1_STANDARD_DEVIATION", "2_STANDARD_DEVIATIONS", "3_STANDARD_DEVIATIONS"
    ] = Field(
        default="1_STANDARD_DEVIATION",
        description=(
            "Size of the standard deviational ellipse to create. Use "
            "1_STANDARD_DEVIATION for the core distribution, or larger values "
            "to show broader spread around the mean center."
        ),
    )
    weight_field: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Optional numeric field used to weight features when calculating "
            "direction, dispersion, and ellipse size. Use None for unweighted "
            "directional distribution."
        ),
    )


class KernelDensityInput(ToolInput):
    """Input contract for estimating a continuous density raster from features."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to point or polyline features used as density inputs. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_raster: str = Field(
        ...,
        description=(
            "Absolute output raster path to create with density values. Existing "
            "outputs require overwrite=true."
        ),
    )
    population_field: str = Field(
        default="NONE",
        max_length=64,
        description=(
            "Optional count or weight field used to scale each input feature's "
            "contribution to density. Use 'NONE' to weight every feature as 1."
        ),
    )
    cell_size: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional output raster cell size in map units. Use None to let ArcPy "
            "choose a default based on input extent and data."
        ),
    )
    search_radius: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional kernel bandwidth or search radius in map units. Larger "
            "values create smoother density surfaces; use None for ArcPy's default."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing output raster is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_raster": "write",
    }


class HotspotAnalysisInput(StatsInOut):
    """Input contract for identifying statistically significant hot and cold spots."""

    input_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Numeric attribute field analyzed for statistically significant spatial "
            "clustering of high and low values."
        ),
    )
    conceptualization: Conceptualization = Field(
        default="FIXED_DISTANCE_BAND",
        description=(
            "Spatial relationship model used to define feature neighbors, such as "
            "FIXED_DISTANCE_BAND, INVERSE_DISTANCE, K_NEAREST_NEIGHBORS, or "
            "contiguity-based relationships."
        ),
    )
    distance_method: DistanceMethod = Field(
        default="EUCLIDEAN_DISTANCE",
        description=(
            "Distance calculation method used for spatial relationships. Use "
            "EUCLIDEAN_DISTANCE for straight-line distance or MANHATTAN_DISTANCE "
            "for grid-like movement."
        ),
    )
    distance_band: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional distance threshold in map units used by distance-based "
            "conceptualizations. Use None when ArcPy should infer or not require "
            "a distance band."
        ),
    )


class SpatialAutocorrelationInput(ToolInput):
    """Input contract for Global Moran's I, returning scalar statistics only."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class whose spatial autocorrelation "
            "will be measured. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    input_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Numeric attribute field used to calculate Global Moran's I spatial "
            "autocorrelation statistics."
        ),
    )
    conceptualization: Conceptualization = Field(
        default="INVERSE_DISTANCE",
        description=(
            "Spatial relationship model used to define feature neighbors, such as "
            "INVERSE_DISTANCE, FIXED_DISTANCE_BAND, K_NEAREST_NEIGHBORS, or "
            "contiguity-based relationships."
        ),
    )
    distance_method: DistanceMethod = Field(
        default="EUCLIDEAN_DISTANCE",
        description=(
            "Distance calculation method used for spatial weights. Use "
            "EUCLIDEAN_DISTANCE for straight-line distance or MANHATTAN_DISTANCE "
            "for grid-like movement."
        ),
    )
    standardization: Literal["NONE", "ROW"] = Field(
        default="ROW",
        description=(
            "Spatial weights standardization method. ROW standardizes neighbor "
            "weights by row; NONE uses raw weights."
        ),
    )
    distance_band: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional distance threshold in map units used for distance-based "
            "spatial relationships. Use None when no explicit threshold is needed."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"in_features": "read"}


__all__ = [
    "Conceptualization",
    "DirectionalDistributionInput",
    "DistanceMethod",
    "HotspotAnalysisInput",
    "KernelDensityInput",
    "MeanCenterInput",
    "SpatialAutocorrelationInput",
    "StatsInOut",
]
