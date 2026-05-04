---
name: openapi-spec-generation
description: Generate an OpenAPI 3.0.3 spec yaml from a single Express.js route file. Use this whenever the user asks to "generate openapi spec", "openapi generation", "create api spec", "document this route", or otherwise wants a route file turned into an OpenAPI document — even when they don't say the word "openapi" explicitly. Also use when an agent needs to produce an OpenAPI yaml from JS/TS source. Auto-detects auth middleware. Has optional IBM API Connect (APIC) and Apigee modes that emit platform-specific extensions when the user mentions either platform.
---

# OpenAPI Spec Generation

Turn one Express.js route file into an OpenAPI 3.0.3 yaml. Default mode emits a clean vendor-neutral spec; opt-in modes add IBM API Connect or Apigee extensions for direct deployment.

## When to use

- User asks for "openapi spec", "openapi generation", "api spec", "document this route", or shows you a route file and wants documentation.
- An agent or workflow needs an OpenAPI yaml derived from Express source.
- User mentions **IBM APIC / API Connect / apic** → use IBM APIC mode (see `references/ibm-apic.md`).
- User mentions **Apigee / Apigee Edge / Apigee X** → use Apigee mode (see `references/apigee.md`).

If the request is to spec multiple files at once, do them one file at a time using this same workflow — don't try to bulk-generate.

## Inputs

- One Express route file path (e.g., `app/routes/foo.js`).
- Optional target: `default` (assumed), `ibm-apic`, or `apigee`.
- Optional output path. If absent, infer from project conventions (see step 2).

## Workflow

### 1. Read the route source

Read the entire route file. You're looking for:

- **Express patterns**: `app.get(...)`, `app.post(...)`, `router.get/post/put/delete/patch`, `app.use(prefix, sub)`, `app.METHOD(path, mw1, mw2, handler)`.
- **Path strings**: convert `:param` to `{param}` for OpenAPI. Strip query strings.
- **Middleware chain**: every function reference between the path and the final handler is a middleware. These are your auth-detection signal.
- **Inside each handler**:
  - `req.params.X` → path parameter (already declared in the path)
  - `req.query.X` / `req.query['x']` → query parameter
  - `req.body.X` / destructured `const {a,b} = req.body` → request body fields
  - `req.headers['x-...']` → header parameter
  - `res.status(N)` / `.status(N).json(...)` / `.sendStatus(N)` → response code
  - `res.json({...})`, `res.send(...)`, `res.render(...)` → response shape
  - SQL strings (`db.execute('SELECT a, b, c FROM ...')`, `?` placeholders) → hint at request inputs and response columns
  - Calls to other services / APIs → may shape the response

When a field's type is non-obvious (returned by a library, comes from external API, etc.), emit `# TODO: verify type` rather than guessing. A spec that admits uncertainty is more useful than one that confidently lies.

### 2. Detect the project's spec style

Before writing, look in the project for an existing OpenAPI directory. Common locations: `openapi/`, `docs/openapi/`, `api-spec/`, `specs/`. Read 1–2 sibling specs to match:

- **File naming convention** (e.g., `app-routes-{name}.yaml`, `routes-{name}.yaml`, `{name}.openapi.yaml`)
- **Servers list** — copy what's there
- **Whether shared components** are inline per-file or referenced from a shared `components.yaml`
- **Tag naming style**, info block style

If no openapi directory exists, place the file beside the route as `{route-basename}.openapi.yaml`. Tell the user where you put it.

### 3. Detect authentication

Scan the route file's middleware chain. Common patterns:

| Middleware pattern | Security scheme |
|---|---|
| `requireAuth`, `authMiddleware`, `verifyToken`, `firebaseAuth`, `firebaseVerifyToken`, `isAuthenticated`, `ensureAuth*` | `bearerAuth` (HTTP bearer) — or `cookieAuth` if the file reads `req.cookies.token` / uses sessions |
| `passport.authenticate('jwt' \| 'bearer', ...)` | `bearerAuth` |
| `passport.authenticate('basic')` | `basicAuth` |
| Reads `req.headers['x-api-key']` or similar | `apiKeyAuth` (header, name = matched header) |
| No middleware between path and handler | No `security` on that operation |

If a global middleware applies the auth (e.g., `app.use(requireAuth)` near the top of the file), apply security at the document level instead of per-operation.

If you see a middleware whose purpose isn't obvious from its name, read its source briefly to classify — but don't go down a rabbit hole. When unsure, document the chosen scheme with a comment explaining what you assumed.

### 4. Build the spec

Compose the yaml top-down. Match the depth and style of any sibling specs you read in step 2; otherwise use these defaults:

- `openapi: 3.0.3` — pin this exact version. Don't drop to `3.0.0` or jump to `3.1.0` even if a sibling spec uses something different (in this codebase the convention is `3.0.3`). If you truly need a different version, ask first.
- `info`:
  - `title`: humanized filename + ` API ({path/to/route.js})`
  - `description`: one-line summary inferred from the file's purpose
  - `version: 1.0.0`
- `servers`: from a sibling spec, or `http://localhost:3000` as fallback
- `tags`: one tag derived from the filename (use the same name across all operations in this file)
- `paths`: every operation, each with:
  - `summary` (verb-based, e.g., "Create a new crypto operation")
  - `description` (longer, optional)
  - `operationId` (camelCase: verb + resource, e.g., `getCryptoOperations`, `createCryptoOperation`)
  - `tags`
  - `security` (per detected auth — omit if none)
  - `parameters` (path, query, header)
  - `requestBody` (for POST/PUT/PATCH) referencing a schema
  - `responses` — at minimum the success code and the error codes the handler can actually produce. Always include `401` if the operation is secured, and a generic `500` reference.
- `components`:
  - `schemas`: one per logical entity. Inline-define small ones; `$ref` shared ones.
  - `responses`: shared `Unauthorized`, `BadRequest`, `NotFound`, `InternalServerError` with `$ref` from operations.
  - `securitySchemes`: declare the schemes you used in step 3.

### 5. Update / merge / diff existing spec

If a yaml already exists at the target path, **do not overwrite blindly**. Instead:

1. Read the existing yaml.
2. Generate the new yaml from the route file as if from scratch.
3. **Merge with these rules**:
   - **Preserve manual content**: any `description`, `example`, `x-*` extension, or richer schema detail in the existing file that the new generation would not reproduce — keep it.
   - **Preserve identifier names verbatim**: parameter names, schema property names, schema names, `operationId`s, and tag names in the existing spec are load-bearing — they may be referenced by client code, API gateway configs, or downstream tooling. **Never silently rename** `carteira_id` to `portfolio_id`, `userId` to `user_id`, etc., even if the new name reads better. If the source code clearly uses a different name than the existing spec, flag it as `# TODO: name mismatch — source uses 'X', spec uses 'Y'` and let the user choose, rather than picking one.
   - **Add new endpoints** found in the source that the spec is missing.
   - **Flag stale endpoints** (in spec, not in source) by leaving them in place with a comment: `# TODO: endpoint not found in source — remove or update?`. Don't silently delete.
   - **Update parameters/responses** to match source structure (add missing status codes, add fields the source clearly emits). But if the existing entry has a richer schema and yours is more generic, keep the richer one and note that it was re-verified.
4. **Show the diff** to the user before writing. Use `diff -u <existing> <new>` and present the unified diff. If the diff is more than a handful of lines, or if any preserved manual content was at risk of being lost, ask the user to confirm before writing.

If no existing spec, just write the new one.

### 6. Target-specific extensions

The default spec is vendor-neutral. Two opt-in modes add platform extensions:

- **IBM APIC mode** — read [references/ibm-apic.md](references/ibm-apic.md) and follow it. Triggered by user mentioning IBM APIC, IBM API Connect, or apic.
- **Apigee mode** — read [references/apigee.md](references/apigee.md) and follow it. Triggered by user mentioning Apigee, Apigee Edge, or Apigee X.

Don't include these extensions in the default mode — they add noise to a generic spec and can confuse non-target tooling.

## Output

After writing:

- Confirm the path the spec was written to.
- Report: number of endpoints, auth scheme(s) detected, any `# TODO` markers (and why).
- If you merged with an existing spec: show the diff summary (N additions, M removals, K endpoints flagged stale).

## Anti-patterns to avoid

- **Inventing fields.** If `req.body.x` is referenced but you can't tell whether `x` is a string or number, write `# TODO: verify type` rather than guessing.
- **Inventing servers, URLs, or domains.** Never write a production URL (e.g., `https://api.example.com`) you didn't see in a sibling spec, the route file, or the user's prompt. Default to `http://localhost:3000` (or whatever a sibling spec actually contains) and add `# TODO: set production URL` if needed.
- **Renaming identifiers during merge.** Parameter names, schema property names, and operation IDs are referenced externally — preserve them verbatim. Flag mismatches with `# TODO`, don't auto-correct.
- **Stripping hand-written content during merge.** Manual `description` and `example` text is the most valuable part of a spec — preserve it.
- **Adding IBM/Apigee extensions when not asked.** They're noise outside their target platforms.
- **Bulk regeneration.** This skill does one route file at a time. Generating ten at once skips per-file judgment and produces lower-quality specs.
- **Over-engineering for tiny files.** If the route file has two endpoints and no shared schemas, don't construct a `$ref`-heavy components graph. Match the project's existing depth.
- **Guessing the auth scheme.** If middleware behavior is unclear, read its source briefly. If still unclear, pick the most likely scheme and add a comment explaining the assumption.
