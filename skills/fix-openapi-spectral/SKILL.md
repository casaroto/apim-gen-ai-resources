---
name: fix-openapi-spectral
description: Fix OpenAPI 3.x specifications based on Stoplight Spectral and OWASP API Security findings returned by an MCP Spectral server or CLI output. Use when Codex is asked to repair, harden, or improve an OpenAPI YAML/JSON file after lint/security results such as missing operationId, tags, descriptions, security schemes, HTTPS servers, rate-limit headers, 401/429/500 responses, schema bounds, or OWASP API 2023 rule violations.
---

# Fix OpenAPI Spectral

## Workflow

1. Locate the OpenAPI spec and the Spectral findings.
2. If findings are not provided, run the available Spectral MCP tool first:
   - Prefer `spectral_lint_api_file` when the MCP server runs in a container and cannot see host paths.
   - Use `spectral_lint_api` when the MCP server can access the file path.
3. Capture the baseline count by severity and by rule.
4. Group findings by endpoint and rule before editing.
5. Fix the OpenAPI document itself. Do not silence rules unless the user explicitly asks for waivers.
6. Preserve the API contract unless a security finding requires an explicit change. Avoid inventing business fields, auth schemes, or status codes that conflict with the existing API.
7. Re-run Spectral after editing and iterate until errors are resolved or remaining findings require product decisions.
8. Run a final validation with the strictest useful threshold, ideally `fail_severity: "hint"`, to reveal warnings/hints hidden by error-only runs.
9. Report what changed, what passed, and any residual findings that need human confirmation.

## Editing Principles

- Prefer minimal, standards-compliant OpenAPI 3.x changes.
- Preserve existing path names, methods, schemas, examples, and vendor extensions unless they are clearly invalid.
- Add reusable components for repeated responses, headers, schemas, and security schemes.
- Use `$ref` to avoid repeating common error responses or rate-limit headers across operations.
- Add concise operation descriptions and tags that match the domain vocabulary already present in the spec.
- Use exact header names where the ruleset expects them, especially `Access-Control-Allow-Origin` and `Retry-After`.
- Treat OWASP `severity: 0` findings as security-critical even when they are small OpenAPI changes.
- If a fix changes runtime behavior, call it out in the final answer.

## Common Fix Strategy

Use this sequence for broad cleanup:

1. Top-level metadata:
   - Add `info.description`.
   - Add `info.contact` if an owner can be inferred; otherwise use a neutral placeholder only if acceptable in the repo.
   - Add `servers[*].x-internal: true|false`.
   - Prefer `https://` server URLs for non-local environments.
2. Components:
   - Add `components.securitySchemes` when operations are unprotected and the API is not intentionally public.
   - Add reusable `ErrorResponse`, standard error responses, CORS headers, `Retry-After`, and common rate-limit headers.
3. Operations:
   - Ensure each operation has `operationId`, `summary`, `description`, and non-empty `tags`.
   - Add `security` per operation or top-level security when appropriate.
   - Add `401`, `429`, and `500` responses where missing.
   - Add `400`, `422`, or `4XX` validation responses for operations with inputs.
   - Add required headers to direct inline success responses as well as referenced error responses.
4. Schemas:
   - Add string constraints such as `maxLength`, `enum`, `const`, `format`, or `pattern`.
   - Add numeric bounds where meaningful.
   - Add array `maxItems` where collection size should be bounded.
   - Prefer opaque string identifiers such as UUIDs when OWASP flags predictable numeric IDs; if changing ID type would break clients, stop and report the decision point.
   - Add `required` fields only when the API contract clearly implies they are required.

## Rule Reference

For concrete rule-to-fix mappings, read `references/spectral-findings.md`.

## MCP Usage Notes

When using the containerized MCP:

```python
await session.call_tool(
    "spectral_lint_api_file",
    {"api_file": openapi_text, "file_name": "openapi.yaml", "fail_severity": "hint"},
)
```

When using a host-visible MCP:

```python
await session.call_tool(
    "spectral_lint_api",
    {"api_path": "/absolute/path/openapi.yaml", "fail_severity": "hint"},
)
```

If a Spectral wrapper fails to parse successful output like `[]No results with a severity of ... found!`, treat that as no findings and fix the wrapper to parse the leading JSON value before the trailing human message.

## Final Response

Include:

- The file edited.
- The main categories of fixes.
- Spectral before/after counts if available.
- Any remaining findings and why they remain.
