# middleware: fix GetHead look-ahead inside a mounted router

When `GetHead` is used inside a mounted sub-router, its look-ahead asks the top-level router (`rctx.Routes`) about the sub-router-relative `rctx.RoutePath`. As a result:

- a sub-router's own `Head(...)` handler is ignored and the GET handler runs instead, and
- if the parent has a HEAD route at the same relative path, the GET fallback is skipped and the request gets a 405.

```go
sub := chi.NewRouter()
sub.Use(middleware.GetHead)
sub.Head("/hi", headHandler) // never called for HEAD /api/hi
sub.Get("/hi", getHandler)
r := chi.NewRouter()
r.Mount("/api", sub)
```

This change runs the look-ahead with the full request path when a parent router has already matched (`len(rctx.RoutePatterns) > 0`). The root's `Match` already recurses into mounted routers. Behaviour of `GetHead` on the root router is unchanged. Adds `TestGetHeadInMountedRouter` covering both cases. It fails on master and passes with the fix. `go test ./...` passes.

---
*Note: this issue was found by a [Quality Playbook](https://github.com/andrewstellman/quality-playbook) run on chi. The reproduction and fix were done by Claude (Anthropic).*
