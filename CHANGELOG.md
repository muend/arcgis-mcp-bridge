# Changelog

All notable changes to **arcgis-mcp-bridge** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- `calculate_field`: default `expression_type` changed from `PYTHON3` to
  `ARCADE` (Esri's sandboxed expression language). `PYTHON3` expressions —
  arbitrary code execution inside the worker — now require an explicit
  `confirm: true`, enforced by a Pydantic `model_validator` at the Layer-A
  contract boundary **and** by the central destructive-tool dispatcher gate
  in Layer B (the spec is now registered `destructive=True`).
- `raster_calculator`: expressions are constrained to a pure map-algebra
  grammar (identifiers, numbers, arithmetic/comparison/boolean operators;
  no quotes, no dunder sequences) by a contract `field_validator`.

### Added

- `ARCGIS_MCP_MAX_WORKERS` (default `2`): an `asyncio.Semaphore` inside
  `SubprocessBackend` now bounds concurrently live arcpy worker
  subprocesses. Parallel agent fan-out queues FIFO at the orchestration
  boundary instead of stampeding RAM and finite Esri license seats
  (`ExtensionLicenseError` under load).
- `health_check` now reports `max_workers`.
- Community assets: `CONTRIBUTING.md`, issue templates (bug report /
  feature request), `CITATION.cff`, this changelog.

### Changed

- `server.py` composition root is now **lazy**: a memoized `get_runtime()`
  (`functools.lru_cache(maxsize=1)`) replaces import-time `_bootstrap()`.
  Importing the module no longer validates the environment or raises
  `SystemExit(1)` — test suites import safely; `main()` still resolves the
  runtime eagerly so misconfigured deployments fail before the handshake.
- Packaging metadata: PyPI keywords and Trove classifiers added.

## [0.5.0] — 2026-06-11

The 100-tool parity milestone: a secure, local-first, asynchronous MCP
server exposing ArcGIS Pro's ArcPy engine over stdio JSON-RPC.

### Added

- **100 declarative geoprocessing tools across 10 verticals**:
  `map_layer_management` (10), `data_management` (22),
  `geometry_analysis` (23), `coordinate_reference_projection` (4),
  `raster_operations` (15), `vision_analytics` (1), `export_layout` (9),
  `editing_topology` (7), `network_analysis` (4), `spatial_statistics` (5).
- **Two-process isolation**: an async FastMCP protocol host (Layer A) that
  never imports arcpy, bridged over NDJSON pipes to a spawn-per-call ArcPy
  worker (Layer B) on the licensed ArcGIS Pro interpreter. Native crashes
  terminate the worker, never the server.
- **PathGuard sandboxing**: every filesystem argument declares a
  `read`/`write`/`read_list` role in its contract; one shared enforcement
  function applies the allowed-roots boundary in both processes
  (deepest-existing-prefix resolution, traversal/UNC/NUL/device-name
  rejection, explicit overwrite discipline).
- **Pydantic v2 contracts throughout**: frozen, `extra="forbid"` models for
  the tool surface and the IPC envelope; schema and validation derive from
  the same class.
- **Destructive mutation safety floor**: confirm-gated specs enforced by
  registry construction and the worker dispatcher.
- **Declarative ToolSpec registry**: one generic Layer-A proxy factory and
  one generic Layer-B dispatcher serve the whole catalog; adding a tool
  touches two files.
- **Sketch → GIS pipeline** (`extract_sketch_to_gis`): hand-drawn parcel
  boundary photo to geodatabase feature class via ORB+RANSAC registration
  and HSV ink segmentation.
- Mocked-arcpy test architecture (no ArcGIS or license needed), Ruff +
  strict Mypy gate, `make verify-all`, idempotent `setup_env.py` conda
  clone, CI on Ubuntu and Windows.

[Unreleased]: https://github.com/muend/arcgis-mcp-bridge/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/muend/arcgis-mcp-bridge/releases/tag/v0.5.0
