# Ech0 HTTP Routing and API Surface

## Overview

The HTTP layer is built on [Gin](https://github.com/gin-gonic/gin). Route registration is separated from handler implementation: `internal/router/` contains one file per domain area that calls registration functions, while `internal/handler/` contains the actual handler logic in matching subpackages. The Gin engine is created once and passed through the Wire dependency graph.

## Route Groups

Routes are organized into three access groups defined in `internal/router/`:

| Group | Authentication Required | Notes |
|---|---|---|
| `PublicRouterGroup` | No | Heatmap, hello endpoint, backup export, website title |
| `AuthRouterGroup` | JWT (anonymous-downgrade for some routes) | Most read and write endpoints |
| `AdminRouterGroup` | JWT + admin role | User management, system settings |

The `AuthRouterGroup` applies `JWTAuthMiddleware` globally. Certain routes within this group allow anonymous access: the middleware falls back to a `NoopViewer` rather than returning HTTP 401 when no token is present.

All groups are also wrapped with `middleware.NoCache()` which sets `Cache-Control: no-store` to prevent browser caching of API responses.

## Route Registration

The `SetupRouter(engine, bundle)` function calls one setup function per domain:

```
setupEchoRoutes       — post CRUD, tag management, queries
setupUserRoutes       — login, register, OAuth, passkey, profile
setupFileRoutes       — upload, list, delete media
setupCommentRoutes    — comment CRUD, moderation
setupSettingRoutes    — system settings, S3, OAuth2, passkey, webhooks, tokens
setupInboxRoutes      — inbox list, read, delete
setupConnectRoutes    — instance federation connections
setupDashboardRoutes  — metrics, log streaming
setupAgentRoutes      — AI agent invocation
setupBackupRoutes     — export and restore
setupMigrationRoutes  — data migration jobs
setupInitRoutes       — first-run initialization status
setupCommonRoutes     — heatmap, ping, website title
setupTemplateRoutes   — server-side rendered RSS and OG templates
setupResourceRoutes   — static file serving
```

Each function receives the shared `AppRouterGroup` and the `handler.Bundle`.

## Handler Bundle

`handler.Bundle` is a struct that aggregates all handler types into a single injectable value. Wire constructs it by composing all handler provider sets:

```go
type Bundle struct {
    WebHandler       *web.WebHandler
    UserHandler      *user.UserHandler
    EchoHandler      *echo.EchoHandler
    FileHandler      *file.FileHandler
    CommentHandler   *comment.CommentHandler
    InitHandler      *init.InitHandler
    CommonHandler    *common.CommonHandler
    SettingHandler   *setting.SettingHandler
    InboxHandler     *inbox.InboxHandler
    ConnectHandler   *connect.ConnectHandler
    BackupHandler    *backup.BackupHandler
    MigrationHandler *migration.MigrationHandler
    DashboardHandler *dashboard.DashboardHandler
    AgentHandler     *agent.AgentHandler
}
```

## Key API Endpoints

### Echo (Posts)

| Method | Path | Auth | Scopes |
|---|---|---|---|
| `POST` | `/api/echo/query` | Optional (anon OK) | — |
| `GET` | `/api/echo/page` | Optional (anon OK) | — |
| `GET` | `/api/echo/today` | Optional (anon OK) | — |
| `GET` | `/api/echo/:id` | Optional (anon OK) | — |
| `GET` | `/api/echo/tag/:tagid` | Optional (anon OK) | — |
| `POST` | `/api/echo` | Required | `echo:write` |
| `PUT` | `/api/echo` | Required | `echo:write` |
| `DELETE` | `/api/echo/:id` | Required | `echo:write` |
| `GET` | `/api/tags` | Public | — |
| `DELETE` | `/api/tag/:id` | Required | `echo:write` |
| `PUT` | `/api/echo/like/:id` | Public | — |

The `POST /api/echo/query` endpoint replaces the deprecated paged query endpoints and accepts a JSON `EchoQueryDto` for flexible filtering and sorting.

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/login` | No | Password login, returns session token |
| `POST` | `/api/register` | No | Register (if enabled) |
| `GET` | `/api/user` | Required | Current user profile |
| `PUT` | `/api/user` | Required | Update profile |
| `GET` | `/api/allusers` | Admin | List all users |
| `GET` | `/api/oauth/login` | No | Initiate OAuth2 flow |
| `GET` | `/api/oauth/callback` | No | OAuth2 callback handler |
| `POST` | `/api/passkey/login/begin` | No | Begin passkey challenge |
| `POST` | `/api/passkey/login/finish` | No | Complete passkey login |

### Settings (Admin)

| Method | Path | Auth | Scopes |
|---|---|---|---|
| `GET` | `/api/settings` | Required | — |
| `PUT` | `/api/settings` | Admin | `admin:settings` |
| `GET/PUT` | `/api/settings/s3` | Admin | `admin:settings` |
| `GET/PUT` | `/api/settings/oauth2` | Admin | `admin:settings` |
| `GET/PUT` | `/api/settings/passkey` | Admin | `admin:settings` |
| `GET/POST/PUT/DELETE` | `/api/webhook` | Admin | `admin:settings` |
| `GET/POST/DELETE` | `/api/access-tokens` | Required | `admin:token` |

### Dashboard and Logs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/system/logs` | Paginated log query (file-based) |
| `GET` | `/api/system/logs/stream` | Recent in-memory log buffer |
| `GET` | `/ws/system/logs` | WebSocket real-time log stream |
| `GET` | `/api/heatmap` | Activity heatmap data |

## Swagger / OpenAPI

A Swagger UI is mounted at `/swagger/*any` using `gin-swagger`. The spec is generated from `// @` annotations in handler code by running:

```shell
swag init -g internal/server/server.go -o internal/swagger
```

The spec is embedded in the binary and served from the `/swagger/index.html` endpoint.

## API Response Envelope

All JSON responses use a generic `Result[T]` envelope:

```go
type Result[T any] struct {
    Code          int            `json:"code"`
    Message       string         `json:"msg"`
    ErrorCode     string         `json:"error_code,omitempty"`
    MessageKey    string         `json:"message_key,omitempty"`
    MessageParams map[string]any `json:"message_params,omitempty"`
    Data          T              `json:"data"`
}
```

Success responses have `code: 1`. Failure responses have `code: 0` with `msg` populated. Localized clients should prefer `message_key` + `message_params` over the `msg` string.

Helper functions `commonModel.OK[T]`, `commonModel.Fail[T]`, and `commonModel.FailWithLocalized[T]` construct envelopes consistently across all handlers.

## Middleware Stack

The full middleware chain for a typical authenticated API request:

1. `middleware.NoCache()` — sets no-store headers
2. `middleware.JWTAuthMiddleware()` — parses token, attaches viewer to context
3. (optional) `middleware.RequireScopes(...)` — verifies access token scopes
4. `middleware.MaintenanceMiddleware()` — returns 503 during maintenance mode

CORS is handled by a separate `middleware.SetupCORS(engine)` call at router setup time, before any route groups are registered.
