#!/usr/bin/env sh
set -e

# MCP_SETTINGS is consumed by the upstream main.py and forwarded to FastMCP.
# We use it to bind host/port for streamable-http transport.
export MCP_SETTINGS="${MCP_SETTINGS:-{\"host\":\"${APIGEE_MCP_HOST}\",\"port\":${APIGEE_MCP_PORT}}}"

# Inject the bearer token into MCPProxy via the SECURITY env var. main.py calls
# BaseSecurity.parse_security_parameters_from_env after load_configuration, so
# this overrides the literal "BEARER_TOKEN" placeholder in mcp_config.json.
# Operator must export BEARER_TOKEN to a Google OAuth access token, e.g.
#   podman run -e BEARER_TOKEN="$(gcloud auth print-access-token)" ...
if [ -n "${BEARER_TOKEN}" ] && [ -z "${SECURITY}" ]; then
    export SECURITY="{\"type\":\"http\",\"schema_parameters\":{\"scheme\":\"bearer\"},\"value\":\"${BEARER_TOKEN}\"}"
fi

cd /app/upstream/mcp_server
exec python run_server.py
