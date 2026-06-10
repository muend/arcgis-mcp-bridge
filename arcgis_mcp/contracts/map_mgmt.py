"""Input models — Category 1: Map / Layer Management (catalog #1-10).

All tools operate on a SAVED .aprx project file via ``arcpy.mp``. They
cannot reach into a live, open ArcGIS Pro session (Esri exposes no IPC for
that); changes become visible after the project is (re)opened. Models that
mutate the project expose ``save: bool = True`` so a dry-run inspection
path exists.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Optional

from pydantic import Field

from .base import PathRole, ToolInput


class AprxInput(ToolInput):
    """Shared base: every map-management tool starts from an .aprx path."""

    aprx_path: str = Field(..., min_length=1, description="Absolute .aprx path.")
    path_fields: ClassVar[dict[str, PathRole]] = {"aprx_path": "read"}


class MapScopedInput(AprxInput):
    """Shared base: tools that target one map inside the project."""

    map_name: Optional[str] = Field(
        default=None, description="Map name; None targets the first map."
    )


class LayerScopedInput(MapScopedInput):
    """Shared base: tools that target one layer inside one map."""

    layer_name: str = Field(..., min_length=1, description="Layer (Contents) name.")


class AddLayerToMapInput(MapScopedInput):
    data_path: str = Field(..., description="Dataset to add (FC/raster path).")
    save: bool = Field(default=True, description="Persist the .aprx afterwards.")
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "data_path": "read",
    }


class RemoveLayerFromMapInput(LayerScopedInput):
    save: bool = True
    confirm: bool = Field(
        default=False, description="Must be true: removing a layer is destructive."
    )


class ListMapsInput(AprxInput):
    pass


class ListLayersInMapInput(MapScopedInput):
    pass


class SetLayerVisibilityInput(LayerScopedInput):
    visible: bool = Field(..., description="True to show, False to hide.")
    save: bool = True


class MoveLayerOrderInput(LayerScopedInput):
    reference_layer: str = Field(..., min_length=1)
    position: Literal["BEFORE", "AFTER"] = "BEFORE"
    save: bool = True


class RenameLayerInput(LayerScopedInput):
    new_name: str = Field(..., min_length=1, max_length=255)
    save: bool = True


class ZoomToLayerInput(LayerScopedInput):
    save: bool = True


class SetLayerSymbologyInput(LayerScopedInput):
    lyrx_path: str = Field(..., description="Source .lyrx symbology file.")
    save: bool = True
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "lyrx_path": "read",
    }


class SaveProjectInput(AprxInput):
    pass
