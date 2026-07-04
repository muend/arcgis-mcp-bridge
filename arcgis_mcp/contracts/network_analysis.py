"""Input models — Category 8: Network Analysis (catalog #91-94)."""

from __future__ import annotations

from typing import ClassVar, List, Optional

from pydantic import Field

from .base import PathRole, ToolInput


class NetworkBaseInput(ToolInput):
    """Shared base for network analysis tools solved against a network dataset."""

    network_dataset: str = Field(
        ...,
        description=(
            "Absolute path to the ArcGIS network dataset used for routing or "
            "accessibility analysis. The path must be inside a configured "
            "PathGuard allowed root and must be usable by ArcPy Network Analyst."
        ),
    )
    travel_mode: Optional[str] = Field(
        default=None,
        description=(
            "Optional named travel mode from the network dataset, for example "
            "'Driving Time' or 'Walking Time'. Use None to let ArcPy use the "
            "network dataset default travel mode."
        ),
        max_length=120,
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create with the solved network "
            "analysis result. Existing outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing network analysis output "
            "feature class is intended."
        ),
    )


class ServiceAreaInput(NetworkBaseInput):
    """Input contract for solving service area polygons or lines around facilities."""

    facilities: str = Field(
        ...,
        description=(
            "Absolute path to point facilities used as service area origins, such "
            "as schools, hospitals, stations, depots, or stores. The path must be "
            "inside a configured PathGuard allowed root."
        ),
    )
    cutoffs: List[float] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Break values in the selected travel mode units, for example "
            "[5, 10, 15] for minutes when using a time-based travel mode. Each "
            "cutoff creates a service area threshold around the facilities."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "facilities": "read",
        "out_features": "write",
    }


class RouteAnalysisInput(NetworkBaseInput):
    """Input contract for solving routes through ordered stop points."""

    stops: str = Field(
        ...,
        description=(
            "Absolute path to an ordered point feature class of route stops, such "
            "as A-to-B or multi-stop stop sequences. The path must be inside a "
            "configured PathGuard allowed root."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "stops": "read",
        "out_features": "write",
    }


class OdCostMatrixInput(NetworkBaseInput):
    """Input contract for solving origin-destination travel cost relationships."""

    origins: str = Field(
        ...,
        description=(
            "Absolute path to point origin features, such as homes, demand points, "
            "facilities, depots, or candidate locations. The path must be inside "
            "a configured PathGuard allowed root."
        ),
    )
    destinations: str = Field(
        ...,
        description=(
            "Absolute path to point destination features, such as services, jobs, "
            "facilities, stores, stations, or opportunities. The path must be "
            "inside a configured PathGuard allowed root."
        ),
    )
    cutoff: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Optional maximum impedance or travel cost in the selected travel mode "
            "units. Use None to solve without an explicit cutoff; use a positive "
            "value to limit origin-destination matches."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "network_dataset": "read",
        "origins": "read",
        "destinations": "read",
        "out_features": "write",
    }


class ClosestFacilityInput(NetworkBaseInput):
    """Input contract for finding nearest facilities for incident points."""

    facilities: str = Field(
        ...,
        description=(
            "Absolute path to candidate facility points that may be matched to "
            "incidents, such as hospitals, stations, schools, depots, or stores. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    incidents: str = Field(
        ...,
        description=(
            "Absolute path to incident or demand point features that need nearest "
            "facility matches. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    facilities_to_find: int = Field(
        default=1,
        ge=1,
        le=100,
        description=(
            "Number of nearest facilities to find for each incident. Use 1 for "
            "nearest-only workflows, or a higher value for candidate comparison."
        ),
    )
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
