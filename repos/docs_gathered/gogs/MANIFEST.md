# Gogs documentation corpus

Reference documentation for the `gogs` self-hosted Git service captured at one historical point in its main branch.

## Files

- `architecture_overview.md` — top-level binary, command structure, package layout, embedded assets, and the relationship between subcommands.
- `configuration.md` — INI configuration loading, the typed sections in `internal/conf/static.go`, custom directory layout, and authentication source files.
- `routing_and_middleware.md` — Macaron-based HTTP router, middleware composition, route grouping, and per-request context wrappers.
- `database_layer.md` — GORM + XORM persistence layer, supported backends, store interfaces, and migration runner.
- `permission_model.md` — `AccessMode` enum, the access table, permission resolution rules, and how organization teams and site-admin status interact with per-repository access.
- `authentication_backends.md` — `Provider` interface, the four external backends (LDAP, SMTP, PAM, GitHub), the `LoginSource` store, token authentication, reverse-proxy authentication, and two-factor enrollment.
- `git_protocols.md` — smart HTTP, the optional built-in SSH server, the external sshd `serv` shim, Git LFS routes, and the working-pool serialization model.
- `webhooks_and_background_jobs.md` — webhook events, the in-process delivery queue, hook task lifecycle, cron jobs, and the mailer.
- `rest_api.md` — `/api/v1/` route map, API authentication, request and response shapes from `go-gogs-client`, pagination, admin endpoints, and the contents API.
