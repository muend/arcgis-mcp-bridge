# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

## [0.5.0] — 2026-06-11

### Added

- **100-tool catalog** across 10 GIS verticals: map management,
  data management, geometry analysis, coordinate projection,
  raster operations, vision analytics, export/layout, editing &
  topology, network analysis, spatial statistics.
- **Two-process isolation**: Layer A (FastMCP/stdio) never imports
  arcpy. Layer B (licensed interpreter) is the only legal import
  site. A native arcpy crash kills the worker, not the server.
- **PathGuard sandbox**: every filesystem argument is fully resolved
  (symlinks, `..`, relative segments) and containment-checked against
  `ARCGIS_MCP_ALLOWED_ROOTS` in both processes independently.
- **Destructive mutation safety floor**: 10 state-mutating tools
  require explicit `confirm: true`. Gate fires before arcpy import.
- **`calculate_field` PYTHON3 mode restriction**: blocked at Layer-A
  contract boundary unless `confirm: true` is supplied.
- **`raster_calculator` expression grammar**: constrained to pure
  map-algebra — no quotes, no dunder access.
- **`extract_sketch_to_gis`**: hand-drawn sketch → GDB feature class
  via ORB+RANSAC image registration and HSV ink segmentation.
- **`ARCGIS_MCP_MAX_WORKERS` concurrency ceiling**: semaphore bounds
  live arcpy subprocesses to prevent license-seat stampede and OOM.
- **CI without ArcGIS license**: MagicMock injection runs the full
  suite on hosted runners (Ubuntu + Windows matrix).
- **Idempotent `setup_env.py`**: clones `arcgispro-py3` →
  `arcgis-mcp-env`, verifies arcpy, emits JSON report.
- Ruff `E/W/F/I/B/RUF` + mypy `strict = true` across 31 source files.

### Architecture

- Layer A: FastMCP on bridge interpreter, async semaphore dispatch,
  zero arcpy imports, lazy `lru_cache` composition root.
- Layer B: `arcgis_mcp.worker` spawned per job via
  `asyncio.create_subprocess_exec`; stdout rebound to stderr;
  single sanctioned write = final NDJSON frame.
- Declarative registry: one `ToolSpec` + one generic proxy factory
  + one generic dispatcher. Adding a tool touches two files only.
- 5-class error taxonomy:
  `validation · security · license · geoprocessing · internal`

[0.5.0]: https://github.com/muend/arcgis-mcp-bridge/releases/tag/v0.5.0
