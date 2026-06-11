"""setup_env.py — backward-compatibility shim (repo-root entry point).

The setup automation now lives inside the package as
``arcgis_mcp.setup_env`` so the PyPI install can expose it as the
``arcgis-mcp-setup`` console script. This shim keeps the documented
git-clone workflow (``python setup_env.py``) working unchanged.

Prefer one of:
    arcgis-mcp-setup                  # after `pip install arcgis-mcp-bridge`
    python -m arcgis_mcp.setup_env    # from a source checkout
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling package importable when run from a bare checkout
# (no `pip install -e .` yet) — the whole point of this shim.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcgis_mcp.setup_env import main

if __name__ == "__main__":
    raise SystemExit(main())
