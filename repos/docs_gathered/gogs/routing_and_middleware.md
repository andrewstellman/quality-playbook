# Routing and Middleware

The HTTP layer is built on [Macaron](https://gopkg.in/macaron.v1). The `web` subcommand in `internal/cmd/web.go` builds a `*macaron.Macaron`, registers every route, and starts the listener.

## Macaron instance

`newMacaron()` composes middleware in a fixed order:

1. `macaron.Logger()` (skippable via `[server] DISABLE_ROUTER_LOG`).
2. `macaron.Recovery()`.
3. `gzip.Gziper()` when `[server] EnableGzip`.
4. URL-prefix middleware for `fcgi`.
5. `macaron.Static` registrations: custom public, embedded public (with ETag), avatar upload path, repository avatar upload path.
6. `macaron.Renderer` with templates from `templates/` plus a custom-directory override; `template.FuncMap()` registers Gogs' template helpers.
7. `i18n.I18n` for translations (default `en-US`).
8. `cache.Cacher` (memory, memcache, Redis).
9. `captcha.Captchaer` for registration captcha.
10. `toolbox.Toolboxer` — exposes `/healthcheck` and similar, with a database-ping check.

Session, CSRF, and authentication middleware are attached inside route-group registration so they apply only to relevant subtrees.

## Route groups

`runWeb` creates three toggles up front:

- `reqSignIn` — requires a logged-in session.
- `ignSignIn` — populates the user if present, respects `[auth] REQUIRE_SIGNIN_VIEW`.
- `reqSignOut` — requires the caller be anonymous.

`bindIgnErr` (from `go-macaron/binding`) binds form bodies and continues to the handler on binding failure so the handler can re-render with field errors.

Top-level grouping:

- `/` (home, explore, `/install`, `/issues`, `/pulls`).
- `/user/...` — sign-in, sign-up, OAuth callbacks, two-factor recovery, dashboard, settings.
- `/org/...` — organization management.
- `/repo/...` — creation, migration, fork.
- `/<username>/<reponame>/...` — repository view, commits, branches, issues, pulls, wiki, settings.
- `/admin/...` — site admin.
- `/api/v1/...` — REST API.
- LFS routes and Git smart-HTTP routes under `/<username>/<reponame>.git/`.
- `/dev/template/:name` — developer template renderer (dev mode only).

`m.SetAutoHead(true)` makes every GET also respond to HEAD.

## Serving the listener

`runWeb` calls `route.GlobalInit` to load configuration, initialize the database, set up cron, and start the optional built-in SSH server. Then it switches on `conf.Server.Protocol`:

- `http` — `http.ListenAndServe`.
- `https` — `http.ListenAndServeTLS` with TLS config respecting `TLS_MIN_VERSION`.
- `fcgi` — `fcgi.Serve` behind a FastCGI front end.
- `unix` — Unix domain socket with the configured permission mask.

## Per-request context

Handlers receive Gogs-specific wrappers from `internal/context/`:

- `*context.Context` — web pages. Carries `User`, `IsLogged`, `IsBasicAuth`, `IsTokenAuth`, `Repo`, `Org`, `Cache`, `Session`, `Flash`, `Link`, `csrf`. Helpers include `Tr`, `Success(template)`, `Error(status, log)`, `NotFound()`, `Redirect(...)`.
- `*context.APIContext` — REST handlers. Provides `Error(status, title, obj)`, `NotFoundOrError(err, log)`, JSON response helpers.
- `*HTTPContext` (in `internal/route/repo/http.go`) — Git smart-HTTP, authenticates via HTTP Basic and resolves owner/repository.

`context.Contexter()` and `context.APIContexter()` produce these and resolve the active repository or organization from URL parameters.

## CSRF, sessions, and customization

CSRF tokens are issued by the `csrf` middleware, embedded in templates as hidden fields, and exposed to AJAX via cookie. The cookie name is `[session] CSRF_COOKIE_NAME`. Session storage uses `go-macaron/session`; the provider comes from `[session] Provider` and `ProviderConfig`.

Because custom paths are registered first, deployments ship per-site branding by placing files in `custom/public/img/logo.png` or `custom/templates/home.tmpl`. `AppendDirectories` makes custom HTML templates extend rather than wholesale replace the embedded ones.
