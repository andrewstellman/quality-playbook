# Code Review: go-chi/chi `middleware/`

Repo: https://github.com/go-chi/chi
Pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
Scope: `middleware/`

## Defect 1 — `Compressor.selectEncoder` ignores `q=0` in `Accept-Encoding`, compressing responses for clients that explicitly forbade an encoding

**File/line:** `middleware/compress.go`, `matchAcceptEncoding` (lines 260-267), called from `selectEncoder` (lines 231-258).

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

**What goes wrong:** `selectEncoder` splits the `Accept-Encoding` header on commas and then does a plain substring `strings.Contains(v, encoding)` check against each comma-separated token, completely ignoring any `;q=` weight. Per RFC 9110 §12.5.3, a `q=0` (or `q=0.000`) on a coding means that coding is **not acceptable** to the client. A header such as `Accept-Encoding: gzip;q=0, deflate` explicitly forbids gzip, but `matchAcceptEncoding(["gzip;q=0", " deflate"], "gzip")` still returns `true` because `"gzip;q=0"` contains the substring `"gzip"`. The server will then gzip-encode the response anyway.

I reproduced this directly against the package:

```go
compressor := middleware.NewCompressor(5, "text/plain")
h := compressor.Handler(handlerThatSetsContentType("text/plain"))
req.Header.Set("Accept-Encoding", "gzip;q=0, deflate;q=0")
h.ServeHTTP(w, req)
// w.Header().Get("Content-Encoding") == "gzip"   <-- should not be gzip
```

Test output:
```
main_test.go:21: Content-Encoding: "gzip"
main_test.go:23: server used gzip despite client sending gzip;q=0 (explicitly forbidding it)
--- FAIL: TestQZero (0.00s)
```

**Why it's wrong:** The package doc for `Compress`/`NewCompressor` says it "compresses response body of a given content types ... based on Accept-Encoding request header" — i.e., it claims to implement Accept-Encoding negotiation, but it does not honor the qvalue-0 "forbidden" semantics defined by the HTTP spec it's implementing. A client that sends `gzip;q=0` (e.g. because it cannot decode gzip, or a proxy/tool disabling compression for a specific request) can still receive a gzip body it did not ask for and may not be able to decompress.

**Severity:** medium — it's a spec-compliance/content-negotiation bug with a real-world trigger (any client or intermediary that disables a specific coding via `q=0`), though the more common encodings (gzip/deflate) are also the ones almost always accepted, limiting day-to-day blast radius.

**Suggested fix:** Parse each `Accept-Encoding` token into (name, qvalue) instead of doing a raw substring match, e.g.:

```go
func matchAcceptEncoding(accepted []string, encoding string) bool {
	for _, v := range accepted {
		name, params, _ := strings.Cut(strings.TrimSpace(v), ";")
		if strings.TrimSpace(name) != encoding {
			continue
		}
		if q, ok := strings.CutPrefix(strings.TrimSpace(params), "q="); ok {
			if qv, err := strconv.ParseFloat(q, 64); err == nil && qv == 0 {
				return false
			}
		}
		return true
	}
	return false
}
```
(Exact-match the coding name rather than `Contains`, and treat `q=0` as a rejection.)

---

## Defect 2 — `RouteHeaders`/`HeaderRouter.Handler` picks a header non-deterministically when more than one header is registered

**File/line:** `middleware/route_headers.go`, `HeaderRouter.Handler` (lines 77-108), specifically the loop at line 86:

```go
// find first matching header route, and continue
for header, matchers := range hr {
    ...
}
```

`HeaderRouter` is `type HeaderRouter map[string][]HeaderRoute` — one slice per registered header name. The doc block for `RouteHeaders` explicitly advertises registering rules keyed on *different* headers (its own example routes on `"Host"` in one call and implies the same mechanism generalizes; `Route`/`RouteAny` are designed to be chained for arbitrary header names, and nothing in the API restricts them to a single header). But `Handler` iterates `hr` — a Go map — with `for header, matchers := range hr`, and Go randomizes map iteration order on every iteration. When two or more *different* headers are registered and a request carries values matching routes under more than one of them, which route wins is chosen at random per request, contradicting the comment "find first matching header route" (which implies a stable, deterministic precedence).

Reproduced directly:

```go
hr := middleware.RouteHeaders().
    Route("X-A", "match", handlerA).
    Route("X-B", "match", handlerB)
h := hr.Handler(next)
// send the same request (both X-A: match and X-B: match) 30 times
```

Test output:
```
rh_test.go:35: distinct results across identical requests: map[A:true B:true]
rh_test.go:37: non-deterministic routing result for the same request: map[A:true B:true]
--- FAIL: TestRouteHeadersOrder (0.00s)
```

The same identical request is routed to handler A on some calls and handler B on others, purely because of Go's randomized map iteration (confirmed independently: iterating a 5-key map 20 times in isolation produced 5 distinct orderings).

**Why it's wrong:** Middleware routing that silently varies per-process-run/per-call for identical input violates the reasonable expectation set by the code's own comment ("find first matching header route") and by the feature's purpose (deterministically directing "the flow of a request through a middleware stack based on a request header"). This is exactly the kind of bug that's invisible in local testing (a given run may consistently favor one order) but manifests as flaky/inconsistent production behavior — e.g., inconsistently applied CORS policy or inconsistent virtual-host routing depending on which headers a request happens to carry.

**Severity:** medium — it only manifests when a caller registers routes on more than one distinct header (a supported and documented use pattern), but when it does trigger, the resulting behavior is silently non-deterministic per request, which is a serious usability/correctness problem for a routing primitive. No test file exists for `route_headers.go`, so nothing currently catches this.

**Suggested fix:** Preserve registration order explicitly instead of relying on map iteration — e.g., track headers in a separate `[]string` (or a `[]struct{header string; routes []HeaderRoute}` slice) populated by `Route`/`RouteAny`/`RouteDefault` in call order, and iterate that slice in `Handler` instead of ranging over the map.

---

## Other areas reviewed with no confirmed defect

- `throttle.go` — token/backlog channel accounting, timer cleanup, and `Retry-After` handling all look correct (including the `ctx.Done()` branches during backlog wait).
- `basic_auth.go` — uses `subtle.ConstantTimeCompare` for the password only (username lookup via map is not attacker-timing-sensitive since it's not secret); looks fine.
- `client_ip.go` — the newer `ClientIPFrom*` family (fail-closed on unparseable/short XFF chains, v4-mapped/zone normalization before prefix checks) is carefully written and its stated invariants hold on inspection.
- `wrap_writer.go` — the `httpFancyWriter.ReadFrom` fast path explicitly avoids double-counting bytes when Tee/Discard is active; verified the accounting is consistent.
- `recoverer.go`, `request_id.go`, `logger.go`, `nocache.go`, `content_type.go`, `content_charset.go`, `content_encoding.go`, `get_head.go`, `strip.go`, `clean_path.go`, `path_rewrite.go`, `url_format.go`, `sunset.go`, `heartbeat.go`, `page_route.go`, `value.go`, `maybe.go`, `supress_notfound.go`, `middleware.go`, `terminal.go` — reviewed; behavior matches documented intent, no confirmed defects.
- `timeout.go` — worth flagging as a minor (not confidently a "defect") observation: the deferred `if ctx.Err() == context.DeadlineExceeded { w.WriteHeader(...) }` can fire an extra `WriteHeader(504)` call after a slow handler that ignored `ctx.Done()` already wrote a full, valid response past the deadline. Because Go's `net/http` silently ignores/logs superfluous `WriteHeader` calls, this doesn't corrupt the client's response, so I'm not filing it as a confirmed defect — but it does mean the middleware can attempt to signal a timeout after the real response was already sent, which is more surprising than the doc comment ("returns a 504 Gateway Timeout error") suggests.

## Files read

- middleware/throttle.go
- middleware/compress.go
- middleware/realip.go
- middleware/client_ip.go
- middleware/timeout.go
- middleware/route_headers.go
- middleware/content_charset.go
- middleware/content_encoding.go
- middleware/basic_auth.go
- middleware/request_size.go
- middleware/get_head.go
- middleware/strip.go
- middleware/logger.go
- middleware/recoverer.go
- middleware/request_id.go
- middleware/wrap_writer.go
- middleware/url_format.go
- middleware/path_rewrite.go
- middleware/sunset.go
- middleware/nocache.go
- middleware/heartbeat.go
- middleware/content_type.go
- middleware/value.go
- middleware/maybe.go
- middleware/supress_notfound.go
- middleware/terminal.go
- middleware/page_route.go
- middleware/clean_path.go
- middleware/middleware.go
- go.mod (for module path/Go version context)

Verification performed: wrote and ran standalone Go tests against a local copy of the package (`go test`) to confirm both reported defects reproduce (Accept-Encoding `q=0` gzip test, and RouteHeaders non-determinism test across 30 identical requests), plus an isolated Go program confirming Go's map iteration order is randomized per-iteration (used to substantiate Defect 2).
