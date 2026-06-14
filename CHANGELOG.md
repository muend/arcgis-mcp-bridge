# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

## [0.6.0] — 2026-06-14

### Added

- **uv ecosystem**: committed `uv.lock`, a `uv sync --locked` install path, and
  a CI `uv-locked-gate` job that validates the lockfile on Python 3.11 + 3.12.
- **`arcgis-mcp-setup --install-runtime-deps`** (with `--with-vision` /
  `--project-root`): provisions the cloned worker interpreter with the bridge's
  runtime dependencies so `-m arcgis_mcp.worker` imports without a manual step.
- **Startup fail-fast on a missing scratch geodatabase**:
  `Settings.from_environment` raises a clear `ConfigError` instead of failing
  cryptically deep inside a worker.
- **81 unit tests** (up from 6): PathGuard, Pydantic contracts, generic
  `apply_path_guard` + `register` invariants, worker error-kind mapping, and
  `Settings.from_environment` validation.
- **Packaging pipeline**: a CI `build-dist` job builds the wheel + sdist and
  smoke-tests them in a clean environment; a tag-triggered `release.yml`
  publishes to PyPI via Trusted Publishing (OIDC, no stored token).

### Changed

- `__version__` now derives from installed package metadata
  (`importlib.metadata`) — a single source of truth that can no longer drift
  from `pyproject.toml`.
- MCP `serverInfo.version` now reports the project version (previously the
  `mcp` library version, e.g. 1.27.2).
- Tightened dependency bounds: `fastmcp>=3.4,<4`, `mcp>=1.27.2,<2`,
  `pydantic>=2.5,<3`.
- arcpy is now opaque to mypy (`follow_imports="skip"` +
  `follow_imports_for_stubs=true`), fixing a local-only crash on machines with
  ArcGIS Pro installed (PEP 695 stubs under a py311 target).
- Path B install docs now create a hermetic dev venv (dropped
  `--system-site-packages`) to keep ArcGIS site-packages out of the test gates.

### Removed

- Unused direct dependencies `fastapi` and `uvicorn` — the stdio server never
  imported them; they arrive transitively via `fastmcp` when needed.

### Fixed

- Documentation corrections: vision extra dependencies, `ARCGIS_MCP_ALLOWED_ROOTS`
  optionality, the "ten verticals" count, and the `execution.py` cwd/PYTHONPATH
  docstring.

[0.6.0]: https://github.com/muend/arcgis-mcp-bridge/compare/v0.5.1...v0.6.0

## [0.5.1] — 2026-06-13

### Fixed

- `__init__.__version__` string `0.1.0`'dan `0.5.1`'e hizalandı.
- `CITATION.cff` sürümü `pyproject.toml` ile eşleştirildi.
- `SECURITY.md` desteklenen sürüm tablosu gerçek versiyon şemasına düzeltildi.

[0.5.1]: https://github.com/muend/arcgis-mcp-bridge/compare/v0.5.0...v0.5.1

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
