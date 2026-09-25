"""tests/test_geojson_import.py — import_from_geojson geometry handling.

JSONToFeatures reads a .geojson file as POLYGON unless given a geometry type,
so point and line files used to import as empty feature classes without any
error (issue #25). The worker now detects the type, passes it explicitly, and
refuses to report an empty import as success. arcpy is a per-test MagicMock.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from arcgis_mcp.contracts.data_mgmt import ImportFromGeojsonInput
from arcgis_mcp.tools.data_mgmt import GeojsonImportError, _import_from_geojson


def _feature(geometry: dict | None, fid: int = 1) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": {"id": fid}}


def _collection(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


_POINT = {"type": "Point", "coordinates": [115.97, 24.39]}
_LINE = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
_MULTILINE = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]]]}
_POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}


def _write(tmp_path: Path, doc: object, name: str = "in.geojson") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def _arcpy(count: int) -> MagicMock:
    arcpy = MagicMock()
    arcpy.management.GetCount.return_value = [str(count)]
    return arcpy


def _inp(in_json: str, **kwargs: object) -> ImportFromGeojsonInput:
    return ImportFromGeojsonInput(in_json=in_json, out_features="C:/o.gdb/fc", **kwargs)


# --------------------------------------------------------------------------- #
# Geometry-type detection
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("features", "expected"),
    [
        ((_feature(_POINT), _feature(_POINT, 2)), "POINT"),
        ((_feature(_LINE), _feature(_MULTILINE, 2)), "POLYLINE"),
        ((_feature(_POLYGON),), "POLYGON"),
        ((_feature(_POINT), _feature(None, 2)), "POINT"),  # null geometry ignored
    ],
)
def test_detected_geometry_type_is_passed_explicitly(
    tmp_path: Path, features: tuple[dict, ...], expected: str
) -> None:
    path = _write(tmp_path, _collection(*features))
    arcpy = _arcpy(count=2)

    out = _import_from_geojson(arcpy, _inp(path))

    arcpy.conversion.JSONToFeatures.assert_called_once_with(path, "C:/o.gdb/fc", expected)
    assert out == {"output": "C:/o.gdb/fc", "geometry_type": expected, "count": 2}


def test_single_feature_document_is_detected(tmp_path: Path) -> None:
    path = _write(tmp_path, _feature(_POINT))
    arcpy = _arcpy(count=1)
    assert _import_from_geojson(arcpy, _inp(path))["geometry_type"] == "POINT"


def test_utf8_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "bom.geojson"
    path.write_text(json.dumps(_collection(_feature(_POINT))), encoding="utf-8-sig")
    assert _import_from_geojson(_arcpy(1), _inp(str(path)))["geometry_type"] == "POINT"


def test_mixed_geometry_is_rejected_before_arcpy_runs(tmp_path: Path) -> None:
    path = _write(tmp_path, _collection(_feature(_POINT), _feature(_LINE, 2)))
    arcpy = _arcpy(count=1)

    with pytest.raises(GeojsonImportError, match="mixes geometry types"):
        _import_from_geojson(arcpy, _inp(path))
    arcpy.conversion.JSONToFeatures.assert_not_called()


def test_explicit_geometry_type_selects_from_mixed_file(tmp_path: Path) -> None:
    path = _write(tmp_path, _collection(_feature(_POINT), _feature(_LINE, 2)))
    arcpy = _arcpy(count=1)

    out = _import_from_geojson(arcpy, _inp(path, geometry_type="POLYLINE"))

    arcpy.conversion.JSONToFeatures.assert_called_once_with(path, "C:/o.gdb/fc", "POLYLINE")
    assert out["geometry_type"] == "POLYLINE"


@pytest.mark.parametrize(
    "doc",
    [
        _collection(),
        _collection(_feature(None)),
        [1, 2, 3],
    ],
)
def test_nothing_importable_is_rejected(tmp_path: Path, doc: object) -> None:
    with pytest.raises(GeojsonImportError):
        _import_from_geojson(_arcpy(0), _inp(_write(tmp_path, doc)))


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken.geojson"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(GeojsonImportError, match="not valid GeoJSON"):
        _import_from_geojson(_arcpy(0), _inp(str(path)))


def test_empty_import_fails_loudly(tmp_path: Path) -> None:
    path = _write(tmp_path, _collection(_feature(_POINT)))
    with pytest.raises(GeojsonImportError, match="imported 0 POINT features"):
        _import_from_geojson(_arcpy(count=0), _inp(path))


def test_esri_json_passes_through_without_geometry_type(tmp_path: Path) -> None:
    path = _write(tmp_path, {"geometryType": "esriGeometryPoint", "features": []}, "in.json")
    arcpy = _arcpy(count=0)

    assert _import_from_geojson(arcpy, _inp(path)) == {"output": "C:/o.gdb/fc"}
    arcpy.conversion.JSONToFeatures.assert_called_once_with(path, "C:/o.gdb/fc")


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


def test_geometry_type_defaults_to_detection() -> None:
    assert _inp("C:/d/in.geojson").geometry_type is None


def test_geometry_type_is_rejected_for_esri_json() -> None:
    with pytest.raises(ValidationError, match=r"only to \.geojson"):
        _inp("C:/d/in.json", geometry_type="POINT")


def test_geometry_type_must_be_a_geojson_type() -> None:
    with pytest.raises(ValidationError):
        _inp("C:/d/in.geojson", geometry_type="MULTIPATCH")
