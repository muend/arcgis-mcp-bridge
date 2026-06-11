# Contributing to arcgis-mcp-bridge

## Environment Setup

```bash
git clone https://github.com/muend/arcgis-mcp-bridge.git
cd arcgis-mcp-bridge
python setup_env.py          # clones arcgispro-py3 → arcgis-mcp-env
pip install -e ".[dev]"      # ruff, mypy, pytest, pytest-cov
```

> **Windows note:** if `conda` is not on PATH, set `ARCGIS_CONDA_EXE`
> to the full path of `conda.exe` before running `setup_env.py`.

## Quality Gate

```bash
make verify-all   # ruff + mypy strict + security-audit (no arcpy needed)
python -m pytest  # 6/6 smoke tests
```

All CI checks must pass before a PR is mergeable. The suite runs
without an ArcGIS installation — `conftest.py` injects MagicMock
proxies for `arcpy`.

## Adding Tool #101

Touches exactly **two files**:

### 1. Input contract — `arcgis_mcp/contracts/<category>.py`

```python
class MyNewToolInput(ToolInput):
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }
    in_features:  str
    out_features: str
    overwrite:    bool = False
    # destructive tools must also add:
    # confirm: bool = False
```

### 2. Spec + worker — `arcgis_mcp/tools/<category>.py`

```python
def _my_new_tool(arcpy: Any, inp: c.MyNewToolInput) -> dict:
    arcpy.analysis.MyTool(inp.in_features, inp.out_features)
    return {"output": inp.out_features}

register(ToolSpec(
    name        = "my_new_tool",
    category    = Category.GEOMETRY,
    description = "One sentence Claude will read as a tool description.",
    input_model = c.MyNewToolInput,
    worker_fn   = _my_new_tool,
    destructive = False,
))
```

> If the tool mutates its input, set `destructive=True` and add
> `confirm: bool = False` to the model. The registry refuses to
> register a destructive spec without a confirm gate.

## Commit Convention

```
feat:     new tool or capability
fix:      bug fix
docs:     documentation only
refactor: no behavior change
test:     test additions
chore:    CI, tooling, deps
```

## Good First Issues

Check [issues](https://github.com/muend/arcgis-mcp-bridge/issues)
for `good first issue` labels. Current needs:

- Integration tests with mocked arcpy for individual tools
- ArcGIS Pro 3.4 compatibility verification
- Windows path edge cases in PathGuard

## Code of Conduct

Be respectful and constructive. Abusive PRs/issues will be closed.
