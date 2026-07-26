# Ech0 Testing Conventions

## Overview

Ech0 follows a layered test strategy: unit tests for isolated logic, integration tests for subsystem interactions, and router-level tests that exercise the full middleware and route setup against an in-memory SQLite database. Tests are colocated with the code they cover (`_test.go` files in the same package).

## Test Locations

| Package | Test file(s) | What is tested |
|---|---|---|
| `internal/router` | `router_test.go` | Route registration, middleware enforcement, scope checks |
| `internal/middleware` | `auth_test.go`, `scope_test.go` | JWT auth middleware, scope enforcement |
| `internal/cache` | `restretto_test.go`, `patterns_test.go` | Cache put/get/eviction behavior |
| `internal/storage` | `manager_test.go` | Config merging, selector reload |
| `internal/backup` | `backup_test.go` | Archive creation, file exclusion, temp atomics |
| `internal/database` | `database_test.go` | GORM provider initialization |
| `internal/service/echo` | `echo_test.go` | Post CRUD service logic |
| `internal/service/inbox` | `inbox_test.go` | Inbox read/clear behavior |
| `internal/service/migrator` | `migrator_test.go` | ETL pipeline batch outcomes |
| `internal/service/setting` | `access_token_service_test.go` | Token lifecycle, scope validation |
| `internal/service/user` | `oauth_service_test.go` | OAuth flow, OIDC verification |
| `internal/util/jwt` | `jwt_test.go` | Token generation and parsing |
| `web/tests` | Various `.test.ts` files | Frontend markdown rendering, gallery, store init, utilities |

## Backend Test Conventions

### In-Memory Database

Tests that require database access create an in-memory SQLite instance:

```go
func initTestDatabase(t *testing.T) {
    t.Helper()
    db, err := gorm.Open(sqlite.Open("file::memory:?cache=shared"), &gorm.Config{})
    if err != nil {
        t.Fatalf("init test db failed: %v", err)
    }
    database.SetDB(db)
}
```

The `cache=shared` parameter allows the same in-memory database to be accessed across multiple `gorm.Open` calls within the same test process, which is needed when Wire-assembled components each call the database provider.

### Handler Bundle Construction

Router tests construct minimal handler bundles by passing `nil` services to each handler constructor. Handlers constructed with nil services skip nil checks internally and return appropriate errors when called, allowing route-level tests (registration, middleware behavior) to run without a full service graph:

```go
func buildTestHandlers() *handler.Bundle {
    return handler.NewBundle(
        webHandler.NewWebHandler(),
        userHandler.NewUserHandler(nil),
        echoHandler.NewEchoHandler(nil),
        // ...
    )
}
```

### Gin Test Mode

All tests using Gin set `gin.SetMode(gin.TestMode)` before creating an engine to suppress the startup banner and suppress route logging noise.

### HTTP Test Helpers

Tests use `net/http/httptest`:

```go
req := httptest.NewRequest(http.MethodGet, "/api/user", nil)
rec := httptest.NewRecorder()
engine.ServeHTTP(rec, req)

if rec.Code != http.StatusUnauthorized {
    t.Fatalf("expected %d, got %d", http.StatusUnauthorized, rec.Code)
}
```

### Token Fixture Generation

JWT tests and router scope tests generate real tokens using the production `jwtUtil.GenerateToken` and `jwtUtil.CreateAccessClaimsWithExpiry` functions. Tests verify actual middleware behavior against real token payloads:

```go
token, err := jwtUtil.GenerateToken(
    jwtUtil.CreateAccessClaimsWithExpiry(
        user,
        int64(time.Hour),
        []string{authModel.ScopeEchoRead},
        authModel.AudiencePublic,
        "jti-read-only",
    ),
)
```

## Router-Level Integration Tests

`TestSetupRouter_RegistersKeyRoutes` verifies that expected routes are registered by iterating `engine.Routes()` and checking for presence of method/path pairs. This catches missed route registrations when adding new handlers.

`TestSetupRouter_AuthGroupProtected` and `TestSetupRouter_AllUsersRouteProtected` confirm that authenticated routes return HTTP 401 without a token.

`TestSetupRouter_AccessTokenWithoutRequiredScopeGetsForbidden` and `TestSetupRouter_AccessTokenWithScopePasses` test the full JWT + scope middleware stack: a token with insufficient scopes gets HTTP 403, a token with the required scope gets HTTP 200.

## Service-Level Tests

Service tests interact through the service interface (`ports.go`) and use mock or in-memory repositories. The migrator test exercises `Runner.RunBatch` by injecting stub implementations of all four pipeline stages and verifying `BatchOutcome` fields.

The access token service test covers the full token lifecycle: create with scopes, list, and delete. It verifies that created tokens are parseable as valid access tokens with the expected scope list.

## Frontend Tests

The `web/tests/` directory uses Vitest with Vue Test Utils.

| Test file | Coverage |
|---|---|
| `editor/markdown.renderer.test.ts` | Markdown-to-HTML rendering output |
| `editor/markdown.performance.test.ts` | Rendering time for large documents |
| `editor/markdown.task-list.test.ts` | Task list checkbox rendering |
| `gallery/TheImageGallery.test.ts` | Gallery component mount and interaction |
| `gallery/usePhotoSwipeGallery.test.ts` | PhotoSwipe composable lifecycle |
| `stores/setting.init.test.ts` | Pinia setting store initialization logic |
| `utils/loadExternalAsset.test.ts` | Dynamic script/stylesheet injection utility |

Frontend tests run via `pnpm test` from the `web/` directory.

## Quality Artefacts

The `quality/` directory contains additional test and specification files:

- `functional_test.go` — functional tests against the running application
- `regression_test.go` — regression tests corresponding to resolved bug reports
- `CONTRACTS.md` — formal behavioral contracts for each subsystem
- `COVERAGE_MATRIX.md` — mapping from requirements to test coverage
- `TDD_TRACEABILITY.md` — traceability from test cases to requirements

These are maintained as part of the project's quality program and should be updated when new requirements or tests are added.

## Running Tests

Backend:

```shell
# Run all tests from the project root
go test ./...

# Run with race detector
go test -race ./...

# Run a specific package
go test ./internal/router/...
```

Frontend:

```shell
cd web
pnpm test          # run once
pnpm test --watch  # watch mode
```

Linting:

```shell
golangci-lint run   # lint
golangci-lint fmt   # format
```
