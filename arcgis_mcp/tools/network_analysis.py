"""ToolSpecs + worker implementations — Category 8: Network Analysis.

Every solver follows the same four-phase arcpy.na lifecycle (DRY: one
``_solve`` pipeline): make analysis layer -> AddLocations per role ->
Solve -> CopyFeatures of the result sublayer. All of it runs inside the
shared ``extension(arcpy, "Network")`` license guard.

Case-sensitivity guard: ``MakeServiceAreaAnalysisLayer``,
``MakeRouteAnalysisLayer``, ``MakeODCostMatrixAnalysisLayer``,
``MakeClosestFacilityAnalysisLayer``, ``AddLocations``, ``Solve`` match
Esri's arcpy.na signatures exactly; result sublayer names ("Polygons",
"Routes", "Lines") are the Esri defaults.
"""

from __future__ import annotations

from typing import Any

from ..contracts import network_analysis as c
from ..registry import Category, ToolSpec, register
from ._licensing import extension


class NetworkSolveError(ValueError):
    """The NA layer solved to an empty/unusable result."""


def _solve(
    arcpy: Any,
    layer_obj: Any,
    locations: dict[str, str],
    sublayer: str,
    out_features: str,
) -> dict[str, Any]:
    """Shared phase 2-4: load locations, solve, materialize the sublayer."""
    for role, fc in locations.items():
        arcpy.na.AddLocations(layer_obj, role, fc)
    arcpy.na.Solve(layer_obj)

    result_layers = layer_obj.listLayers(sublayer)
    if not result_layers:
        raise NetworkSolveError(
            f"Solve produced no {sublayer!r} sublayer — check that the inputs "
            "fall within the network dataset's extent."
        )
    arcpy.management.CopyFeatures(result_layers[0], out_features)
    count = int(arcpy.management.GetCount(out_features)[0])
    return {"output": out_features, "features": count}


# ------------------------------------------------------------------- tools --


def _service_area(arcpy: Any, inp: c.ServiceAreaInput) -> dict:
    with extension(arcpy, "Network"):
        made = arcpy.na.MakeServiceAreaAnalysisLayer(
            network_data_source=inp.network_dataset,
            layer_name="SA",
            travel_mode=inp.travel_mode,
            cutoffs=list(inp.cutoffs),
        )
        out = _solve(
            arcpy,
            made.getOutput(0),
            {"Facilities": inp.facilities},
            "Polygons",
            inp.out_features,
        )
    out["cutoffs"] = list(inp.cutoffs)
    return out


def _route_analysis(arcpy: Any, inp: c.RouteAnalysisInput) -> dict:
    with extension(arcpy, "Network"):
        made = arcpy.na.MakeRouteAnalysisLayer(
            network_data_source=inp.network_dataset,
            layer_name="Route",
            travel_mode=inp.travel_mode,
        )
        return _solve(
            arcpy,
            made.getOutput(0),
            {"Stops": inp.stops},
            "Routes",
            inp.out_features,
        )


def _od_cost_matrix(arcpy: Any, inp: c.OdCostMatrixInput) -> dict:
    with extension(arcpy, "Network"):
        made = arcpy.na.MakeODCostMatrixAnalysisLayer(
            network_data_source=inp.network_dataset,
            layer_name="OD",
            travel_mode=inp.travel_mode,
            cutoff=inp.cutoff,
        )
        return _solve(
            arcpy,
            made.getOutput(0),
            {"Origins": inp.origins, "Destinations": inp.destinations},
            "Lines",
            inp.out_features,
        )


def _closest_facility(arcpy: Any, inp: c.ClosestFacilityInput) -> dict:
    with extension(arcpy, "Network"):
        made = arcpy.na.MakeClosestFacilityAnalysisLayer(
            network_data_source=inp.network_dataset,
            layer_name="CF",
            travel_mode=inp.travel_mode,
            number_of_facilities_to_find=inp.facilities_to_find,
        )
        out = _solve(
            arcpy,
            made.getOutput(0),
            {"Facilities": inp.facilities, "Incidents": inp.incidents},
            "Routes",
            inp.out_features,
        )
    out["facilities_to_find"] = inp.facilities_to_find
    return out


# -------------------------------------------------------------- registrations

_CAT = Category.NETWORK

_SPECS = (
    (
        "service_area",
        (
            "Solve reachable service area polygons around facility points using "
            "ArcPy Network Analyst MakeServiceAreaAnalysisLayer. Use this to map "
            "accessibility around schools, hospitals, stations, depots, stores, "
            "or emergency facilities at one or more travel cutoffs. Requires a "
            "Network Analyst license; reads a network_dataset and facilities, then "
            "writes solved polygon features to out_features inside PathGuard roots."
        ),
        c.ServiceAreaInput,
        _service_area,
    ),
    (
        "route_analysis",
        (
            "Solve the best route through ordered stop points using ArcPy Network "
            "Analyst MakeRouteAnalysisLayer. Use this for A-to-B routing, multi-stop "
            "field visits, logistics paths, inspection sequences, or travel-time "
            "analysis over a configured network dataset. Requires a Network Analyst "
            "license; reads stops and writes solved route features to out_features."
        ),
        c.RouteAnalysisInput,
        _route_analysis,
    ),
    (
        "od_cost_matrix",
        (
            "Solve origin-destination travel cost lines using ArcPy Network Analyst "
            "MakeODCostMatrixAnalysisLayer. Use this to measure travel time or "
            "distance between demand points and destinations such as services, jobs, "
            "facilities, stores, or transit stops. Requires a Network Analyst license; "
            "supports travel_mode and optional cutoff, then writes OD line results "
            "to out_features inside PathGuard allowed roots."
        ),
        c.OdCostMatrixInput,
        _od_cost_matrix,
    ),
    (
        "closest_facility",
        (
            "Find nearest facility routes for incident points using ArcPy Network "
            "Analyst MakeClosestFacilityAnalysisLayer. Use this to match demand or "
            "incident locations to hospitals, stations, schools, depots, stores, or "
            "other candidate facilities by network travel cost. Requires a Network "
            "Analyst license; supports facilities_to_find and writes solved route "
            "features to out_features."
        ),
        c.ClosestFacilityInput,
        _closest_facility,
    ),
)

for _name, _desc, _model, _fn in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn))
