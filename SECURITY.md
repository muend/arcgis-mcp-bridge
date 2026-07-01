# Security Policy

## Supported Versions

We actively monitor and patch security vulnerabilities. Since `arcgis-mcp-bridge` directly interacts with local ArcGIS Pro Python environments (`arcpy`) and processes live LLM contexts through the Model Context Protocol (MCP), we strongly recommend always running the latest release from PyPI.

| Version  | Supported          |
| -------- | ------------------ |
| v0.6.x   | :white_check_mark: |
| < v0.6.0 | :x:                |

The current supported release line is `v0.6.x`; users should prefer the newest available patch release, currently `v0.6.1`.

## Scope of Security Responsibility

Because this project bridges local GIS workflows, licensed ArcGIS Pro runtimes, and LLM-driven tool calls, users are responsible for keeping their local execution boundary narrow and intentional:

1. **API Secret Masking:** Never hardcode `ANTHROPIC_API_KEY`, MCP host credentials, service tokens, database credentials, or other secrets inside ArcGIS Pro scripts, workspace directories, notebooks, geodatabases, or example datasets. Use environment variables or your platform’s secret-management mechanism.
2. **Spatial Data Privacy:** Be cautious when exposing tools that allow an LLM host to query local File Geodatabases (`.gdb`), Enterprise SDE connections, infrastructure datasets, cadastral data, personal data, or proprietary project work.
3. **Path Boundary Configuration:** Keep `ARCGIS_MCP_ALLOWED_ROOTS` as narrow as practical. Do not point it at broad directories such as the user home directory, system drives, synced cloud roots, or unrelated project archives.
4. **Destructive Operations:** Treat tools requiring `confirm=true` as mutating operations. Review target paths and inputs carefully before allowing append, delete, repair, field calculation, projection definition, or other state-changing geoprocessing calls.
5. **LLM Context Hygiene:** Do not paste untrusted instructions, unknown project files, or sensitive workspace listings into an MCP host session unless you are comfortable with the model using that context to select and parameterize GIS tools.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.** Instead, use GitHub's **Private Vulnerability Reporting** feature to submit a secure advisory directly to the maintainer.

### Our Process Once Reported

1. The maintainer will acknowledge the report within 48 hours and coordinate a private workspace on GitHub to assess the vulnerability.
2. A fix will be developed and validated against supported `arcpy` environment structures where applicable.
3. A patched release will be published to PyPI, and a GitHub Security Advisory will be published to document the issue and credit the reporter when appropriate.
