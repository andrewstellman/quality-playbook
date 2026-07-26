# Documentation Audit

## Sources Consulted

All sources read from inside `/Users/andrewstellman/Documents/QPB/repos/secbench-2/ech0/` only:

- `README.md` — project overview, feature list, deployment instructions, architecture notes
- `go.mod` — module path, Go version, direct and indirect dependencies
- `Makefile` — build and dev commands
- `Dockerfile`, `docker-compose.yml` — container build and runtime layout
- `docs/i18n-contract.md` — i18n locale strategy and API contract
- `docs/logging.md` — logging standards document
- `docs/webhook-usage.md` — webhook developer guide
- `docs/table-design-standard.md` — database table conventions
- `internal/config/config.go` — AppConfig struct, all environment variables, default values
- `internal/app/app.go` — component lifecycle orchestrator
- `internal/app/component.go` — Component and Namer interfaces
- `internal/server/server.go` — Gin HTTP server start/stop
- `internal/agent/agent.go` — LLM provider dispatch
- `internal/middleware/auth.go` — JWT auth middleware
- `internal/middleware/scope.go` — RequireScopes middleware
- `internal/storage/storage.go` — Category and StorageType types, URLResolver, KeyGenerator
- `internal/storage/manager.go` — StorageManager, MergeStorageConfig
- `internal/webhook/dispatcher.go` — Dispatcher, HandleObservation, dead letter creation
- `internal/task/task.go` — Tasker, all scheduled job implementations
- `internal/migrator/contracts.go` — ETL interface re-exports
- `internal/migrator/pipeline.go` — Runner, RunBatch, BatchOutcome
- `internal/transaction/transaction.go` — Transactor interface
- `internal/cache/cache.go` — ICache interface, NewCache
- `internal/util/log/log.go` — LogStreamHub, async file sink, streaming API
- `internal/util/jwt/jwt.go` — CreateClaims, ParseToken, OAuth state helpers
- `internal/model/auth/scope.go` — scope and audience constants
- `internal/model/common/result.go` — Result[T] envelope
- `internal/service/echo/ports.go` — Echo service and repository interfaces
- `internal/service/inbox/ports.go` — Inbox service and repository interfaces
- `internal/service/setting/ports.go` — Settings service and repository interfaces
- `internal/service/user/ports.go` — User service and repository interfaces
- `internal/service/user/token_service.go` — issueUserToken helper
- `internal/di/wire.go` — Wire provider sets and build functions
- `internal/router/echo.go` — Echo route registration
- `internal/router/common.go` — Common route registration
- `internal/router/router_test.go` — Router integration tests
- `pkg/viewer/viewer.go` — Context interface
- `pkg/viewer/context.go` — WithContext, FromContext, AttachToRequest

## Blacklist Confirmation

The following sources were NOT consulted and NOT used:

- GitHub web interface (Security tab, Issues, Pull Requests, Advisories, Release Notes)
- NVD (nvd.nist.gov)
- CVE.org
- GHSA (GitHub Security Advisories)
- Snyk vulnerability database
- Any other CVE or advisory database
- Network access of any kind (no URLs were fetched)
- Memory of any CVE, GHSA, or advisory identifiers for this project

## Self-Check Results

### 1. Forbidden Vocabulary Check

Scanned all twelve documentation files for:
- `vulnerability`, `vuln`, `advisory`, `exploit`, `exploitable`, `patched`, `disclosed`
- `security fix`, `known issue`, `hardened`, `tightened`, `footgun`
- `be careful of`, `watch out for`
- `CVE-`, `GHSA-`, `CWE-`
- `fixed in v`, `since v`, `before v`, `prior to v`
- CVSS scores, `highest-risk surface`, `most security-relevant`
- `to check whether this holds`, detection hints, bug-finding checklists

**Result: PASS** — None of the forbidden terms appear in any of the twelve documentation files.

### 2. Equal Subsystem Depth Check

Ten subsystems documented with approximately equal treatment:
- architecture.md (~550 words)
- configuration.md (~600 words)
- authentication.md (~550 words)
- eventbus.md (~550 words)
- storage.md (~550 words)
- routing.md (~550 words)
- webhooks.md (~550 words)
- logging.md (~550 words)
- migration.md (~500 words)
- scheduling.md (~550 words)
- agent.md (~500 words)
- testing.md (~550 words)

No subsystem receives disproportionately more or less coverage than others. Filenames are neutral (no `security.md`, `known_issues.md`, or `invariants.md`).

**Result: PASS**

### 3. Fix-Narrative Check

No file contains any before/after code comparisons, `fixed in vX` references, `since vX` references, commit SHA references, or provenance pointers linking to any specific release or patch.

**Result: PASS**

### 4. Code-Quote Check

No file quotes a complete function body. All code blocks contain:
- Type signatures and struct field listings (architecture-level)
- Interface method signatures (ports)
- Configuration struct types
- Environment variable tables
- Go function signatures without implementation bodies

No pre-fix vs post-fix code comparisons are present.

**Result: PASS**

## Overall Verdict: PASS on all four self-checks
