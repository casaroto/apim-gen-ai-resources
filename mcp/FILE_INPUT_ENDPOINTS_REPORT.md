# MCP File Input Endpoints Report

Date: 2026-05-04

## Goal

Confirm that each MCP server under `mcp/` has a way to receive file content directly through an MCP tool or HTTP endpoint, then add missing file-content tools, register the changed MCPs, and test the result.

## Inventory

| MCP | Existing file path support | Direct file-content support after this work |
| --- | --- | --- |
| IBM API Connect deploy | `apic_set_credentials`, `apic_publish_product`, `apic_deploy_product` | `apic_set_credentials_file`, `apic_publish_product_file`, `apic_deploy_product_file` |
| Apigee deploy | `apigee_import_proxy_bundle`, `apigee_deploy_proxy_bundle` | `apigee_import_proxy_bundle_file`, `apigee_deploy_proxy_bundle_file` |
| Kong deploy | `kong_apply_openapi` | `kong_apply_openapi_file` |
| WSO2 deploy | `wso2_import_openapi` | `wso2_import_openapi_file` |
| Postman/Newman tests | `newman_run_api_tests` | Already existed: `newman_run_api_tests_file`; HTTP `POST /api-tests/openapi` |
| Spectral tests | `spectral_lint_api` | Already existed: `spectral_lint_api_file` |

## Changes Made

### IBM API Connect

Updated `mcp/deploy/ibm-apic/mcp-apic-deploy-http/server.py`.

Added tools:

- `apic_set_credentials_file`: accepts credentials JSON content, writes it to a temporary file, runs `apic client-creds:set`, then removes the temporary file.
- `apic_publish_product_file`: accepts product YAML content, writes it to a temporary file, runs `apic products:publish`, then removes the temporary file.
- `apic_deploy_product_file`: accepts product YAML content and optionally credentials JSON content, writes temporary files, runs the full deploy flow, then removes the temporary files.

Updated `mcp/deploy/ibm-apic/mcp-apic-deploy-http/README.md` with examples.

### Apigee

Updated `mcp/deploy/apigee/mcp-apigee-deploy-http/extra_tools.py`.

Added tools:

- `apigee_import_proxy_bundle_file`: accepts a base64-encoded ZIP bundle, writes it to a temporary file, imports it through the Apigee Admin API, then removes the temporary file.
- `apigee_deploy_proxy_bundle_file`: accepts a base64-encoded ZIP bundle, imports it, deploys the returned revision, and stops on the first failed step.

Updated `mcp/deploy/apigee/mcp-apigee-deploy-http/README.md` with examples.

### Kong

Updated `mcp/deploy/kong/mcp-kong-deploy-http/server.py`.

Added tool:

- `kong_apply_openapi_file`: accepts OpenAPI YAML/JSON content directly, parses it in memory, and deploys the API as a Kong Service and Route.

Updated `mcp/deploy/kong/mcp-kong-deploy-http/README.md` with examples.

### WSO2

Updated `mcp/deploy/wso2/mcp-wso2-deploy-http/server.py`.

Added tool:

- `wso2_import_openapi_file`: accepts OpenAPI YAML/JSON content directly, writes it to a temporary file for the WSO2 import API, then removes the temporary file.

Updated `mcp/deploy/wso2/mcp-wso2-deploy-http/README.md` with examples.

## Registrations

Registered temporary HTTP MCP entries for validation:

```text
apic-deploy-http-file-test    http://localhost:8785/mcp
apigee-deploy-http-file-test  http://localhost:8786/mcp
kong-deploy-http-file-test    http://localhost:8780/mcp
wso2-deploy-http-file-test    http://localhost:8767/mcp
```

Alternate ports were used for APIC and Kong because `8765` and `8770` were already occupied by `gvproxy`.

Existing registered test MCPs:

```text
postman-newman-api-tests-http  http://localhost:8772/mcp
spectral-api-tests-http        http://localhost:8771/mcp
```

## Verification

Syntax check:

```bash
python3 -m py_compile \
  mcp/deploy/ibm-apic/mcp-apic-deploy-http/server.py \
  mcp/deploy/kong/mcp-kong-deploy-http/server.py \
  mcp/deploy/wso2/mcp-wso2-deploy-http/server.py \
  mcp/deploy/apigee/mcp-apigee-deploy-http/extra_tools.py
```

Result: passed.

Behavioral checks:

- APIC: `apic_deploy_product_file` was tested with a fake `apic` executable. It wrote posted product and credentials content to temp files and executed the expected four steps: `set_credentials`, `login`, `set_catalog`, `publish_product`.
- Kong: `kong_apply_openapi_file` was tested with a mocked Kong Admin API request function. It parsed posted OpenAPI content and issued the expected service and route upserts.
- WSO2: `wso2_import_openapi_file` was tested with mocked WSO2 login/import calls. It wrote posted OpenAPI content to a temp file available during import.
- Apigee: `apigee_deploy_proxy_bundle_file` was tested with a mocked Apigee HTTP call. It decoded base64 ZIP content, imported the temp bundle, and deployed the returned revision.

Live MCP tool-list checks:

```text
apic   tool_count=8   file tools: apic_deploy_product_file, apic_publish_product_file, apic_set_credentials_file
kong   tool_count=8   file tools: kong_apply_openapi_file
wso2   tool_count=10  file tools: wso2_import_openapi_file
apigee tool_count=19  file tools: apigee_deploy_proxy_bundle_file, apigee_import_proxy_bundle_file
```

Spectral:

- `spectral_lint_api_file` already existed and remains documented.
- `http://localhost:8771/mcp` returned `406` to plain `curl`, which is expected for MCP Streamable HTTP without MCP headers.

Postman/Newman:

- `newman_run_api_tests_file` already existed.
- HTTP `POST /api-tests/openapi` already existed.
- The registered HTTP endpoint on `8772` was not running during this validation, so no live HTTP call was made for Postman/Newman.

## Notes

- The new file-content tools are additive; existing path-based tools were preserved.
- Temporary files are removed after each tool call.
- Binary Apigee ZIP bundles are accepted as base64 content because MCP tool arguments are JSON.
- Real end-to-end deployment still requires valid platform credentials and live API manager/gateway targets.
