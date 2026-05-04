# Apigee Deploy MCP HTTP Server

HTTP MCP server for the Apigee Admin API, packaged as a container.

This server wraps the upstream [`ag2-mcp-servers/apigee-api`](https://github.com/ag2-mcp-servers/apigee-api) package and runs it with MCP Streamable HTTP transport. It also adds custom tools for API proxy ZIP bundle upload and deployment, because the generated upstream tools do not handle multipart uploads.

## Tools

Generated Apigee tools are curated in [`config/mcp_config.json`](config/mcp_config.json). The configured operations include API proxy, API product, developer, app, shared flow, and deployment helper operations.

Custom deploy tools:

- `apigee_import_proxy_bundle`: imports an Apigee API proxy ZIP bundle and returns the new revision.
- `apigee_import_proxy_bundle_file`: imports an Apigee API proxy ZIP bundle from base64 content supplied directly to the MCP tool.
- `apigee_deploy_proxy_revision`: deploys a proxy revision to an environment.
- `apigee_undeploy_proxy_revision`: undeploys a proxy revision from an environment.
- `apigee_get_proxy_deployment`: gets deployment status for a proxy revision.
- `apigee_list_envgroup_hostnames`: lists environment group hostnames for an organization.
- `apigee_deploy_proxy_bundle`: imports a ZIP bundle and deploys the returned revision in one flow.
- `apigee_deploy_proxy_bundle_file`: imports a base64 ZIP bundle and deploys the returned revision in one flow.

## Endpoint

When the container is running, the MCP endpoint is:

```text
http://localhost:8765/mcp
```

This endpoint expects an MCP Streamable HTTP client.

## Required Configuration

Apigee uses Google OAuth. Set `BEARER_TOKEN` at runtime:

```bash
export BEARER_TOKEN="$(gcloud auth print-access-token)"
```

Tokens are short-lived, usually around one hour, so refresh the token before restarting the container or before long deploy sessions.

The Apigee organization is not baked into the config. Pass it as a tool argument, for example:

```json
{
  "organization": "my-apigee-org"
}
```

## Build And Run

Build:

```bash
cd /path/to/mcp/deploy/apigee/mcp-apigee-deploy-http
docker build -t mcp-apigee-deploy-http .
```

Run:

```bash
docker run -d --name mcp-apigee-deploy-http -p 8765:8765 \
  -e BEARER_TOKEN="$(gcloud auth print-access-token)" \
  mcp-apigee-deploy-http
```

If you need to deploy local proxy ZIP bundles, mount a bundle directory into `/opt/apigee`:

```bash
docker run -d --name mcp-apigee-deploy-http -p 8765:8765 \
  -e BEARER_TOKEN="$(gcloud auth print-access-token)" \
  -v "$PWD/bundles:/opt/apigee:ro" \
  mcp-apigee-deploy-http
```

Then pass `bundle_file` as a file name relative to `/opt/apigee`, or pass an absolute path inside the container.

Logs:

```bash
docker logs -f mcp-apigee-deploy-http
```

Stop:

```bash
docker rm -f mcp-apigee-deploy-http
```

## MCP Registration

Codex registration:

```bash
codex mcp add apigee-deploy-http --url http://localhost:8765/mcp
```

Equivalent config:

```toml
[mcp_servers.apigee-deploy-http]
url = "http://localhost:8765/mcp"
```

## Tool Usage

Import and deploy a proxy bundle in one call:

```json
{
  "organization": "my-apigee-org",
  "environment": "test",
  "name": "book-backend-demo",
  "bundle_file": "book-backend-demo.zip",
  "override": true
}
```

Import and deploy a proxy bundle from base64 content:

```json
{
  "organization": "my-apigee-org",
  "environment": "test",
  "name": "book-backend-demo",
  "bundle_file_base64": "<base64-encoded zip>",
  "file_name": "book-backend-demo.zip",
  "override": true
}
```

Generate the base64 payload from a local bundle:

```bash
base64 -i book-backend-demo.zip
```

Deploy a known revision:

```json
{
  "organization": "my-apigee-org",
  "environment": "test",
  "name": "book-backend-demo",
  "revision": "1",
  "override": true
}
```

List environment group hostnames:

```json
{
  "organization": "my-apigee-org"
}
```

Custom tool responses use this shape:

```json
{
  "ok": true,
  "status_code": 200,
  "body": {}
}
```

The full deploy flow returns `steps` and stops on the first failed step.

## Runtime Configuration

Runtime configuration is handled through environment variables and [`config/mcp_config.json`](config/mcp_config.json). [`config.properties`](config.properties) is an operator note file and is not loaded directly by the server.

Environment variables:

- `BEARER_TOKEN`: required Google OAuth access token.
- `APIGEE_MCP_HOST`: bind host. Defaults to `0.0.0.0`.
- `APIGEE_MCP_PORT`: bind port. Defaults to `8765`.
- `CONFIG_PATH`: path to the MCP proxy config. Defaults to `/app/config/mcp_config.json`.
- `MCP_SETTINGS`: JSON forwarded to FastMCP.
- `APIGEE_BUNDLE_DIR`: bundle lookup directory. Defaults to `/opt/apigee`.
- `APIGEE_API_BASE`: Apigee API base URL. Defaults to `https://apigee.googleapis.com`.
- `APIGEE_HTTP_TIMEOUT`: HTTP timeout in seconds. Defaults to `120`.

## Operations Configuration

The upstream Apigee API surface has many endpoints. This server exposes a curated subset from `operations[]` in [`config/mcp_config.json`](config/mcp_config.json).

To expose more generated Apigee operations:

1. Add operation entries to `config/mcp_config.json`.
2. Rebuild the image.
3. Restart the container.

## Notes

- The upstream Apigee MCP package is generated from the Apigee OpenAPI spec. Verify critical tool behavior against the official Apigee REST reference before production use.
- Google OAuth bearer tokens expire; use a refreshed token or a service-account-backed token flow for long-running use.
- The HTTP MCP endpoint is unauthenticated. Keep it local or put it behind an authenticated proxy if exposed.

## Remove

```bash
codex mcp remove apigee-deploy-http
docker rm -f mcp-apigee-deploy-http
docker rmi mcp-apigee-deploy-http
```
