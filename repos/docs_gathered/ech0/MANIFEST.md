# Ech0 Documentation Manifest

| File | Description |
|---|---|
| architecture.md | High-level architecture, project layout, component lifecycle, dependency injection, and design philosophy |
| configuration.md | Complete environment variable reference and runtime-overridable settings |
| authentication.md | JWT tokens, scopes, OAuth2/OIDC, WebAuthn passkeys, and viewer context abstraction |
| eventbus.md | Busen event bus, event contracts, publisher facade, subscriber implementations, and dead letter handling |
| storage.md | VireFS unified storage layer, StorageManager, categories, key generation, backup integration |
| routing.md | Gin route groups, handler bundle, API endpoint surface, middleware stack, response envelope |
| webhooks.md | Webhook dispatcher, delivery flow, signature verification, dead letter queue, management API |
| logging.md | zap-based structured logging, in-memory log stream, async file writing, WebSocket streaming |
| migration.md | ETL pipeline (Extractor, Transformer, Validator, Loader), migration worker, v3-to-v4 path |
| scheduling.md | gocron task scheduler, four recurring jobs, dynamic backup schedule updates, worker pool |
| agent.md | Multi-provider AI agent, Generate function, Eino framework, event-driven invocation |
| testing.md | Test conventions, in-memory SQLite fixtures, router integration tests, frontend tests |
| MANIFEST.md | This file |
| _audit.md | Sources consulted, blacklist confirmation, and self-check results |
