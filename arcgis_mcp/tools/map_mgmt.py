"""ToolSpecs + worker implementations — Category 1: Map / Layer Management.

Worker functions receive ``arcpy`` as a parameter (never imported here) and
a pre-guarded, fully resolved input model. Case-sensitivity guard: all
arcpy.mp attribute names below match Esri signatures exactly
(``listMaps``, ``addDataFromPath``, ``moveLayer``, ``ApplySymbologyFromLayer``).
"""

from __future__ import annotations

from typing import Any

from ..contracts import map_mgmt as c
from ..registry import Category, ToolSpec, register

# ---------------------------------------------------------------- helpers --


class MapTargetError(LookupError):
    """Map or layer named in the request does not exist in the project."""


def _open_map(arcpy: Any, aprx_path: str, map_name: str | None) -> tuple[Any, Any]:
    """Open project and resolve the target map (None = first map)."""
    aprx = arcpy.mp.ArcGISProject(aprx_path)
    maps = aprx.listMaps(map_name) if map_name else aprx.listMaps()
    if not maps:
        raise MapTargetError(f"No map matching {map_name!r} in {aprx_path}")
    return aprx, maps[0]


def _find_layer(m: Any, layer_name: str) -> Any:
    layers = m.listLayers(layer_name)
    if not layers:
        raise MapTargetError(f"Layer {layer_name!r} not found in map {m.name!r}")
    return layers[0]


def _finish(aprx: Any, save: bool, **extra: Any) -> dict[str, Any]:
    if save:
        aprx.save()
    return {"saved": save, **extra}


# ------------------------------------------------------------------- tools --


def _add_layer_to_map(arcpy: Any, inp: c.AddLayerToMapInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    lyr = m.addDataFromPath(inp.data_path)
    return _finish(aprx, inp.save, map=m.name, layer_added=lyr.name)


def _remove_layer_from_map(
    arcpy: Any, inp: c.RemoveLayerFromMapInput
) -> dict[str, Any]:
    if not inp.confirm:
        raise PermissionError(
            "remove_layer_from_map is destructive: set confirm=true to proceed."
        )
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    m.removeLayer(_find_layer(m, inp.layer_name))
    return _finish(aprx, inp.save, map=m.name, layer_removed=inp.layer_name)


def _list_maps(arcpy: Any, inp: c.ListMapsInput) -> dict[str, Any]:
    aprx = arcpy.mp.ArcGISProject(inp.aprx_path)
    return {"maps": [m.name for m in aprx.listMaps()]}


def _list_layers_in_map(arcpy: Any, inp: c.ListLayersInMapInput) -> dict[str, Any]:
    _, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    return {
        "map": m.name,
        "layers": [
            {
                "name": lyr.name,
                "visible": bool(getattr(lyr, "visible", True)),
                "is_group": bool(lyr.isGroupLayer),
                "source": lyr.dataSource if lyr.supports("DATASOURCE") else None,
            }
            for lyr in m.listLayers()
        ],
    }


def _set_layer_visibility(arcpy: Any, inp: c.SetLayerVisibilityInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    lyr = _find_layer(m, inp.layer_name)
    lyr.visible = inp.visible
    return _finish(aprx, inp.save, layer=lyr.name, visible=inp.visible)


def _move_layer_order(arcpy: Any, inp: c.MoveLayerOrderInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    m.moveLayer(
        _find_layer(m, inp.reference_layer),
        _find_layer(m, inp.layer_name),
        inp.position,
    )
    return _finish(
        aprx,
        inp.save,
        moved=inp.layer_name,
        relative_to=inp.reference_layer,
        position=inp.position,
    )


def _rename_layer(arcpy: Any, inp: c.RenameLayerInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    lyr = _find_layer(m, inp.layer_name)
    old = lyr.name
    lyr.name = inp.new_name
    return _finish(aprx, inp.save, renamed_from=old, renamed_to=inp.new_name)


def _zoom_to_layer(arcpy: Any, inp: c.ZoomToLayerInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    lyr = _find_layer(m, inp.layer_name)
    extent = arcpy.Describe(lyr.dataSource).extent
    cam = m.defaultCamera
    cam.setExtent(extent)
    m.defaultCamera = cam
    return _finish(
        aprx,
        inp.save,
        layer=lyr.name,
        extent={
            "xmin": extent.XMin,
            "ymin": extent.YMin,
            "xmax": extent.XMax,
            "ymax": extent.YMax,
        },
    )


def _set_layer_symbology(arcpy: Any, inp: c.SetLayerSymbologyInput) -> dict[str, Any]:
    aprx, m = _open_map(arcpy, inp.aprx_path, inp.map_name)
    lyr = _find_layer(m, inp.layer_name)
    arcpy.management.ApplySymbologyFromLayer(lyr, inp.lyrx_path)
    return _finish(aprx, inp.save, layer=lyr.name, symbology_source=inp.lyrx_path)


def _save_project(arcpy: Any, inp: c.SaveProjectInput) -> dict[str, Any]:
    aprx = arcpy.mp.ArcGISProject(inp.aprx_path)
    aprx.save()
    return {"saved": True, "aprx": inp.aprx_path}


# -------------------------------------------------------------- registrations

_CAT: Category = Category.MAP_MGMT

register(
    ToolSpec(
        "add_layer_to_map",
        _CAT,
        (
            "Add a dataset to a map inside a saved ArcGIS Pro .aprx project using "
            "arcpy.mp addDataFromPath. Use this to load feature classes, rasters, "
            "tables, or other supported GIS datasets into an existing project map "
            "before styling, exporting, or layout automation. Operates on the saved "
            ".aprx file, not a live ArcGIS Pro session, and saves the project when "
            "save=true."
        ),
        c.AddLayerToMapInput,
        _add_layer_to_map,
    )
)
register(
    ToolSpec(
        "remove_layer_from_map",
        _CAT,
        (
            "Remove a named layer from a map inside a saved ArcGIS Pro .aprx project "
            "using map.removeLayer. Use this for controlled map cleanup before "
            "export, packaging, or automated project updates. This changes the map "
            "contents but does not delete the underlying dataset; confirm=true is "
            "required because the project structure is mutated."
        ),
        c.RemoveLayerFromMapInput,
        _remove_layer_from_map,
        destructive=True,
    )
)
register(
    ToolSpec(
        "list_maps",
        _CAT,
        (
            "List map names inside a saved ArcGIS Pro .aprx project using "
            "aprx.listMaps. Use this discovery tool before map-scoped operations "
            "when the target map name is unknown or when validating project contents. "
            "Reads the project file only and does not modify or save it."
        ),
        c.ListMapsInput,
        _list_maps,
    )
)
register(
    ToolSpec(
        "list_layers_in_map",
        _CAT,
        (
            "List layers in a selected map with visibility, group-layer status, and "
            "data source information where available. Use this to discover exact "
            "Contents-pane layer names before visibility, ordering, symbology, rename, "
            "or zoom operations. Reads the saved .aprx project only and does not "
            "modify layer state."
        ),
        c.ListLayersInMapInput,
        _list_layers_in_map,
    )
)
register(
    ToolSpec(
        "set_layer_visibility",
        _CAT,
        (
            "Show or hide a named layer in a selected ArcGIS Pro map by updating "
            "lyr.visible. Use this before layout or map export to control which "
            "datasets appear in the final map. This mutates layer visibility in the "
            "saved .aprx project when save=true but does not alter the source dataset."
        ),
        c.SetLayerVisibilityInput,
        _set_layer_visibility,
    )
)
register(
    ToolSpec(
        "move_layer_order",
        _CAT,
        (
            "Move a named layer before or after a reference layer in the map drawing "
            "order using map.moveLayer. Use this to control cartographic stacking, "
            "for example placing boundaries above imagery or analysis results above "
            "base layers. This updates the saved .aprx project when save=true."
        ),
        c.MoveLayerOrderInput,
        _move_layer_order,
    )
)
register(
    ToolSpec(
        "rename_layer",
        _CAT,
        (
            "Rename a layer as displayed in the ArcGIS Pro Contents pane by updating "
            "lyr.name. Use this to make automated map outputs clearer before export, "
            "handoff, or presentation. This renames the map layer only, does not "
            "rename the underlying dataset, and saves the .aprx project when save=true."
        ),
        c.RenameLayerInput,
        _rename_layer,
    )
)
register(
    ToolSpec(
        "zoom_to_layer",
        _CAT,
        (
            "Set the selected map's default camera extent to match a named layer's "
            "data extent. Use this before exporting a map view or reopening the "
            ".aprx so the map focuses on a study area, boundary, analysis result, "
            "or target dataset. Reads the layer data source extent, updates the map "
            "defaultCamera, and saves the project when save=true."
        ),
        c.ZoomToLayerInput,
        _zoom_to_layer,
    )
)
register(
    ToolSpec(
        "set_layer_symbology",
        _CAT,
        (
            "Apply cartographic symbology from a source .lyrx layer file to a named "
            "target layer using ArcPy ApplySymbologyFromLayer. Use this to standardize "
            "colors, classifications, labels, renderers, and map styling before export "
            "or project delivery. Reads the target layer and .lyrx file inside "
            "PathGuard allowed roots and saves the .aprx project when save=true."
        ),
        c.SetLayerSymbologyInput,
        _set_layer_symbology,
    )
)
register(
    ToolSpec(
        "save_project",
        _CAT,
        (
            "Explicitly save a saved ArcGIS Pro .aprx project using aprx.save. Use "
            "this after a sequence of map, layer, layout, visibility, camera, or "
            "symbology changes when the project must be persisted before export or "
            "handoff. Operates on the saved .aprx file and returns the saved project "
            "path."
        ),
        c.SaveProjectInput,
        _save_project,
    )
)
