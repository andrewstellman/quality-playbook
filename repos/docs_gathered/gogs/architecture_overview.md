# Architecture Overview

Gogs is a self-hosted Git service written in Go and shipped as a single static binary. Its vision is a "simple, stable and extensible self-hosted Git service that can be set up in the most painless way." It targets whatever Go targets — Linux, macOS, Windows, and ARM hosts.

## Top-level binary

`main` lives at the repository root in `gogs.go` and uses `urfave/cli` to dispatch into subcommands:

- `web` — start the HTTP server (the long-lived process).
- `serv` — invoked from a Git SSH session for a registered key.
- `hook` — invoked by Git server-side hooks (pre-receive, update, post-receive).
- `cert` — generate a self-signed TLS certificate.
- `admin` — administrative actions.
- `import` — bulk import utilities.
- `backup` / `restore` — database and asset archive helpers.

Each subcommand is in its own file under `internal/cmd/`.

## Package layout

Library code lives under `internal/` so it is not importable externally. Top-level directories:

- `conf/` — embedded default assets (`app.ini`, locales, license/gitignore/readme/label templates).
- `docker/` — Dockerfiles and supervisord configuration.
- `docs/` — `admin/`, `dev/`, `user/` documentation.
- `internal/` — all application source.
- `public/`, `templates/` — built static assets and HTML templates, embedded into the binary.
- `scripts/` — packaging scripts.

Inside `internal/`, packages map to subsystems: `app/`, `cmd/`, `conf/`, `context/`, `cron/`, `db/`, `auth/`, `route/`, `ssh/`, `markup/`, `email/`, `avatar/`, `process/`, `sync/`, `template/`, `form/`, `mocks/`, plus small utilities (`errutil`, `lfsutil`, `netutil`, `osutil`, `pathutil`, `strutil`, `tool`, `userutil`, `repoutil`).

## Three Git transports

The binary supports SSH (an external `sshd` plus a `serv` shim, or the built-in `golang.org/x/crypto/ssh` server), smart HTTP/HTTPS, and Git LFS over HTTP. Each transport authenticates independently and delegates to common repository-storage code (see `git_protocols.md`).

## Process model

Gogs runs as a single OS process with goroutines for the HTTP server, the optional SSH server, the cron scheduler, the webhook delivery queue, and per-repository synchronization pools. Primitives in `internal/sync/` provide an `ExclusivePool` (per-repository serialization) and a `UniqueQueue` (deduplicated work). Logging uses `unknwon.dev/clog/v2`.

## Asset embedding and build

Default configuration files, HTML templates, locales, license/gitignore/readme templates, and built CSS/JS are embedded via Go's `embed` package. Files dropped into `custom/` shadow embedded versions. `[server] LOAD_ASSETS_FROM_DISK = true` switches to disk-backed reads — useful during iteration.

The project uses [Task](https://github.com/go-task/task) as its build tool: compile the Go binary, build frontend assets (Less → CSS), and run code generation. `docs/dev/local_development.md` documents the development setup. The Dockerfile produces an Alpine-based image with the binary, embedded assets, and a supervisord-managed SSH server inside the container (under `docker/`).

## Public API client

The companion module `github.com/gogs/go-gogs-client` defines request and response struct types for the REST API. The server imports it as `api` throughout `internal/route/api/v1/` so wire types stay in lock-step with the client.
