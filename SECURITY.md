# Security Policy

## Supported Versions

We actively monitor and patch security vulnerabilities. Since `arcgis-mcp-bridge` directly interacts with local ArcGIS Pro Python environments (`arcpy`) and processes live LLM contexts via Model Context Protocol (MCP), we strongly recommend always running the latest release from PyPI.

| Version | Supported          |
| ------- | ------------------ |
| v0.5.x  | :white_check_mark: |
| < v0.5.0  | :x:                |

## Scope of Security Responsibility

Due to the nature of bridging Local GIS Workflows and Cloud-based LLMs, please ensure:
1. **API Secret Masking:** Never hardcode your `ANTHROPIC_API_KEY` or custom MCP credentials within your ArcGIS Pro scripts or workspace directories. Use environment variables.
2. **Spatial Data Privacy:** Be cautious when exposing tools that allow the LLM to query local File Geodatabases (`.gdb`) or Enterprise SDE paths containing sensitive infrastructure or personal data.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.** Instead, please use GitHub's **Private Vulnerability Reporting** feature to submit a secure advisory directly to the maintainer.

### Our Process Once Reported:
1. The maintainer will acknowledge your report within 48 hours and coordinate a private workspace on GitHub to assess the vulnerability.
2. A fix will be developed and validated against supported `arcpy` environment structures.
3. A patched release will be pushed to PyPI, and a security advisory will be published to credit your contribution to the community.
