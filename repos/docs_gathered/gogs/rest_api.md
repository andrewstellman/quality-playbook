# REST API

The REST API is mounted under `/api/v1/` by `apiv1.RegisterRoutes(m)` in `internal/cmd/web.go`. Wire-format types come from the companion module `github.com/gogs/go-gogs-client`, imported as `api` throughout `internal/route/api/v1/`.

## URL shape

Routes follow GitHub-style verbs and paths so GitHub clients can be retargeted with minimal change:

- `/api/v1/markdown` and `/api/v1/markdown/raw`.
- `/api/v1/users/:username[/...]` — public information and follow management.
- `/api/v1/user/...` — authenticated-user variants (emails, keys, following, issues).
- `/api/v1/repos/:owner/:reponame/...` — repository content, hooks, collaborators, issues, pulls, labels, milestones, contents, releases.
- `/api/v1/orgs/:org/...` — organization metadata, teams, members.
- `/api/v1/admin/...` — site-admin endpoints.
- `/api/v1/repositories/search` — global repository search.

Each repository route group is wrapped by `repoAssignment()` so handlers can read `c.Repo.Repository`, `c.Repo.Owner`, and `c.Repo.AccessMode` directly.

## Authentication

Four mechanisms, applied via per-group middleware:

- `reqBasicAuth()` — HTTP Basic credentials (used for token creation).
- `reqToken()` — a personal access token in `Authorization: token <value>` or as the HTTP Basic password against any username.
- `reqAdmin()` — `User.IsAdmin == true`.
- `reqRepoWriter()` / `reqRepoAdmin()` — resolved repository access mode at least Write or Admin.

Anonymous reads against public repositories work without middleware on listing endpoints; on per-repository endpoints, `repoAssignment()` performs the public-floor check via `db.Perms.AccessMode`.

## API context

Handlers receive `*context.APIContext` (in `internal/context/api.go`). It wraps `*Context` and adds JSON-only helpers:

- `Error(status int, title string, obj any)` — emits `{"message": ..., "url": ...}` plus the HTTP status.
- `NotFound()` — convenience 404.
- `NotFoundOrError(err, log)` — 404 when `err` is a `NotFound` marker, 500 otherwise.

The standard JSON error payload includes a `url` pointing at the API docs.

## Request and response shapes

Representative wire types in `go-gogs-client`:

- `api.User`, `api.Repository`, `api.Organization`, `api.Team`.
- `api.Issue`, `api.PullRequest`, `api.Label`, `api.Milestone`, `api.Comment`.
- `api.Release`, `api.ReleaseAttachment`.
- `api.Branch`, `api.Tag`, `api.RepoCommit`.
- `api.Hook`, `api.Payload`, and per-event payloads (`PushPayload`, `IssuePayload`, …).

`internal/route/api/v1/convert/` adapts persistent models (`db.User`, `db.Repository`, …) into wire shapes. Conversion functions are pure and unit-testable.

## Pagination and binding

Listing endpoints accept `page` (1-based) plus a fixed page size from `[api] MaxResponseItems` (default 50). Page headers follow `Link: <...>; rel="next"`.

`binding.Bind(target{})` adapts request bodies and form data into option structs (`api.CreateRepoOption`, `api.CreateHookOption`, `api.EditIssueOption`, `form.MigrateRepo`). Binding errors flow to the handler so it can produce a 422 with field details.

## Misc and admin endpoints

`POST /api/v1/markdown` renders markdown for the supplied source; `POST /api/v1/markdown/raw` accepts the raw payload without JSON envelope. `GET /api/v1/version` and `GET /api/v1/healthcheck` round out the helpers.

`/api/v1/admin/...` requires `reqToken()` and `reqAdmin()`. The endpoints mirror the web admin pages: user CRUD (`POST/PATCH/DELETE /admin/users/:username`), keys and repos on behalf of users, organization creation, and team/member management. They reuse the same `convert` adapters.

## Hooks and contents APIs

`GET/POST /repos/:owner/:reponame/hooks` and `PATCH/DELETE /repos/:owner/:reponame/hooks/:id` manage repository webhooks. Payloads use `api.CreateHookOption` (`Type`, `Config`, `Events`, `Active`). `POST .../hooks/:id/tests` enqueues a synthetic push so users can verify the configured URL.

`GET /repos/:owner/:reponame/contents/:path` returns Base64-encoded file contents and the file hash. `PUT` accepts `api.UpdateRepoFileOptions` and rewrites the file in a server-side commit, respecting `[repository.editor]` settings.

## Versioning

The API is exposed under `/v1`. New features add endpoints rather than reshaping existing ones; the `convert` package isolates wire-shape evolution from internal model changes. `go-gogs-client` is versioned independently and is the canonical reference for the wire format.
