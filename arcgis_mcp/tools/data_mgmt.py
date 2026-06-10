"""ToolSpecs + worker implementations — Category 2: Data Management.

Case-sensitivity guard: function names below mirror exact Esri signatures —
``CreateFeatureclass`` (lowercase c!), ``CreateFileGDB``, ``AddXY``,
``FeatureClassToShapefile``, ``FeaturesToJSON``, ``JSONToFeatures``,
``TableToExcel``, ``ExcelToTable``, ``ExportTable``,
``CalculateGeometryAttributes``.
"""

from __future__ import annotations

from typing import Any

from ..contracts import data_mgmt as c
from ..registry import Category, ToolSpec, register


def _require_confirm(inp: Any, tool: str) -> None:
    if not getattr(inp, "confirm", False):
        raise PermissionError(f"{tool} is irreversible: set confirm=true to proceed.")


# ------------------------------------------------------------------- tools --


def _create_feature_class(arcpy: Any, inp: c.CreateFeatureClassInput) -> dict:
    sr = arcpy.SpatialReference(inp.wkid) if inp.wkid else None
    arcpy.env.overwriteOutput = inp.overwrite
    res = arcpy.management.CreateFeatureclass(  # exact Esri casing
        out_path=inp.out_gdb,
        out_name=inp.name,
        geometry_type=inp.geometry_type,
        spatial_reference=sr,
    )
    return {"created": str(res), "geometry_type": inp.geometry_type, "wkid": inp.wkid}


def _delete_dataset(arcpy: Any, inp: c.DeleteDatasetInput) -> dict:
    _require_confirm(inp, "delete_dataset")
    arcpy.management.Delete(inp.dataset)
    return {"deleted": inp.dataset}


def _copy_features(arcpy: Any, inp: c.CopyFeaturesInput) -> dict:
    arcpy.management.CopyFeatures(inp.in_features, inp.out_features)
    return {"output": inp.out_features}


def _rename_dataset(arcpy: Any, inp: c.RenameDatasetInput) -> dict:
    arcpy.management.Rename(inp.dataset, inp.new_name)
    return {"renamed_from": inp.dataset, "renamed_to": inp.new_name}


def _add_field(arcpy: Any, inp: c.AddFieldInput) -> dict:
    arcpy.management.AddField(
        in_table=inp.dataset,
        field_name=inp.field_name,
        field_type=inp.field_type,
        field_length=inp.length,
        field_alias=inp.alias,
    )
    return {"field_added": inp.field_name, "type": inp.field_type}


def _delete_field(arcpy: Any, inp: c.DeleteFieldInput) -> dict:
    _require_confirm(inp, "delete_field")
    arcpy.management.DeleteField(inp.dataset, inp.fields)
    return {"fields_deleted": inp.fields}


def _calculate_field(arcpy: Any, inp: c.CalculateFieldInput) -> dict:
    arcpy.management.CalculateField(
        in_table=inp.dataset,
        field=inp.field_name,
        expression=inp.expression,
        expression_type=inp.expression_type,
    )
    return {"field": inp.field_name, "expression_type": inp.expression_type}


def _add_fields_batch(arcpy: Any, inp: c.AddFieldsBatchInput) -> dict:
    descriptions = [
        [f.name, f.type, f.alias or f.name, f.length, None, None] for f in inp.fields
    ]
    arcpy.management.AddFields(inp.dataset, descriptions)
    return {"fields_added": [f.name for f in inp.fields]}


def _get_field_info(arcpy: Any, inp: c.GetFieldInfoInput) -> dict:
    return {
        "fields": [
            {
                "name": f.name,
                "type": f.type,
                "length": f.length,
                "alias": f.aliasName,
                "nullable": f.isNullable,
            }
            for f in arcpy.ListFields(inp.dataset)
        ]
    }


def _get_feature_count(arcpy: Any, inp: c.GetFeatureCountInput) -> dict:
    return {"count": int(arcpy.management.GetCount(inp.dataset)[0])}


def _describe_dataset(arcpy: Any, inp: c.DescribeDatasetInput) -> dict:
    d = arcpy.Describe(inp.dataset)
    sr = getattr(d, "spatialReference", None)
    ext = getattr(d, "extent", None)
    return {
        "name": d.name,
        "data_type": d.dataType,
        "shape_type": getattr(d, "shapeType", None),
        "crs": (
            f"EPSG:{sr.factoryCode}"
            if sr and sr.factoryCode
            else (sr.name if sr else None)
        ),
        "extent": (
            {"xmin": ext.XMin, "ymin": ext.YMin, "xmax": ext.XMax, "ymax": ext.YMax}
            if ext
            else None
        ),
    }


def _create_file_gdb(arcpy: Any, inp: c.CreateFileGdbInput) -> dict:
    res = arcpy.management.CreateFileGDB(inp.parent_folder, inp.gdb_name)
    return {"created": str(res)}


def _compact_gdb(arcpy: Any, inp: c.CompactGdbInput) -> dict:
    arcpy.management.Compact(inp.gdb)
    return {"compacted": inp.gdb}


def _export_to_shapefile(arcpy: Any, inp: c.ExportToShapefileInput) -> dict:
    arcpy.conversion.FeatureClassToShapefile(inp.in_features, inp.output_folder)
    return {"output_folder": inp.output_folder}


def _export_to_geojson(arcpy: Any, inp: c.ExportToGeojsonInput) -> dict:
    arcpy.env.overwriteOutput = inp.overwrite
    arcpy.conversion.FeaturesToJSON(
        in_features=inp.in_features,
        out_json_file=inp.out_json,
        geoJSON="GEOJSON",
        outputToWGS84="WGS84",
    )
    return {"output": inp.out_json, "crs": "EPSG:4326"}


def _import_from_geojson(arcpy: Any, inp: c.ImportFromGeojsonInput) -> dict:
    arcpy.env.overwriteOutput = inp.overwrite
    arcpy.conversion.JSONToFeatures(inp.in_json, inp.out_features)
    return {"output": inp.out_features}


def _table_to_excel(arcpy: Any, inp: c.TableToExcelInput) -> dict:
    arcpy.env.overwriteOutput = inp.overwrite
    arcpy.conversion.TableToExcel(inp.table, inp.out_xlsx)
    return {"output": inp.out_xlsx}


def _excel_to_table(arcpy: Any, inp: c.ExcelToTableInput) -> dict:
    arcpy.env.overwriteOutput = inp.overwrite
    arcpy.conversion.ExcelToTable(inp.in_xlsx, inp.out_table, inp.sheet)
    return {"output": inp.out_table}


def _feature_to_csv(arcpy: Any, inp: c.FeatureToCsvInput) -> dict:
    # Pro 3.x replaces the CopyRows+TableToCSV pipeline with ExportTable.
    arcpy.env.overwriteOutput = inp.overwrite
    arcpy.conversion.ExportTable(inp.in_table, inp.out_csv)
    return {"output": inp.out_csv}


def _get_extent(arcpy: Any, inp: c.GetExtentInput) -> dict:
    ext = arcpy.Describe(inp.dataset).extent
    return {
        "xmin": ext.XMin,
        "ymin": ext.YMin,
        "xmax": ext.XMax,
        "ymax": ext.YMax,
        "crs": ext.spatialReference.name if ext.spatialReference else None,
    }


def _calculate_geometry(arcpy: Any, inp: c.CalculateGeometryInput) -> dict:
    arcpy.management.CalculateGeometryAttributes(
        in_features=inp.dataset,
        geometry_property=[[inp.field_name, inp.geometry_property]],
        length_unit=inp.length_unit or "",
        area_unit=inp.area_unit or "",
    )
    return {"field": inp.field_name, "property": inp.geometry_property}


def _add_xy_coordinates(arcpy: Any, inp: c.AddXyCoordinatesInput) -> dict:
    arcpy.management.AddXY(inp.dataset)  # exact Esri casing
    return {"updated": inp.dataset, "fields": ["POINT_X", "POINT_Y"]}


# -------------------------------------------------------------- registrations

_CAT = Category.DATA_MGMT

_SPECS: tuple[tuple[str, str, type, Any, bool], ...] = (
    (
        "create_feature_class",
        "Create a new feature class in a GDB (CreateFeatureclass).",
        c.CreateFeatureClassInput,
        _create_feature_class,
        False,
    ),
    (
        "delete_dataset",
        "Delete a FC/table/raster (Delete). Irreversible; requires confirm=true.",
        c.DeleteDatasetInput,
        _delete_dataset,
        True,
    ),
    (
        "copy_features",
        "Copy features preserving CRS and schema (CopyFeatures).",
        c.CopyFeaturesInput,
        _copy_features,
        False,
    ),
    (
        "rename_dataset",
        "Rename a dataset inside its GDB (Rename).",
        c.RenameDatasetInput,
        _rename_dataset,
        False,
    ),
    (
        "add_field",
        "Add one field to a table/FC (AddField).",
        c.AddFieldInput,
        _add_field,
        False,
    ),
    (
        "delete_field",
        "Drop fields from a table/FC (DeleteField). Requires confirm=true.",
        c.DeleteFieldInput,
        _delete_field,
        True,
    ),
    (
        "calculate_field",
        "Compute field values with a PYTHON3/ARCADE/SQL expression (CalculateField).",
        c.CalculateFieldInput,
        _calculate_field,
        False,
    ),
    (
        "add_fields_batch",
        "Add multiple fields in one call (AddFields).",
        c.AddFieldsBatchInput,
        _add_fields_batch,
        False,
    ),
    (
        "get_field_info",
        "List field names, types, lengths and aliases (ListFields).",
        c.GetFieldInfoInput,
        _get_field_info,
        False,
    ),
    (
        "get_feature_count",
        "Return the feature/row count (GetCount).",
        c.GetFeatureCountInput,
        _get_feature_count,
        False,
    ),
    (
        "describe_dataset",
        "Return CRS, geometry type and extent metadata (Describe).",
        c.DescribeDatasetInput,
        _describe_dataset,
        False,
    ),
    (
        "create_file_gdb",
        "Create a new file geodatabase (CreateFileGDB).",
        c.CreateFileGdbInput,
        _create_file_gdb,
        False,
    ),
    (
        "compact_gdb",
        "Compact a GDB to reclaim space (Compact).",
        c.CompactGdbInput,
        _compact_gdb,
        False,
    ),
    (
        "export_to_shapefile",
        "Export a FC to shapefile in a folder (FeatureClassToShapefile).",
        c.ExportToShapefileInput,
        _export_to_shapefile,
        False,
    ),
    (
        "export_to_geojson",
        "Export features to GeoJSON in WGS84 (FeaturesToJSON).",
        c.ExportToGeojsonInput,
        _export_to_geojson,
        False,
    ),
    (
        "import_from_geojson",
        "Create a FC from GeoJSON (JSONToFeatures).",
        c.ImportFromGeojsonInput,
        _import_from_geojson,
        False,
    ),
    (
        "table_to_excel",
        "Export an attribute table to .xlsx (TableToExcel).",
        c.TableToExcelInput,
        _table_to_excel,
        False,
    ),
    (
        "excel_to_table",
        "Import an .xlsx sheet as a GDB table (ExcelToTable).",
        c.ExcelToTableInput,
        _excel_to_table,
        False,
    ),
    (
        "feature_to_csv",
        "Export attributes to CSV (ExportTable, Pro 3.x).",
        c.FeatureToCsvInput,
        _feature_to_csv,
        False,
    ),
    (
        "get_extent",
        "Return xmin/ymin/xmax/ymax of a dataset (Describe().extent).",
        c.GetExtentInput,
        _get_extent,
        False,
    ),
    (
        "calculate_geometry",
        "Write area/length/centroid values into a field (CalculateGeometryAttributes).",
        c.CalculateGeometryInput,
        _calculate_geometry,
        False,
    ),
    (
        "add_xy_coordinates",
        "Add POINT_X/POINT_Y fields to a point FC (AddXY).",
        c.AddXyCoordinatesInput,
        _add_xy_coordinates,
        False,
    ),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
