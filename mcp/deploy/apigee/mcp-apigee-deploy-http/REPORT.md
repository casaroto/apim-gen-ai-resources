# mcp-apigee-deploy-http

HTTP-transport MCP server for the Apigee Admin API, packaged as a container.
Wraps the upstream [ag2-mcp-servers/apigee-api](https://github.com/ag2-mcp-servers/apigee-api)
(auto-generated from the Apigee OpenAPI spec) and runs it in `streamable-http`
mode behind port 8765, mirroring the layout of `mcp-apic-deploy-http`.

## Layout

```
mcp-apigee-deploy-http/
├── Dockerfile
├── entrypoint.sh
├── config.properties        # operator notes (env vars, not loaded at runtime)
├── config/
│   └── mcp_config.json      # MCPProxy config: server URL, auth, exposed ops
└── REPORT.md
```

The upstream Python package is installed during image build via
`git clone` + `pip install`, pinned with the `APIGEE_API_REF` build arg.

## Build

```sh
docker build -t mcp-apigee-deploy-http .
```

Pin a specific upstream commit:

```sh
docker build --build-arg APIGEE_API_REF=<sha> -t mcp-apigee-deploy-http .
```

## Run

```sh
docker run --rm -p 8765:8765 \
  -e BEARER_TOKEN="$(gcloud auth print-access-token)" \
  mcp-apigee-deploy-http
```

The MCP endpoint is then reachable at `http://localhost:8765/mcp`.

## Configuration

- **Auth** — Apigee uses Google OAuth. Set `BEARER_TOKEN` to a fresh access
  token (`gcloud auth print-access-token`). Tokens expire in ~1 hour.
- **Server URL** — `https://apigee.googleapis.com` (set in `mcp_config.json`).
- **Operations exposed** — see `operations[]` in `config/mcp_config.json`.
  The full Apigee surface has hundreds of endpoints; this config curates a
  publish/deploy subset (proxies, products, developers, environments,
  deployments). Add more by appending to the array and rebuilding.
- **Organization** — is *not* baked into the config; it's a path parameter on
  each tool call (e.g. `organization=orgs/<your-org>`).

## Differences from `mcp-apic-deploy-http`

| | mcp-apic-deploy-http | mcp-apigee-deploy-http |
|---|---|---|
| Backing CLI | `apic` Linux binary, bundled in image | none — direct HTTPS to Apigee API |
| Tool source | hand-written `server.py` | auto-generated proxy from OpenAPI |
| Auth | username/password/realm via `apic login` | Google OAuth bearer token |
| Working dir | `/opt/apic` (holds bundle YAMLs) | n/a — bundles uploaded via signed URL |
| Tool count | 5 hand-picked | configurable, ~10 curated by default |

## Caveats

- Upstream is auto-generated and labeled "Beta" — verify each tool's behavior
  against the [Apigee REST reference](https://cloud.google.com/apigee/docs/reference/apis/apigee/rest)
  before relying on it.
- The upstream ships a placeholder `mcp_config.json` pointed at
  `events.1password.com`; we override it via `CONFIG_PATH`.
- Bearer tokens are short-lived. For long-running deployments, mount a token
  refresher or use a service-account-backed sidecar.
