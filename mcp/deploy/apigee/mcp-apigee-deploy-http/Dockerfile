# mcp-apigee-deploy-http: HTTP-transport MCP server for the Apigee Admin API.
# Wraps the upstream ag2-mcp-servers/apigee-api project in streamable-http mode.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APIGEE_MCP_HOST=0.0.0.0 \
    APIGEE_MCP_PORT=8765 \
    CONFIG_PATH=/app/config/mcp_config.json

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG APIGEE_API_REF=main
RUN git clone --depth 1 --branch ${APIGEE_API_REF} \
        https://github.com/ag2-mcp-servers/apigee-api.git /app/upstream \
    && pip install --no-cache-dir /app/upstream \
    && pip install --no-cache-dir "uvicorn>=0.31.0"

# Upstream main.py has a typo (UnsuportedSecurityStub) that newer ag2 fixed.
# Rewrite the import + references so the server boots against current ag2.
RUN sed -i 's/UnsuportedSecurityStub/UnsupportedSecurityStub/g' \
        /app/upstream/mcp_server/main.py

# Google's OAuth2 security scheme isn't recognized by autogen.mcp.mcp_proxy, so
# every Apigee operation registers an UnsupportedSecurityStub. Without this
# patch, HTTPBearer params (BEARER_TOKEN) never match and tool calls fail with
# 'does not match any given security'. Patch the stub to accept HTTPBearer
# params; HTTPBearer.Parameters.apply already injects the Authorization header.
RUN printf '%s\n' \
    'from autogen.mcp.mcp_proxy import security as _sec' \
    'def _stub_accept(self, params):' \
    '    return isinstance(params, _sec.HTTPBearer.Parameters)' \
    '_sec.UnsupportedSecurityStub.accept = _stub_accept' \
    '' \
    > /tmp/_security_patch.py \
    && cat /tmp/_security_patch.py /app/upstream/mcp_server/main.py \
       > /tmp/main_patched.py \
    && mv /tmp/main_patched.py /app/upstream/mcp_server/main.py

COPY config/ /app/config/
COPY extra_tools.py run_server.py /app/upstream/mcp_server/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default mount point for proxy bundles passed to apigee_import_proxy_bundle.
# Override at run time with `-v /local/dir:/opt/apigee:ro,Z`.
RUN mkdir -p /opt/apigee
ENV APIGEE_BUNDLE_DIR=/opt/apigee

EXPOSE 8765
CMD ["/app/entrypoint.sh"]
