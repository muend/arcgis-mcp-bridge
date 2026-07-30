"""Input models — Vision Analytics: Sketch-to-GIS pipeline.

One tool, one strict schema. The model carries everything the worker needs
to run the four pipeline phases (registration -> segmentation ->
georeferencing -> GDB commit) without consulting any out-of-band state.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, model_validator

from .base import PathRole, ToolInput

InkColor = Literal["Red", "Black", "Blue"]
SketchFeatureType = Literal["Polygon", "Polyline"]


class ExtractSketchSchema(ToolInput):
    """Contract for ``extract_sketch_to_gis``.

    Path discipline (two reads, one write): both images must exist inside
    an allowed root; the target feature class is a write surface. Because
    the target is GDB-internal, PathGuard validates its container and
    dataset-name legality; existence/schema compatibility is enforced by
    the worker against the live geodatabase (only arcpy can know it).
    """

    sketch_image: str = Field(
        ...,
        min_length=1,
        description="Smartphone photo of the hand-drawn sketch (jpg/png).",
    )
    base_layout: str = Field(
        ...,
        min_length=1,
        description="Clean exported digital map layout the sketch was drawn on.",
    )
    target_feature_class: str = Field(
        ...,
        min_length=1,
        description="Existing GDB feature class to append extracted features to.",
    )

    # Real-world envelope of the layout image (same CRS as the target FC).
    xmin: float = Field(..., description="West edge of the layout extent.")
    ymin: float = Field(..., description="South edge of the layout extent.")
    xmax: float = Field(..., description="East edge of the layout extent.")
    ymax: float = Field(..., description="North edge of the layout extent.")

    feature_type: SketchFeatureType = "Polygon"
    ink_color: InkColor = "Red"

    # Tunables with conservative defaults (documented in the tool surface).
    min_contour_area_px: float = Field(
        default=80.0,
        ge=0.0,
        description="Contours smaller than this many pixels^2 are noise.",
    )
    simplify_epsilon_px: float = Field(
        default=2.0,
        ge=0.0,
        description="Douglas-Peucker tolerance in pixels (0 = no simplify).",
    )
    confirm: bool = Field(
        default=False,
        description="Must be true: this tool APPENDS rows into the target FC.",
    )

    path_fields: ClassVar[dict[str, PathRole]] = {
        "sketch_image": "read",
        "base_layout": "read",
        "target_feature_class": "write",
    }

    @model_validator(mode="after")
    def _envelope_sane(self) -> "ExtractSketchSchema":
        """A degenerate or inverted envelope would map every pixel to NaN/garbage."""
        if not (self.xmax > self.xmin and self.ymax > self.ymin):
            raise ValueError(
                "Envelope must satisfy xmax > xmin and ymax > ymin "
                f"(got x: {self.xmin}..{self.xmax}, y: {self.ymin}..{self.ymax})."
            )
        return self


__all__ = ["ExtractSketchSchema", "InkColor", "SketchFeatureType"]
