# Worker Service — packages/worker

## Overview

`packages/worker` is a separate Koa HTTP service identified by `ServiceType.WORKER`. It handles platform-wide, tenant-global concerns: user management, authentication, email delivery, organisation configuration, licence enforcement, SSO provider setup, activity logging, and SCIM provisioning. This separation keeps user-management and platform-administration concerns out of the per-app `packages/server` process.

The worker is configured separately from the server. Its startup loads `worker/src/environment.ts` and communicates with the server using the shared `INTERNAL_API_KEY`.

## Key Configuration Variables

```
WORKER_PORT          — HTTP listen port (preferred over PORT)
COUCH_DB_URL         — CouchDB connection string
REDIS_URL            — Redis connection string
MINIO_URL            — Object store endpoint
APPS_URL             — URL of the app-service for internal cross-service calls
ACCOUNT_PORTAL_URL   — Cloud account portal URL
INTERNAL_API_KEY     — Shared secret for service-to-service requests
JWT_SECRET           — Used to sign session JWTs
SALT_ROUNDS          — bcrypt rounds for password hashing
SMTP_USER / SMTP_PASSWORD / SMTP_HOST / SMTP_PORT — Email configuration
MULTI_TENANCY        — Enable multi-tenant mode
SELF_HOSTED          — Enable self-hosted-specific behaviour
DISABLE_ACCOUNT_PORTAL — Disable cloud account portal links
PASSWORD_MIN_LENGTH  — Minimum password length (default 12)
LOGIN_FAILURE_LOCKOUT_COUNT — Consecutive failures before lockout
LOGIN_LOCKOUT_SECONDS — Lockout duration in seconds
SESSION_EXPIRY_SECONDS — Redis session TTL (default 7 days)
COOKIE_DOMAIN        — Domain for auth cookies (multi-subdomain setups)
```

## Route Groups

Routes are registered in `worker/src/api/routes/index.ts` and are split into:

### Global routes (`routes/global/`)

| Module | Endpoints | Responsibility |
|--------|-----------|---------------|
| `auth` | `/api/global/auth/:tenantId/*` | Login, logout, password reset, SSO callbacks |
| `configs` | `/api/global/configs/*` | SMTP, Google, OIDC, Budibase AI, and other platform configs |
| `email` | `/api/global/email/send` | Send test or templated emails |
| `events` | `/api/global/events/*` | Internal event forwarding |
| `github` | `/api/global/auth/github/*` | GitHub OAuth for plugin installation |
| `license` | `/api/global/license/*` | License key management and activation |
| `roles` | `/api/global/roles/*` | Global role definitions |
| `self` | `/api/global/self` | Current user's own profile and settings |
| `templates` | `/api/global/templates/*` | Email template CRUD |
| `users` | `/api/global/users/*` | User CRUD, bulk invite, group membership |
| `auditLogs` | `/api/global/auditlogs/*` | Activity log search |
| `groups` | `/api/global/groups/*` | User group CRUD |
| `scim` | `/api/global/scim/*` | SCIM 2.0 provisioning (users and groups) |

### System routes (`routes/system/`)

| Module | Endpoints | Responsibility |
|--------|-----------|---------------|
| `accounts` | `/api/system/accounts/*` | Account portal integration |
| `environment` | `/api/system/environment` | Read platform environment flags |
| `logs` | `/api/system/logs` | Platform log access |
| `restore` | `/api/system/restore` | Backup restore |
| `status` | `/api/system/status` | Health check |
| `tenants` | `/api/system/tenants/*` | Tenant lifecycle management |

## User Management

The `users` controller and its backing SDK (`worker/src/sdk/users/`) handle:

- Creating users with hashed passwords (bcrypt, configurable `SALT_ROUNDS`).
- Enforcing `PASSWORD_MIN_LENGTH`.
- Assigning global admin / builder flags.
- Sending welcome invitation emails.
- Bulk user imports (CSV or JSON).
- Group membership: users may belong to groups; groups carry role assignments that are inherited by their members at query time via `groups.enrichUserRolesFromGroups`.
- SCIM 2.0: the `scim` routes implement the SCIM 2.0 schema for Users and Groups, enabling integration with identity providers (Okta, Azure AD, etc.) for automated provisioning and deprovisioning.

## Email

The worker provides email delivery via `nodemailer` using the SMTP configuration stored in CouchDB (`ConfigType.SMTP`). Template-based emails (invitation, password reset, welcome) are rendered using `@budibase/string-templates` with a context containing the recipient's details and platform URLs. A fallback SMTP config can be enabled via `SMTP_FALLBACK_ENABLED` for self-hosted deployments that have not yet configured their own SMTP server.

## Configuration Management

All platform-level configuration is stored as `Config` documents in the global CouchDB database. The config controller provides `GET /api/global/configs/:type` and `POST /api/global/configs` for reading and writing typed configs. Config types include:

| ConfigType | Contents |
|------------|---------|
| `SMTP` | SMTP host, port, auth credentials |
| `GOOGLE` | Google OAuth2 client ID/secret |
| `OIDC` | One or more OpenID Connect provider configs |
| `SETTINGS` | Platform name, logo, analytics toggle, AI setup wizard flag |
| `AI` | AI provider configs (provider, model, API key) |
| `TRANSLATIONS` | Custom translation overrides |
| `BRANDING` | Custom branding overrides |

Reading a config via `GET` populates an in-memory cache (1-minute TTL via `@budibase/backend-core` cache layer) to avoid repeated CouchDB reads on hot paths.

## Licensing

The licence controller proxies licence-related calls to the Budibase account portal and stores the activated licence in Redis for fast access. The `@budibase/pro` package provides the `licensing` middleware used by the main server, which reads the cached licence and enforces quotas (rows, users, automations, plugins).

## Activity logging

The worker processes activity log events from the `auditLogQueue` (a Bull queue backed by Redis). Each event is written to the `bb-activity-logs` CouchDB database via `pro.sdk.auditLogs.write`. The activity log controller exposes a search API backed by CouchDB Mango queries, with filters on event type, user, and time range.

## Internal Service Communication

The worker and server communicate via HTTP using the `INTERNAL_API_KEY` header for authentication. The `internalApi` middleware in `backend-core` validates this key. Cross-service calls include: the server calling the worker to look up user details, generate API keys, and check licence state.
