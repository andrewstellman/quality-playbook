# Code Review: go-chi/chi `middleware/` (pinned commit 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc)

## Defect 1: `RouteHeaders`/`HeaderRouter.Handler` chooses among matching header rules nondeterministically

**File/line:** `middleware/route_headers.go:86` (the `for header, matchers := range hr` loop inside `HeaderRouter.Handler`, lines 78-108)

**What goes wrong:** `HeaderRouter` is a `map[string][]HeaderRoute` (`type HeaderRouter map[string][]HeaderRoute`, line 46). `Handler` iterates it with `for header, matchers := range hr`. Go randomizes map iteration order on every `range`. If a caller registers rules keyed on more than one distinct header name (exactly the pattern shown in the file's own doc comment, which demonstrates both a `Host`-based example and a separate `Origin`-based CORS example, lines 12-41), and a single incoming request has values for more than one of those headers that both match a registered rule, the middleware selected is chosen at random per-request rather than deterministically by registration order.

I reproduced this directly: registering one rule on `Host: example.com` and another on `Origin: https://foo.com`, then sending 200 requests that satisfy both conditions, the handler wrote body `"A"` (the Host rule) sometimes and `"B"` (the Origin rule) other times, in the same process:
```
results seen: map[A:true B:true]
```

**Why it is wrong:** The package doc comment for `RouteHeaders` explicitly presents "setup multiple CORS handlers" as a supported use case, differentiating an "origin servers" branch (with `AllowCredentials: true`) from a "third-party public requests" branch (`AllowCredentials: false`). If both a Host-style rule and an Origin-style rule are registered and a request happens to satisfy both, `HeaderRouter.Handler`'s reliance on Go map iteration order means the credentialed-vs-uncredentialed CORS policy applied to that request is randomly chosen at runtime — a genuine, security-relevant nondeterminism, not just a code-quality nit. Even outside the CORS example, any use of `RouteHeaders` with rules on two or more distinct header names has no defined precedence, contradicting the "first matching header route" comment at line 85 (there is no well-defined "first" over a randomized map).

**Severity:** Medium (functional nondeterminism; can produce security-relevant inconsistent behavior in the CORS use case the docs themselves recommend).

**Suggested fix:** Store an explicit registration order alongside the map (e.g., keep a `[]string` of header names in the order first seen, or change `HeaderRouter` to hold an ordered slice of `{header string, routes []HeaderRoute}` instead of a map), and iterate that in `Handler` instead of ranging the map directly.

---

## Defect 2: `Compress` middleware's `Accept-Encoding` matching ignores `q=0` refusal and is a naive substring match

**File/line:** `middleware/compress.go:230-267`, specifically `matchAcceptEncoding` (lines 260-267) and its caller `selectEncoder` (lines 231-258)

**What goes wrong:** `selectEncoder` splits the raw `Accept-Encoding` header on commas (line 235) and, for each configured encoder in precedence order, calls `matchAcceptEncoding(accepted, name)`, which does:
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
This is a plain substring test against the raw comma-split fragments — it never parses or honors the `;q=` weight, so a client explicitly disabling an encoding is not respected. I confirmed this by sending `Accept-Encoding: gzip;q=0, deflate;q=0` (a client that has said "acceptable weight is 0", i.e. "do not use this encoding") to a `Compress` handler and it still compressed with gzip:
```
Content-Encoding: "gzip"
```
The same substring approach also produces false positives for any Accept-Encoding token that merely contains the encoder name as a substring (e.g. `xgzip`), which I also confirmed:
```
matchAcceptEncoding([]string{"xgzip"}, "gzip") == true
```

**Why it is wrong:** Per RFC 9110 §12.5.3 (the `Accept-Encoding` semantics that this middleware exists to implement), "A value of q=0 means 'not acceptable'" and the server must not use content codings the client marked `q=0`. `matchAcceptEncoding` has no awareness of the `;q=` parameter at all, so any client that lists an encoding with `q=0` (a legitimate, standard way to say "I understand this token exists but cannot/will not decode it") gets a response encoded with it anyway. Nothing in the package's own comments claims this limitation is intentional — the doc for `Compress`/`NewCompressor` describes selecting an encoder "based on Accept-Encoding request header" with no caveat about ignoring quality values.

**Severity:** Medium (spec-noncompliant; can break clients — proxies, embedded HTTP clients, specific browser configurations — that use `q=0` to opt out of an encoding they cannot handle, since they will receive a response body they cannot decode).

**Suggested fix:** Parse each `Accept-Encoding` token into `(coding, qvalue)` (splitting on `;q=`), skip any token with `q=0`, and match tokens by exact coding name (case-insensitive) rather than raw substring containment.

---

## Other things checked, not reported as defects

I read every non-test file in `middleware/` closely and specifically checked (via small throwaway Go test snippets run against `go test`/`go vet`, plus manual tracing) the following areas that looked like plausible defect sites but turned out correct as written:
- `client_ip.go`: XFF right-to-left walking, trusted-proxy counting, v4-mapped/zone normalization, and fail-closed behavior on parse failure all check out against their documented semantics.
- `wrap_writer.go`: the `httpFancyWriter.ReadFrom` tee/discard fast-path vs `io.Copy` fallback does not double-count `bytes` as its comment claims to avoid.
- `compressResponseWriter.WriteHeader`/`Write`/`Close` ordering in `compress.go`'s `Handler` (the `defer cleanup()` / `defer cw.Close()` pair) closes the encoder before returning it to the `sync.Pool`, avoiding a reuse race.
- `strip.go`'s `RedirectSlashes` backslash-to-slash normalization happens before trimming, correctly closing the open-redirect vector it documents.
- `throttle.go`'s token/backlog channel accounting and `select` structure.
- The full `middleware/...` package (`go build`, `go vet`, `go test`) is clean at the pinned commit.

I did not find defects in: `basic_auth.go`, `clean_path.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `timeout.go`, `url_format.go`, `value.go`, `wrap_writer.go`.

---

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
- `middleware/strip.go`
- `middleware/sunset.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`
- `middleware/throttle.go`
- `middleware/timeout.go`
- `middleware/url_format.go`
- `middleware/value.go`
- `middleware/wrap_writer.go`
- `middleware/compress_test.go` (grepped for existing Accept-Encoding/q=0 coverage — found none)
- `go.mod` (Go version check)

Also ran, against a scratch copy of the checkout: `go build ./middleware/...`, `go vet ./middleware/...`, `go test ./middleware/...` (all pass), and several throwaway test files (removed afterward) to confirm the two defects above reproduce.
