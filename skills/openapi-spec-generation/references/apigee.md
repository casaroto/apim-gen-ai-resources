# Apigee Mode

Read this when the user mentions Apigee, Apigee Edge, or Apigee X. The goal is to produce an OpenAPI 3.0.3 yaml that can drive Apigee proxy generation (via apigeecli, the Apigee Maven plugin, or `apigee-deploy-maven-plugin`-style imports).

## What Apigee adds on top of vanilla OpenAPI

Apigee is largely vanilla-OpenAPI-friendly, but a few extensions make a spec deployment-ready:

1. **`x-google-backend`** (Apigee X / Cloud Endpoints) at the document root — points the generated proxy at the upstream service.
2. **`x-google-api-name`** / **`x-google-management`** — for naming and quota/metric definitions.
3. **API key / OAuth security** — typically expressed via `apiKey` (header `x-apikey`) and/or OAuth2 schemes that map to `VerifyAPIKey` and `OAuthV2` policies.
4. **Optional `x-apigee-*` hints** — flow hooks, target overrides per environment.

Operations themselves stay normal OpenAPI.

## Required additions

### Backend target

For Apigee X, add to the document root:

```yaml
x-google-backend:
  address: http://localhost:3000
  protocol: h2
  deadline: 60
```

Adjust:
- `address`: must come from (1) a sibling spec's `servers[0].url`, (2) the user's explicit instruction, or (3) the default `http://localhost:3000`. **Do not invent a production URL** like `https://api.example.com`. If you don't have a real value, keep the default and add `# TODO: set real backend address`.
- `protocol`: `h2` for HTTP/2 (most backends), or omit for HTTP/1.1.
- `deadline`: seconds before Apigee gives up on the backend. 60 is a safe default.

For Apigee Edge (legacy) the equivalent is set in the proxy's `TargetEndpoint.xml`, not in the OpenAPI spec — note this to the user if they're on Edge, and emit a `# Apigee Edge: target URL is configured in the proxy XML, not here` comment instead.

### Security schemes

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: x-apikey
    oauth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://YOUR-ORG.apigee.net/oauth2/token
          scopes:
            read: Read access
            write: Write access
```

Apply at the document root:

```yaml
security:
  - apiKeyAuth: []
```

If the route file's auth detection turned up bearer JWT, keep that scheme in addition — Apigee can validate the JWT via a `VerifyJWT` policy on top of `VerifyAPIKey`. Add a comment that the JWT is the application-level auth.

If the user is using `OAuthV2` (Apigee's built-in OAuth provider), use the `oauth2` scheme above and adjust `tokenUrl` to their proxy's token endpoint. Mark with `# TODO: replace YOUR-ORG and token path` if you don't know it.

### Optional: quota and metrics

If the user mentions rate limiting / quotas, add to the document root:

```yaml
x-google-management:
  metrics:
    - name: read-requests
      displayName: Read requests
      valueType: INT64
      metricKind: DELTA
  quota:
    limits:
      - name: read-limit
        metric: read-requests
        unit: 1/min/{project}
        values:
          STANDARD: 1000
```

Don't include this block unless the user asked for quota — it has no effect alone and adds noise.

## What to keep unchanged

Operations (`paths`), request bodies, schemas, response definitions — leave as the default workflow produces them.

## Things not to do

- **Don't invent flow hooks or policy attachments** (`x-apigee-flow-hooks`, target overrides) the user didn't ask for. They're deployment-specific.
- **Don't hardcode a production backend address.** Use a placeholder if you don't have one and mark it `# TODO`.
- **Don't drop the bearer/JWT auth** the route file actually uses. Layer it on top of `apiKeyAuth`.
- **Don't conflate Apigee Edge and Apigee X.** They have different extension fields. If the user says "Apigee" without qualifier, ask — or default to Apigee X (the current product) and note the assumption.

## Confidence

The fields above represent the minimum useful Apigee additions. Apigee's deeper proxy configuration (flows, conditional routes, fault rules, KVM lookups) lives in proxy bundle XML, not in OpenAPI — don't try to encode it here. When unsure about a field, emit `# TODO: verify against Apigee docs / your org config` rather than guessing.
