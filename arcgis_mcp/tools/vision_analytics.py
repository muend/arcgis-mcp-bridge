"""ToolSpec + worker implementation — Sketch-to-GIS computer vision pipeline.

Pipeline (executed entirely in Layer B):

    A. Registration  — ORB feature matching + RANSAC homography aligns the
                       smartphone photo onto the clean digital layout,
                       removing perspective distortion (cv2.findHomography
                       -> cv2.warpPerspective).
    B. Segmentation  — HSV color-space thresholding isolates hand-drawn ink
                       (Red / Black / Blue) from the printed background,
                       followed by morphological open/close denoising.
    C. Georeference  — cv2.findContours extracts pixel rings; each vertex
                       maps to world coordinates via the layout envelope:
                           X = Xmin + (px_x / W) * (Xmax - Xmin)
                           Y = Ymax - (px_y / H) * (Ymax - Ymin)
    D. GDB commit    — arcpy.da.InsertCursor appends Polygon/Polyline
                       geometries (built in the target FC's spatial
                       reference) into the whitelisted feature class.

Import discipline: cv2/numpy are imported INSIDE the worker function via
``_lazy_cv()`` — this module is also imported by Layer A (registry
population), which must never pay OpenCV's memory footprint. The CV
helpers are module-level pure functions taking (cv2, np) as parameters,
so they are unit-testable without arcpy.

Failure philosophy: unrecoverable phases (unreadable image, registration
below the RANSAC inlier floor, geometry-type mismatch) raise ValueError ->
structured ``validation`` frames. Recoverable conditions (zero contours,
skipped degenerate rings, non-finite vertices) DO NOT fail the job — they
are reported in a ``warnings`` array alongside the partial result.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from ..contracts.vision_analytics import ExtractSketchSchema
from ..registry import Category, ToolSpec, register

LOG: Final[logging.Logger] = logging.getLogger("arcgis_mcp.tools.vision")

#: Minimum RANSAC inliers below which a homography is considered garbage.
_MIN_INLIERS: Final[int] = 12
#: Minimum ORB matches required before even attempting RANSAC.
_MIN_MATCHES: Final[int] = 4
_ORB_FEATURES: Final[int] = 4000
_RANSAC_REPROJ_PX: Final[float] = 5.0

#: HSV ink ranges as (lower, upper) bound pairs. Red wraps the hue circle,
#: so it needs two bands. S/V floors reject the printed background, which
#: is typically desaturated relative to fresh ink.
_INK_HSV_RANGES: Final[
    dict[str, list[tuple[tuple[int, int, int], tuple[int, int, int]]]]
] = {
    "Red": [((0, 70, 50), (10, 255, 255)), ((170, 70, 50), (180, 255, 255))],
    "Blue": [((100, 70, 50), (130, 255, 255))],
    "Black": [((0, 0, 0), (180, 255, 60))],  # low V = dark ink, any hue
}


def _lazy_cv() -> tuple[Any, Any]:
    """Import cv2/numpy inside Layer B with an actionable failure message."""
    try:
        import cv2  # noqa: PLC0415 — deferred by design
        import numpy as np  # noqa: PLC0415
    except ImportError as exc:
        raise ValueError(
            "OpenCV/NumPy are not installed in the worker environment. "
            "Install them into the interpreter referenced by "
            "ARCPY_PYTHON_PATH:  pip install opencv-python-headless numpy"
        ) from exc
    return cv2, np


# --------------------------------------------------------------------------- #
# Phase A — registration
# --------------------------------------------------------------------------- #


def register_sketch(
    cv2: Any, np: Any, sketch: Any, base: Any
) -> tuple[Any, dict[str, Any]]:
    """Align the photo onto the layout. Returns (warped_image, diagnostics).

    ORB + BFMatcher(Hamming, cross-check) + RANSAC. Crosshair-GCP detection
    is intentionally NOT a separate code path: printed crosshairs are
    themselves high-contrast corner features, so ORB locks onto them
    naturally — one estimator, fewer branches (DRY at algorithm level).
    """
    gray_s = cv2.cvtColor(sketch, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=_ORB_FEATURES)
    kp_s, des_s = orb.detectAndCompute(gray_s, None)
    kp_b, des_b = orb.detectAndCompute(gray_b, None)
    if des_s is None or des_b is None or len(kp_s) < _MIN_MATCHES:
        raise ValueError(
            "Registration failed: not enough detectable features. Ensure the "
            "photo is sharp and the printed layout has visible detail or "
            "corner crosshair anchors."
        )

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(matcher.match(des_s, des_b), key=lambda m: m.distance)
    if len(matches) < _MIN_MATCHES:
        raise ValueError(
            f"Registration failed: only {len(matches)} feature matches "
            f"(need >= {_MIN_MATCHES})."
        )

    src_pts = np.float32([kp_s[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_b[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, _RANSAC_REPROJ_PX)

    inliers = int(mask.sum()) if mask is not None else 0
    if H is None or inliers < _MIN_INLIERS:
        raise ValueError(
            f"Registration failed: homography rejected ({inliers} RANSAC "
            f"inliers, floor is {_MIN_INLIERS}). Re-shoot the photo flatter, "
            "with all four layout corners in frame."
        )

    h, w = base.shape[:2]
    warped = cv2.warpPerspective(sketch, H, (w, h))
    return warped, {
        "method": "ORB+RANSAC",
        "matches": len(matches),
        "ransac_inliers": inliers,
    }


# --------------------------------------------------------------------------- #
# Phase B — segmentation
# --------------------------------------------------------------------------- #


def build_ink_mask(cv2: Any, np: Any, image_bgr: Any, ink_color: str) -> Any:
    """Binary mask of the requested ink color via HSV thresholding."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in _INK_HSV_RANGES[ink_color]:
        mask |= cv2.inRange(hsv, np.array(lower), np.array(upper))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # despeckle
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # bridge pen gaps
    return mask


# --------------------------------------------------------------------------- #
# Phase C — pixel -> world transform
# --------------------------------------------------------------------------- #


def contours_to_world(
    cv2: Any,
    np: Any,
    mask: Any,
    envelope: tuple[float, float, float, float],
    *,
    min_area_px: float,
    epsilon_px: float,
    closed: bool,
) -> tuple[list[list[tuple[float, float]]], dict[str, int]]:
    """Vectorize the mask and map every vertex into world coordinates.

    Returns (rings, stats) where rings are lists of finite (x, y) tuples.
    Degenerate or non-finite geometry is counted, never raised.
    """
    import math  # noqa: PLC0415 — stdlib, trivial

    xmin, ymin, xmax, ymax = envelope
    h, w = mask.shape[:2]
    sx, sy = (xmax - xmin) / float(w), (ymax - ymin) / float(h)
    min_vertices = 3 if closed else 2

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stats = {
        "found": len(contours),
        "kept": 0,
        "skipped_small": 0,
        "skipped_degenerate": 0,
        "dropped_nonfinite_vertices": 0,
    }
    rings: list[list[tuple[float, float]]] = []

    for cnt in contours:
        if cv2.contourArea(cnt) < min_area_px:
            stats["skipped_small"] += 1
            continue
        if epsilon_px > 0:
            cnt = cv2.approxPolyDP(cnt, epsilon_px, closed)

        ring: list[tuple[float, float]] = []
        for px, py in cnt.reshape(-1, 2):
            wx = xmin + (float(px) / w) * (xmax - xmin)
            wy = ymax - (float(py) / h) * (ymax - ymin)
            if not (math.isfinite(wx) and math.isfinite(wy)):
                stats["dropped_nonfinite_vertices"] += 1
                continue
            ring.append((wx, wy))

        if len(ring) < min_vertices:
            stats["skipped_degenerate"] += 1
            continue
        rings.append(ring)
        stats["kept"] += 1

    LOG.debug("vectorize: %s (px->world scale %.6f x %.6f)", stats, sx, sy)
    return rings, stats


# --------------------------------------------------------------------------- #
# Phase D — GDB commit + orchestration (worker entrypoint)
# --------------------------------------------------------------------------- #


def _extract_sketch_to_gis(arcpy: Any, inp: ExtractSketchSchema) -> dict[str, Any]:
    """Full pipeline. Receives guarded paths; appends rows into the target FC."""
    cv2, np = _lazy_cv()
    warnings: list[str] = []

    # --- target schema preflight (cheapest arcpy check first) -------------
    desc = arcpy.Describe(inp.target_feature_class)
    if str(desc.shapeType) != inp.feature_type:
        raise ValueError(
            f"Geometry-type mismatch: target FC is {desc.shapeType}, request "
            f"says {inp.feature_type}. Refusing to insert incompatible rows."
        )
    sr = desc.spatialReference

    # --- A. load + register -----------------------------------------------
    sketch = cv2.imread(inp.sketch_image, cv2.IMREAD_COLOR)
    base = cv2.imread(inp.base_layout, cv2.IMREAD_COLOR)
    if sketch is None:
        raise ValueError(f"Could not decode sketch image: {inp.sketch_image}")
    if base is None:
        raise ValueError(f"Could not decode base layout: {inp.base_layout}")

    aligned, reg_info = register_sketch(cv2, np, sketch, base)

    # --- B. ink segmentation ----------------------------------------------
    mask = build_ink_mask(cv2, np, aligned, inp.ink_color)
    if int(mask.sum()) == 0:
        return {
            "features_written": 0,
            "registration": reg_info,
            "warnings": [
                f"No {inp.ink_color} ink detected after registration. "
                "Check ink_color, pen saturation, or photo lighting."
            ],
        }

    # --- C. vectorize + georeference ---------------------------------------
    rings, stats = contours_to_world(
        cv2,
        np,
        mask,
        (inp.xmin, inp.ymin, inp.xmax, inp.ymax),
        min_area_px=inp.min_contour_area_px,
        epsilon_px=inp.simplify_epsilon_px,
        closed=(inp.feature_type == "Polygon"),
    )
    if stats["skipped_small"]:
        warnings.append(
            f"{stats['skipped_small']} contour(s) below "
            f"min_contour_area_px={inp.min_contour_area_px} ignored."
        )
    if stats["skipped_degenerate"]:
        warnings.append(f"{stats['skipped_degenerate']} degenerate ring(s) skipped.")
    if stats["dropped_nonfinite_vertices"]:
        warnings.append(
            f"{stats['dropped_nonfinite_vertices']} non-finite "
            "vertex(es) dropped during georeferencing."
        )
    if not rings:
        return {
            "features_written": 0,
            "registration": reg_info,
            "contour_stats": stats,
            "warnings": [
                *warnings,
                "Ink was detected but produced no usable geometry; consider "
                "lowering min_contour_area_px.",
            ],
        }

    # --- D. native GDB commit ----------------------------------------------
    geometry_cls = arcpy.Polygon if inp.feature_type == "Polygon" else arcpy.Polyline
    written = 0
    with arcpy.da.InsertCursor(inp.target_feature_class, ["SHAPE@"]) as cursor:
        for ring in rings:
            pts = [arcpy.Point(x, y) for x, y in ring]
            if inp.feature_type == "Polygon" and ring[0] != ring[-1]:
                pts.append(arcpy.Point(*ring[0]))  # close the ring explicitly
            cursor.insertRow([geometry_cls(arcpy.Array(pts), sr)])
            written += 1

    return {
        "features_written": written,
        "target": inp.target_feature_class,
        "feature_type": inp.feature_type,
        "ink_color": inp.ink_color,
        "spatial_reference": sr.name if sr else None,
        "registration": reg_info,
        "contour_stats": stats,
        "warnings": warnings,
    }


# -------------------------------------------------------------- registration

register(
    ToolSpec(
        "extract_sketch_to_gis",
        Category.VISION,
        "Sketch-to-GIS pipeline: align a smartphone photo of a hand-drawn sketch "
        "onto its printed map layout (ORB+RANSAC homography), extract the "
        "requested ink color (HSV segmentation), georeference the vectors using "
        "the layout envelope, and append Polygon/Polyline features into an "
        "existing GDB feature class. APPENDS rows — requires confirm=true. "
        "Worker env needs: pip install opencv-python-headless numpy.",
        ExtractSketchSchema,
        _extract_sketch_to_gis,
        destructive=True,  # appends to live data: explicit confirm required
    )
)
