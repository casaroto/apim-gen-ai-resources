# Spectral MCP Report

## Setup

- Created FastMCP server: `technology/spectral/mcp-spectral-api-tests/server.py`
- Installed global Spectral CLI: `@stoplight/spectral-cli@6.15.1`
- Installed local npm dependencies:
  - `@stoplight/spectral-cli@6.15.1`
  - `@stoplight/spectral-owasp-ruleset@2.0.1`
- Configured `.spectral.yaml` with:
  - `spectral:oas`
  - `@stoplight/spectral-owasp-ruleset`

## MCP Tools

- `spectral_version`
- `spectral_lint_api`
- `spectral_lint_api_file`
- `spectral_lint_default_branchesmock`

## Test Target

`/Users/casaroto/projetos/technology/apic/mcp-apic-deploy-http/assets/branchesmock_1.0.0.yaml`

## Results

- Spectral version: `6.15.1`
- Exit code: `1`
- Passed: `false`
- Total findings: `82`
- Severity summary:
  - Errors: `13`
  - Warnings: `69`
  - Info: `0`
  - Hints: `0`

## Findings By Rule

| Count | Rule |
| ---: | --- |
| 12 | `owasp:api4:2023-rate-limit-responses-429` |
| 12 | `owasp:api8:2023-define-error-responses-401` |
| 12 | `owasp:api8:2023-define-error-responses-500` |
| 6 | `operation-description` |
| 6 | `operation-operationId` |
| 6 | `operation-tags` |
| 6 | `owasp:api8:2023-define-error-validation` |
| 6 | `owasp:api4:2023-rate-limit` |
| 6 | `owasp:api4:2023-string-limit` |
| 6 | `owasp:api4:2023-string-restricted` |
| 1 | `info-contact` |
| 1 | `info-description` |
| 1 | `owasp:api9:2023-inventory-access` |
| 1 | `oas3-unused-component` |

## Validation

- Direct Spectral CLI run completed and returned JSON findings.
- Python wrapper run completed with `finding_count=82`.
- MCP stdio protocol test listed all tools and successfully called:
  - `spectral_version`
  - `spectral_lint_default_branchesmock`
- Codex registration validated with:
  - `codex mcp list`
  - `codex mcp get spectral-api-tests`

## Codex Registration

Host server registered in `/Users/casaroto/.codex/config.toml`:

```toml
[mcp_servers.spectral-api-tests]
command = "uv"
args = ["run", "python", "server.py"]
cwd = "/Users/casaroto/projetos/technology/spectral/mcp-spectral-api-tests"
```

## Container Version

Built a containerized MCP variant using `technology/apic/mcp-apic-deploy-http/Dockerfile` as the packaging reference.

Files added:

- `Dockerfile`
- `.dockerignore`
- `requirements.txt`
- `assets/branchesmock_1.0.0.yaml`
- `tests/smoke_stdio.py`

Image:

- Name: `spectral-api-tests-mcp:latest`
- Image id: `sha256:11559210fd750b3db40c55af7627ecdd725ec356abf03ed788fa59c1ba99b6b2`
- Size: `137197536` bytes
- Architecture: `arm64`

Container internals:

- MCP transport: `stdio`
- Default API path: `/app/assets/branchesmock_1.0.0.yaml`
- Ruleset path: `/app/.spectral.yaml`
- Spectral binary: `/app/node_modules/.bin/spectral`

Build command:

```bash
docker build -t spectral-api-tests-mcp:latest .
```

Codex container registration:

```toml
[mcp_servers.spectral-api-tests-container]
command = "docker"
args = ["run", "--rm", "-i", "spectral-api-tests-mcp:latest"]
```

Container validation:

- `docker run --rm spectral-api-tests-mcp:latest ./node_modules/.bin/spectral --version`
  returned `6.15.1`.
- `uv run python tests/smoke_stdio.py`
  listed all three MCP tools and called `spectral_lint_default_branchesmock`.
- Direct in-container Python call returned:
  - `passed=false`
  - `returncode=1`
  - `finding_count=82`
  - `summary={"error": 13, "warn": 69, "info": 0, "hint": 0}`
- `codex mcp list` and `codex mcp get spectral-api-tests-container`
  show the container MCP as enabled.

Issue found and fixed:

- First container MCP test failed with `IndexError` because `/app/server.py` does not have enough parent directories for the host-only `SERVER_DIR.parents[1]` path calculation.
- Fixed `server.py` by making the host fallback defensive and using `SPECTRAL_DEFAULT_API_PATH=/app/assets/branchesmock_1.0.0.yaml` inside the container.

## Streamable HTTP Container Version

Built a Streamable HTTP container variant for Codex URL-based MCP registration.

Files added:

- `Dockerfile.http`
- `tests/smoke_http.py`

Image:

- Name: `spectral-api-tests-mcp-http:latest`
- Image id: `sha256:808a407bcb982aaacec3f8fea8fb951b038a2f07997f0d2880fe685d1f0ddb43`
- Size: `137196665` bytes
- Architecture: `arm64`

Container runtime:

```bash
docker run -d --name spectral-api-tests-mcp-http -p 8771:8771 spectral-api-tests-mcp-http:latest
```

Running container:

- Name: `spectral-api-tests-mcp-http`
- Port: `0.0.0.0:8771->8771/tcp`
- MCP URL: `http://localhost:8771/mcp`

Codex HTTP registration:

```toml
[mcp_servers.spectral-api-tests-http]
url = "http://localhost:8771/mcp"
```

Codex validation:

- `codex mcp add spectral-api-tests-http --url http://localhost:8771/mcp`
- `codex mcp get spectral-api-tests-http`
- `codex mcp list`

Codex reports:

- transport: `streamable_http`
- url: `http://localhost:8771/mcp`
- status: `enabled`

HTTP MCP validation:

- `uv run python tests/smoke_http.py`
  listed all three MCP tools and successfully called:
  - `spectral_version`
  - `spectral_lint_default_branchesmock`
  - `spectral_lint_api_file`
- Result from the HTTP container:
  - Spectral version: `6.15.1`
  - `passed=false`
  - `returncode=1`
  - `api_path=/app/assets/branchesmock_1.0.0.yaml`
  - `ruleset_path=/app/.spectral.yaml`
  - `finding_count=82`
  - `summary={"error": 13, "warn": 69, "info": 0, "hint": 0}`

Observation:

- Plain `curl http://localhost:8771/mcp` returns `406 Not Acceptable` because the Streamable HTTP endpoint requires MCP-compatible headers and an event-stream-capable client. This is expected. The official MCP `streamablehttp_client` succeeds.

## Posted API File Tool

Added `spectral_lint_api_file` to allow clients to post OpenAPI YAML/JSON content directly instead of passing a filesystem path.

Signature:

```python
def spectral_lint_api_file(
    api_file: str,
    file_name: str = "openapi.yaml",
    ruleset_path: str | None = None,
    fail_severity: str = "error",
) -> dict[str, Any]
```

Implementation notes:

- Validates that `api_file` is non-empty.
- Preserves parser inference by using the suffix from `file_name`; defaults to `.yaml`.
- Writes the posted content to a temporary file for the Spectral CLI invocation.
- Deletes the temporary file after the lint run.
- Returns the same response shape as `spectral_lint_api`, plus `api_file_name`.

Validation:

- Direct Python call against posted `branchesmock_1.0.0.yaml` content returned:
  - `passed=false`
  - `returncode=1`
  - `api_file_name=branchesmock_1.0.0.yaml`
  - `finding_count=82`
  - `summary={"error": 13, "warn": 69, "info": 0, "hint": 0}`
- Rebuilt images:
  - `spectral-api-tests-mcp:latest`: `sha256:9a3eaa3c42698de600670be410028a99a6d7439435da0eeb22f0b2286756726d`
  - `spectral-api-tests-mcp-http:latest`: `sha256:8674d6b72e225385b939e7729f0524c1f49957c9a9ef93428c15035f3c277178`
- Restarted `spectral-api-tests-mcp-http` on port `8771`.
- `tests/smoke_stdio.py` and `tests/smoke_http.py` both list `spectral_lint_api_file` and successfully call it with posted YAML content.
