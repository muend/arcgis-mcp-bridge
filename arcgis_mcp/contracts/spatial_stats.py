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
    """Shared base: one input FC, one output FC."""

    in_features: str = Field(..., min_length=1)
    out_features: str = Field(..., min_length=1)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class MeanCenterInput(StatsInOut):
    weight_field: Optional[str] = Field(default=None, max_length=64)
    case_field: Optional[str] = Field(default=None, max_length=64)


class DirectionalDistributionInput(StatsInOut):
    ellipse_size: Literal[
        "1_STANDARD_DEVIATION", "2_STANDARD_DEVIATIONS", "3_STANDARD_DEVIATIONS"
    ] = "1_STANDARD_DEVIATION"
    weight_field: Optional[str] = Field(default=None, max_length=64)


class KernelDensityInput(ToolInput):
    in_features: str
    out_raster: str
    population_field: str = Field(
        default="NONE",
        max_length=64,
        description="Count/weight field; 'NONE' weights every feature as 1.",
    )
    cell_size: Optional[float] = Field(default=None, gt=0)
    search_radius: Optional[float] = Field(
        default=None, gt=0, description="Bandwidth in map units; None = default."
    )
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_raster": "write",
    }


class HotspotAnalysisInput(StatsInOut):
    input_field: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Numeric field analyzed for clustering.",
    )
    conceptualization: Conceptualization = "FIXED_DISTANCE_BAND"
    distance_method: DistanceMethod = "EUCLIDEAN_DISTANCE"
    distance_band: Optional[float] = Field(
        default=None, gt=0, description="Band/threshold in map units."
    )


class SpatialAutocorrelationInput(ToolInput):
    """Global Moran's I — returns scalar statistics, writes no dataset."""

    in_features: str
    input_field: str = Field(..., min_length=1, max_length=64)
    conceptualization: Conceptualization = "INVERSE_DISTANCE"
    distance_method: DistanceMethod = "EUCLIDEAN_DISTANCE"
    standardization: Literal["NONE", "ROW"] = "ROW"
    distance_band: Optional[float] = Field(default=None, gt=0)
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
