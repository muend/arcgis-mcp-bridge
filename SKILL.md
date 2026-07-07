---
name: arcgis-mcp-bridge
description: "Secure local-first MCP server for ArcGIS Pro / ArcPy geoprocessing. Exposes 100 declarative ArcPy tools to MCP-compatible clients such as Claude Desktop and Cursor through stdio JSON-RPC. Use when operating local ArcGIS Pro data, running ArcPy/geoprocessing, managing geodatabases, projecting vector/raster data, running raster/network/spatial-statistics tools, exporting layouts, or building guarded agentic GIS workflows. The server isolates the MCP host from the licensed ArcPy runtime with a two-process server/worker model, PathGuard filesystem sandboxing, and explicit confirmation gates for destructive operations. Real geoprocessing requires Windows plus a licensed ArcGIS Pro environment. Triggers: ArcGIS, ArcGIS Pro, ArcPy, MCP, GIS automation, geoprocessing, .aprx, geodatabase, buffer, clip, intersect, project raster, kernel density, service area, spatial statistics, Claude Desktop, Cursor."
---

# arcgis-mcp-bridge

`arcgis-mcp-bridge` is a local-first MCP server for **ArcGIS Pro / ArcPy** geoprocessing.

It lets an MCP-compatible client call ArcPy tools through a controlled local bridge. The important part is the boundary around ArcPy: the MCP server handles validation, routing, and filesystem checks, while real geoprocessing runs in a separate ArcGIS Pro Python worker process.

This is not a hosted GIS service. It is also not a live ArcGIS Pro GUI add-in. It is meant for local, headless, repeatable ArcPy workflows where safety, clear tool contracts, and process isolation matter.

Repository:

```text
https://github.com/muend/arcgis-mcp-bridge
```

## Use this skill when

Use `arcgis-mcp-bridge` when a user wants to run controlled local ArcGIS Pro / ArcPy workflows such as:

- inspect geodatabases, feature classes, tables, rasters, and `.aprx` projects
- create, describe, copy, delete, or convert GIS datasets
- run geoprocessing tools such as buffer, clip, intersect, union, erase, dissolve, merge, spatial join, select, or near
- project vector or raster data with WKID / EPSG-based coordinate systems
- run raster operations such as slope, aspect, hillshade, raster calculator, zonal statistics, and hydrology tools
- run Network Analyst workflows such as service area, route, OD cost matrix, and closest facility
- run spatial statistics such as mean center, directional distribution, kernel density, Getis-Ord Gi* hot spots, and Global Moran's I
- manage ArcGIS Pro project maps, layers, visibility, symbology, camera extent, and layout export
- build local agentic GIS pipelines without granting the agent unrestricted filesystem access

## Do not use this skill when

Do not treat this server as:

- a cloud-hosted ArcPy runtime
- a replacement for ArcGIS Pro licensing
- a live controller for an already-open ArcGIS Pro desktop session
- an unrestricted filesystem automation tool
- a general Python execution sandbox

Real ArcPy execution requires:

- Windows
- ArcGIS Pro
- a licensed ArcPy runtime
- local GIS data
- a valid `ARCPY_PYTHON_PATH`

Cloud MCP directories can help users discover the server, inspect metadata, or run startup-style checks. They cannot run real ArcPy geoprocessing without a licensed ArcGIS Pro runtime.

## Operating model

The project uses two isolated layers.

### Layer A: MCP server

The MCP server owns the tool-facing side of the system.

It handles:

- MCP stdio / JSON-RPC communication
- tool discovery
- Pydantic input validation
- PathGuard filesystem checks
- destructive-operation confirmation gates
- async subprocess dispatch
- structured error mapping

Layer A does **not** import ArcPy.

That is intentional. ArcPy is licensed, Windows-bound, native-code dependent, and expensive to load. Keeping it out of the MCP host process makes the server easier to test and keeps ArcPy failures away from the protocol layer.

### Layer B: ArcPy worker

The worker process owns the GIS execution side.

It runs under the interpreter configured by `ARCPY_PYTHON_PATH` and is responsible for:

- importing ArcPy
- executing the selected ArcPy geoprocessing operation
- collecting ArcPy messages
- returning a structured result or structured error

The worker boundary is the main runtime isolation mechanism. If ArcPy fails inside the worker, the MCP server can report that failure without importing ArcPy itself.

## Entry point

For MCP clients and registries, the stdio command is:

```text
arcgis-mcp-server
```

The setup helper is:

```text
arcgis-mcp-setup
```

Use `arcgis-mcp-setup` to prepare or inspect the ArcGIS-capable worker environment, then use the reported Python interpreter as `ARCPY_PYTHON_PATH`.

## Installation

Install from PyPI:

```bash
pip install arcgis-mcp-bridge
```

or:

```bash
uv pip install arcgis-mcp-bridge
```

Then run:

```bash
arcgis-mcp-setup
```

The setup command reports a `python_exe` path. That path is normally the value to put in `ARCPY_PYTHON_PATH`.

## Required configuration

The required environment variable is:

```text
ARCPY_PYTHON_PATH
```

It must point to a Python interpreter that can import:

- `arcpy`
- `arcgis_mcp.worker`
- runtime dependencies such as Pydantic

Common optional variables:

```text
ARCGIS_MCP_ALLOWED_ROOTS
ARCGIS_MCP_SCRATCH_GDB
ARCGIS_MCP_MAX_WORKERS
ARCGIS_MCP_LOG_FILE
ARCGIS_MCP_LOG_LEVEL
ARCGIS_MCP_TOOL_TIMEOUT
```

Typical Windows configuration:

```text
ARCPY_PYTHON_PATH=C:\...\envs\arcgis-mcp-env\python.exe
ARCGIS_MCP_ALLOWED_ROOTS=C:\GIS\Data;C:\Workspace
ARCGIS_MCP_MAX_WORKERS=2
```

Keep `ARCGIS_MCP_ALLOWED_ROOTS` narrow. Do not expose a full drive or user home directory unless that is genuinely intended.

## MCP client configuration

For a normal PyPI installation:

```json
{
  "mcpServers": {
    "arcgis-mcp-bridge": {
      "command": "arcgis-mcp-server",
      "env": {
        "ARCPY_PYTHON_PATH": "C:\\...\\envs\\arcgis-mcp-env\\python.exe",
        "ARCGIS_MCP_ALLOWED_ROOTS": "C:\\GIS\\Data;C:\\Workspace",
        "ARCGIS_MCP_MAX_WORKERS": "2"
      }
    }
  }
}
```

For a local source checkout:

```json
{
  "mcpServers": {
    "arcgis-mcp-bridge": {
      "command": "C:\\...\\envs\\arcgis-mcp-env\\Scripts\\python.exe",
      "args": [
        "-m",
        "arcgis_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\arcgis-mcp-bridge",
        "ARCPY_PYTHON_PATH": "C:\\...\\envs\\arcgis-mcp-env\\python.exe",
        "ARCGIS_MCP_ALLOWED_ROOTS": "C:\\GIS\\Data;C:\\Workspace",
        "ARCGIS_MCP_MAX_WORKERS": "2"
      }
    }
  }
}
```

## First call

Always start with:

```text
health_check
```

Input:

```json
{}
```

`health_check` verifies the server-to-worker path without importing ArcPy. It is the safest first test after installation because it checks the MCP server, worker interpreter, allowed roots, and scratch workspace before any real geoprocessing runs.

## Tool catalog

The current catalog contains **100 ArcGIS Pro / ArcPy tools** across 10 verticals.

| Vertical | Count | Examples |
|---|---:|---|
| Map & Layer Management | 10 | list maps, list layers, add layer, visibility, symbology, zoom, save project |
| Data Management | 22 | geodatabase lifecycle, feature classes, fields, Describe, Excel, GeoJSON, CSV |
| Geometry Analysis | 23 | buffer, clip, intersect, erase, union, dissolve, merge, spatial join, near, fishnet |
| Projection & CRS | 4 | define projection, project features, project raster, inspect spatial reference |
| Raster Operations | 15 | map algebra, slope, aspect, hillshade, zonal stats, hydrology, raster conversion |
| Vision / Sketch-to-GIS | 1 | register photographed sketch and commit extracted geometry to a geodatabase |
| Export & Layout | 9 | export PDF/PNG, map frame extent, scale, text, legend, layout size |
| Editing & Topology | 7 | append, repair geometry, check geometry, delete identical, topology validation |
| Network Analysis | 4 | service area, route, OD cost matrix, closest facility |
| Spatial Statistics | 5 | mean center, directional ellipse, kernel density, hot spots, Moran's I |

Some tools require Esri extension licenses. Spatial Analyst and Network Analyst tools check out the corresponding extension through a shared license guard and check it back in after execution.

## Safety model

Every filesystem parameter in a tool contract declares its role:

```text
read
write
read_list
```

PathGuard applies those roles before the request reaches ArcPy.

It enforces:

- allowed root directories
- resolved paths rather than raw untrusted strings
- geodatabase-aware path handling
- read/write discipline
- overwrite opt-in
- rejection of traversal or out-of-root paths
- structured `security` errors for blocked requests

Destructive or state-mutating tools require explicit confirmation:

```json
{
  "confirm": true
}
```

Examples include:

```text
append_features
calculate_field
define_projection
delete_dataset
delete_field
delete_identical
extract_sketch_to_gis
near_analysis
remove_layer_from_map
repair_geometry
```

The goal is not to make autonomous GIS work risk-free. The goal is to make the boundary explicit: the agent receives a constrained tool surface instead of unrestricted access to the user's filesystem and ArcPy runtime.

## Example requests

After `health_check` succeeds, an MCP client can ask for workflows such as:

```text
List all feature classes in C:\GIS\city.gdb.
```

```text
Buffer roads by 100 meters and save the output inside my scratch geodatabase.
```

```text
Project parcels to EPSG:32635 and write the result to C:\GIS\out.gdb\parcels_utm.
```

```text
Run kernel density on incident_points with a 500 meter search radius.
```

```text
Find the 3 nearest facilities to each incident using my network dataset.
```

```text
Add the analysis output to my ArcGIS Pro project and export the layout as a PDF.
```

## Difference from live ArcGIS Pro bridges

Some ArcGIS agent integrations focus on controlling an already-open ArcGIS Pro desktop session through an add-in, socket, or live GUI bridge.

`arcgis-mcp-bridge` is different.

It does not drive the visible ArcGIS Pro UI. It focuses on headless local geoprocessing through a standalone MCP server. ArcPy is treated as an isolated execution backend, not as code imported directly into the MCP host process.

Use a live ArcGIS Pro bridge when the goal is to operate the open desktop session and watch changes happen in the ArcGIS Pro UI.

Use `arcgis-mcp-bridge` when the goal is controlled local ArcPy geoprocessing, repeatable GIS pipelines, explicit filesystem boundaries, structured tool contracts, and testable server-side orchestration.

## Testing

The test suite runs without ArcGIS Pro by mocking ArcPy.

It checks:

- Pydantic contracts
- PathGuard behavior
- registry invariants
- destructive confirmation gates
- worker error mapping
- settings and environment validation

Run:

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

Expected current result:

```text
81 passed
```

This does not mean every real-world GIS dataset and every ArcPy tool combination has been exhaustively tested. It means the server-side contracts, guards, registry, and error boundaries can be verified in CI without an ArcGIS Pro installation.

## Notes for agents

- Prefer `health_check` before real work.
- Ask for or infer a narrow allowed workspace before reading or writing GIS data.
- Do not request destructive tools unless the user clearly intends the mutation.
- Use `confirm: true` only for explicit destructive operations.
- Keep output paths inside `ARCGIS_MCP_ALLOWED_ROOTS`.
- For raster, network, and spatial-statistics tools, consider whether required Esri extensions are available.
- Treat cloud listings as discovery surfaces, not execution environments.

## Trademark and affiliation

This is an independent open-source project.

ArcGIS, ArcGIS Pro, ArcPy, and Esri are trademarks or registered trademarks of Esri. This project is not affiliated with or endorsed by Esri.
