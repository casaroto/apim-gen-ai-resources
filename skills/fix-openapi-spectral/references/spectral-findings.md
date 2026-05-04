# Spectral and OWASP Finding Fixes

Use these mappings when correcting OpenAPI specs from Spectral output.

## Metadata and Inventory

`info-contact`
: Add an `info.contact` object. Prefer a real team email or URL from the repo. If none exists, ask or leave a clearly marked placeholder only when placeholders are acceptable.

`info-description`
: Add a concise `info.description` explaining the API purpose and audience.

`owasp:api9:2023-inventory-access`
: Add `x-internal: true` for private/internal APIs or `x-internal: false` for public/external APIs to every `servers` item.

`owasp:api9:2023-inventory-environment`
: Make `servers[*].description` name the environment, such as `local`, `development`, `staging`, or `production`.

`owasp:api8:2023-no-server-http`
: Change server URLs from `http://` to `https://` except for true local development endpoints. If retaining local HTTP, document that it is local in the server description and tell the user the finding may remain.

Use `info.contact` cautiously. Prefer real ownership metadata from the repository. If the API is only a demo and no owner exists, a generic team contact can be acceptable, but call it out if it is a placeholder.

## Operation Quality

`operation-operationId`
: Add stable camelCase or lowerCamelCase operation IDs. Use verb+noun patterns such as `listBooks`, `createBook`, `getBookById`.

`operation-description`
: Add meaningful descriptions. Do not duplicate summaries word-for-word.

`operation-tags`
: Add non-empty tags. Reuse existing domain tags such as `Books`, `Health`, `Accounts`, or `Branches`.

`oas3-unused-component`
: Remove unused components or reference them from operations. Prefer referencing reusable responses/schemas when they are still useful.

## Security

`owasp:api2:2023-read-restricted`
`owasp:api2:2023-write-restricted`
: Add an appropriate security requirement unless the operation is intentionally public. Reuse an existing `components.securitySchemes` entry. If none exists, add a conventional scheme only when it matches the target platform, for example:

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT bearer token authentication following RFC8725 best current practices.
security:
  - bearerAuth: []
```

For public health checks, prefer an explicit operation-level `security: []` only if the team intentionally allows anonymous access; otherwise a finding may remain.

`owasp:api2:2023-jwt-best-practices`
: If using JWT bearer auth, make the security scheme description explicitly mention RFC8725.

## Error Responses

`owasp:api8:2023-define-error-responses-401`
: Add a `401` response for protected operations.

`owasp:api8:2023-define-error-responses-500`
: Add a `500` response to operations.

`owasp:api8:2023-define-error-validation`
: Add `400`, `422`, or `4XX` for operations with request bodies, parameters, or validation constraints.

Prefer shared responses:

```yaml
components:
  schemas:
    ErrorResponse:
      type: object
      required: [message]
      properties:
        code:
          type: string
          maxLength: 64
        message:
          type: string
          maxLength: 512
  responses:
    Unauthorized:
      description: Authentication is missing or invalid.
      headers:
        Access-Control-Allow-Origin:
          $ref: "#/components/headers/Access-Control-Allow-Origin"
        X-RateLimit-Limit:
          $ref: "#/components/headers/RateLimitLimit"
        X-RateLimit-Remaining:
          $ref: "#/components/headers/RateLimitRemaining"
        X-RateLimit-Reset:
          $ref: "#/components/headers/RateLimitReset"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    InternalServerError:
      description: Unexpected server error.
      headers:
        Access-Control-Allow-Origin:
          $ref: "#/components/headers/Access-Control-Allow-Origin"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
```

## Rate Limiting

`owasp:api4:2023-rate-limit-responses-429`
: Add a `429` response with content.

`owasp:api4:2023-rate-limit-retry-after`
: Add a `Retry-After` header to `429` responses.

`owasp:api4:2023-rate-limit`
: Add rate-limit headers to `2XX` and `4XX` responses when the rule requires them. Prefer reusable headers:

```yaml
components:
  headers:
    RateLimitLimit:
      description: Request limit for the current window.
      schema:
        type: integer
        minimum: 0
    RateLimitRemaining:
      description: Remaining requests in the current window.
      schema:
        type: integer
        minimum: 0
    RateLimitReset:
      description: Seconds until the current rate-limit window resets.
      schema:
        type: integer
        format: int32
        minimum: 0
        maximum: 86400
    RetryAfter:
      description: Seconds to wait before retrying after rate limiting.
      schema:
        type: integer
        format: int32
        minimum: 0
        maximum: 86400
```

Attach headers with:

```yaml
headers:
  X-RateLimit-Limit:
    $ref: "#/components/headers/RateLimitLimit"
  X-RateLimit-Remaining:
    $ref: "#/components/headers/RateLimitRemaining"
  X-RateLimit-Reset:
    $ref: "#/components/headers/RateLimitReset"
```

## CORS

`owasp:api8:2023-define-cors-origin`
: Define `Access-Control-Allow-Origin` on every response. The reusable component name must be the literal header name for this ruleset:

```yaml
components:
  headers:
    Access-Control-Allow-Origin:
      description: Allowed CORS origin for browser clients.
      schema:
        type: string
        enum: ["https://api.example.com"]
```

Then attach it to inline responses and reusable responses:

```yaml
headers:
  Access-Control-Allow-Origin:
    $ref: "#/components/headers/Access-Control-Allow-Origin"
```

Avoid wildcard `*` unless the API is intentionally public and that CORS posture is acceptable.

## Schema Bounds

`owasp:api4:2023-string-limit`
: Add `maxLength`, `enum`, or `const` to string schemas.

`owasp:api4:2023-string-restricted`
: Add `format`, `pattern`, `enum`, or `const` to string schemas when meaningful.

`owasp:api4:2023-array-limit`
: Add `maxItems` to array schemas.

`owasp:api4:2023-integer-limit`
`owasp:api4:2023-number-limit`
: Add `minimum`, `maximum`, `exclusiveMinimum`, or `exclusiveMaximum`.

`owasp:api4:2023-integer-format`
: Add `format: int32` or `format: int64`.

`owasp:api4:2023-integer-limit-legacy`
: Add both `minimum` and `maximum`.

`owasp:api1:2023-no-numeric-ids`
: Prefer opaque string identifiers such as UUIDs:

```yaml
schema:
  type: string
  format: uuid
  maxLength: 36
```

Changing an existing path or schema ID from integer to UUID is a breaking API contract change. Do it only when acceptable for the task, and always mention it in the final response.

Use domain-safe defaults only when no stronger signal exists:

- IDs: `minimum: 1`
- UUID IDs: `type: string`, `format: uuid`, `maxLength: 36`
- Names/titles: `maxLength: 255`
- Short status/code values: `maxLength: 64`
- Error messages: `maxLength: 512`

## Validation Loop

After edits:

1. Run Spectral again through the same MCP server.
2. Prefer `fail_severity: "hint"` for the final pass so all severities are visible.
3. Compare finding counts by severity and rule.
4. If the MCP wrapper receives successful Spectral output shaped like `[]No results with a severity of 'error' found!`, parse the leading JSON array and treat the trailing message as informational.
5. If a rule remains because it needs a product/security decision, explain the decision point instead of guessing.
