#!/usr/bin/env python3
"""Generate the MCP static server card and sync manifest.json tools.

This server's real tools execute against a licensed ArcGIS Pro runtime that no
scanner has, so Smithery cannot auto-enumerate the catalog. Both the static
server card (URL-published path) and the MCPB manifest tool list (local bundle
path) are generated here from the declarative registry. Importing
`arcgis_mcp.tools` registers every ToolSpec WITHOUT importing arcpy (Layer A is
arcpy-free by construction), so generation is deterministic, offline, and needs
zero ArcGIS dependency.

Usage (from repo root):
    PYTHONPATH=. python scripts/generate_server_card.py
Outputs:
    .well-known/mcp/server-card.json   (static server card, all 100 tools)
    manifest.json                      (tools[] array synced in place)
"""

from __future__ import annotations

import json
from pathlib import Path

import arcgis_mcp.tools  # noqa: F401  side-effect: populates the registry
from arcgis_mcp import registry

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_JSON = REPO_ROOT / "server.json"
CARD_PATH = REPO_ROOT / ".well-known" / "mcp" / "server-card.json"
MANIFEST_PATH = REPO_ROOT / "manifest.json"


def _server_meta() -> tuple[str, str]:
    data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    return data["title"], data["version"]


def _described(spec: registry.ToolSpec) -> str:
    d = spec.description
    if spec.destructive:
        d += " [Destructive: requires confirm=true.]"
    return d


def _card_tool(spec: registry.ToolSpec) -> dict[str, object]:
    schema = spec.input_model.model_json_schema()
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": schema.get("properties", {}),
    }
    if "required" in schema:
        input_schema["required"] = schema["required"]
    if "$defs" in schema:
        input_schema["$defs"] = schema["$defs"]
    annotations = {
        "destructiveHint": spec.destructive,
        "openWorldHint": False,  # all tools operate on local GIS data only
    }
    if spec.name.startswith(("get_", "list_", "describe_")):
        annotations["readOnlyHint"] = True
    output_schema = {
        "type": "object",
        "description": (
            "Structured result frame: tool-specific fields on success, or a "
            "classified error object (validation/security/license/"
            "geoprocessing/internal) on failure."
        ),
        "additionalProperties": True,
    }
    return {
        "name": spec.name,
        "title": spec.name.replace("_", " ").title(),
        "description": _described(spec),
        "inputSchema": input_schema,
        "outputSchema": output_schema,
        "annotations": annotations,
    }


def _sorted_specs() -> list[registry.ToolSpec]:
    return sorted(registry.all_specs(), key=lambda s: (s.category.value, s.name))


def write_server_card() -> None:
    title, version = _server_meta()
    card = {
        "serverInfo": {"name": title, "version": version},
        "authentication": {"required": False},
        "tools": [_card_tool(s) for s in _sorted_specs()],
        "resources": [],
        "prompts": [],
    }
    CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    CARD_PATH.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {CARD_PATH.relative_to(REPO_ROOT)} - {len(card['tools'])} tools, v{version}.")


def sync_manifest_tools() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # manifest.json must stay MCPB-schema valid: `mcpb pack` rejects any key
    # other than name/description in tools[]. Full inputSchema entries live in
    # server-card.json and are injected into the bundle by build_smithery_bundle.py.
    manifest["tools"] = [
        {"name": s.name, "description": _described(s)} for s in _sorted_specs()
    ]
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Synced manifest.json tools - {len(manifest['tools'])} entries.")


def main() -> None:
    write_server_card()
    sync_manifest_tools()


if __name__ == "__main__":
    main()
