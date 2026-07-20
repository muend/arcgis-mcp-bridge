# ArcGIS Pro runtime benchmark

This directory separates mocked CI coverage from evidence produced by a real,
licensed ArcGIS Pro runtime. The benchmark is intentionally small: it proves the
MCP-to-worker pipeline, a non-mutating ArcPy call, a new-output write, follow-up
inspection, PathGuard rejection, and the destructive confirmation gate.

It does **not** claim that all catalog tools, ArcGIS extensions, platforms, or
data-dependent geoprocessing workflows have been validated.

## Safety contract

- Run only against a dedicated, existing allowed root and scratch file GDB.
- The harness sets one allowed root and `ARCGIS_MCP_MAX_WORKERS=1`.
- Read-only mode never creates a GIS dataset.
- `--write-check` creates one uniquely named, empty WGS 84 point feature class.
- The harness never requests overwrite and never sends `confirm=true`.
- The unconfirmed-delete case must fail; the created artifact is retained.
- Published JSON replaces all configured local paths with placeholders.

## Run it

Install the bridge into an isolated host environment. Ensure the ArcGIS Pro
worker interpreter can import both `arcpy` and `arcgis_mcp.worker`, then run:

```powershell
python -m benchmarks.arcgis_pro_smoke `
  --arcpy-python "C:\Path\To\arcgispro-py3\python.exe" `
  --allowed-root "C:\ArcGISBench" `
  --scratch-gdb "C:\ArcGISBench\scratch.gdb" `
  --source-commit "$(git rev-parse HEAD)" `
  --arcgis-pro-version "3.7" `
  --expected-tool-count 103 `
  --write-check `
  --output "benchmarks\results\local.json"
```

Omit `--write-check` for the four-case read-only condition. A passing write-
safety run contains eight cases:

1. exact tool-surface discovery;
2. server-to-worker `health_check`;
3. ArcPy-backed WGS 84 spatial-reference lookup;
4. PathGuard rejection of an existing path outside the declared root;
5. creation of a uniquely named empty point feature class;
6. description of the created dataset;
7. a zero-row feature count;
8. rejection of `delete_dataset` with `confirm=false`.

Exit code `0` means every case matched its expected outcome, `1` means one or
more cases failed, and `2` means configuration or execution could not start.

## Result contract and interpretation

[`schema.json`](schema.json) is the machine-readable result contract. Results
report simple unweighted case counts. Per-call wall time includes ArcPy worker
startup and is retained for diagnostics only; one host run is not a performance
comparison. Do not pool results across ArcGIS Pro, bridge, FastMCP, Python, or
hardware versions.

The committed result in [`results/`](results/) is maintainer-generated evidence
for its exact declared environment and source commit. Reproduce it before making
claims about a different installation.
