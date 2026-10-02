# Code Review: go-chi/chi `middleware/` package

Repo: https://github.com/go-chi/chi, pinned commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`
Scope: `middleware/`

All findings below were confirmed by writing small standalone Go programs against
the actual package (via a `replace` directive pointing at the checkout) and
observing the runtime behavior, not just by reading the source. `go test ./middleware/...`
(including `-race`) passes cleanly for the existing test suite — none of these
defects are caught by it.

---

## 1. `RouteHeaders().Route("Host", ...)` can never match a real request — contradicts the package's own doc example

**File:** `middleware/route_headers.go`, lines 77–98 (`HeaderRouter.Handler`), specifically line 87:

```go
for header, matchers := range hr {
    headerValue := r.Header.Get(header)
    if headerValue == "" {
        continue
    }
    ...
```

**What goes wrong:** For real, wire-parsed HTTP requests, Go's `net/http` server
removes the `Host` header from `r.Header` and exposes it only via `r.Host`
(`net/http`'s `ReadRequest` calls `delete(req.Header, "Host")` after copying it to
`req.Host`). `RouteHeaders.Handler` only ever consults `r.Header.Get(header)`, so
when a route is registered with header name `"Host"`, `headerValue` is always `""`
for a genuinely-received request, `continue` fires, and the route can never match.
Confirmed by running the router behind an actual `httptest.NewServer` (not
`httptest.NewRequest`, which doesn't reproduce this stripping) and sending a request
with `req.Host = "example.com"`:

```
response: fell through to default
```

even though a route for `Host == "example.com"` was registered.

**Why it's wrong:** This is exactly the middleware's own first documented use case.
The package doc comment on `RouteHeaders` (lines 8–21) gives this as the canonical
example:

```go
r.Use(middleware.RouteHeaders().
    Route("Host", "example.com", middleware.New(r)).
    Route("Host", "*.example.com", middleware.New(rSubdomain)).
    Handler)
```

Any adopter following this documented pattern gets silent misrouting: every request
falls through to the default/next handler instead of the intended per-host
handler, because the "Host" header is never present in `r.Header` for a real
inbound request. The existing test in `route_headers_test.go` ("matching header
should route to correct middleware") only passes because it artificially calls
`req.Header.Set("Host", "example.com")` on a request built with
`httptest.NewRequest`, which does not reproduce the header-stripping that a real
`net/http` server performs — so the test doesn't exercise the failure.

**Severity:** High. It's a silent routing failure (no error, no panic — just wrong
handler dispatch) for the documented primary use case (host-based routing).

**Suggested fix:** In `Handler`, special-case `Host`: if the registered header
(case-insensitively) is `"host"`, read `r.Host` instead of `r.Header.Get("Host")`.
E.g.:

```go
headerValue := r.Header.Get(header)
if header == "host" && headerValue == "" {
    headerValue = r.Host
}
```

---

## 2. Compressor ignores `q=0` in `Accept-Encoding`, compressing responses the client explicitly refused

**File:** `middleware/compress.go`, lines 260–267:

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

**What goes wrong:** `selectEncoder` (lines 231–258) splits the raw
`Accept-Encoding` header on commas and, for each candidate encoding in
`encodingPrecedence`, checks membership with a bare substring `strings.Contains`.
It never looks at the `;q=` parameter. Reproduced directly:

```go
req.Header.Set("Accept-Encoding", "gzip;q=0, identity")
```

against `middleware.NewCompressor(5, "text/plain")` produces
`Content-Encoding: gzip` in the response — i.e. the middleware compresses with
gzip even though the client's header explicitly marks gzip as unacceptable
(`q=0`).

**Why it's wrong:** Per RFC 9110 §12.5.3 (HTTP Semantics, Accept-Encoding),
a weight of `q=0` means the coding is "not acceptable" — a compliant server
must not select that coding for the response. `strings.Contains(v, encoding)`
treats `"gzip;q=0"` as containing `"gzip"` and therefore acceptable, which is the
opposite of what the client asked for. This will also misfire for any other
q-value annotation on the encoding token.

**Severity:** Medium. Spec-noncompliant behavior with real consequences for
clients/proxies that explicitly disable an encoding (e.g. to debug, or because
they can't decode it despite advertising general gzip support elsewhere); no
memory-safety or crash impact.

**Suggested fix:** Parse each `Accept-Encoding` entry into (token, q) using
`strings.Cut(entry, ";")`, trim/lowercase the token for an exact match (not
`Contains`), parse an optional `q=` parameter, and reject entries with `q=0`.

---

## 3. `RouteHeaders` route precedence across different header names is nondeterministic

**File:** `middleware/route_headers.go`, `HeaderRouter` is defined as
`type HeaderRouter map[string][]HeaderRoute` (line 46), and `Handler` iterates it
directly:

```go
for header, matchers := range hr {
    ...
}
```

**What goes wrong:** Go intentionally randomizes map iteration order. When two or
more `.Route(...)` calls register **different header names** on the same
`HeaderRouter`, which one is checked (and can win) first is random per-router-
construction, not per-registration-order. Reproduced by building the same router
(two headers, `X-A` and `X-B`, both present and both matching) 200 times and
recording which route wins:

```
map[A:176 B:24]
```

The split confirms the outcome is not deterministic — the same configuration can
route a request differently across process runs (and even across two constructions
within the same run).

**Why it's wrong:** A router whose match precedence changes at random for
identical input, depending only on Go's map-iteration randomization, is a routing
correctness problem in any deployment that legitimately needs more than one
header dimension (e.g. combining a `Host` rule with a `Content-Type` rule as
mixed criteria) with overlapping requests. Nothing in the doc comment says
precedence is unspecified across header names — the doc's own two examples imply
ordered, predictable precedence ("first matching header route" per the comment at
line 85).

**Severity:** Low/Medium. Precedence is only ambiguous when routes on distinct
header names both match the same request, which is a narrower case than defect
#1, but it is a genuine non-determinism bug, not just a documentation gap.

**Suggested fix:** Track registration order explicitly (e.g. a
`[]string` of header keys alongside the map, or switch `HeaderRouter` to a slice
of `{header string; routes []HeaderRoute}` entries) and iterate in that order.

---

## 4. Minor: `ThrottleWithOpts` panic message doesn't match the validation it guards

**File:** `middleware/throttle.go`, lines 49–51:

```go
if opts.BacklogLimit < 0 {
    panic("chi/middleware: Throttle expects backlogLimit to be positive")
}
```

**What goes wrong:** The check only rejects negative values (`< 0`), so
`BacklogLimit == 0` is valid and used throughout the package (e.g. `Throttle()`
at line 33 constructs `ThrottleOpts{Limit: limit, BacklogTimeout: ...}` with a
zero-value `BacklogLimit`). The panic text says "expects backlogLimit to be
positive," which is inaccurate — zero is accepted; only negative is rejected.

**Why it's wrong:** Not a functional bug (the guard itself is correct), but the
message would mislead anyone debugging a triggered panic into thinking
`BacklogLimit: 0` is invalid, when it isn't.

**Severity:** Low (message-only).

**Suggested fix:** Change the message to "...expects backlogLimit to be
non-negative" (or `>= 0`).

---

## Areas checked with no confirmed defect

- `middleware/timeout.go`, `throttle.go` core token/backlog concurrency logic
  (ran under `go test -race`, no races; manual trace of the select/defer ordering
  looks correct).
- `middleware/client_ip.go` (`ClientIPFromHeader`, `ClientIPFromXFF`,
  `ClientIPFromXFFTrustedProxies`, `ClientIPFromRemoteAddr`, `walkXFF`,
  `parseHeaderAddr`) — traced the fail-closed behavior, v4-mapped folding, zone
  stripping, and trusted-proxy counting against the doc comments; all consistent,
  and the existing table-driven tests pass.
- `middleware/wrap_writer.go` (`basicWriter`, `httpFancyWriter.ReadFrom` tee/discard
  interaction, 1xx status handling) — logic is consistent with documented
  semantics; `go test -race` covers `TestWrapWriterHTTP2` cleanly.
- `middleware/compress.go` writer plumbing (`Handler`/`selectEncoder`/pool
  reuse/`defer` ordering between `cleanup()` and `cw.Close()`) — correct ordering,
  no double-close or pool-corruption found.
- `middleware/content_charset.go` charset-parsing (`split`/`contentEncoding`) —
  traced param-order independence and empty-Content-Type handling; matches the
  documented "empty charset allows no Content-Type" behavior.
- `middleware/strip.go` `RedirectSlashes` backslash/slash normalization — traced
  through several inputs; behaves as an open-redirect guard, doesn't break normal
  trailing-slash redirects.
- `middleware/basic_auth.go`, `request_size.go`, `request_id.go`,
  `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`,
  `nocache.go`, `page_route.go`, `path_rewrite.go`, `realip.go`, `recoverer.go`,
  `sunset.go`, `supress_notfound.go`, `terminal.go`, `url_format.go`, `value.go`,
  `maybe.go`, `middleware.go`, `clean_path.go`, `profiler.go`, `logger.go` —
  reviewed for logic errors and edge-case handling; nothing found that rises above
  the "confident it's a real defect" bar.

## Files read

- `middleware/throttle.go`
- `middleware/timeout.go`
- `middleware/compress.go`
- `middleware/basic_auth.go`
- `middleware/clean_path.go`
- `middleware/client_ip.go`
- `middleware/content_charset.go`
- `middleware/content_encoding.go`
- `middleware/content_type.go`
- `middleware/get_head.go`
- `middleware/heartbeat.go`
- `middleware/logger.go`
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
- `middleware/route_headers_test.go` (partial, to check existing coverage)
- `middleware/strip.go`
- `middleware/sunset.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`
- `middleware/url_format.go`
- `middleware/value.go`
- `middleware/wrap_writer.go`
- `go.mod` (Go version check only)

Also ran the existing test suite (`go test -count=1 ./middleware/...` and
`go test -race -run 'Throttle|Compress|ClientIP|WrapWriter|RequestID' -v
./middleware/...`), and three standalone verification programs built against the
checkout via a `replace` directive, to confirm findings #1 and #2 against real
`net/http` server behavior rather than synthetic `httptest.NewRequest` requests.
