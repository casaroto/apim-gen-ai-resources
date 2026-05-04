# MCP Spectral API Tests

FastMCP server that runs Stoplight Spectral with the OpenAPI ruleset and the OWASP API Security 2023 ruleset.

## Tools

- `spectral_version`: returns the Spectral CLI version.
- `spectral_lint_api`: runs Spectral against a local OpenAPI file.
- `spectral_lint_api_file`: runs Spectral against OpenAPI YAML/JSON content posted directly to the MCP tool.
- `spectral_lint_default_branchesmock`: runs the bundled default test target, `branchesmock_1.0.0.yaml`.

## Local Run

```bash
uv run python server.py
```

The default MCP transport is `stdio`, which is the transport used by Codex.

## Container Run

```bash
docker build -t spectral-api-tests-mcp:latest .
docker run --rm -i spectral-api-tests-mcp:latest
```

The container also uses MCP `stdio`, so it is suitable for Codex registration through `docker run --rm -i`.

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
