# mcp-apic-deploy-http: HTTP-transport MCP server bundling the apic Linux CLI.
# Everything (CLI, credentials, product YAMLs, config) lives in the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APIC_MCP_HOST=0.0.0.0 \
    APIC_MCP_PORT=8765

# Tools the apic CLI may shell out to (curl, ca-certs).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# apic CLI + working files live under /opt/apic (matches config.properties).
RUN mkdir -p /opt/apic
COPY assets/apic /opt/apic/apic
COPY assets/credentials.json /opt/apic/credentials.json
COPY assets/branches_1.0.0.yaml /opt/apic/branches_1.0.0.yaml
COPY assets/branchesmock_1.0.0.yaml /opt/apic/branchesmock_1.0.0.yaml
RUN chmod +x /opt/apic/apic \
    && /opt/apic/apic --accept-license --live-help=false

COPY server.py config.properties ./

EXPOSE 8765
CMD ["python", "server.py"]
