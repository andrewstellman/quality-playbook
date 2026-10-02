# Code review: chi `middleware/`

Repo: go-chi/chi, pinned commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, scope `middleware/`.

Reviewed every `.go` file under `middleware/` (production code) and skimmed the corresponding `_test.go` files for documented intent. Ran `go build ./...` and `go test ./middleware/...` (all pre-existing tests pass, 26s, no failures). Wrote small throwaway probe tests (copied into the work checkout, then deleted) to confirm the two defects below by direct execution rather than by inspection alone.

## Defect 1: `AllowContentEncoding` rejects a valid, standards-compliant single `Content-Encoding` header with multiple comma-separated values

- **File/line:** `middleware/content_encoding.go:17-29` (function `AllowContentEncoding`, the closure body)
- **What goes wrong:** The middleware reads `r.Header["Content-Encoding"]`, which returns one string per *separate header line* the client sent. It does not split each element on `,`. If a client (correctly, per HTTP) sends a single header line `Content-Encoding: gzip, deflate` instead of two separate `Content-Encoding` lines, `requestEncodings` is `[]string{"gzip, deflate"}` — one element containing both tokens. The allow-list lookup `allowedEncodings[strings.TrimSpace(strings.ToLower(encoding))]` then looks up the literal string `"gzip, deflate"`, which is never in the map (the map only ever contains single tokens like `"gzip"`, `"deflate"`), so the request is rejected with 415 even though both `gzip` and `deflate` are individually allowed.
- **Why it is wrong:** RFC 7230 §3.2.2 states that multiple header fields with the same field name are semantically equivalent to one field with the values joined by commas — a compliant client/proxy is free to send either form. The package's own test file documents this exact intent in a comment at `middleware/content_encoding_test.go:15-19`:
  ```go
  // support for:
  // Content-Encoding: gzip
  // Content-Encoding: deflate
  // Content-Encoding: gzip, deflate
  // Content-Encoding: deflate, gzip
  ```
  However, the test that is supposed to exercise the comma-joined form (`"Support for gzip and deflate encoding"` / `"Support for deflate and gzip encoding"`) builds the request with `r.Header.Set("Content-Encoding", encoding)` inside a loop over `tt.encodings` — `Set` overwrites rather than appends, so only the *last* encoding in the slice ever actually reaches the header. The test therefore never sends a real comma-joined value and passes despite the code not supporting the case the comment claims it supports. I verified this directly: sending an actual `Content-Encoding: gzip, deflate` single header through `AllowContentEncoding("deflate", "gzip")` returns 415, not 200.
- **Severity:** Medium. It's a functional correctness bug that produces false-positive rejections (fails closed, so not a security bypass), but it will reject legitimate requests from any client or intermediary that folds `Content-Encoding` into one comma-separated header — a common and spec-legal representation — directly contradicting the middleware's own documented support matrix.
- **Suggested fix:** Split each header value on `,` (trimming whitespace) before checking against the allow-list, e.g.:
  ```go
  for _, raw := range requestEncodings {
      for _, encoding := range strings.Split(raw, ",") {
          if _, ok := allowedEncodings[strings.TrimSpace(strings.ToLower(encoding))]; !ok {
              w.WriteHeader(http.StatusUnsupportedMediaType)
              return
          }
      }
  }
  ```
  and fix the test helper to use `r.Header.Add` (or build the joined string once) so the comma-joined case is actually exercised.

## Defect 2: `RouteHeaders`/`HeaderRouter.Handler` picks a nondeterministic route when more than one registered header key matches the same request

- **File/line:** `middleware/route_headers.go:77-98`, specifically the loop at line 86: `for header, matchers := range hr`
- **What goes wrong:** `HeaderRouter` is `map[string][]HeaderRoute`, keyed by (lowercased) header name. `Route()`/`RouteAny()` let a caller register routes under different header names on the same `HeaderRouter` (the type signature imposes no restriction to a single header). `Handler`'s comment says "find first matching header route, and continue" (line 85), implying a deterministic, registration-order-based selection — but the implementation iterates the routes with `range` directly over the Go map `hr`, and Go map iteration order is randomized on every `range`, not just once per process. When a single request carries values for two or more registered header keys that both match, the middleware's route selection is not stable across otherwise-identical requests.
- **Why it is wrong:** The doc comment's own wording ("find first matching header route") asserts a deterministic "first match" semantic, and the package's worked examples (CORS: authorized-origin policy vs. public-origin policy) are safety/security-relevant — picking the wrong branch unpredictably would apply the wrong CORS policy to a given request. I confirmed the nondeterminism directly: registering `Route("X-A", "1", ...)` and `Route("X-B", "1", ...)` on the same `HeaderRouter`, then sending 200 identical requests (both headers present) through the same handler instance, produced both outcomes (`Matched: A` and `Matched: B`) within a single test run — i.e., the same input can route to a different middleware depending on the (unseeded) map iteration order for that call.
- **Severity:** Medium. Requires a `RouteHeaders()` configuration that mixes more than one distinct header key with routes that can simultaneously match a single request — not the single-header-key pattern shown in every doc example and every existing test — but when that configuration is used, the resulting behavior is silently nondeterministic rather than erroring or documented as "unspecified priority," which is a real trap for anyone who reasonably reads "find first matching header route" as ordered.
- **Suggested fix:** Track registration order explicitly (e.g., an ordered slice of `{header string; routes []HeaderRoute}` alongside/instead of the bare map, or a separate `[]string` recording insertion order of keys) and iterate in that order instead of `range`ing the map directly.

## Other things checked, no defect found

- `throttle.go`: token/backlog channel capacities and fill loop are correct for the documented `Limit`/`BacklogLimit` semantics; the "try immediate token, then fall back to a timer" fast path is functionally equivalent to blocking immediately, just avoids starting a timer needlessly.
- `timeout.go`, `wrap_writer.go` (including the `ReadFrom` tee/discard byte-counting comment), `client_ip.go` (`ClientIPFromXFF`, `ClientIPFromXFFTrustedProxies`, `walkXFF`, v4-mapped/zone normalization), `recoverer.go`, `request_id.go`, `basic_auth.go`, `compress.go`, `content_charset.go`, `content_type.go`, `strip.go`, `sunset.go`, `nocache.go`, `heartbeat.go`, `get_head.go`, `url_format.go`, `profiler.go`, `maybe.go`, `middleware.go`, `request_size.go`, `page_route.go`, `path_rewrite.go`, `supress_notfound.go`, `terminal.go`, `realip.go`, `value.go` — read in full; behavior matches their documented contracts and existing tests, including the edge cases I specifically probed (fail-closed IP parsing, off-by-N boundary cases in `ClientIPFromXFFTrustedProxies`, which I traced by hand against `client_ip_test.go`'s table and confirmed the code matches its own spec).
- The full `go test ./middleware/...` suite (all `_test.go` files in scope) passes with no failures, confirming no regression against the project's own test suite.

## Files read

`middleware/throttle.go`, `middleware/timeout.go`, `middleware/compress.go`, `middleware/wrap_writer.go`, `middleware/logger.go`, `middleware/basic_auth.go`, `middleware/get_head.go`, `middleware/url_format.go`, `middleware/client_ip.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_type.go`, `middleware/route_headers.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/value.go`, `middleware/heartbeat.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/terminal.go`, `middleware/supress_notfound.go`, `middleware/maybe.go`, `middleware/middleware.go`, `middleware/request_size.go`, `middleware/client_ip_test.go` (excerpt), `middleware/content_encoding_test.go` (full), `middleware/route_headers_test.go` (excerpt), `go.mod`.
