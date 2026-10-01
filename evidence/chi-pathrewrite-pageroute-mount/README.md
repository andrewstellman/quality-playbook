# chi: `PathRewrite` and `PageRoute` use `r.URL.Path`, so inside a mounted router they don't do what they do at the root

**Verdict: NEEDS-MAINTAINER-INPUT.** Both behaviours reproduce on master, but the intended semantics inside a mounted router aren't documented. No fix is proposed. The patch here adds tests only, and those tests encode *one* possible reading.
QPB source: chi-1.6.0 BUG-002.

## Pinned upstream
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (2026-09-18), go1.25.1 linux/arm64.

## Behaviour
- `PathRewrite` (`middleware/path_rewrite.go:9-16`) rewrites `r.URL.Path`. At the root this changes routing, because `routeHTTP` falls back to `r.URL.Path` when `rctx.RoutePath` is empty (`mux.go:455-470`). Inside a mounted router, `rctx.RoutePath` is already set, so the rewrite has **no effect on routing**. In `red.log`, `r.URL.Path` becomes `/api/v1/endpoint` but the sub-router still routes `/endpoint` and returns 404.
- `PageRoute` (`middleware/page_route.go:10-19`) compares `r.URL.Path`, the full path. Inside a router mounted at `/site`, `PageRoute("/about", ...)` never fires for `/site/about`. `PageRoute("/site/about", ...)` would work.
- Other chi middlewares that are mount-aware (`StripSlashes`, `RedirectSlashes` at `middleware/strip.go:17-22,44-49`) read `rctx.RoutePath` first.

## What the docs say
- `PathRewrite`: "a simple middleware which allows you to rewrite the request URL path." It does rewrite the URL path. Its effect on routing is not stated. The only test (`TestPathRewrite`) is at the root.
- `PageRoute`: "allows you to route a static GET request at the middleware stack level." It does not say whether `path` is absolute or relative to the mount.

## Why no fix
- For `PageRoute`, an absolute path is a valid reading and works today. Switching to relative matching would break anyone who passes absolute paths.
- For `PathRewrite`, the QPB-proposed fix rewrites `rctx.RoutePath` *instead of* `r.URL.Path` when mounted. That changes what handlers see in `r.URL.Path`. A backward-compatible alternative (rewrite both) is possible, but it still changes behaviour and needs a maintainer decision.

## Evidence
- `red.log`: both new tests fail on master (`404`, and body `"catch-all"`).
- `suite-before.log`: master passes.
- No green or suite-after logs: no fix was written.

## Disclosure search
`repo:go-chi/chi PathRewrite OR PageRoute`: 1 result, #639 (the original PageRoute PR, merged 2021, no description). Nothing about mounted routers.

## Open question
Are these middlewares meant to work relative to a mount point? If yes, `PathRewrite` is the stronger case to raise, since it fails silently while appearing to succeed. That question fits an issue better than a PR.
