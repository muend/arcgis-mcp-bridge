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
        "Add a dataset to a map inside an .aprx project (arcpy.mp addDataFromPath). "
        "Operates on the saved project file, not a live Pro session.",
        c.AddLayerToMapInput,
        _add_layer_to_map,
    )
)
register(
    ToolSpec(
        "remove_layer_from_map",
        _CAT,
        "Remove a layer from a map (map.removeLayer). Requires confirm=true.",
        c.RemoveLayerFromMapInput,
        _remove_layer_from_map,
        destructive=True,
    )
)
register(
    ToolSpec(
        "list_maps",
        _CAT,
        "List all map names inside an .aprx project (aprx.listMaps).",
        c.ListMapsInput,
        _list_maps,
    )
)
register(
    ToolSpec(
        "list_layers_in_map",
        _CAT,
        "List layers of one map with visibility, group flag and data source.",
        c.ListLayersInMapInput,
        _list_layers_in_map,
    )
)
register(
    ToolSpec(
        "set_layer_visibility",
        _CAT,
        "Show or hide a layer (lyr.visible).",
        c.SetLayerVisibilityInput,
        _set_layer_visibility,
    )
)
register(
    ToolSpec(
        "move_layer_order",
        _CAT,
        "Change draw order: move a layer BEFORE/AFTER a reference layer "
        "(map.moveLayer).",
        c.MoveLayerOrderInput,
        _move_layer_order,
    )
)
register(
    ToolSpec(
        "rename_layer",
        _CAT,
        "Rename a layer as shown in the Contents pane (lyr.name).",
        c.RenameLayerInput,
        _rename_layer,
    )
)
register(
    ToolSpec(
        "zoom_to_layer",
        _CAT,
        "Set the map's default camera to a layer's extent.",
        c.ZoomToLayerInput,
        _zoom_to_layer,
    )
)
register(
    ToolSpec(
        "set_layer_symbology",
        _CAT,
        "Apply symbology from a .lyrx file (ApplySymbologyFromLayer).",
        c.SetLayerSymbologyInput,
        _set_layer_symbology,
    )
)
register(
    ToolSpec(
        "save_project",
        _CAT,
        "Save the .aprx project file (aprx.save).",
        c.SaveProjectInput,
        _save_project,
    )
)
