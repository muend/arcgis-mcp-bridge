"""Shared Esri extension licensing guard (Spatial, 3D, Network).

Extracted from raster_ops so every licensed vertical (raster, network,
spatial statistics) uses ONE checkout/checkin implementation (DRY).
``CheckInExtension`` runs in ``finally``: a geoprocessing crash can never
leave a licensed seat locked.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class ExtensionLicenseError(ValueError):
    """Required Esri extension license is not available on this machine."""


@contextmanager
def extension(arcpy: Any, name: str) -> Iterator[None]:
    """Checkout/checkin guard for licensed extensions.

    Args:
        arcpy: The injected arcpy module (Layer B only).
        name: Esri extension code — 'Spatial', '3D', 'Network', ...
    """
    if arcpy.CheckExtension(name) != "Available":
        raise ExtensionLicenseError(
            f"The {name} extension license is not available. "
            "Enable it in ArcGIS Pro (Settings > Licensing) and retry."
        )
    arcpy.CheckOutExtension(name)
    try:
        yield
    finally:
        arcpy.CheckInExtension(name)  # never leave the seat locked


__all__ = ["ExtensionLicenseError", "extension"]
