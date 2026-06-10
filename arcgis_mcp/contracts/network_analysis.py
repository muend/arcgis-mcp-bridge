"""Input models — Category 8: Network Analysis (catalog #91-94)."""

from __future__ import annotations

from typing import ClassVar, List, Optional

from pydantic import Field

from .base import PathRole, ToolInput


class NetworkBaseInput(ToolInput):
    """Shared base: every NA tool solves against a network dataset."""

    network_dataset: str = Field(..., description="Path to the network dataset.")
    travel_mode: Optional[str] = Field(
        default=None,
        description="Named travel mode (e.g. 'Driving Time'); None = default.",
        max_length=120,
    )
    out_features: str = Field(..., description="Solved result feature class.")
    overwrite: bool = False


class ServiceAreaInput(NetworkBaseInput):
    facilities: str = Field(..., description="Point FC of facilities.")
    cutoffs: List[float] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Break values in travel-mode units, e.g. [5, 10, 15] minutes.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "facilities": "read",
        "out_features": "write",
    }


class RouteAnalysisInput(NetworkBaseInput):
    stops: str = Field(..., description="Ordered point FC of route stops (A->B->...).")
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "stops": "read",
        "out_features": "write",
    }


class OdCostMatrixInput(NetworkBaseInput):
    origins: str
    destinations: str
    cutoff: Optional[float] = Field(
        default=None, gt=0, description="Max impedance; None = unlimited."
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "origins": "read",
        "destinations": "read",
        "out_features": "write",
    }


class ClosestFacilityInput(NetworkBaseInput):
    facilities: str
    incidents: str
    facilities_to_find: int = Field(default=1, ge=1, le=100)
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "facilities": "read",
        "incidents": "read",
        "out_features": "write",
    }


__all__ = [
    "ClosestFacilityInput",
    "NetworkBaseInput",
    "OdCostMatrixInput",
    "RouteAnalysisInput",
    "ServiceAreaInput",
]
