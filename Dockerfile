FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    ARCPY_PYTHON_PATH=/usr/local/bin/python \
    ARCGIS_MCP_ALLOWED_ROOTS=/tmp/arcgis-mcp \
    ARCGIS_MCP_SCRATCH_GDB=/tmp/arcgis-mcp/scratch.gdb \
    ARCGIS_MCP_LOG_LEVEL=INFO \
    ARCGIS_MCP_MAX_WORKERS=1

RUN mkdir -p /tmp/arcgis-mcp/scratch.gdb

COPY pyproject.toml README.md ./
COPY arcgis_mcp ./arcgis_mcp

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

CMD ["arcgis-mcp-server"]
