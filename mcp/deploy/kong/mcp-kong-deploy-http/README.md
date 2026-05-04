# Kong Deploy MCP HTTP Server

HTTP MCP server for deploying APIs to Kong Gateway through the Kong Admin API.

The server exposes MCP Streamable HTTP on `/mcp` and provides tools to upsert Kong Services and Routes directly, or to deploy an OpenAPI file as a Service and Route pair.

## Tools

- `kong_get_status`: checks Kong node status with `GET /status`.
- `kong_list_services`: lists Kong Services.
- `kong_list_routes`: lists all routes, or routes for a specific service.
- `kong_apply_service`: upserts a Kong Service by name.
- `kong_apply_route`: upserts a Kong Route for a service.
- `kong_delete_service`: deletes a Kong Service and its routes.
- `kong_apply_openapi`: reads an OpenAPI spec and deploys it as a Service and Route.
- `kong_apply_openapi_file`: deploys OpenAPI YAML/JSON content supplied directly to the MCP tool.

## Endpoints

When the container is running, the MCP endpoint is:

```text
http://localhost:8770/mcp
```

Health check:

```text
http://localhost:8770/healthz
```

## Required Configuration

Set Kong Admin API connection values in [`config.properties`](config.properties), or override them with environment variables.

Important fields:

```properties
admin_url=http://host.containers.internal:8001
admin_token=
request_timeout=30.0
working_dir=/opt/kong
default_service_name=books-service
default_upstream_url=http://backend:3000
default_route_path=/books-api
```

`admin_token` is optional for Kong OSS. For Kong Enterprise or Konnect gateways that require an admin token, set it in `config.properties` or with `KONG_ADMIN_TOKEN`.

## Build And Run

Build:

```bash
cd /path/to/mcp/deploy/kong/mcp-kong-deploy-http
docker build -t kong-deploy-http:latest .
```

Run:

```bash
docker run -d --name kong-deploy-http -p 8770:8770 kong-deploy-http:latest
```

If you need to deploy OpenAPI files from the host, mount them into `/opt/kong`:

```bash
docker run -d --name kong-deploy-http -p 8770:8770 \
  -v "$PWD:/opt/kong:ro" \
  kong-deploy-http:latest
```

Logs:

```bash
docker logs -f kong-deploy-http
```

Stop:

```bash
docker rm -f kong-deploy-http
```

## MCP Registration

Codex registration:

```bash
codex mcp add kong-deploy-http --url http://localhost:8770/mcp
```

Equivalent config:

```toml
[mcp_servers.kong-deploy-http]
url = "http://localhost:8770/mcp"
```

## Tool Usage

Check connectivity to Kong:

```text
kong_get_status
```

Create or update a service:

```json
{
  "name": "books-service",
  "upstream_url": "http://backend:3000"
}
```

Create or update a route:

```json
{
  "name": "books-route",
  "service": "books-service",
  "paths": ["/books-api"],
  "strip_path": true
}
```

Deploy an OpenAPI spec:

```json
{
  "spec_file": "server.openapi.yaml",
  "upstream_url": "http://backend:3000",
  "service_name": "books-service",
  "route_name": "books-route",
  "route_path": "/books-api",
  "strip_path": true
}
```

`spec_file` can be an absolute path inside the container or a path relative to `working_dir`, which defaults to `/opt/kong`.

Deploy OpenAPI content directly:

```json
{
  "openapi_file": "openapi: 3.0.0\ninfo:\n  title: Books API\n  version: 1.0.0\nservers:\n  - url: /books-api\npaths: {}\n",
  "file_name": "server.openapi.yaml",
  "upstream_url": "http://backend:3000",
  "service_name": "books-service",
  "route_name": "books-route",
  "route_path": "/books-api"
}
```

## Runtime Configuration

Environment variables:

- `KONG_MCP_HOST`: bind host. Defaults to `0.0.0.0`.
- `KONG_MCP_PORT`: bind port. Defaults to `8770`.
- `KONG_MCP_CONFIG`: path to `config.properties`. Defaults to `/app/config.properties` inside the image.
- `KONG_MCP_LOG_LEVEL`: Python logging level. Defaults to `INFO`.
- `KONG_ADMIN_URL`: overrides `admin_url`.
- `KONG_ADMIN_TOKEN`: overrides `admin_token`.

## Notes

- `kong_apply_openapi` reads the OpenAPI `info.title`, `info.version`, and `servers[0].url` to derive defaults when explicit service or route values are omitted.
- The HTTP MCP endpoint is unauthenticated. Keep it local or put it behind an authenticated proxy if exposed.
- `host.containers.internal` is useful when Kong Admin API is published on the host and the MCP server runs in a container.

## Remove

```bash
codex mcp remove kong-deploy-http
docker rm -f kong-deploy-http
docker rmi kong-deploy-http:latest
```
