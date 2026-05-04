# IBM API Connect (APIC) Mode

Read this when the user mentions IBM APIC, IBM API Connect, or apic. The goal is to produce an OpenAPI 3.0.3 yaml that API Connect's developer portal and gateway will accept directly.

## What APIC adds on top of vanilla OpenAPI

API Connect requires three things a vanilla spec doesn't have:

1. **`x-ibm-name`** at the document root — the slug used to identify the API.
2. **`x-ibm-configuration`** at the document root — the gateway/runtime configuration: properties, security definitions, CORS, gateway type, assembly (the policy chain that runs on requests).
3. **`security` schemes** that match APIC's expected forms — typically client-id/client-secret pairs delivered as headers, plus optional OAuth2.

Operations themselves stay normal OpenAPI; the platform-specific bits live at the document root.

## Required additions

### `x-ibm-name`
Slug derived from the API title, lowercase, hyphens. E.g., title "Crypto Operations API" → `x-ibm-name: crypto-operations-api`.

### `x-ibm-configuration` block

Emit this block at the document root:

```yaml
x-ibm-configuration:
  enforced: true
  testable: true
  phase: realized
  cors:
    enabled: true
  gateway: datapower-api-gateway
  type: rest
  properties:
    target-url:
      value: http://localhost:3000
      description: Backend service URL
      encoded: false
  catalogs: {}
  activity-log:
    enabled: true
    success-content: activity
    error-content: payload
  application-authentication:
    certificate: false
  assembly:
    execute:
      - invoke:
          version: 2.0.0
          title: invoke
          header-control:
            type: blocklist
            values: []
          parameter-control:
            type: allowlist
            values: []
          target-url: $(target-url)$(request.path)$(request.search)
          follow-redirects: false
          timeout: 60
          verb: keep
          cache-response: protocol
          cache-ttl: 900
          stop-on-error: []
```

Adjust:
- `gateway`: `datapower-api-gateway` is the modern default. Use `datapower-gateway` only if the user explicitly says they're on the v5-compatible gateway.
- `target-url.value`: this must come from one of three places — (1) a sibling spec's `servers[0].url`, (2) the user's explicit instruction, or (3) the default `http://localhost:3000`. **Do not invent a production-looking URL** (e.g., `https://api.example.com`, `https://api.<company>.com`). If you don't have a real value, keep `http://localhost:3000` and add `# TODO: set real backend target URL`.
- `assembly.execute`: a single `invoke` to the backend is the safe default. If the user has provided a more elaborate flow (e.g., rate-limit then invoke then transform), include those policies; otherwise stick to `invoke` and don't invent.

Also: don't add an `x-ibm-endpoints` block, an `x-ibm-configuration.servers` block, or any other endpoint-listing extension on top of the standard root `servers` array — they're redundant with `servers` and easy to fill with invented URLs.

### Security schemes

APIC typically expects `clientIdHeader` + `clientSecretHeader` as an API-key pair. Add to `components.securitySchemes`:

```yaml
clientIdHeader:
  type: apiKey
  in: header
  name: X-IBM-Client-Id
clientSecretHeader:
  type: apiKey
  in: header
  name: X-IBM-Client-Secret
```

And at the document root (or per-operation):

```yaml
security:
  - clientIdHeader: []
    clientSecretHeader: []
```

If the route file's auth detection turned up something else (bearer JWT, OAuth2), keep the detected scheme **in addition** — APIC supports layered security. Note in a comment that the bearer/OAuth scheme is the application-level auth on top of APIC's client-id gating.

## What to keep unchanged

Operations (`paths`), schemas, response definitions — leave these as the default workflow produces. APIC doesn't require operation-level extensions for basic deployment.

## Things not to do

- **Don't invent assembly policies** the user didn't ask for (rate-limit, jwt-validate, gatewayscript, etc.). The single `invoke` default is correct for a baseline spec.
- **Don't hard-code a real production target URL.** Use the `$(target-url)` property reference so the URL is environment-configurable.
- **Don't drop the bearer/JWT auth** the route file actually uses. Layer it; don't replace it.
- **Don't add `x-ibm-*` extensions on every operation.** They live at the document root.

## Confidence

The fields above are the minimum APIC accepts in practice. If the user has a specific APIC catalog/space configuration, organization properties, or assembly requirements, ask before adding — those are deployment-specific and easy to get wrong. When unsure about a field's exact form, emit it with `# TODO: verify against APIC docs / your catalog` rather than guessing.
