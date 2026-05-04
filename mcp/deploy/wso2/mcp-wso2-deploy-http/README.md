# WSO2 Deploy MCP HTTP Server

HTTP MCP server for deploying and testing APIs in WSO2 API Manager 4.x.

The server exposes MCP Streamable HTTP and wraps the WSO2 Publisher, DevPortal, Dynamic Client Registration, OAuth2, and gateway endpoints.

## Tools

- `wso2_login`: performs Dynamic Client Registration and OAuth2 password grant, then caches the token in memory.
- `wso2_import_openapi`: imports a local OpenAPI file and creates a WSO2 API.
- `wso2_import_openapi_file`: imports OpenAPI YAML/JSON content supplied directly to the MCP tool.
- `wso2_deploy_revision`: creates and deploys an API revision to a gateway environment.
- `wso2_publish_api`: transitions an API from `CREATED` to `PUBLISHED`.
- `wso2_create_subscription`: creates or finds an application, subscribes it to the API, and generates production keys.
- `wso2_get_access_token`: gets an OAuth2 client credentials token for invoking the API.
- `wso2_invoke_api`: invokes the deployed API through the WSO2 gateway.
- `wso2_list_apis`: lists APIs in the Publisher, optionally filtered by query.
- `wso2_delete_api`: undeploys revisions and deletes the API.

## Endpoint

When the server is running, the MCP endpoint is:

```text
http://localhost:8767/mcp
```

This endpoint expects an MCP Streamable HTTP client.

## Required Configuration

Configuration is provided through environment variables:

- `WSO2_BASE_URL`: WSO2 management URL. Defaults to `https://localhost:9443`.
- `WSO2_GW_URL`: WSO2 gateway URL. Defaults to `https://localhost:8243`.
- `WSO2_USERNAME`: WSO2 username. Defaults to `admin`.
- `WSO2_PASSWORD`: WSO2 password. Defaults to `admin`.
- `WSO2_MCP_PORT`: MCP HTTP port. Defaults to `8767`.

HTTPS certificate verification is disabled in the client because local WSO2 API Manager setups commonly use self-signed certificates.

## Run Locally

```bash
cd /path/to/mcp/deploy/wso2/mcp-wso2-deploy-http
uv run python server.py
```

With explicit WSO2 connection values:

```bash
WSO2_BASE_URL=https://localhost:9443 \
WSO2_GW_URL=https://localhost:8243 \
WSO2_USERNAME=admin \
WSO2_PASSWORD=admin \
WSO2_MCP_PORT=8767 \
uv run python server.py
```

## MCP Registration

Codex registration:

```bash
codex mcp add wso2-deploy-http --url http://localhost:8767/mcp
```

Equivalent config:

```toml
[mcp_servers.wso2-deploy-http]
url = "http://localhost:8767/mcp"
```

## Tool Usage

Login:

```json
{
  "username": "admin",
  "password": "admin",
  "base_url": "https://localhost:9443"
}
```

Import an OpenAPI file:

```json
{
  "name": "BooksAPI",
  "version": "1.0.0",
  "context": "/books",
  "openapi_path": "/path/to/server.openapi.yaml",
  "target_endpoint": "http://localhost:3000"
}
```

Import OpenAPI content directly:

```json
{
  "name": "BooksAPI",
  "version": "1.0.0",
  "context": "/books",
  "openapi_file": "openapi: 3.0.0\ninfo:\n  title: Books API\n  version: 1.0.0\npaths: {}\n",
  "file_name": "server.openapi.yaml",
  "target_endpoint": "http://localhost:3000"
}
```

Deploy a revision:

```json
{
  "api_id": "<api-id>",
  "gateway_env": "Default"
}
```

Publish the API:

```json
{
  "api_id": "<api-id>"
}
```

Create a subscription and generate production keys:

```json
{
  "api_id": "<api-id>",
  "app_name": "default-app",
  "tier": "Unlimited"
}
```

Get an invoke token from the generated keys:

```json
{
  "consumer_key": "<consumer-key>",
  "consumer_secret": "<consumer-secret>",
  "scope": "default"
}
```

Invoke the deployed API:

```json
{
  "api_id": "<api-id>",
  "path": "/",
  "method": "GET",
  "access_token": "<access-token>"
}
```

List APIs:

```json
{
  "query": "name:BooksAPI"
}
```

Delete an API:

```json
{
  "api_id": "<api-id>"
}
```

## Typical Deploy Flow

1. `wso2_login`
2. `wso2_import_openapi` or `wso2_import_openapi_file`
3. `wso2_deploy_revision`
4. `wso2_publish_api`
5. `wso2_create_subscription`
6. `wso2_get_access_token`
7. `wso2_invoke_api`

## Development

Run tests:

```bash
uv run pytest
```

## Notes

- The server stores the current WSO2 access token only in process memory.
- `wso2_login` resets the cached client and token when called with new credentials.
- `wso2_delete_api` attempts to undeploy active revisions before deleting the API.
- The HTTP MCP endpoint is unauthenticated. Keep it local or protect it if exposed.
