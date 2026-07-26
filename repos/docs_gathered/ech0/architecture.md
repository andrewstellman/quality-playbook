# Ech0 Architecture and Design Philosophy

## Overview

Ech0 is a self-hosted personal microblog platform written in Go (backend) and Vue 3 (frontend). It is designed as a single-binary, low-footprint service that teams or individuals can run on any Linux, Windows, or ARM host. The central design goal is a timeline-first publishing experience where posts, links, and media live in a system the operator fully controls.

## Project Layout

```
ech0/
  cmd/                  CLI entry points (serve, backup)
  cmd/ech0/main.go      Binary entrypoint
  internal/             All private application packages
    app/                Component lifecycle orchestrator
    agent/              LLM provider bridge
    async/              Worker pool
    backup/             Archive and restore logic
    bootstrap/          Startup sequencing
    cache/              In-process Ristretto cache
    captcha/            Embedded CAPTCHA (gocap)
    cli/                Interactive CLI/TUI helpers
    config/             Environment-driven configuration
    database/           GORM/SQLite setup
    di/                 Wire-generated dependency injection
    event/              Busen event bus (bus, publisher, registry, subscriber)
    handler/            HTTP handler layer (one subpackage per domain)
    i18n/               Localization (go-i18n)
    middleware/         Gin middleware (auth, CORS, scope, maintenance)
    migrator/           ETL pipeline for data migration
    model/              Domain data types and DTOs
    persona/            System identity helpers
    repository/         Data access layer
    router/             Gin route registration
    server/             HTTP server lifecycle
    service/            Business logic (one subpackage per domain)
    storage/            VireFS unified storage manager
    swagger/            Auto-generated OpenAPI docs
    task/               gocron-based background scheduler
    transaction/        GORM transaction abstraction
    tui/                Bubbletea terminal UI
    util/               Shared utilities (crypto, jwt, log, etc.)
    webhook/            Webhook dispatcher
  pkg/
    viewer/             Public context abstraction for caller identity
  template/             Go HTML templates
  web/                  Vue 3 / Vite SPA
  docs/                 In-tree design documents
  quality/              Test and quality-assurance artefacts
```

## Layered Architecture

The backend follows a conventional layered architecture with strict import discipline:

```
handler  →  service  →  repository  →  database
              ↓
           event bus  →  subscribers  →  webhook dispatcher
```

Each layer communicates through interface types declared in `ports.go` files. The handler layer calls the service layer; the service layer calls repositories through interfaces. No layer imports a deeper peer's concrete type directly.

The aliasing convention is enforced throughout:
- Model layer imports use the `xxxModel` alias
- Utility layer uses `xxxUtil`
- Handler layer uses `xxxHandler`
- Service layer uses `xxxService`
- Repository layer uses `xxxRepository`

## Component Lifecycle

The `internal/app` package defines the application orchestrator. It implements a `Component` interface:

```go
type Component interface {
    Start(ctx context.Context) error
    Stop(ctx context.Context) error
}
```

The `App.Run()` method starts each registered component in order and reverses the list on shutdown. On signal reception (SIGINT, SIGTERM), it calls `Stop()` on every component in reverse-start order and supports a configurable stop timeout. Before and after start/stop, hooks (`[]Hook`) can be registered for setup and teardown tasks.

Components registered in the production application include:
- **Database** (GORM/SQLite provider)
- **EventRegistrar** (Busen bus subscriptions)
- **Server** (Gin HTTP runtime)
- **Tasker** (gocron background scheduler)
- **Migrator worker** (optional ETL background processor)

## Dependency Injection

Ech0 uses Google Wire for compile-time dependency injection. The `internal/di/wire.go` file declares provider sets:

- `InfraSet` — database, event bus, cache, transaction
- `HandlerGraphSet` — all handler, service, and repository bindings
- `EventGraphSet` — event subscribers and webhook dispatcher bindings
- `TaskerGraphSet` — background job bindings
- `MigratorGraphSet` — ETL pipeline bindings

Running `go generate` in `internal/di/` regenerates `wire_gen.go`. No manual wiring of constructor calls is needed when adding new subsystems: only a provider function and Wire set membership are required.

## Frontend Architecture

The `web/` directory contains a Vue 3 SPA built with Vite and styled with UnoCSS. State is managed with Pinia stores. The SPA communicates with the backend through a typed API client (`web/src/service/api/`) and a WebSocket connection for real-time log streaming.

The SPA is distributed as an embedded binary in the production Docker image so the server binary is fully self-contained. Development separates the frontend (port 5173) from the backend (port 6277) with a Vite proxy.

## Key Design Decisions

**Single-binary distribution.** The entire application — Go binary, embedded web assets, SQLite database — ships as one container image and requires no external runtime dependencies.

**Event-driven decoupling.** All inter-subsystem side effects (webhook dispatch, AI agent invocations, inbox updates) flow through the Busen event bus rather than direct calls, keeping the service layer free of cross-cutting concerns.

**Interface-first ports.** Every subsystem boundary is expressed as a Go interface in a `ports.go` file. Concrete implementations live in separate files and are wired at startup. This makes each subsystem independently testable.

**Configuration surface via environment variables only.** All runtime parameters are read from environment variables on startup (with `.env` file support via `godotenv`). There is no YAML or TOML configuration file at the application level.
