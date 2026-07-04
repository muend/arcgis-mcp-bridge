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
        (
            "Create an empty feature class inside an existing file geodatabase "
            "using ArcPy CreateFeatureclass. Use this to prepare a controlled "
            "output dataset with a chosen geometry type and optional WKID before "
            "loading, editing, or analysis. Reads the target geodatabase path "
            "inside a PathGuard allowed root and returns the created dataset."
        ),
        c.CreateFeatureClassInput,
        _create_feature_class,
        False,
    ),
    (
        "delete_dataset",
        (
            "Delete an existing feature class, table, raster, or geodatabase item "
            "using ArcPy Delete. This operation is irreversible and mutates local "
            "project data, so confirm=true is required. The target dataset must "
            "be inside a configured PathGuard allowed root."
        ),
        c.DeleteDatasetInput,
        _delete_dataset,
        True,
    ),
    (
        "copy_features",
        (
            "Copy an existing feature class or layer to a new output feature "
            "class using ArcPy CopyFeatures. Use this to create a safe working "
            "copy while preserving geometry, attributes, schema, and spatial "
            "reference. Reads in_features and writes out_features inside "
            "PathGuard allowed roots; existing outputs require overwrite=true."
        ),
        c.CopyFeaturesInput,
        _copy_features,
        False,
    ),
    (
        "rename_dataset",
        (
            "Rename an existing dataset within its current workspace using ArcPy "
            "Rename. Use this for controlled cleanup of intermediate feature "
            "classes, tables, or rasters. This mutates the workspace namespace "
            "but does not edit feature geometry or attribute values; the dataset "
            "path must be inside a PathGuard allowed root."
        ),
        c.RenameDatasetInput,
        _rename_dataset,
        False,
    ),
    (
        "add_field",
        (
            "Add one attribute field to an existing feature class or table using "
            "ArcPy AddField. Use this to prepare schema before imports, joins, "
            "calculations, or manual editing. Mutates the input dataset schema; "
            "the dataset must be inside a PathGuard allowed root."
        ),
        c.AddFieldInput,
        _add_field,
        False,
    ),
    (
        "delete_field",
        (
            "Delete one or more fields from an existing feature class or table "
            "using ArcPy DeleteField. Use this only when unwanted attribute "
            "columns should be permanently removed. This mutates the input schema "
            "and drops data, so confirm=true is required."
        ),
        c.DeleteFieldInput,
        _delete_field,
        True,
    ),
    (
        "calculate_field",
        (
            "Calculate values for an existing field using ArcPy CalculateField. "
            "Use this for controlled attribute updates with ARCADE, SQL, or "
            "PYTHON3 expressions. The default ARCADE mode is preferred for "
            "LLM-facing workflows; PYTHON3 executes worker-side code and, like "
            "all value overwrites, requires confirm=true."
        ),
        c.CalculateFieldInput,
        _calculate_field,
        True,
    ),
    (
        "add_fields_batch",
        (
            "Add multiple fields to an existing feature class or table in one "
            "operation using ArcPy AddFields. Use this to prepare a complete "
            "attribute schema before imports, calculations, joins, or QA/QC. "
            "Mutates the input dataset schema; field names, types, aliases, and "
            "lengths are validated before execution."
        ),
        c.AddFieldsBatchInput,
        _add_fields_batch,
        False,
    ),
    (
        "get_field_info",
        (
            "List field metadata for an existing feature class or table using "
            "ArcPy ListFields. Use this to inspect schema before calculating, "
            "deleting, joining, or exporting attributes. Returns field names, "
            "types, lengths, aliases, and nullable status without modifying data."
        ),
        c.GetFieldInfoInput,
        _get_field_info,
        False,
    ),
    (
        "get_feature_count",
        (
            "Return the row or feature count for an existing dataset using ArcPy "
            "GetCount. Use this as a lightweight validation step before and after "
            "geoprocessing, filtering, import, export, or QA/QC workflows. Reads "
            "one dataset inside a PathGuard allowed root and does not modify data."
        ),
        c.GetFeatureCountInput,
        _get_feature_count,
        False,
    ),
    (
        "describe_dataset",
        (
            "Describe an existing feature class, table, raster, or geodatabase "
            "item using ArcPy Describe. Use this to inspect data type, geometry "
            "type, coordinate reference system, and extent before choosing an "
            "analysis tool. Reads metadata only and does not modify the dataset."
        ),
        c.DescribeDatasetInput,
        _describe_dataset,
        False,
    ),
    (
        "create_file_gdb",
        (
            "Create a new file geodatabase using ArcPy CreateFileGDB. Use this "
            "to prepare a workspace for scratch outputs, copied data, imports, "
            "or project-specific analysis results. The parent folder must exist "
            "inside a PathGuard allowed root; the tool returns the created "
            "geodatabase path."
        ),
        c.CreateFileGdbInput,
        _create_file_gdb,
        False,
    ),
    (
        "compact_gdb",
        (
            "Compact an existing file geodatabase using ArcPy Compact. Use this "
            "as maintenance after heavy editing, deletion, or intermediate output "
            "cleanup to reclaim storage and improve geodatabase performance. "
            "Mutates the geodatabase storage layout but not feature content."
        ),
        c.CompactGdbInput,
        _compact_gdb,
        False,
    ),
    (
        "export_to_shapefile",
        (
            "Export a feature class to shapefile format using ArcPy "
            "FeatureClassToShapefile. Use this when data must be shared with "
            "legacy GIS tools or systems that require shapefiles. Reads the input "
            "features and writes shapefile components into an existing output "
            "folder inside PathGuard allowed roots."
        ),
        c.ExportToShapefileInput,
        _export_to_shapefile,
        False,
    ),
    (
        "export_to_geojson",
        (
            "Export features to a WGS84 GeoJSON file using ArcPy FeaturesToJSON. "
            "Use this to share vector data with web maps, APIs, notebooks, or "
            "non-Esri tools. Reads in_features and writes an output .geojson file "
            "inside PathGuard allowed roots; existing files require overwrite=true."
        ),
        c.ExportToGeojsonInput,
        _export_to_geojson,
        False,
    ),
    (
        "import_from_geojson",
        (
            "Convert a GeoJSON file into an ArcGIS feature class using ArcPy "
            "JSONToFeatures. Use this to bring web, API, or exchange-format vector "
            "data into a geodatabase for ArcGIS analysis. Reads an input .geojson "
            "file and writes out_features inside PathGuard allowed roots; existing "
            "outputs require overwrite=true."
        ),
        c.ImportFromGeojsonInput,
        _import_from_geojson,
        False,
    ),
    (
        "table_to_excel",
        (
            "Export an attribute table or feature class table to an Excel workbook "
            "using ArcPy TableToExcel. Use this to share tabular GIS attributes "
            "with analysts, reports, or spreadsheet workflows. Reads the input "
            "table and writes an .xlsx file inside PathGuard allowed roots; "
            "existing files require overwrite=true."
        ),
        c.TableToExcelInput,
        _table_to_excel,
        False,
    ),
    (
        "excel_to_table",
        (
            "Import an Excel worksheet into a geodatabase table using ArcPy "
            "ExcelToTable. Use this to bring spreadsheet-based attributes, lookup "
            "tables, or external tabular data into ArcGIS. Reads an .xlsx workbook "
            "and writes a geodatabase table inside PathGuard allowed roots; existing "
            "outputs require overwrite=true."
        ),
        c.ExcelToTableInput,
        _excel_to_table,
        False,
    ),
    (
        "feature_to_csv",
        (
            "Export a feature class or table to a CSV file using ArcPy ExportTable. "
            "Use this to move attribute data into notebooks, data pipelines, reports, "
            "or non-GIS tools. Reads the input table or feature class and writes a "
            ".csv output inside PathGuard allowed roots; existing files require "
            "overwrite=true."
        ),
        c.FeatureToCsvInput,
        _feature_to_csv,
        False,
    ),
    (
        "get_extent",
        (
            "Return xmin, ymin, xmax, ymax, and CRS metadata for an existing dataset "
            "using ArcPy Describe().extent. Use this to understand spatial coverage "
            "before clipping, map export, fishnet creation, raster analysis, or "
            "spatial QA/QC. Reads metadata only and does not modify the dataset."
        ),
        c.GetExtentInput,
        _get_extent,
        False,
    ),
    (
        "calculate_geometry",
        (
            "Calculate area, length, perimeter, centroid, or point coordinate values "
            "into an attribute field using ArcPy CalculateGeometryAttributes. Use "
            "this to populate measurement fields for reporting, QA/QC, labeling, "
            "or downstream analysis. Mutates the input dataset by writing geometry "
            "values into the specified field."
        ),
        c.CalculateGeometryInput,
        _calculate_geometry,
        False,
    ),
    (
        "add_xy_coordinates",
        (
            "Add or update POINT_X and POINT_Y coordinate fields on point features "
            "using ArcPy AddXY. Use this when point coordinates are needed for "
            "export, QA/QC, labeling, tabular analysis, or integration with non-GIS "
            "systems. Mutates the input dataset by adding or updating coordinate "
            "fields, so run it on an intended working dataset."
        ),
        c.AddXyCoordinatesInput,
        _add_xy_coordinates,
        False,
    ),
)

for _name, _desc, _model, _fn, _destructive in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn, destructive=_destructive))
