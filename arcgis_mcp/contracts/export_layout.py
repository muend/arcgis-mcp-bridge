"""Input models — Category 6: Export & Layout (catalog #75-83)."""

from __future__ import annotations

from typing import ClassVar, Literal, Optional

from pydantic import Field

from .base import PathRole
from .map_mgmt import AprxInput


class LayoutScopedInput(AprxInput):
    """Shared base: tools that target one layout inside the project."""

    layout_name: Optional[str] = Field(
        default=None, description="Layout name; None targets the first layout."
    )


class MapFrameScopedInput(LayoutScopedInput):
    """Shared base: tools that target one map frame inside one layout."""

    map_frame: Optional[str] = Field(
        default=None, description="Map frame name; None targets the first frame."
    )
    save: bool = True


class ListLayoutsInput(AprxInput):
    pass


class ExportLayoutPdfInput(LayoutScopedInput):
    out_pdf: str = Field(..., description="Output .pdf path.")
    resolution: int = Field(default=300, ge=72, le=1200, description="DPI.")
    image_quality: Literal["BEST", "BETTER", "NORMAL", "FASTER", "FASTEST"] = "BEST"
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_pdf": "write",
    }


class ExportLayoutPngInput(LayoutScopedInput):
    out_png: str = Field(..., description="Output .png path.")
    resolution: int = Field(default=300, ge=72, le=1200, description="DPI.")
    transparent_background: bool = False
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_png": "write",
    }


class ExportMapAsImageInput(AprxInput):
    """Export a map view directly (no layout) via its default view."""

    map_name: Optional[str] = Field(
        default=None, description="Map name; None targets the first map."
    )
    out_png: str = Field(..., description="Output .png path.")
    width: int = Field(default=1920, ge=64, le=10000, description="Pixels.")
    height: int = Field(default=1080, ge=64, le=10000, description="Pixels.")
    resolution: int = Field(default=96, ge=72, le=600, description="DPI.")
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "aprx_path": "read",
        "out_png": "write",
    }


class SetMapScaleInput(MapFrameScopedInput):
    scale: float = Field(..., gt=0, description="Denominator, e.g. 1000 for 1:1000.")


class SetMapExtentFromLayerInput(MapFrameScopedInput):
    layer_name: str = Field(..., min_length=1)


class UpdateTextElementInput(LayoutScopedInput):
    element_name: str = Field(..., min_length=1, description="Text element name.")
    new_text: str = Field(..., min_length=0, max_length=10000)
    save: bool = True


class UpdateLegendInput(LayoutScopedInput):
    legend_name: Optional[str] = Field(
        default=None, description="Legend element name; None targets the first."
    )
    layer_name: str = Field(..., min_length=1)
    action: Literal["ADD", "REMOVE"] = "ADD"
    map_frame: Optional[str] = None
    save: bool = True


class SetLayoutSizeInput(LayoutScopedInput):
    page_width: float = Field(..., gt=0, description="In the layout's page units.")
    page_height: float = Field(..., gt=0)
    save: bool = True


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
