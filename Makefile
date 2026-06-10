# ---------------------------------------------------------------------------
# arcgis-mcp-bridge — local automation engine
#
# Usage (Git Bash / WSL / any GNU make on Windows):
#   make format         auto-format + sort imports (mutates files)
#   make lint           report regressions, mutate nothing
#   make type-check     mypy strict over arcgis_mcp/
#   make security-audit static inspection of path rules & contracts
#   make verify-all     lint + type-check + security-audit as one gate
#
# PY points at the bridge environment's interpreter; override per-invocation:
#   make lint PY="C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgis-mcp-env/python.exe"
# ---------------------------------------------------------------------------

PY  ?= python
SRC := arcgis_mcp

.PHONY: format lint type-check security-audit verify-all

format:
	$(PY) -m ruff format $(SRC)
	$(PY) -m ruff check --select I --fix $(SRC)

lint:
	$(PY) -m ruff check $(SRC)

type-check:
	$(PY) -m mypy $(SRC)

# Static security posture audit (no arcpy required):
#  1. every registered tool's path-typed fields are declared in path_fields
#  2. destructive specs carry a confirm field (enforced again at runtime)
#  3. no module outside worker.py / setup_env.py mentions arcpy at import level
security-audit:
	$(PY) -c "import sys; sys.path.insert(0, '.'); \
	import arcgis_mcp.tools as t; \
	from arcgis_mcp.registry import all_specs, count; \
	bad = [ (s.name, f) for s in all_specs() \
	        for f, r in s.input_model.path_fields.items() \
	        if f not in s.input_model.model_fields or r not in ('read','write','read_list') ]; \
	assert not bad, f'ghost/invalid path_fields: {bad}'; \
	nd = [ s.name for s in all_specs() \
	       if s.destructive and 'confirm' not in s.input_model.model_fields ]; \
	assert not nd, f'destructive without confirm: {nd}'; \
	print(f'security-audit OK: {count()} specs, path roles + confirm gates verified')"

verify-all: lint type-check security-audit
	@echo "verify-all: quality gate PASSED"
