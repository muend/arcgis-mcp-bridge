#!/usr/bin/env python3
"""Build a Smithery-publishable .mcpb bundle for arcgis-mcp-bridge.

Two validators disagree about the bundle manifest:

  * `mcpb pack` / `mcpb validate` reject any key other than name/description
    inside `tools[]` (strict MCPB manifest schema).
  * Smithery's release API (ServerCard.Tool) REQUIRES an `inputSchema` object
    on every tool, or it 400s with "expected object, received undefined".

So we pack with the MCPB-valid manifest (name+description only), then inject
the full `inputSchema` per tool — sourced from the generated server card — into
the manifest.json *inside* the packed bundle. `smithery mcp publish` reads that
manifest verbatim (it does not re-run the strict MCPB schema), so the enriched
tools reach the server and validate.

Run generate_server_card.py first (keeps server-card.json in sync), then:
    python scripts/build_smithery_bundle.py
Output:
    arcgis-mcp-bridge.mcpb   (ready for `smithery mcp publish`)
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CARD_PATH = REPO_ROOT / ".well-known" / "mcp" / "server-card.json"
OUT_BUNDLE = REPO_ROOT / "arcgis-mcp-bridge.mcpb"


def _pack(raw: Path) -> None:
    cmd = f'npx -y @anthropic-ai/mcpb pack . "{raw}"'
    print(f"$ {cmd}")
    res = subprocess.run(cmd, cwd=REPO_ROOT, shell=True)
    if res.returncode != 0 or not raw.exists():
        sys.exit("mcpb pack failed — is Node/npx installed and manifest valid?")


def _enriched_tools() -> list[dict]:
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    # ServerCard.Tool = {name, description?, inputSchema{type:'object',...}}
    return card["tools"]


def _inject(raw: Path) -> None:
    tools = _enriched_tools()
    with zipfile.ZipFile(raw, "r") as zin:
        names = zin.namelist()
        if "manifest.json" not in names:
            sys.exit("packed bundle has no manifest.json")
        manifest = json.loads(zin.read("manifest.json"))
        manifest["tools"] = tools
        with zipfile.ZipFile(OUT_BUNDLE, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "manifest.json":
                    zout.writestr(
                        "manifest.json",
                        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    )
                else:
                    zout.writestr(item, zin.read(item.filename))
    print(f"Wrote {OUT_BUNDLE.name} — {len(tools)} tools with schemas + annotations injected.")


def main() -> None:
    if not CARD_PATH.exists():
        sys.exit("Run scripts/generate_server_card.py first (server-card.json missing).")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw.mcpb"
        _pack(raw)
        _inject(raw)


if __name__ == "__main__":
    main()
