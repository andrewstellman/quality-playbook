# chi: `middleware.GetHead` looks up the wrong path inside a mounted sub-router

**Verdict: CONFIRMED.** Reproduced on unpatched master, fixed, full suite green. No existing issue or PR found (searches below).
QPB source: chi-1.6.0 run, BUG-014 (found by that run's Phase 4 Council spec audit).

## Pinned upstream
- Repo: https://github.com/go-chi/chi
- SHA: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (commit date 2026-09-18T13:51:53+02:00, "middleware: honor Discard when flushing (#1185)")
- Cloned 2026-09-27.
- Toolchain: go1.25.1 linux/arm64, official tarball from go.dev (sha256 `65a3e34f...a95a87d`, matches go.dev's published checksum). Ubuntu's `golang-go` is 1.18, too old for chi's `go 1.24`. `GOTOOLCHAIN=local`.

## Defect
`GetHead` checks whether a dedicated HEAD route exists by calling `rctx.Routes.Match(tctx, "HEAD", routePath)`.

- `middleware/get_head.go:13-29`: `routePath` is `rctx.RoutePath`. Inside a mounted sub-router, `Mount`'s handler has already shifted that value past the mount point (`mux.go:327`, `rctx.RoutePath = mx.nextRoutePath(rctx)`), so it is relative to the sub-router.
- `mux.go:72-75` and `mux.go:83`: `rctx.Routes` is set once, to the top-level mux. A sub-router's `ServeHTTP` reuses the parent's context and never changes it.

So when `GetHead` is `Use()`d inside a mounted router, it asks the **root** router about a **sub-router-relative** path. Two consequences, both reproduced:

1. A dedicated `Head(...)` handler in the sub-router is ignored. The request is served by the GET handler.
2. If the root happens to have a HEAD route at the same relative path, the lookup gives a false positive, the GET fallback is skipped, and the sub-router answers **405** for a path that has a GET handler.

`GetHead` used on the root router (the existing `TestGetHead`) is not affected.

## Expected behaviour
The middleware's doc comment (`middleware/get_head.go:9`):

> "GetHead automatically route undefined HEAD requests to GET handlers."

In case 1 the HEAD request is *defined*, but it still goes to GET. In case 2 it is undefined, but it never reaches the GET handler. The README middleware table says the same thing: "Automatically route undefined HEAD requests to GET handlers".

## Fix (see `0001-*.patch`)
Inside a mounted router (`len(rctx.RoutePatterns) > 0`, meaning a parent has already matched a pattern), do the look-ahead against the root using the full request path (`r.URL.RawPath`, or `r.URL.Path` if that's empty), the same way the root's `routeHTTP` picks its path. `root.Match` already recurses into mounted sub-routers. The GET fallback still sets `rctx.RoutePath` to the relative path, as before. At the root level (`RoutePatterns` empty) nothing changes.

## Red / green
- `red.log`: new `TestGetHeadInMountedRouter` fails on both assertions: `got "get" (status 200)` and `got "" (status 405)`.
- `green.log`: passes with the fix.
- `nested-mount-check.log`: scratch test, **not** in the patch. It covers two levels of mounting with a URL param in the mount pattern (`/api` → `/{tenant}` → `GetHead`). On master, `HEAD /api/acme/x` returns `X-H="get"`. With the fix it returns `"head:acme"`. The GET fallback and 404 behave the same on both.
- `suite-before.log` / `suite-after.log`: `go test -count=1 ./...` passes on both (the after run is at the patched commit `2ff7bfb`).
- `gofmt -l` and `go vet ./middleware`: clean.

## Disclosure search (GitHub API search via web_fetch, 2026-09-27)
- `repo:go-chi/chi GetHead`: 14 results. All are about the 405 `Allow` header (#1030, PRs #1031, #1095, #1178, #1181, #1142), the original feature (#238, #247, #248), a nil-pointer issue from a v1→v5 upgrade (#980), CleanPath (#786/#787), or #755. #755 is root-level `GetHead` + `Route` returning 405 (closed 2022). The root-level case passes on current master (`TestGetHead`). **None cover `GetHead` inside a mounted router.**
- `repo:go-chi/chi HEAD in:title mount OR subrouter OR sub-router`: nothing relevant.
- `repo:go-chi/chi HEAD mounted OR "sub-router" OR subrouter GET handler`: 27 results by title, none relevant.
- `repo:go-chi/chi "rctx.Routes"`: #623 (closed 2022, feature request). It notes that `Context.Routes` "only stores the root Router" and asks for a `SubRoutes` field. Same root cause, not reported as a GetHead bug. #940 is the SupressNotFound PR.

## Open questions for the maintainer / Andrew
- The heuristic "inside a mount if `RoutePatterns` is non-empty" is small, but it is indirect. The alternative is the core change requested in #623: expose the current sub-router on the context. That is a bigger API decision.
- If middleware *inside* the sub-router rewrites `rctx.RoutePath` before `GetHead` runs (e.g. `StripSlashes`), the full-path look-ahead does not see that rewrite. Current master is also wrong in that case (it asks the root about a relative path), so this is not a regression. It is still a limitation.
- chi has many open PRs touching `GetHead` (the Allow-header ones above). They don't touch the look-ahead line, but a rebase may be needed if one merges first.
