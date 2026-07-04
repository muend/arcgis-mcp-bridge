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
    """Shared base for tools that read a saved ArcGIS Pro project file."""

    aprx_path: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to the saved ArcGIS Pro .aprx project file. The path "
            "must be inside a configured PathGuard allowed root. Tools operate on "
            "the saved project file, not a live open ArcGIS Pro session."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"aprx_path": "read"}


class MapScopedInput(AprxInput):
    """Shared base for tools that target one map inside an ArcGIS Pro project."""

    map_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of the map inside the .aprx project. Use None to target the "
            "first map returned by ArcGIS Pro."
        ),
    )


class LayerScopedInput(MapScopedInput):
    """Shared base for tools that target one layer inside one map."""

    layer_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Layer name as shown in the ArcGIS Pro Contents pane for the selected "
            "map. The layer must exist in the resolved map."
        ),
    )


class AddLayerToMapInput(MapScopedInput):
    """Input contract for adding a dataset as a layer to a project map."""

    data_path: str = Field(
        ...,
        description=(
            "Absolute path to the feature class, table, raster, or supported GIS "
            "dataset to add as a map layer. The dataset must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after adding the layer. Use false "
            "for temporary in-memory inspection before another operation."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "data_path": "read",
    }


class RemoveLayerFromMapInput(LayerScopedInput):
    """Input contract for removing a layer from a map in a saved project."""

    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after removing the layer from the map."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. Removing a layer mutates the saved map structure in the "
            ".aprx project, although it does not delete the underlying dataset."
        ),
    )


class ListMapsInput(AprxInput):
    """List maps available in a saved ArcGIS Pro project without modifying it."""


class ListLayersInMapInput(MapScopedInput):
    """List layers in a selected map without modifying the ArcGIS Pro project."""


class SetLayerVisibilityInput(LayerScopedInput):
    """Input contract for showing or hiding a layer in a selected map."""

    visible: bool = Field(
        ...,
        description=(
            "True to show the layer in the map; false to hide it. This changes "
            "layer visibility in the .aprx project when save=true."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after changing layer visibility."
        ),
    )


class MoveLayerOrderInput(LayerScopedInput):
    """Input contract for moving a layer before or after another layer."""

    reference_layer: str = Field(
        ...,
        min_length=1,
        description=(
            "Name of the existing reference layer used as the placement anchor "
            "for the moved layer."
        ),
    )
    position: Literal["BEFORE", "AFTER"] = Field(
        default="BEFORE",
        description=(
            "Where to place layer_name relative to reference_layer in the map "
            "drawing order: BEFORE or AFTER."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after updating layer draw order."
        ),
    )


class RenameLayerInput(LayerScopedInput):
    """Input contract for renaming a layer in a selected map."""

    new_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "New layer name to display in the ArcGIS Pro Contents pane. This "
            "renames the map layer only and does not rename the underlying dataset."
        ),
    )
    save: bool = Field(
        default=True,
        description="When true, save the .aprx project after renaming the layer.",
    )


class ZoomToLayerInput(LayerScopedInput):
    """Input contract for setting a map view or frame extent to a layer."""

    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after updating the view or camera "
            "extent to the selected layer."
        ),
    )


class SetLayerSymbologyInput(LayerScopedInput):
    """Input contract for applying symbology from a .lyrx layer file."""

    lyrx_path: str = Field(
        ...,
        description=(
            "Absolute path to the source .lyrx layer file whose symbology will be "
            "applied to the target layer. The file must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after applying the layer symbology."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "lyrx_path": "read",
    }


class SaveProjectInput(AprxInput):
    """Input contract for explicitly saving a saved ArcGIS Pro project file."""
