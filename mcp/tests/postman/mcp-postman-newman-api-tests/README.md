# Postman/Newman API Tests MCP

FastMCP server that builds a Postman collection from an OpenAPI 3.x file, runs it with Newman, and returns a complete test report.

## Tools

- `newman_version`: returns the Newman CLI version used by the server.
- `newman_run_api_tests`: generates and runs API tests from an OpenAPI file.
- `newman_run_api_tests_file`: generates and runs API tests from OpenAPI YAML/JSON content sent directly to the MCP tool.

Generated Postman collections are saved by default in `collections/`. Override with `NEWMAN_COLLECTIONS_DIR` or the `collections_dir` argument on `newman_run_api_tests_file`.

When `NEWMAN_MCP_TRANSPORT=streamable-http`, the server also exposes:

- `GET /health`
- `POST /api-tests/openapi`

The POST endpoint accepts JSON with `api_file`, `target_url`, `authorization`, and optional Newman settings. It also accepts raw OpenAPI YAML/JSON in the body, with `Authorization` as an HTTP header and settings as query parameters.

## Example

```json
{
  "api_path": "/Users/casaroto/projetos/kong-demo/openapi-1.yaml",
  "target_url": "https://localhost:8243/books-api/1.0.0/books",
  "authorization": "Bearer <token>",
  "insecure": true
}
```

## Container

Build:

```bash
docker build -t postman-newman-api-tests-mcp:latest .
```

Run over stdio:

```bash
docker run --rm -i \
  -v "$PWD/collections:/app/collections" \
  postman-newman-api-tests-mcp:latest
```

Run over streamable HTTP:

```bash
docker run --rm --network host \
  -e NEWMAN_MCP_TRANSPORT=streamable-http \
  -v "$PWD/collections:/app/collections" \
  postman-newman-api-tests-mcp:latest
```
