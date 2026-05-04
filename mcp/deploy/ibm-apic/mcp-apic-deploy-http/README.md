# IBM API Connect Deploy MCP HTTP Server

HTTP MCP server for deploying IBM API Connect products with the `apic` CLI.

The server runs in a container, exposes MCP Streamable HTTP on `/mcp`, and bundles the Linux `apic` binary, product YAML files, credentials file, and deployment config.

## Tools

- `apic_set_credentials`: runs `apic client-creds:set`.
- `apic_login`: logs in to API Connect.
- `apic_set_catalog`: sets the active API Connect catalog.
- `apic_publish_product`: publishes a product YAML to a catalog.
- `apic_deploy_product`: runs the full deploy flow: set credentials, login, set catalog, and publish product.
- `apic_set_credentials_file`: sets client credentials from JSON content supplied directly to the MCP tool.
- `apic_publish_product_file`: publishes a product from YAML content supplied directly to the MCP tool.
- `apic_deploy_product_file`: runs the full deploy flow from product YAML content, optionally with credentials JSON content.

## Endpoints

When the container is running, the MCP endpoint is:

```text
http://localhost:8765/mcp
```

Health check:

```text
http://localhost:8765/healthz
```

## Required Configuration

Before building and running this MCP server, fill in the deployment values in:

- [`config.properties`](config.properties): API Connect server, username, password, realm, catalog URL, catalog name, default product file, and TLS behavior.
- [`assets/credentials.json`](assets/credentials.json): IBM API Connect toolkit endpoints, client IDs, client secrets, and cloud ID required by the `apic` CLI.

The deploy flow depends on those files. If either file keeps placeholder or empty values, the MCP server can start, but `apic_login`, `apic_publish_product`, and `apic_deploy_product` will not deploy successfully.

Important `config.properties` fields:

```properties
apic_binary_path=/opt/apic/apic
working_dir=/opt/apic
credentials_file=credentials.json
server=
username=
password=
realm=provider/default-idp-2
catalog_url=
catalog_name=
default_product_file=branches_1.0.0.yaml
insecure_skip_tls_verify=true
```

`insecure_skip_tls_verify=true` prepends `--insecure-skip-tls-verify` to `apic` invocations. For production, prefer installing the trusted CA chain in the image and setting this to `false`.

## Build And Run

Build:

```bash
cd /path/to/mcp/deploy/ibm-apic/mcp-apic-deploy-http
podman build --platform linux/amd64 -t apic-deploy-http:latest .
```

Run:

```bash
podman run -d --name apic-deploy-http -p 8765:8765 apic-deploy-http:latest
```

Logs:

```bash
podman logs -f apic-deploy-http
```

Stop:

```bash
podman rm -f apic-deploy-http
```

## MCP Registration

Claude registration:

```bash
claude mcp add --transport http --scope user apic-deploy-http http://localhost:8765/mcp
```

After registration, call the tools through the MCP client. For example:

```text
Use apic_deploy_product on the apic-deploy-http server to publish branches_1.0.0.yaml.
```

After `config.properties` and `assets/credentials.json` are completed, zero-argument calls can use the values baked into the image.

## Tool Arguments

`apic_login` accepts:

- `server`
- `username`
- `password`
- `realm`

`apic_set_catalog` accepts:

- `catalog_url`

`apic_publish_product` accepts:

- `product_file`
- `catalog_name`
- `scope`, default `catalog`

`apic_deploy_product` accepts any of the values above and falls back to `config.properties` for omitted fields.

## File Content Tools

Use these tools when the MCP client should send the file content directly instead of referring to a file already inside the container.

Set credentials from JSON content:

```json
{
  "credentials_json": "{\n  \"cloud_id\": \"...\",\n  \"toolkit\": {\n    \"endpoint\": \"...\",\n    \"client_id\": \"...\",\n    \"client_secret\": \"...\"\n  }\n}",
  "file_name": "credentials.json"
}
```

Publish product YAML content:

```json
{
  "product_yaml": "product: 1.0.0\ninfo:\n  name: branches\n  version: 1.0.0\n",
  "file_name": "branches_1.0.0.yaml",
  "catalog_name": "sandbox",
  "scope": "catalog"
}
```

Deploy product YAML content in one flow:

```json
{
  "product_yaml": "product: 1.0.0\ninfo:\n  name: branches\n  version: 1.0.0\n",
  "product_file_name": "branches_1.0.0.yaml",
  "credentials_json": "{\n  \"cloud_id\": \"...\"\n}",
  "server": "https://api-manager.example.com",
  "username": "org1",
  "password": "<password>",
  "realm": "provider/default-idp-2",
  "catalog_url": "https://api-manager.example.com/api/catalogs/org1/sandbox",
  "catalog_name": "sandbox"
}
```

## Runtime Configuration

Environment variables:

- `APIC_MCP_HOST`: bind host. Defaults to `0.0.0.0`.
- `APIC_MCP_PORT`: bind port. Defaults to `8765`.
- `APIC_MCP_CONFIG`: path to the config file. Defaults to `/app/config.properties` inside the image.
- `APIC_MCP_LOG_LEVEL`: Python logging level. Defaults to `INFO`.

## Notes

- The bundled `apic` binary is Linux x86-64, so the image is built with `--platform linux/amd64`.
- The `apic` license is accepted at image build time.
- Secrets in `credentials.json` and `config.properties` are copied into the image. For production, inject them at runtime with secrets or mounts instead.
- The HTTP MCP endpoint is unauthenticated. Keep it bound locally or protect it behind an authenticated proxy if exposed.

## Remove

```bash
claude mcp remove apic-deploy-http -s user
podman rm -f apic-deploy-http
podman rmi localhost/apic-deploy-http:latest
```
