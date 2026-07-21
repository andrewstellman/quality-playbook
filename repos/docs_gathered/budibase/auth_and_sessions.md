# Auth and Sessions — packages/backend-core/src/auth, packages/worker

## Overview

Authentication and session management are implemented in `packages/backend-core` and exposed through the worker service (`packages/worker`). The worker provides global auth endpoints (login, logout, SSO callbacks, password reset) while the main server handles app-level session extension and the "self" endpoint. All authentication state is stored in Redis; CouchDB holds user documents and API keys.

## Authentication Strategies

Budibase uses [Passport.js](http://www.passportjs.org/) with the following strategies, registered in `packages/backend-core/src/auth/auth.ts`:

| Strategy | Provider | Registration |
|----------|----------|-------------|
| Local | username + password | `passport.use(new LocalStrategy(local.options, local.authenticate))` |
| Google OAuth2 | Google | Configured dynamically from `ConfigType.GOOGLE` |
| OIDC | OpenID Connect | Configured dynamically from `ConfigType.OIDC` |

SSO strategies are registered at runtime by reading the stored config from CouchDB via `configs.getConfig`. The `configType` key controls which config document is loaded. Multiple OIDC providers may be configured.

OAuth2 access tokens for SSO sessions are refreshed automatically using `passport-oauth2-refresh` when the access token expires.

## Login / Logout Flow (worker)

The worker's `global/auth` controller handles:

1. **POST `/api/global/auth/:tenantId/login`** — validates credentials via `localStrategy`, creates a session, sets a signed JWT cookie (`budibase:auth`) and a CSRF cookie.
2. **POST `/api/global/auth/:tenantId/logout`** — clears cookies, invalidates the session in Redis.
3. **GET/POST `/api/global/auth/:tenantId/google/callback`** — Google OAuth2 callback; creates or updates the user, creates a session.
4. **GET/POST `/api/global/auth/:tenantId/oidc/callback`** — OIDC callback.
5. **POST `/api/global/auth/:tenantId/reset`** — sends a password-reset email with a time-limited token stored in Redis.
6. **POST `/api/global/auth/:tenantId/reset/update`** — validates the reset token and updates the password.

A login lockout mechanism is implemented in the worker's auth controller: failed attempts are counted in Redis under `auth:login:fail:<email>`. After a configurable number of failures (`LOGIN_FAILURE_LOCKOUT_COUNT`), the account is locked for `LOGIN_LOCKOUT_SECONDS` seconds and the response includes `X-Account-Locked: 1` and `Retry-After` headers.

## Session Model

Sessions are stored in Redis by `packages/backend-core/src/security/sessions.ts`. The key format is `<userId>/<sessionId>`. Each session record contains:

```ts
interface Session {
  userId: string
  sessionId: string
  lastAccessedAt: string
  createdAt: string
  tenantId: string
  csrfToken?: string
}
```

Sessions expire after `SESSION_EXPIRY_SECONDS` (default: 7 days). The TTL is refreshed on each authenticated request if the last refresh was more than `SESSION_UPDATE_PERIOD` milliseconds ago (default: 60 seconds). The maximum number of concurrent sessions per user is controlled by `MAX_SESSIONS_PER_USER` from `@budibase/shared-core`.

`invalidateSessions(userId, opts)` accepts an optional list of specific session IDs; if none are provided, all sessions for the user are invalidated. This is called on password change, user deletion, and explicit logout.

## Authentication Middleware

`packages/backend-core/src/middleware/authenticated.ts` is the core request-authentication middleware, mounted as `buildAuthMiddleware`. For each request it:

1. Reads the JWT from the `budibase:auth` cookie (or `Authorization: Bearer` header for API-key auth).
2. If the token is a valid JWT: decodes the session cookie, looks up the `Session` in Redis, fetches the `User` from the user cache, and attaches both to `ctx.user`. Refreshes the session TTL.
3. If the request carries an API key (header `x-budibase-api-key`): validates it against the internal API key (for service-to-service calls) or decrypts it and looks up the user ID in CouchDB via the `by_api_key` view.
4. Sets `ctx.isAuthenticated`, `ctx.internal`, `ctx.publicEndpoint`, and `ctx.loginMethod` accordingly.
5. If neither credential is present and the endpoint is public (`publicAllowed: true`), continues unauthenticated.

## Role and Permission Model

Roles are stored per-workspace as `Role` documents in the workspace CouchDB database. Budibase ships four built-in roles:

| Role ID | Inherits | Description |
|---------|----------|-------------|
| `PUBLIC` | — | Unauthenticated access |
| `BASIC` | `PUBLIC` | Authenticated app user |
| `POWER` | `BASIC` | Power user with extended data access |
| `ADMIN` | `POWER` | Full app admin |

Custom roles can be created; they declare an `inherits` field pointing to another role ID. The permission system resolves the full inherited chain via `getAllRoles`.

Permission levels form a hierarchy: `EXECUTE (0) < READ (1) < WRITE (2) < ADMIN (3)`. The `authorized` middleware (`packages/server/src/middleware/authorized.ts`) checks the requesting user's role against the resource's required `PermissionType` + `PermissionLevel`. Builders bypass all resource-level checks. Global builders bypass workspace-level checks.

Built-in permission IDs (`BuiltinPermissionID`) map roles to default permissions: `READ_ONLY`, `WRITE`, `ADMIN`, `POWER`, `PUBLIC`.

## CSRF Protection

CSRF tokens are generated at session creation and stored in the session record. The `csrf` middleware (`backend-core/src/middleware/csrf.ts`) validates that state-mutating requests (POST, PUT, DELETE, PATCH) carry the token in the `x-csrf-token` header. Requests from internal services (identified by the `x-budibase-type: internal` header) bypass CSRF checking.

## Multi-Tenancy

Tenancy is a first-class concept. Each tenant has its own CouchDB global database (`<tenantId>_global-db`) and separate workspace databases. The `buildTenancyMiddleware` extracts the tenant ID from the JWT, the subdomain, or a custom header, and sets it in the async-local-storage context via `doInTenant`. All DB helpers automatically use the tenant-scoped database name. The `MULTI_TENANCY` environment variable enables or disables multi-tenant mode; when disabled, all requests use `DEFAULT_TENANT_ID`.
