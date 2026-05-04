# Implementation Report — `apic-deploy-http` MCP Server (HTTP / containerized)

**Date:** 2026-04-29
**Author:** Claude (Opus 4.7)
**Source server:** [`mcp-apic-deploy/server.py`](../mcp-apic-deploy/server.py) (stdio variant — kept untouched)
**Project root:** `/Users/casaroto/projetos/technology/apic/mcp-apic-deploy-http/`

## Goal

Take the existing stdio MCP server that wraps the IBM API Connect publish flow and ship a second variant exposed over **HTTP (MCP Streamable HTTP transport)**, packaged as a self-contained container image. Image bundles the apic Linux CLI (`technology/apic/cli_linux/apic`), credentials, product YAMLs, and config so the container is ready to deploy with no host mounts.

The original stdio server (`mcp-apic-deploy/`) is unchanged and still registered.

## What was built

### Container image: `apic-deploy-http:latest` (417 MB)

`Dockerfile` (Python 3.12-slim base):
- Installs `ca-certificates`, `curl`.
- `pip install -r requirements.txt` → `mcp==1.27.0`, `uvicorn==0.32.0`, `starlette==0.41.3`.
- Copies `cli_linux/apic` (123 MB, statically-linked Linux x86-64 ELF) to `/opt/apic/apic`, plus `credentials.json`, `branches_1.0.0.yaml`, `branchesmock_1.0.0.yaml`.
- Runs `apic --accept-license --live-help=false` once at build time so the license prompt is permanently dismissed in the image.
- Copies `server.py` and `config.properties`.
- `EXPOSE 8765`; `CMD ["python", "server.py"]`.

Built for `linux/amd64` (the apic Linux binary is x86-64; container runs under podman QEMU emulation on the M-series Mac).

### Server: `server.py`

- Same 5 MCP tools as the stdio variant, same JSON return shape:
  `apic_set_credentials`, `apic_login`, `apic_set_catalog`, `apic_publish_product`, `apic_deploy_product`.
- Transport: **MCP Streamable HTTP** (`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`) mounted on `/mcp` in a Starlette app, served by uvicorn on `:8765`. Stateless mode; JSON responses (no SSE).
- `/healthz` route for container liveness.
- New config knob `insecure_skip_tls_verify=true` — when set, prepends `--insecure-skip-tls-verify` to every apic invocation. Required because the slim Debian base does not trust the IBM Cloud cert chain that macOS Keychain accepts.
- Password redaction, 120 s subprocess timeout, structured-error returns — all inherited from the stdio version.

### Config: `config.properties`

Container-internal paths:
```
apic_binary_path=/opt/apic/apic
working_dir=/opt/apic
credentials_file=credentials.json
server=…getnet-api-…appdomain.cloud
username=org1
password=***
realm=provider/default-idp-2
catalog_url=…/api/catalogs/org1/Getnet
catalog_name=getnet
default_product_file=branches_1.0.0.yaml
insecure_skip_tls_verify=true
```

### Tests

- [`tests/smoke_http.py`](tests/smoke_http.py) — connects via the MCP `streamablehttp_client`, performs `initialize` → `tools/list` → `tools/call apic_set_credentials`. Passes.
- [`tests/e2e_deploy.py`](tests/e2e_deploy.py) — calls `apic_deploy_product` with no args. **All 4 steps green; `branches:1.0.0` published.**

### Registration

```
claude mcp add --transport http --scope user apic-deploy-http http://localhost:8765/mcp
```
`claude mcp list` shows `apic-deploy-http: http://localhost:8765/mcp (HTTP) - ✓ Connected`.

## Verification evidence

| Check | Result |
| --- | --- |
| `podman build` | image `localhost/apic-deploy-http:latest` (417 MB) built |
| `curl http://localhost:8765/healthz` | `{"ok":true,"service":"apic-deploy-http"}` |
| `tests/smoke_http.py` | 5 tools listed, `set_credentials` returns `ok=true` |
| `tests/e2e_deploy.py` | `ok=true`, all 4 steps succeed, product **state: published** |
| `claude mcp list` | `apic-deploy-http: ✓ Connected` (HTTP) |
| `claude mcp get apic-deploy-http` | Status: ✓ Connected, Type: http |

Final published product URL (latest run):
`…/api/catalogs/134c1f7c-…/products/30019f25-2f95-43d6-b6a2-869bfa7446c5`

## Issues encountered & fixes

1. **License prompt blocked first apic invocation.**
   First `apic` call inside the container hit `Do you accept the license? [Y/N]` and exited 1.
   *Fix:* `RUN /opt/apic/apic --accept-license --live-help=false` in the Dockerfile so the acceptance is baked into the image.

2. **TLS chain to IBM Cloud not trusted by Debian's CA bundle.**
   `apic login` exited 1 with *"You must provide a CA certificate to verify the server identity."* macOS apic uses Keychain, which trusts the chain; the slim Debian image does not.
   *Fix:* added `insecure_skip_tls_verify` config flag (default `true` in the container config). When set, `--insecure-skip-tls-verify` is prepended to every apic invocation. A stricter alternative would be mounting the corporate root CA into `/etc/ssl/certs/`, but the user asked for self-contained.

## Files produced

```
mcp-apic-deploy-http/
├── Dockerfile                      multi-stage = no; single-stage Python 3.12-slim
├── .dockerignore
├── requirements.txt                mcp 1.27.0, uvicorn 0.32.0, starlette 0.41.3
├── server.py                       Streamable HTTP MCP server, /mcp + /healthz
├── config.properties               container-internal paths + IBM Cloud creds
├── REPORT.md                       this file
├── assets/
│   ├── apic                        Linux x86-64 CLI (copied from cli_linux/)
│   ├── credentials.json
│   ├── branches_1.0.0.yaml
│   └── branchesmock_1.0.0.yaml
└── tests/
    ├── smoke_http.py
    └── e2e_deploy.py
```

## How to use it

Before building and running this MCP server, fill in the deployment values in:

- [`config.properties`](config.properties) — set the API Connect server, username, password, catalog URL, catalog name, and any other environment-specific values.
- [`assets/credentials.json`](assets/credentials.json) — set the IBM API Connect toolkit endpoints, client IDs, client secrets, and cloud ID required by the `apic` CLI.

The deploy flow depends on those files. If either file keeps the placeholder or empty values, the MCP tools can start, but `apic_login`, `apic_publish_product`, and `apic_deploy_product` will not be able to deploy successfully.

From a Claude Code session, the same five tools are available under the new server:

- "Use `apic_deploy_product` on the `apic-deploy-http` server to publish `branches_1.0.0.yaml`."
- "Run `apic_publish_product` with `product_file=branchesmock_1.0.0.yaml`."

After those values are filled, zero-argument calls work because the completed config is baked into the image at build time.

### Lifecycle

```bash
# build
cd /Users/casaroto/projetos/technology/apic/mcp-apic-deploy-http
podman build --platform linux/amd64 -t apic-deploy-http:latest .

# run (foreground/detached)
podman run -d --name apic-deploy-http -p 8765:8765 apic-deploy-http:latest

# logs
podman logs -f apic-deploy-http

# stop / remove
podman rm -f apic-deploy-http
```

## Out of scope / future work

- **Proper TLS:** mount the IBM Cloud root CA and drop `insecure_skip_tls_verify`.
- **Native arm64 image:** rebuild apic for arm64 (or use IBM's official arm64 toolkit) to remove the QEMU emulation warning.
- **Secret hygiene:** `credentials.json` and the password are baked into the image. Production would inject them at runtime via `-v` or secrets.
- **Auth on /mcp:** the HTTP endpoint is unauthenticated. Bind to `127.0.0.1` only (as today) or front with a reverse proxy + token if exposed.

## How to remove

```bash
claude mcp remove apic-deploy-http -s user
podman rm -f apic-deploy-http
podman rmi localhost/apic-deploy-http:latest
rm -rf /Users/casaroto/projetos/technology/apic/mcp-apic-deploy-http
```
