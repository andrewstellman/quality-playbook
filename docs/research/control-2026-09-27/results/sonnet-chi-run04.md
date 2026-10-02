# Code review — go-chi/chi `middleware/`

Repo: go-chi/chi, pinned commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`
Scope: `middleware/`

## Defect 1 — `SupressNotFound` corrupts the shared routing context, causing false 404s for any mounted (`r.Mount(...)`) route

**File:** `middleware/supress_notfound.go`, lines 281–293 (the bug is the call on line 285):

```go
func SupressNotFound(router *chi.Mux) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			rctx := chi.RouteContext(r.Context())
			match := rctx.Routes.Match(rctx, r.Method, r.URL.Path)
			if !match {
				router.NotFoundHandler().ServeHTTP(w, r)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
```

**What goes wrong:** The middleware "peeks" at whether a route exists by calling `Match` using the **live** `*chi.Context` that is attached to the request (`chi.RouteContext(r.Context())`) — the same context object that chi's router will use moments later to perform the *real* routing dispatch in `Mux.routeHTTP`. `Match`/`Find` mutate that context as a side effect of walking the tree (recorded `URLParams`, `RoutePatterns`, and, critically, `RoutePath` for any route that resolves through a subrouter/mount). When the route in question is reached via `r.Mount(...)` (a very common and documented chi pattern), the probe call leaves `rctx.RoutePath` set to the *already-stripped* sub-path from the probe traversal. The real dispatch in `Mux.routeHTTP` (`mux.go`) then reads that same field:

```go
routePath := rctx.RoutePath
if routePath == "" {
    ...use r.URL.Path...
}
```

Because `RoutePath` is no longer empty (it was set by the probe), the top-level router's real `FindRoute` call is performed with the wrong path, and the request that should have matched the mounted route is reported as not found — even though a fully equivalent, unwrapped router mounted the exact same handler successfully.

Reproduced directly against this checkout:

```go
sub := chi.NewRouter()
sub.Get("/users/{id}", handler)

root := chi.NewRouter()
root.Use(middleware.SupressNotFound(root))
root.Mount("/api", sub)

// GET /api/users/42
```
Result: **404 "404 page not found"**. Removing `middleware.SupressNotFound(root)` from `root.Use(...)` (or hitting a non-mounted, directly-registered route) makes the same request return `200 id=42` as expected. Confirmed with `go run` against three cases: direct route + `SupressNotFound` → 200; mounted route + `SupressNotFound` → 404; mounted route without `SupressNotFound` → 200.

**Why it is wrong:** `mux.go` explicitly documents this exact hazard on the `Match`/`Find` methods that `SupressNotFound` calls:

```go
// Match searches the routing tree for a handler that matches the method/path.
// It's similar to routing a http request, but without executing the handler
// thereafter.
//
// Note: the *Context state is updated during execution, so manage
// the state carefully or make a NewRouteContext().
func (mx *Mux) Match(rctx *Context, method, path string) bool {
```

The package's own `GetHead` middleware (`middleware/get_head.go`) does this correctly for the analogous "look ahead before routing" use case, explicitly allocating a scratch context for exactly this reason:

```go
// Temporary routing context to look-ahead before routing the request
tctx := chi.NewRouteContext()
if !rctx.Routes.Match(tctx, "HEAD", routePath) {
```

`SupressNotFound` passes `rctx` (the live context) instead of a fresh `chi.NewRouteContext()`, so its probe corrupts the state the real dispatch depends on. The doc comment for `SupressNotFound` itself promises it will "quickly respond with a 404 if the route is not found" and otherwise be transparent ("continue to the next middleware handler") — instead it actively breaks routing for a whole class of legitimate, matching requests.

There is no test file for this middleware (`supress_notfound_test.go` does not exist), which is consistent with this regression going unnoticed.

**Severity:** High. Any application that puts `middleware.SupressNotFound` in front of a router that also uses `Mount` (sub-routers, versioned APIs, mounted third-party handlers — one of chi's headline features) will see valid requests to mounted routes fail with 404, in production traffic, unconditionally, at 100% reproduction rate.

**Suggested fix:** Use a scratch context for the probe, mirroring `GetHead`:

```go
func SupressNotFound(router *chi.Mux) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tctx := chi.NewRouteContext()
			if !router.Match(tctx, r.Method, r.URL.Path) {
				router.NotFoundHandler().ServeHTTP(w, r)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
```
(Using `router.Match` directly also removes the now-unnecessary dependency on `chi.RouteContext(r.Context())`, which could be `nil` if this middleware runs before chi has attached a routing context.)

---

## Other files reviewed, no confident defects found

I read every non-test `.go` file in `middleware/`: `basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, `wrap_writer.go`. I also read `mux.go`, `tree.go`, `chi.go`, and `context.go` in the repo root for context on routing-context semantics.

Notable areas I checked closely but did not find a defect confident enough to report:
- `client_ip.go` — the XFF-walking, CIDR-trust, and trusted-proxy-count logic (`walkXFF`, `ClientIPFromXFF`, `ClientIPFromXFFTrustedProxies`, `parseHeaderAddr`) is intricate but, traced through carefully (including the right-to-left merge across multiple XFF header lines and v4-mapped/zone normalization), matches its own documentation.
- `compress.go` — `matchAcceptEncoding`'s use of `strings.Contains` for matching `Accept-Encoding` tokens is loose (could match on unintended substrings) but this is long-standing behavior, not something the code's own docs contradict, and I could not construct a case where it causes an actually wrong compression choice for realistic encoding names.
- `wrap_writer.go` — the `Tee`/`Discard`/`ReadFrom` byte-counting paths are subtle (there's an explicit comment warning against double-counting bytes) but the accounting checks out under inspection.
- `basic_auth.go` — password comparison uses `subtle.ConstantTimeCompare`, but the username lookup (`creds[user]`) is a plain map access, which is a theoretical timing side-channel on valid usernames. I did not report this as a defect: it's a long-standing, documented-as-"simple" design tradeoff in this exact middleware rather than a contradiction of stated behavior, and mitigating it fully is a design decision, not a one-line bug.

## Files read

- `middleware/basic_auth.go`
- `middleware/clean_path.go`
- `middleware/client_ip.go`
- `middleware/compress.go`
- `middleware/content_charset.go`
- `middleware/content_encoding.go`
- `middleware/content_type.go`
- `middleware/get_head.go`
- `middleware/heartbeat.go`
- `middleware/logger.go` (read via combined dump, cross-checked)
- `middleware/maybe.go`
- `middleware/middleware.go`
- `middleware/nocache.go`
- `middleware/page_route.go`
- `middleware/path_rewrite.go`
- `middleware/profiler.go`
- `middleware/realip.go`
- `middleware/recoverer.go`
- `middleware/request_id.go`
- `middleware/request_size.go`
- `middleware/route_headers.go`
- `middleware/strip.go`
- `middleware/sunset.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`
- `middleware/throttle.go`
- `middleware/timeout.go`
- `middleware/url_format.go`
- `middleware/value.go`
- `middleware/wrap_writer.go`
- `mux.go` (for `Mux.Match`/`Mux.Find`/`Mux.ServeHTTP`/`Mux.routeHTTP` semantics)
- `tree.go` (for `FindRoute`/`findRoute` context-mutation behavior)
- `context.go` (for `RouteContext`/`NewRouteContext`)

I did not read the `*_test.go` files' contents in depth beyond confirming `supress_notfound_test.go` does not exist; I built and ran a standalone reproduction program against a local module replace of this checkout (`go run`) to confirm Defect 1 rather than relying on static reading alone.
