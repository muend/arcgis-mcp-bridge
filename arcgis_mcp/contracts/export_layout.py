"""Input models — Category 6: Export & Layout (catalog #75-83)."""

from __future__ import annotations

from typing import ClassVar, Literal, Optional

from pydantic import Field

from .base import PathRole
from .map_mgmt import AprxInput


class LayoutScopedInput(AprxInput):
    """Shared base for tools that target one layout inside an ArcGIS Pro project."""

    layout_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of the layout inside the .aprx project. Use None to target the "
            "first layout returned by ArcGIS Pro."
        ),
    )


class MapFrameScopedInput(LayoutScopedInput):
    """Shared base for tools that target one map frame inside one layout."""

    map_frame: Optional[str] = Field(
        default=None,
        description=(
            "Name of the map frame inside the selected layout. Use None to target "
            "the first map frame in that layout."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after applying the layout or map "
            "frame change. Use false for temporary changes before export."
        ),
    )


class ListLayoutsInput(AprxInput):
    """List layouts available in an ArcGIS Pro project without modifying it."""


class ExportLayoutPdfInput(LayoutScopedInput):
    """Export a selected layout from an ArcGIS Pro project to a PDF file."""

    out_pdf: str = Field(
        ...,
        description=(
            "Absolute output .pdf path to create. The path must be inside a "
            "configured PathGuard allowed root; existing files require overwrite=true."
        ),
    )
    resolution: int = Field(
        default=300,
        ge=72,
        le=1200,
        description=(
            "Export resolution in DPI. Use 300 for print-quality output, lower "
            "values for faster preview exports, and higher values for detailed maps."
        ),
    )
    image_quality: Literal["BEST", "BETTER", "NORMAL", "FASTER", "FASTEST"] = Field(
        default="BEST",
        description=(
            "PDF image quality setting passed to ArcGIS Pro layout export. BEST "
            "prioritizes quality; FASTER and FASTEST prioritize speed and smaller files."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing PDF file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_pdf": "write",
    }


class ExportLayoutPngInput(LayoutScopedInput):
    """Export a selected layout from an ArcGIS Pro project to a PNG image."""

    out_png: str = Field(
        ...,
        description=(
            "Absolute output .png path to create. The path must be inside a "
            "configured PathGuard allowed root; existing files require overwrite=true."
        ),
    )
    resolution: int = Field(
        default=300,
        ge=72,
        le=1200,
        description=(
            "Export resolution in DPI. Use 300 for print-quality layout images "
            "and lower values for quick previews."
        ),
    )
    transparent_background: bool = Field(
        default=False,
        description=(
            "When true, export the PNG with a transparent background where the "
            "layout supports transparency."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing PNG file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_png": "write",
    }


class ExportMapAsImageInput(AprxInput):
    """Export a map view directly as a PNG image without using a layout."""

    map_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of the map inside the .aprx project. Use None to target the "
            "first map returned by ArcGIS Pro."
        ),
    )
    out_png: str = Field(
        ...,
        description=(
            "Absolute output .png path to create. The path must be inside a "
            "configured PathGuard allowed root; existing files require overwrite=true."
        ),
    )
    width: int = Field(
        default=1920,
        ge=64,
        le=10000,
        description="Output image width in pixels.",
    )
    height: int = Field(
        default=1080,
        ge=64,
        le=10000,
        description="Output image height in pixels.",
    )
    resolution: int = Field(
        default=96,
        ge=72,
        le=600,
        description=(
            "Export resolution in DPI. Use 96 for screen-oriented exports and "
            "higher values for sharper map images."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing PNG file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_png": "write",
    }


class SetMapScaleInput(MapFrameScopedInput):
    """Set the map scale denominator for a selected map frame."""

    scale: float = Field(
        ...,
        gt=0,
        description=(
            "Scale denominator for the target map frame, for example 1000 for "
            "1:1000 or 50000 for 1:50,000."
        ),
    )


class SetMapExtentFromLayerInput(MapFrameScopedInput):
    """Set a map frame extent to match the extent of a named layer."""

    layer_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Name of the layer whose extent will be used to update the selected "
            "map frame. The layer must exist in the map connected to that frame."
        ),
    )


class UpdateTextElementInput(LayoutScopedInput):
    """Update the text content of a named layout text element."""

    element_name: str = Field(
        ...,
        min_length=1,
        description="Name of the text element to update in the selected layout.",
    )
    new_text: str = Field(
        ...,
        min_length=0,
        max_length=10000,
        description=(
            "New text content to write into the layout element. Use an empty "
            "string to clear the element."
        ),
    )
    save: bool = Field(
        default=True,
        description=(
            "When true, save the .aprx project after updating the text element."
        ),
    )


class UpdateLegendInput(LayoutScopedInput):
    """Add or remove a layer entry in a selected layout legend."""

    legend_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of the legend element to update. Use None to target the first "
            "legend in the selected layout."
        ),
    )
    layer_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Name of the layer to add to or remove from the legend. The layer "
            "must exist in the target map frame."
        ),
    )
    action: Literal["ADD", "REMOVE"] = Field(
        default="ADD",
        description="Legend operation to perform: ADD the layer or REMOVE it.",
    )
    map_frame: Optional[str] = Field(
        default=None,
        description=(
            "Optional map frame name used to resolve the layer. Use None to target "
            "the first map frame in the selected layout."
        ),
    )
    save: bool = Field(
        default=True,
        description="When true, save the .aprx project after updating the legend.",
    )


class SetLayoutSizeInput(LayoutScopedInput):
    """Set the physical page size of a selected layout."""

    page_width: float = Field(
        ...,
        gt=0,
        description="New layout page width in the layout's current page units.",
    )
    page_height: float = Field(
        ...,
        gt=0,
        description="New layout page height in the layout's current page units.",
    )
    save: bool = Field(
        default=True,
        description="When true, save the .aprx project after resizing the layout.",
    )


__all__ = [
    "ExportLayoutPdfInput",
    "ExportLayoutPngInput",
    "ExportMapAsImageInput",
    "LayoutScopedInput",
    "ListLayoutsInput",
    "MapFrameScopedInput",
    "SetLayoutSizeInput",
    "SetMapExtentFromLayerInput",
    "SetMapScaleInput",
    "UpdateLegendInput",
    "UpdateTextElementInput",
]
