# Code Review: chi `middleware/` (commit 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc)

## Summary

Three confirmed defects (one high, two medium), plus one lower-confidence
correctness concern. All were traced by reading the code and cross-checking
against chi's own documented API contracts, RFC 9110, and sibling code in the
same package; the first three were also confirmed by writing and running a
small reproduction against the actual checkout.

---

## 1. `SupressNotFound` corrupts routing state for any mounted sub-router, causing false 404s

**File:** `middleware/supress_notfound.go`, lines 15-26

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

**What goes wrong:** the middleware does a "trial match" to decide whether to
short-circuit to the 404 handler, but it performs that trial match using the
*live* `*chi.Context` pulled from the request (`chi.RouteContext(r.Context())`)
— the same context object the router will use moments later to actually route
the request. `chi.Mux.Match`/`Find` (`mux.go:373-405`) mutate that context as a
side effect: when the matched route lives behind a `Mount()`, `Find` sets
`rctx.RoutePath = mx.nextRoutePath(rctx)` (`mux.go:397`), rewriting it to the
sub-router-relative path (e.g. `/users` instead of `/api/users`). That
mutated `RoutePath` then leaks into `Mux.routeHTTP` (`mux.go:453-471`), which
uses `rctx.RoutePath` verbatim if it is non-empty (`mux.go:460-462`) — but it
uses it against the **top-level** router's tree, not the sub-router's. The
top-level tree has no route for `/users`, so the request 404s even though
`/api/users` is a real, matched route.

I confirmed this by reproducing the exact pattern used here (trial-match with
the live `rctx`) against a router with one `Mount()`:

```
=== RUN   TestSuppressNotFoundStyleMatchCorruptsMountedRoute
    zzsupp_test.go:39: expected 200 from mounted subrouter route, got 404
--- FAIL
```

A `GET /api/users` that should succeed returns 404.

**Why it's wrong:** chi's own `Mux.Match` doc says exactly this, in
`mux.go:369-372`:

```go
// Match searches the routing tree for a handler that matches the method/path.
// It's similar to routing a http request, but without executing the handler
// thereafter.
//
// Note: the *Context state is updated during execution, so manage
// the state carefully or make a NewRouteContext().
```

`SupressNotFound` ignores this warning. Contrast with `GetHead` in the very
same `middleware` package (`middleware/get_head.go:24`), which does the
equivalent look-ahead match correctly:

```go
// Temporary routing context to look-ahead before routing the request
tctx := chi.NewRouteContext()
...
if !rctx.Routes.Match(tctx, "HEAD", routePath) {
```

`GetHead` passes a disposable `tctx`; `SupressNotFound` passes the live
`rctx`. `SupressNotFound`'s own doc comment ("will quickly respond with a 404
if the route is not found ... handy to put at the top of your middleware
stack") promises transparent behavior for routes that DO exist — instead it
breaks them whenever they're behind a mount.

**Severity:** High. Any app that uses `SupressNotFound` together with
`r.Mount(...)` (a very common chi pattern — sub-routers, API versioning,
grouped routes) will see legitimate mounted routes fail with 404. This is
silent: no error, no panic, just a wrong response.

**Suggested fix:** use a fresh routing context for the trial match, exactly
as `GetHead` does:

```go
tctx := chi.NewRouteContext()
match := router.Match(tctx, r.Method, r.URL.Path)
```

(Note also that `rctx` from `chi.RouteContext(r.Context())` could be `nil`
in unusual call contexts, which `router.Match`/`chi.NewRouteContext()`
avoids entirely.)

---

## 2. `Compressor.selectEncoder` treats `;q=0` as acceptance, contradicting RFC 9110 Accept-Encoding semantics

**File:** `middleware/compress.go`, lines 259-266 (`matchAcceptEncoding`)

```go
func matchAcceptEncoding(accepted []string, encoding string) bool {
	for _, v := range accepted {
		if strings.Contains(v, encoding) {
			return true
		}
	}
	return false
}
```

**What goes wrong:** this does a plain substring test, not a token/qvalue
parse. A client that sends `Accept-Encoding: gzip;q=0, deflate` — explicitly
declaring gzip *unacceptable* while allowing deflate — still matches on
`"gzip;q=0, deflate"` containing the substring `"gzip"`, so `gzip` is
selected anyway (gzip has priority in `encodingPrecedence`, being the last
one registered — see `NewCompressor`, `middleware/compress.go:135-137`).

Confirmed by reproduction:

```
=== RUN   TestCompressQZeroRepro
    zzcompress_test.go:19: Content-Encoding: "gzip"
    zzcompress_test.go:21: client explicitly refused gzip (q=0) but server used gzip anyway
--- FAIL
```

**Why it's wrong:** RFC 9110 §12.5.3 (Accept-Encoding) defines `q=0` as
"not acceptable" for that coding. Sending gzip-encoded content to a client
that set `gzip;q=0` violates the negotiation the client asked for — in the
worst case the client has `q=0` on gzip *because* it cannot decode gzip
(e.g. a proxy or tool without gzip support), so the response body becomes
undecodable to it.

**Severity:** Medium. Requires a specific, if standards-compliant, header
from the client; most browsers never send `q=0`, but proxies, API clients,
and deliberately-configured HTTP clients do.

**Suggested fix:** parse `Accept-Encoding` into `(name, qvalue)` tokens
(splitting on `,` then on `;`, defaulting `q=1` when absent) and skip any
name with `q=0`; also honor an explicit `q=0` on `*` correctly.

---

## 3. `compressResponseWriter.isCompressible` compares `Content-Type` case-sensitively

**File:** `middleware/compress.go`, lines 296-309

```go
func (cw *compressResponseWriter) isCompressible() bool {
	// Parse the first part of the Content-Type response header.
	contentType := cw.Header().Get("Content-Type")
	contentType, _, _ = strings.Cut(contentType, ";")

	// Is the content type compressible?
	if _, ok := cw.contentTypes[contentType]; ok {
		return true
	}
	if contentType, _, hadSlash := strings.Cut(contentType, "/"); hadSlash {
		_, ok := cw.contentWildcards[contentType]
		return ok
	}
	return false
}
```

**What goes wrong:** neither the parsed `contentType` nor the keys in
`cw.contentTypes`/`cw.contentWildcards` (populated from the caller-supplied
`types` in `NewCompressor`, `middleware/compress.go:75-91`, unmodified) are
lower-cased. A handler that sets `w.Header().Set("Content-Type", "Text/HTML")`
(valid HTTP) is treated as non-compressible even though `"text/html"` is in
`defaultCompressibleContentTypes`.

Confirmed by reproduction:

```
=== RUN   TestCompressCaseSensitivityRepro
    zzcompress_test.go:36: Content-Encoding: ""
    zzcompress_test.go:38: expected gzip for case-varied but equivalent content-type, got Content-Encoding=""
--- FAIL
```

**Why it's wrong:** media type tokens are case-insensitive per RFC 9110
§8.3.1 ("The type and subtype tokens are case-insensitive."). This package
already knows that: `middleware/content_type.go:34-35` explicitly
lower-cases before comparing (`s = strings.ToLower(strings.TrimSpace(s))`
in `AllowContentType`). `compress.go`'s `isCompressible` does not apply the
same normalization, an inconsistency within the same package for the same
kind of comparison.

**Severity:** Low/Medium. In practice most handlers write lowercase
Content-Type values so this rarely triggers, but it is a genuine, silent
functional gap (responses that should be compressed are not) whenever a
handler (or a wrapped library) emits a mixed-case media type.

**Suggested fix:** lower-case both sides — normalize `types` when building
`allowedTypes`/`allowedWildcards` in `NewCompressor`, and lower-case
`contentType` in `isCompressible` before the map lookups (matching the
pattern already used in `AllowContentType`).

---

## 4. `RouteHeaders` picks a header-match nondeterministically when more than one header name is registered

**File:** `middleware/route_headers.go`, lines 77-108, specifically:

```go
type HeaderRouter map[string][]HeaderRoute
...
func (hr HeaderRouter) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		...
		// find first matching header route, and continue
		for header, matchers := range hr {
```

**What goes wrong:** `HeaderRouter` is a plain Go map keyed by (lower-cased)
header name, and `Handler` iterates it with `for header, matchers := range hr`
to find "the first matching header route." Go map iteration order is
randomized per-run (and can differ between calls in the same process for
`map[string]...`). If a caller chains `.Route()`/`.RouteAny()` calls across
**more than one distinct header name** (the package doc's own two examples
each use a single header name, "Host" or "Origin", so this doesn't surface
in the shipped examples, but nothing prevents mixing them, e.g. a Host rule
and a Content-Type rule together), and a given request's headers satisfy
rules under more than one of those header names, which rule "wins" is
nondeterministic across requests/process runs rather than reflecting the
order the rules were declared in.

**Why it's wrong:** the comment "find first matching header route" implies a
deterministic, presumably declaration-ordered, precedence — which is what a
caller chaining `.Route(...).Route(...)` would reasonably expect. A map
provides no such ordering guarantee.

**Severity:** Low/Medium (lower confidence than items 1-3 — I did not find
this documented as a known limitation, but I also did not find test coverage
exercising more than one header name at a time, so I can't rule out it being
an accepted trade-off). Worth flagging because the failure mode (silently
different middleware executing depending on map iteration order) is hard to
notice and hard to reproduce deterministically once seen in the field.

**Suggested fix:** preserve declaration order — e.g. keep a `[]string`
slice of header names alongside the map (or replace the map with an
ordered slice of `{header, routes}` entries) and iterate that slice in
`Handler`.

---

## Not flagged (considered and ruled out)

- `middleware/client_ip.go` — the XFF/trusted-proxy walking, v4-mapped
  folding, and fail-closed behavior all match their extensive doc comments;
  traced `ClientIPFromXFFTrustedProxies`'s counting logic by hand against a
  2-proxy example and it's correct.
- `middleware/throttle.go`, `middleware/wrap_writer.go`,
  `middleware/recoverer.go`, `middleware/logger.go` — read in full, no
  defects found; the `httpFancyWriter.ReadFrom` double-count-avoidance
  comment in `wrap_writer.go` checks out against the code.
- `middleware/content_charset.go`, `middleware/content_type.go`,
  `middleware/content_encoding.go` — the `ContentLength == 0` skip and
  charset/type parsing match their doc comments.
- `middleware/url_format.go`, `middleware/get_head.go` — traced the path
  arithmetic (dot/slash index handling) against several worked examples; no
  off-by-one found.

---

## Files read

`middleware/basic_auth.go`, `middleware/clean_path.go`,
`middleware/client_ip.go`, `middleware/compress.go`,
`middleware/content_charset.go`, `middleware/content_encoding.go`,
`middleware/content_type.go`, `middleware/get_head.go`,
`middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`,
`middleware/middleware.go`, `middleware/nocache.go`,
`middleware/page_route.go`, `middleware/path_rewrite.go`,
`middleware/profiler.go`, `middleware/realip.go`,
`middleware/recoverer.go`, `middleware/request_id.go`,
`middleware/request_size.go`, `middleware/route_headers.go`,
`middleware/strip.go`, `middleware/sunset.go`,
`middleware/supress_notfound.go`, `middleware/terminal.go`,
`middleware/throttle.go`, `middleware/timeout.go`,
`middleware/url_format.go`, `middleware/value.go`,
`middleware/wrap_writer.go`; also `mux.go`, `tree.go` (context), `context.go`
(chi core, for routing-context semantics referenced above), and
`route_headers_test.go` / `compress_test.go` (to check existing coverage).

Reproductions were written and run against copies of `middleware/` and the
package root inside the given work directory, then deleted; they are not
part of this report as files.
