# Server API — packages/server

## Overview

The `packages/server` package is the primary backend service of Budibase. It is a [Koa](https://koajs.com/) HTTP application that handles all application-level operations: serving the builder and deployed-app assets, providing the REST API used by the builder UI and the public API, executing queries against datasources, and dispatching automation events. The service is identified by `ServiceType.APPS` and normally listens on `APP_PORT` or `APPS_PORT`.

## Startup Sequence

On boot, the server transitions through the states `uninitialised → starting → ready`, exposed via `getState()`. A `GET /health` endpoint returns 503 until the state is `ready` and (when automations are enabled) the Bull queue reports itself healthy. A `GET /version` endpoint returns the current version string.

Startup (`packages/server/src/startup/index.ts`) initialises, in order:

1. Object storage and Redis clients.
2. The JS runner (isolated-VM sandbox).
3. Bull queues: automation queue, app-migration queue, RAG ingestion queue, activity-log queue.
4. Automation triggers (rehydrates scheduled/cron triggers from CouchDB; fires reboot-trigger automations).
5. LiteLLM readiness poll (if `LITELLM_MASTER_KEY` is set).
6. Koa router mount (routes go online last).

## Router Architecture

The router is assembled in `packages/server/src/api/index.ts`. Middleware is applied in this order:

- Response compression (gzip/deflate, threshold 2 KB).
- Static asset routes (bypass auth).
- Authentication middleware (`buildAuthMiddleware`).
- Tenancy middleware (`buildTenancyMiddleware`).
- Active-tenant resolution and licensing check (via `@budibase/pro`).
- Current-workspace resolution.
- Content-Security-Policy middleware (skipped when `DISABLE_CONTENT_SECURITY_POLICY` is set).
- Activity log emission.
- Workspace-migration middleware.
- Cleanup middleware.
- Application routes (see below).
- Public API routes.
- Static fallback routes (mounted last; catch-all).

## Route Groups

Routes are declared by importing side-effect modules (`./ai`, `./analytics`, `./auth`, `./automation`, etc.) that self-register into `EndpointGroup` objects. The groups are:

- **Builder routes** — only accessible to users with builder or admin permissions.
- **Authorized routes** — accessible to any authenticated user with the required resource permission.
- **Public routes** — no authentication required; see `packages/server/src/api/routes/public/`.

The full route list (imported in `routes/index.ts`) covers: ai, analytics, apikeys, auth, automation, backup, chat, component, datasource, debug, deploy, dev, features, integration, layout, metadata, migrations, navigation, oauth2, ops, permission, plugin, query, recaptcha, resource, role, routing, row, rowAction, screen, table, templates, user, view, webhook, workspace, workspaceApp, workspaceHome, workspaceFavourites.

## Public API

The public API (under `/api/public/v1/`) is a separately documented OpenAPI surface. Route files in `routes/public/` carry JSDoc `@openapi` annotations and cover:

| Resource | Methods |
|----------|---------|
| `rows` | create, update, bulk update, search, delete, bulk delete |
| `tables` | create, update, search, delete |
| `views` | create, update, search, delete |
| `queries` | execute |
| `users` | CRUD |
| `roles` | list |
| `applications` | create, search, delete, publish |
| `workspaces` | list |

All public API handlers run through `publicApi` middleware, which enforces API-key authentication and quota checks.

## Key Configuration Variables

Declared in `packages/server/src/environment.ts`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_PORT` / `APPS_PORT` | — | HTTP listen port |
| `COUCH_DB_URL` | — | CouchDB connection |
| `COUCH_DB_SQL_URL` | — | CouchDB-SQS endpoint |
| `REDIS_URL` | — | Redis for queues and sessions |
| `MINIO_URL` | — | Object store endpoint |
| `WORKER_URL` | — | Worker service base URL |
| `PLUGINS_DIR` | `/plugins` | Filesystem path for plugin bundles |
| `QUERY_THREAD_TIMEOUT` | 15 000 ms | Timeout for datasource query worker threads |
| `AUTOMATION_THREAD_TIMEOUT` | 120 000 ms | Timeout for automation execution threads |
| `AUTOMATION_MAX_ITERATIONS` | 200 | Maximum loop iterations in one automation run |
| `AUTOMATION_MAX_NESTED_LOOPS` | 3 | Maximum nested loop depth |
| `JS_RUNNER_MEMORY_LIMIT` | 64 MB | Memory cap for isolated-VM JS execution |
| `JS_PER_EXECUTION_TIME_LIMIT_MS` | 1 500 ms | Per-call time limit for JS execution |
| `APP_FEATURES` | all | Comma-separated list of enabled features (`api`, `automations`) |
| `LITELLM_MASTER_KEY` | — | Enables the LiteLLM proxy gateway |

## Error Handling

All unhandled errors are caught by `middleware/errorHandling.ts`. The handler maps the thrown error's `status` or `statusCode` to the response status (defaulting to 500). For 4xx errors, the error is logged at `warn` level; for 5xx, at `error` level. The response body is an `APIError` object with `message`, `status`, `validationErrors`, and a public-safe `error` field. If the serialised error body would contain a secret value, the body is replaced with a generic message.

## WebSocket Channels

Three Socket.IO namespaces are initialised at startup:

- `/socket/builder` — builder collaboration; tracks which user has which resource selected; broadcasts schema changes when a table, datasource, role, or screen is modified.
- `/socket/grid` — the data grid panel; broadcasts row-level changes to other users viewing the same table.
- `/socket/client` — deployed-app clients; receives published-app events.

The `BaseSocket` class uses a Redis-backed Socket.IO adapter (`@socket.io/redis-adapter`) so that multiple server instances share the same namespace, supporting cluster deployments.

## Test Conventions

Unit tests use Jest with `jest.mock`. Integration tests (e.g., `integration-test/postgres.spec.ts`, `integration-test/mysql.spec.ts`) spin up real database containers via `testcontainers`. The global setup (`globalSetup.ts`) uses Docker to pull and start containers before the Jest suite begins, using a lockfile to prevent parallel test processes from racing on container creation.
