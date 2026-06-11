# Contributing to arcgis-mcp-bridge

Thank you for helping turn ArcGIS Pro into a first-class MCP citizen. This
guide covers the local verification flow, commit conventions, and the exact
pipeline for adding a new tool.

## Local Verification Flow

```bash
git clone https://github.com/muend/arcgis-mcp-bridge.git
cd arcgis-mcp-bridge
python setup_env.py        # idempotent: clones arcgispro-py3 -> arcgis-mcp-env
make verify-all            # ruff lint + mypy strict + security-audit
pytest                     # mocked-arcpy suite: runs WITHOUT ArcGIS installed
```

Notes:

- `setup_env.py` never mutates the read-only `arcgispro-py3` environment; it
  clones it into `arcgis-mcp-env` and reports the resulting `python_exe`.
- The test suite injects `MagicMock` into `sys.modules["arcpy"]` via
  `tests/conftest.py` — contributors and CI runners do **not** need an ArcGIS
  license to validate changes.
- Importing `arcgis_mcp.server` has no side effects: the composition root is
  lazy (`get_runtime()`), so unit tests can import any module safely.
- `ruff check .` and `mypy .` (strict, Pydantic plugin) must both pass with
  zero findings before a PR is opened. `make verify-all` is the one-shot gate.

## Commit Conventions

Commits follow the Conventional Commits prefix discipline:

| Prefix | Use for |
|---|---|
| `feat:` | New tools, new capabilities, new configuration surface |
| `fix:` | Bug fixes, security patches, contract corrections |
| `docs:` | README, CONTRIBUTING, CHANGELOG, docstrings |
| `test:` | Test additions or restructuring |
| `chore:` | CI, packaging, tooling, dependency pins |
| `refactor:` | Behavior-preserving structural change |

Subject line in imperative mood, ≤ 72 characters; body explains *why*, not
*what*. One logical change per commit.

## Adding Tool #101 (the four-step pipeline)

The registry architecture means a new tool touches exactly two source files
plus verification — never the runtime loops in `server.py` or `worker.py`.

### 1. Contracts — `arcgis_mcp/contracts/<category>.py`

Define a frozen Pydantic v2 input model inheriting `ToolInput`. Declare every
filesystem argument in `path_fields` with its security role (`"read"`,
`"write"`, or `"read_list"`). Models producing datasets include
`overwrite: bool = False`; irreversible operations include
`confirm: bool = False` and any cross-field rules as
`model_validator(mode="after")` checks.

```python
class FrobnicateInput(ToolInput):
    in_features: str = Field(..., min_length=1)
    out_features: str = Field(..., min_length=1)
    overwrite: bool = False
    path_fields: ClassVar[dict[str, PathRole]] = {
        "in_features": "read",
        "out_features": "write",
    }
```

### 2. Tools — `arcgis_mcp/tools/<category>.py`

Write the worker function `(arcpy, inp) -> dict`. It receives the `arcpy`
module as a parameter — never import arcpy in a `tools/` module. Use the
shared `_extension()` context manager for Spatial/Network Analyst seats.

### 3. Registry — same `tools/` module

Append the spec tuple to the module's `_SPECS` registration block:
`(name, description, InputModel, worker_fn[, destructive])`. Set
`destructive=True` for anything irreversible — the registry refuses to
register a destructive spec whose model lacks a `confirm` field, and the
dispatcher gates it centrally before the arcpy import is paid.

### 4. Verify

```bash
make verify-all   # lint + mypy strict + live security audit of your spec
pytest            # registry integrity tests pick the new spec up automatically
```

Update the README census matrix (tool counts) in the same PR.

## Pull Request Checklist

- [ ] `make verify-all` passes (ruff, mypy strict, security-audit)
- [ ] `pytest` green without an ArcGIS installation
- [ ] Path-typed fields declared in `path_fields`
- [ ] Destructive operations carry a `confirm` gate
- [ ] Conventional commit prefixes
- [ ] README/CHANGELOG updated where user-visible
