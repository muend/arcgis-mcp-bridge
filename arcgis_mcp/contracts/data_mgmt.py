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
    """Shared base: tools reading one existing dataset/table."""

    dataset: str = Field(..., min_length=1, description="Absolute dataset path.")
    path_fields: ClassVar[dict[str, PathRole]] = {"dataset": "read"}


class InOutInput(ToolInput):
    """Shared base: one input dataset, one output dataset."""

    in_features: str = Field(..., min_length=1)
    out_features: str = Field(..., min_length=1)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }


class CreateFeatureClassInput(ToolInput):
    out_gdb: str = Field(..., description="Existing .gdb to create the FC in.")
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=160)
    geometry_type: EsriGeometry = "POLYGON"
    wkid: Optional[int] = Field(
        default=None,
        ge=1024,
        le=32767 + 200000,
        description="Spatial reference WKID, e.g. 4326. None = unknown CRS.",
    )
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {"out_gdb": "read"}


class DeleteDatasetInput(DatasetInput):
    confirm: bool = Field(
        default=False, description="Must be true: deletion is irreversible."
    )


class CopyFeaturesInput(InOutInput):
    pass


class RenameDatasetInput(DatasetInput):
    new_name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=160)


class AddFieldInput(DatasetInput):
    field_name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=64)
    field_type: EsriFieldType = "TEXT"
    length: Optional[int] = Field(
        default=None, ge=1, le=2147483647, description="TEXT length; ignored otherwise."
    )
    alias: Optional[str] = None


class DeleteFieldInput(DatasetInput):
    fields: List[str] = Field(..., min_length=1)
    confirm: bool = Field(default=False, description="Must be true: drops data.")


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

    field_name: str = Field(..., min_length=1, max_length=64)
    expression: str = Field(..., min_length=1, max_length=4000)
    expression_type: Literal["PYTHON3", "ARCADE", "SQL"] = "ARCADE"
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
    """One field for the batch AddFields call."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=64)
    type: EsriFieldType = "TEXT"
    length: Optional[int] = Field(default=None, ge=1)
    alias: Optional[str] = None


class AddFieldsBatchInput(DatasetInput):
    fields: List[FieldDef] = Field(..., min_length=1, max_length=100)


class GetFieldInfoInput(DatasetInput):
    pass


class GetFeatureCountInput(DatasetInput):
    pass


class DescribeDatasetInput(DatasetInput):
    pass


class CreateFileGdbInput(ToolInput):
    parent_folder: str = Field(..., description="Existing folder for the new .gdb.")
    gdb_name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=100)
    path_fields: ClassVar[dict[str, PathRole]] = {"parent_folder": "read"}


class CompactGdbInput(ToolInput):
    gdb: str = Field(..., description="Path to the .gdb to compact.")
    path_fields: ClassVar[dict[str, PathRole]] = {"gdb": "read"}


class ExportToShapefileInput(ToolInput):
    in_features: str
    output_folder: str = Field(..., description="Existing destination folder.")
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "output_folder": "read",
    }


class ExportToGeojsonInput(ToolInput):
    in_features: str
    out_json: str = Field(..., description="Output .geojson path.")
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_json": "write",
    }


class ImportFromGeojsonInput(ToolInput):
    in_json: str
    out_features: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_json": "read",
        "out_features": "write",
    }


class TableToExcelInput(ToolInput):
    table: str
    out_xlsx: str
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "table": "read",
        "out_xlsx": "write",
    }


class ExcelToTableInput(ToolInput):
    in_xlsx: str
    out_table: str
    sheet: Optional[str] = None
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_xlsx": "read",
        "out_table": "write",
    }


class FeatureToCsvInput(ToolInput):
    in_table: str
    out_csv: str = Field(..., description="Output .csv path.")
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_table": "read",
        "out_csv": "write",
    }


class GetExtentInput(DatasetInput):
    pass


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
    field_name: str = Field(..., max_length=64)
    geometry_property: GeometryProperty
    area_unit: Optional[str] = Field(default=None, description="e.g. SQUARE_METERS")
    length_unit: Optional[str] = Field(default=None, description="e.g. METERS")


class AddXyCoordinatesInput(DatasetInput):
    pass
