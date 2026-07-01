# Contributing to arcgis-mcp-bridge

Thank you for considering a contribution. `arcgis-mcp-bridge` is a local-first MCP bridge for ArcGIS Pro, so contributions should preserve the project's core guarantees: no `arcpy` import in Layer A, strict path validation, deterministic dependency resolution, and clean stdio JSON-RPC transport.

## Environment Setup

### Runtime / ArcGIS Pro setup

Use the packaged setup command to clone ArcGIS Pro's `arcgispro-py3` environment into a writable worker environment and install the bridge runtime dependencies into it:

```bash
pip install arcgis-mcp-bridge
arcgis-mcp-setup --install-runtime-deps
```

If you are working on the Sketch-to-GIS / OpenCV pipeline, include the vision extra:

```bash
arcgis-mcp-setup --install-runtime-deps --with-vision
```

The setup command emits a JSON report. Use its `python_exe` value as `ARCPY_PYTHON_PATH` in your MCP host configuration.

> **Windows note:** if `conda` is not on `PATH`, set `ARCGIS_CONDA_EXE` to the full path of ArcGIS Pro's `conda.exe` before running `arcgis-mcp-setup`.

### Source checkout / development setup

```bash
git clone https://github.com/muend/arcgis-mcp-bridge.git
cd arcgis-mcp-bridge
uv sync --locked --all-extras
```

If you are not using `uv`, install the development extras directly:

```bash
pip install -e ".[dev,vision]"
```

Do not use `--system-site-packages` for the Layer A development environment. Layer A must remain hermetic and must never inherit ArcGIS Pro's native site-packages. ArcPy is only resolved inside the worker interpreter referenced by `ARCPY_PYTHON_PATH`.

## Quality Gate

Run the same checks that CI enforces:

```bash
make verify-all   # ruff + mypy strict + security-audit (no arcpy needed)
python -m pytest  # 81/81 unit tests; arcpy is mocked
```

The automated suite runs without an ArcGIS installation. `tests/conftest.py` injects `MagicMock` proxies for `arcpy` and `arcpy.sa`, so CI can verify contracts, PathGuard behavior, registry invariants, worker error mapping, and configuration validation on hosted runners.

Before opening a PR, make sure:

- `ruff check .` passes.
- `mypy arcgis_mcp` passes under strict mode.
- `python -m pytest` passes.
- `make security-audit` reports a clean registry.
- `uv sync --locked` still resolves without lockfile drift.

## Versioning and Lockfile Discipline

Project versions are derived from Git tags through `setuptools-scm`. Do not add a hardcoded `version = "..."` field back into `pyproject.toml`.

If dependency metadata or build metadata changes, regenerate `uv.lock` and commit it with the related change. The lockfile must stay aligned with the dynamic versioning model so `uv sync --locked`, CI, and tagged release builds all resolve from the same metadata contract.

## Adding Tool #101

A new catalog tool should touch exactly two implementation files:

1. An input contract in `arcgis_mcp/contracts/<category>.py`.
2. A `ToolSpec` registration plus worker function in `arcgis_mcp/tools/<category>.py`.

### 1. Input contract — `arcgis_mcp/contracts/<category>.py`

```python
class MyNewToolInput(ToolInput):
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }
    in_features: str
    out_features: str
    overwrite: bool = False
    # destructive tools must also add:
    # confirm: bool = False
```

### 2. Spec + worker — `arcgis_mcp/tools/<category>.py`

```python
def _my_new_tool(arcpy: Any, inp: c.MyNewToolInput) -> dict[str, Any]:
    arcpy.analysis.MyTool(inp.in_features, inp.out_features)
    return {"output": inp.out_features}

register(
    ToolSpec(
        name="my_new_tool",
        category=Category.GEOMETRY,
        description="One sentence Claude will read as a tool description.",
        input_model=c.MyNewToolInput,
        worker_fn=_my_new_tool,
        destructive=False,
    )
)
```

If the tool mutates its input or appends to live data, set `destructive=True` and add `confirm: bool = False` to the model. The registry refuses to register a destructive spec without a confirm gate.

## Safety and Architecture Rules

- Layer A must never import `arcpy`, `cv2`, or other ArcGIS/native runtime dependencies at module import time.
- All filesystem-touching inputs must declare their role in `path_fields` as `read`, `write`, or `read_list`.
- Every path must pass through the shared PathGuard enforcement path in both Layer A and Layer B.
- Destructive tools must require `confirm=true`.
- Worker stdout must remain reserved for the final NDJSON response frame. Diagnostics belong on stderr or in the configured log file.
- Tool descriptions should be short, concrete, and useful to an MCP host selecting tools.

## Commit Convention

```text
feat:     new tool or capability
fix:      bug fix
docs:     documentation only
refactor: no behavior change
test:     test additions
chore:    CI, tooling, deps
build:    packaging, lockfile, or release-build metadata
```

Examples:

```text
feat: add zonal geometry validator
fix: classify PathGuard rejection as security error
docs: update Claude Desktop setup guide
build: regenerate uv.lock for setuptools-scm dynamic versioning
```

## Good First Issues

Check [issues](https://github.com/muend/arcgis-mcp-bridge/issues) for `good first issue` labels. Current useful contribution areas:

- Integration-style tests with mocked `arcpy` for individual catalog tools.
- ArcGIS Pro 3.4+ compatibility reports.
- Windows path edge cases in PathGuard.
- Small example projects and reproducible demo datasets.
- Documentation improvements for Claude Desktop, Cursor, and other MCP hosts.

## Code of Conduct

Be respectful and constructive. Abusive PRs/issues will be closed.
