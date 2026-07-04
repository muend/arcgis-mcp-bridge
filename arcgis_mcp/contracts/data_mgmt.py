"""Input models — Category 2: Data Management (catalog #11-32)."""

from __future__ import annotations

from typing import ClassVar, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import PathRole, ToolInput

EsriGeometry = Literal["POINT", "MULTIPOINT", "POLYLINE", "POLYGON", "MULTIPATCH"]
EsriFieldType = Literal[
    "TEXT", "SHORT", "LONG", "BIGINTEGER", "FLOAT", "DOUBLE", "DATE", "GUID", "BLOB"
]


class DatasetInput(ToolInput):
    """Shared base for tools that read one existing GIS dataset or table."""

    dataset: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to an existing feature class, table, raster, or "
            "geodatabase item. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class InOutInput(ToolInput):
    """Shared base for tools that read one dataset and create one output."""

    in_features: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute path to the existing input feature class, layer, or table. "
            "The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        min_length=1,
        description=(
            "Absolute output dataset path to create. The path must be inside a "
            "configured PathGuard allowed root; existing outputs require "
            "overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output dataset is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class CreateFeatureClassInput(ToolInput):
    """Create an empty feature class inside an existing file geodatabase."""

    out_gdb: str = Field(
        ...,
        description=(
            "Absolute path to an existing file geodatabase where the new feature "
            "class will be created. The geodatabase must be inside a configured "
            "PathGuard allowed root."
        ),
    )
    name: str = Field(
        ...,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=160,
        description=(
            "Name of the new feature class, without a path. Use a valid ArcGIS "
            "dataset name beginning with a letter or underscore."
        ),
    )
    geometry_type: EsriGeometry = Field(
        default="POLYGON",
        description=(
            "Geometry type for the new feature class: POINT, MULTIPOINT, "
            "POLYLINE, POLYGON, or MULTIPATCH."
        ),
    )
    wkid: Optional[int] = Field(
        default=None,
        ge=1024,
        le=32767 + 200000,
        description=(
            "Optional spatial reference WKID, for example 4326 for WGS 84. "
            "Use None to create the feature class with an unknown coordinate system."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing feature class with the same "
            "name is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"out_gdb": "read"}


class DeleteDatasetInput(DatasetInput):
    """Delete an existing dataset; irreversible and confirmation-gated."""

    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. Deleting a dataset is irreversible and removes the "
            "target feature class, table, raster, or geodatabase item."
        ),
    )


class CopyFeaturesInput(InOutInput):
    """Copy a feature class or layer into a new output feature class."""


class RenameDatasetInput(DatasetInput):
    """Rename an existing dataset within its current workspace."""

    new_name: str = Field(
        ...,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=160,
        description=(
            "New dataset name only, not a full path. Use a valid ArcGIS name "
            "beginning with a letter or underscore."
        ),
    )


class AddFieldInput(DatasetInput):
    """Add one attribute field to an existing table or feature class."""

    field_name: str = Field(
        ...,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=64,
        description=(
            "Name of the field to add. Use a valid ArcGIS field name beginning "
            "with a letter or underscore."
        ),
    )
    field_type: EsriFieldType = Field(
        default="TEXT",
        description=(
            "ArcGIS field type to create, such as TEXT, LONG, DOUBLE, DATE, "
            "GUID, or BLOB."
        ),
    )
    length: Optional[int] = Field(
        default=None,
        ge=1,
        le=2147483647,
        description=(
            "Optional text field length. Used for TEXT fields and ignored by "
            "most numeric, date, GUID, and BLOB field types."
        ),
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional human-readable field alias shown in ArcGIS.",
    )


class DeleteFieldInput(DatasetInput):
    """Delete one or more fields from an existing table or feature class."""

    fields: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "List of field names to delete from the dataset. System-required "
            "fields cannot be deleted by ArcGIS."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true. Dropping fields permanently removes attribute data "
            "from the input dataset."
        ),
    )


class CalculateFieldInput(DatasetInput):
    """Field calculation contract with an expression-channel safety floor.

    Security rationale: ``expression_type="PYTHON3"`` hands the expression to
    a live Python evaluator inside the worker process — a prompt-injected
    expression is arbitrary code execution on the host. The default is
    therefore ``ARCADE`` (Esri's sandboxed expression language, no OS
    access), and PYTHON3 is only honored behind an explicit ``confirm=true``
    opt-in enforced both here (Layer A, fail before spawn) and by the
    dispatcher's destructive-tool gate (Layer B, trust no parent).
    """

    field_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Name of the existing field whose values will be calculated. "
            "The field must already exist in the input dataset."
        ),
    )
    expression: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description=(
            "Calculation expression passed to ArcPy CalculateField. Prefer "
            "ARCADE for LLM-facing workflows because it is sandboxed compared "
            "with PYTHON3."
        ),
    )
    expression_type: Literal["PYTHON3", "ARCADE", "SQL"] = Field(
        default="ARCADE",
        description=(
            "Expression language for the calculation. ARCADE is the default "
            "safer option. PYTHON3 executes Python code in the worker and "
            "requires confirm=true."
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Must be true: calculate_field irreversibly overwrites column "
            "values, and PYTHON3 expressions execute code in the worker."
        ),
    )

    @model_validator(mode="after")
    def _python3_requires_confirm(self) -> "CalculateFieldInput":
        """PYTHON3 = code execution; refuse it without an explicit opt-in."""
        if self.expression_type == "PYTHON3" and not self.confirm:
            raise ValueError(
                "expression_type='PYTHON3' executes arbitrary Python inside "
                "the worker process. Re-issue with confirm=true, or use the "
                "sandboxed 'ARCADE' expression type (the default)."
            )
        return self


class FieldDef(BaseModel):
    """One field definition for the batch AddFields call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=64,
        description=(
            "Name of the field to add. Use a valid ArcGIS field name beginning "
            "with a letter or underscore."
        ),
    )
    type: EsriFieldType = Field(
        default="TEXT",
        description="ArcGIS field type to create, such as TEXT, LONG, DOUBLE, or DATE.",
    )
    length: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Optional text field length. Primarily used when type is TEXT."
        ),
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional human-readable field alias shown in ArcGIS.",
    )


class AddFieldsBatchInput(DatasetInput):
    """Add multiple fields to an existing table or feature class."""

    fields: List[FieldDef] = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Field definitions to add in one ArcPy AddFields operation. Each "
            "definition includes a name, type, optional alias, and optional length."
        ),
    )


class GetFieldInfoInput(DatasetInput):
    """List field names, types, lengths, aliases, and nullable status."""


class GetFeatureCountInput(DatasetInput):
    """Return the row or feature count for an existing dataset."""


class DescribeDatasetInput(DatasetInput):
    """Return dataset metadata such as data type, geometry type, CRS, and extent."""


class CreateFileGdbInput(ToolInput):
    """Create a new file geodatabase in an existing folder."""

    parent_folder: str = Field(
        ...,
        description=(
            "Absolute path to an existing folder where the new file geodatabase "
            "will be created. The folder must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    gdb_name: str = Field(
        ...,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=100,
        description=(
            "Name of the new file geodatabase, without a path. Use a valid "
            "geodatabase name such as analysis_scratch."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"parent_folder": "read"}


class CompactGdbInput(ToolInput):
    """Compact an existing file geodatabase to reclaim space."""

    gdb: str = Field(
        ...,
        description=(
            "Absolute path to the existing file geodatabase to compact. The "
            "geodatabase must be inside a configured PathGuard allowed root."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {"gdb": "read"}


class ExportToShapefileInput(ToolInput):
    """Export a feature class to shapefile format in an existing folder."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class or layer to export. The "
            "path must be inside a configured PathGuard allowed root."
        ),
    )
    output_folder: str = Field(
        ...,
        description=(
            "Existing destination folder for the shapefile output. The folder "
            "must be inside a configured PathGuard allowed root."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "output_folder": "read",
    }


class ExportToGeojsonInput(ToolInput):
    """Export features to a GeoJSON file in WGS84."""

    in_features: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class or layer to export as "
            "GeoJSON. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_json: str = Field(
        ...,
        description=(
            "Absolute output .geojson file path to create. Existing files "
            "require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing GeoJSON file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_json": "write",
    }


class ImportFromGeojsonInput(ToolInput):
    """Convert a GeoJSON file into an ArcGIS feature class."""

    in_json: str = Field(
        ...,
        description=(
            "Absolute path to the input .geojson file to convert. The file must "
            "be inside a configured PathGuard allowed root."
        ),
    )
    out_features: str = Field(
        ...,
        description=(
            "Absolute output feature class path to create from the GeoJSON. "
            "Existing outputs require overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output feature class is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_json": "read",
        "out_features": "write",
    }


class TableToExcelInput(ToolInput):
    """Export an attribute table to an Excel workbook."""

    table: str = Field(
        ...,
        description=(
            "Absolute path to the input table or feature class whose attributes "
            "will be exported. The path must be inside a configured PathGuard "
            "allowed root."
        ),
    )
    out_xlsx: str = Field(
        ...,
        description=(
            "Absolute output .xlsx path to create. Existing files require "
            "overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing Excel file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "table": "read",
        "out_xlsx": "write",
    }


class ExcelToTableInput(ToolInput):
    """Import an Excel worksheet into a geodatabase table."""

    in_xlsx: str = Field(
        ...,
        description=(
            "Absolute path to the input .xlsx workbook. The file must be inside "
            "a configured PathGuard allowed root."
        ),
    )
    out_table: str = Field(
        ...,
        description=(
            "Absolute output geodatabase table path to create. Existing outputs "
            "require overwrite=true."
        ),
    )
    sheet: Optional[str] = Field(
        default=None,
        description=(
            "Optional worksheet name to import. Use None to let ArcPy choose the "
            "default sheet."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description=(
            "Set true only when replacing an existing output table is intended."
        ),
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_xlsx": "read",
        "out_table": "write",
    }


class FeatureToCsvInput(ToolInput):
    """Export a feature class or table to a CSV file."""

    in_table: str = Field(
        ...,
        description=(
            "Absolute path to the input feature class or table whose rows will "
            "be exported. The path must be inside a configured PathGuard allowed root."
        ),
    )
    out_csv: str = Field(
        ...,
        description=(
            "Absolute output .csv file path to create. Existing files require "
            "overwrite=true."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Set true only when replacing an existing CSV file is intended.",
    )
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_table": "read",
        "out_csv": "write",
    }


class GetExtentInput(DatasetInput):
    """Return xmin, ymin, xmax, ymax, and CRS metadata for a dataset extent."""


GeometryProperty = Literal[
    "AREA",
    "AREA_GEODESIC",
    "LENGTH",
    "LENGTH_GEODESIC",
    "PERIMETER_LENGTH",
    "PERIMETER_LENGTH_GEODESIC",
    "CENTROID_X",
    "CENTROID_Y",
    "POINT_X",
    "POINT_Y",
]


class CalculateGeometryInput(DatasetInput):
    """Calculate area, length, perimeter, centroid, or point coordinate attributes."""

    field_name: str = Field(
        ...,
        max_length=64,
        description=(
            "Existing or target field name that will receive the calculated "
            "geometry value."
        ),
    )
    geometry_property: GeometryProperty = Field(
        ...,
        description=(
            "Geometry property to calculate, such as AREA, LENGTH, CENTROID_X, "
            "CENTROID_Y, POINT_X, or POINT_Y."
        ),
    )
    area_unit: Optional[str] = Field(
        default=None,
        description=(
            "Optional area unit for area calculations, for example SQUARE_METERS. "
            "Ignored for non-area geometry properties."
        ),
    )
    length_unit: Optional[str] = Field(
        default=None,
        description=(
            "Optional length unit for length or perimeter calculations, for example "
            "METERS. Ignored for non-length geometry properties."
        ),
    )


class AddXyCoordinatesInput(DatasetInput):
    """Add or update POINT_X and POINT_Y coordinate fields on point features."""
