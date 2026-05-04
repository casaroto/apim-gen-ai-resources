# MCP Spectral API Tests

FastMCP server that runs Stoplight Spectral with the OpenAPI ruleset and the OWASP API Security 2023 ruleset.

It can run in two modes:

- `stdio`, for local or container-based MCP registration.
- `streamable-http`, for URL-based MCP clients.

## Tools

- `spectral_version`: returns the Spectral CLI version.
- `spectral_lint_api`: runs Spectral against a local OpenAPI file.
- `spectral_lint_api_file`: runs Spectral against OpenAPI YAML/JSON content posted directly to the MCP tool.
- `spectral_lint_default_branchesmock`: runs the bundled default test target, `branchesmock_1.0.0.yaml`.

## Endpoints

When running the Streamable HTTP variant, the MCP endpoint is:

```text
http://localhost:8771/mcp
```

This endpoint expects an MCP Streamable HTTP client. A plain browser or basic `curl http://localhost:8771/mcp` request may return `406 Not Acceptable`, which is expected because the request does not include the MCP-compatible headers.

## Local Run

```bash
uv run python server.py
```

The default MCP transport is `stdio`.

Codex local registration example:

```toml
[mcp_servers.spectral-api-tests]
command = "uv"
args = ["run", "python", "server.py"]
cwd = "/path/to/mcp/tests/spectral/mcp-spectral-api-tests"
```

## Tool Usage

Run the default bundled OpenAPI fixture:

```text
spectral_lint_default_branchesmock
```

Run Spectral against a local OpenAPI file:

```json
{
  "api_path": "/path/to/openapi.yaml"
}
```

Run Spectral against posted OpenAPI YAML/JSON content:

```json
{
  "api_file": "openapi: 3.0.0\ninfo:\n  title: Example API\n  version: 1.0.0\npaths: {}\n",
  "file_name": "openapi.yaml"
}
```

Optional arguments supported by lint tools:

- `ruleset_path`: custom Spectral ruleset file. Defaults to `.spectral.yaml`.
- `fail_severity`: Spectral fail threshold. Defaults to `error`.

The lint response includes:

- `passed`
- `returncode`
- `api_path`
- `ruleset_path`
- `fail_severity`
- `summary`
- `finding_count`
- `findings`
- `stderr`

## Container Run

```bash
docker build -t spectral-api-tests-mcp:latest .
docker run --rm -i spectral-api-tests-mcp:latest
```

The container also uses MCP `stdio`, so it is suitable for Codex registration through `docker run --rm -i`.

Codex container registration example:

```toml
[mcp_servers.spectral-api-tests-container]
command = "docker"
args = ["run", "--rm", "-i", "spectral-api-tests-mcp:latest"]
```

## Streamable HTTP Container Run

```bash
docker build -f Dockerfile.http -t spectral-api-tests-mcp-http:latest .
docker run -d --name spectral-api-tests-mcp-http -p 8771:8771 spectral-api-tests-mcp-http:latest
```

The HTTP MCP endpoint is:

```text
http://localhost:8771/mcp
```

Codex registration:

```bash
codex mcp add spectral-api-tests-http --url http://localhost:8771/mcp
```

Equivalent Codex config:

```toml
[mcp_servers.spectral-api-tests-http]
url = "http://localhost:8771/mcp"
```

## Configuration

Environment variables:

- `SPECTRAL_DEFAULT_API_PATH`: default OpenAPI file used by `spectral_lint_api` when `api_path` is omitted.
- `SPECTRAL_MCP_TRANSPORT`: MCP transport. Defaults to `stdio`; the HTTP container sets it to `streamable-http`.
- `SPECTRAL_MCP_PORT`: HTTP port. Defaults to `8771`.
- `SPECTRAL_TIMEOUT_SECONDS`: Spectral CLI timeout in seconds. Defaults to `60`.
- `SPECTRAL_BIN`: Spectral binary to use when `node_modules/.bin/spectral` is not available.

The default ruleset is `.spectral.yaml`, configured with:

- `spectral:oas`
- `@stoplight/spectral-owasp-ruleset`

## Notes

- The bundled default API fixture is `assets/branchesmock_1.0.0.yaml`.
- The HTTP container uses `/app/assets/branchesmock_1.0.0.yaml` as its default API path.
- The server returns Spectral findings as JSON so MCP clients can inspect rule IDs, severities, paths, and messages.
