# Code Review: go-chi/chi `middleware/`

Repo: https://github.com/go-chi/chi, pinned commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`
Scope: `middleware/` (all non-test `.go` files, 27 source files, ~2360 lines)

## Defect 1: `Compress`/`Compressor` ignores Accept-Encoding quality values, including explicit refusal (`q=0`)

- **File/lines:** `middleware/compress.go:225-267` (specifically `selectEncoder`, lines 225-251, and `matchAcceptEncoding`, lines 260-267)
- **What goes wrong:** `matchAcceptEncoding` decides whether an encoding is acceptable using a plain substring test:

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

  `selectEncoder` splits the raw `Accept-Encoding` header on commas and passes each token straight into this function without stripping or evaluating the `;q=` parameter. As a result, a request that sends `Accept-Encoding: gzip;q=0` — which per HTTP semantics means "gzip is *not* acceptable" — still matches, because the string `"gzip;q=0"` contains the substring `"gzip"`. The middleware goes on to gzip-compress the response anyway.

  I reproduced this directly against the checkout:

  ```go
  compressor := NewCompressor(5, "text/plain")
  h := compressor.Handler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
  	w.Header().Set("Content-Type", "text/plain")
  	w.Write([]byte("hello world"))
  }))
  req := httptest.NewRequest("GET", "/", nil)
  req.Header.Set("Accept-Encoding", "gzip;q=0")
  rr := httptest.NewRecorder()
  h.ServeHTTP(rr, req)
  // rr.Header().Get("Content-Encoding") == "gzip"
  ```

  Running this against the package (`go test -run TestQZeroBug -v`) confirms `Content-Encoding: gzip` is set even though the client explicitly declined gzip.

- **Why it is wrong:** RFC 7231 §5.3.1/§5.3.4 (which `Accept-Encoding` follows) specifies that a qvalue of `0` means "not acceptable" — a server must not select that coding. `SetEncoder`'s own doc comment (`middleware/compress.go:157-174`) points readers to MDN's `Accept-Encoding` reference for the header's syntax, i.e., the code itself acknowledges the qvalue-bearing format, but `matchAcceptEncoding` never parses or honors it. Concretely, a client that cannot decode gzip (or wants to explicitly disable it, e.g. for a proxy/cache test) and signals so via `q=0` will receive a gzip-compressed body it did not ask for and may not be able to decode. The same substring-match approach also means an encoding token that merely contains another registered encoding's name as a substring (e.g. a hypothetical `"x-gzip-old"`) would be misidentified as `"gzip"`, though the `q=0` case is the clearer, more common, and more clearly wrong scenario.
- **Severity:** Medium — response body corruption/undecodable content for any client that explicitly disables an encoding via `q=0` (a legitimate, spec-sanctioned way to opt out), and it also silently ignores an explicit client preference. Not a crash or security hole, but it violates documented/standard HTTP negotiation semantics.
- **Suggested fix:** Parse each `Accept-Encoding` token into (coding, qvalue) pairs (trim whitespace, split on `;q=`) and treat `q=0` (or an unparsable qvalue defaulting per spec) as "not acceptable" — skip such entries in `matchAcceptEncoding`/`selectEncoder` rather than doing a raw `strings.Contains` match. At minimum, honor `q=0` as a hard exclusion for the exact coding name (after splitting on `;`), e.g.:

  ```go
  func matchAcceptEncoding(accepted []string, encoding string) bool {
  	for _, v := range accepted {
  		name, params, _ := strings.Cut(strings.TrimSpace(v), ";")
  		if name != encoding {
  			continue
  		}
  		if q, ok := strings.CutPrefix(strings.TrimSpace(params), "q="); ok && q == "0" {
  			return false
  		}
  		return true
  	}
  	return false
  }
  ```

## Other areas reviewed, no confident defects found

I read every non-test file in `middleware/` end to end and specifically checked:

- `throttle.go` — token/backlog channel accounting, the "try immediate token" fast path, timer cleanup on all branches, and the `Retry-After` header logic. Consistent with its doc comments; no leak or race found.
- `client_ip.go` — `ClientIPFromHeader`, `ClientIPFromXFF`, `ClientIPFromXFFTrustedProxies`, `ClientIPFromRemoteAddr`, and `walkXFF`. Walked through the off-by-one-prone counting logic in `ClientIPFromXFFTrustedProxies` by hand against how proxies actually append to `X-Forwarded-For`; it lines up correctly with the documented "N trusted hops" semantics, including the fail-closed behavior on short/garbled chains and the v4-mapped/zone normalization.
- `wrap_writer.go` — `ReadFrom` tee/discard routing explicitly avoids double-counting bytes (verified the logic is self-consistent); `WriteHeader`'s special-case for 1xx status codes and `Discard()` looks correct.
- `strip.go` (`RedirectSlashes`) — the `path := ...` inside the `if` block shadows the outer `path` variable, but every subsequent use in that same block scope refers to the shadowed variable, so it behaves correctly (just unusual style, which is out of scope per the review instructions).
- `content_charset.go`, `content_type.go`, `content_encoding.go` — `ContentLength == 0` skip semantics match their doc comments; charset parsing logic traced through several header variants (with/without charset, with extra params) and matches expected output.
- `recoverer.go`, `wrap_writer.go`, `route_headers.go`, `url_format.go`, `get_head.go`, `basic_auth.go`, `request_id.go`, `realip.go`, `nocache.go`, `sunset.go`, `heartbeat.go`, `page_route.go`, `path_rewrite.go`, `request_size.go`, `profiler.go`, `terminal.go`, `middleware.go`, `maybe.go`, `value.go`, `supress_notfound.go`, `clean_path.go` — read fully; behavior matches doc comments and no logic errors, incorrect edge-case handling, or concurrency issues found.

I also built the module (`go build ./...`) and ran the existing test suite (`go test ./middleware/...`), which passes in full — consistent with the `q=0` gap above not being covered by any existing test.

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
- `CHANGELOG.md` (skimmed for context; not part of the review scope)

I also ran `go build ./...` and `go test ./middleware/...` from a writable copy of the checkout, and wrote/ran a one-off reproduction test (`TestQZeroBug`, deleted after use) to confirm Defect 1 against the live code rather than by inspection alone.
