# Code review — go-chi/chi `middleware/`

Repo: go-chi/chi, pinned commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, scope `middleware/`.

## Defect 1: `AllowContentEncoding` rejects a valid single-header, comma-separated `Content-Encoding` list even when every encoding in it is allowed

- **File/line:** `middleware/content_encoding.go`, lines 17 and 24–28.

```go
requestEncodings := r.Header["Content-Encoding"]
...
// All encodings in the request must be allowed
for _, encoding := range requestEncodings {
    if _, ok := allowedEncodings[strings.TrimSpace(strings.ToLower(encoding))]; !ok {
        w.WriteHeader(http.StatusUnsupportedMediaType)
        return
    }
}
```

- **What goes wrong:** `r.Header["Content-Encoding"]` returns one string per *header line*; it does not split a single line's comma-separated value list. `Content-Encoding` is a list-type header (RFC 9110 §8.4: `Content-Encoding = #content-coding`), and a client is entitled to send it as one line, e.g. `Content-Encoding: gzip, deflate`. When that happens, `requestEncodings` is `[]string{"gzip, deflate"}` — a single element containing the literal string `"gzip, deflate"`. The loop looks up `"gzip, deflate"` as a whole in `allowedEncodings`, which will never match (the map only ever contains individual encoding names such as `"gzip"` and `"deflate"`), so the request is rejected with 415 even though both `gzip` and `deflate` are in the configured whitelist.

- **Why it is wrong:** The package's own test file documents the intended support matrix in its header comment (`middleware/content_encoding_test.go` lines 15–19):
  ```go
  // support for:
  // Content-Encoding: gzip
  // Content-Encoding: deflate
  // Content-Encoding: gzip, deflate
  // Content-Encoding: deflate, gzip
  ```
  i.e. a single `Content-Encoding: gzip, deflate` header is explicitly claimed to be supported. The implementation does not honor this because it never splits on commas — only requests that arrive as *multiple separate header lines* (added via `Header.Add`, one encoding per line) are handled correctly.

  I verified this with a standalone reproduction against the checked-out code:
  - `r.Header.Set("Content-Encoding", "gzip, deflate")` (one line, comma-separated) → **415** (should be 200 per the documented support matrix, since both `gzip` and `deflate` are allowed).
  - `r.Header.Add("Content-Encoding", "gzip"); r.Header.Add("Content-Encoding", "deflate")` (two separate lines) → **200** (correct).

  The existing `TestContentEncodingMiddleware` test does not catch this because it builds its "combined encoding" cases with a bug of its own: it calls `r.Header.Set("Content-Encoding", encoding)` inside a `for _, encoding := range tt.encodings` loop (`content_encoding_test.go` lines 66–68). `Header.Set` overwrites rather than appends, so for the "gzip and deflate" and "deflate and br" cases only the *last* encoding in the slice ends up on the request at all — the test never actually sends a combined value, single-line or multi-line, and passes for the wrong reason.

- **Severity:** Medium. It's a false-rejection (correctness) bug, not a security bypass — legitimate, RFC-compliant requests using a combined `Content-Encoding` header are incorrectly refused with 415 even though the middleware's own documented behavior says they should be accepted. Depending on how a client library batches encodings, this can silently break otherwise-conforming clients.

- **Suggested fix:** Split each header line on commas (and trim/lowercase each piece) before checking against `allowedEncodings`, e.g.:
  ```go
  for _, line := range requestEncodings {
      for _, encoding := range strings.Split(line, ",") {
          if _, ok := allowedEncodings[strings.TrimSpace(strings.ToLower(encoding))]; !ok {
              w.WriteHeader(http.StatusUnsupportedMediaType)
              return
          }
      }
  }
  ```
  and fix the test helper to use `r.Header.Add` (or build a single comma-joined `Set` call) so the "combined encoding" cases actually exercise the claimed behavior, including the single-header comma-separated form.

## Other areas reviewed, no confident defects found

I read every non-test file in `middleware/` (`basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, `wrap_writer.go`), plus the corresponding test files, and ran `go test ./middleware/...` (all pass) and `go vet ./middleware/...` (clean) against the pinned commit.

Areas I scrutinized closely but concluded are correct as written:
- `throttle.go`: token/backlog channel accounting, the `select` fallthrough ordering, and the `Retry-After` header logic all matched the documented semantics on manual trace-through.
- `compress.go`: encoder pool `Reset`/`Close`/`defer` ordering (the `defer cleanup(); defer cw.Close()` pair runs `Close` *before* the encoder is returned to the pool, which is correct), wildcard content-type validation in `NewCompressor`, and `matchAcceptEncoding`'s substring match (a known, pre-existing imprecision around `q=0` that is not specific to this scope and not something I could attribute to this commit).
- `client_ip.go`: the XFF right-to-left walk, trusted-proxy counting, and v4-mapped/zone normalization all matched their extensive doc comments under manual simulation.
- `strip.go` / `url_format.go` / `get_head.go`: route-path vs. `r.URL.Path` fallback logic is consistent with chi's routing context conventions.

No other defect met the confidence bar for this report.

## Files read

- `middleware/basic_auth.go`, `basic_auth_test.go`
- `middleware/clean_path.go`, `clean_path_test.go`
- `middleware/client_ip.go`, `client_ip_test.go`, `client_ip_bench_test.go`, `client_ip_example_test.go`
- `middleware/compress.go`, `compress_test.go`
- `middleware/content_charset.go`, `content_charset_test.go`
- `middleware/content_encoding.go`, `content_encoding_test.go`
- `middleware/content_type.go`, `content_type_test.go`
- `middleware/get_head.go`, `get_head_test.go`
- `middleware/heartbeat.go`, `heartbeat_test.go`
- `middleware/logger.go`, `logger_test.go`
- `middleware/maybe.go`
- `middleware/middleware.go`, `middleware_test.go`
- `middleware/nocache.go`
- `middleware/page_route.go`
- `middleware/path_rewrite.go`, `path_rewrite_test.go`
- `middleware/profiler.go`
- `middleware/realip.go`, `realip_test.go`
- `middleware/recoverer.go`, `recoverer_test.go`
- `middleware/request_id.go`, `request_id_test.go`
- `middleware/request_size.go`
- `middleware/route_headers.go`, `route_headers_test.go`
- `middleware/strip.go`, `strip_test.go`
- `middleware/sunset.go`, `sunset_test.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`, `terminal_test.go`
- `middleware/throttle.go`, `throttle_test.go`
- `middleware/timeout.go`
- `middleware/url_format.go`, `url_format_test.go`
- `middleware/value.go`, `value_test.go`
- `middleware/wrap_writer.go`, `wrap_writer_test.go`
- `go.mod` (module/Go version check)

Commands run: `go test ./middleware/...`, `go vet ./middleware/...`, and a standalone reproduction (`go test -run TestZZVerify...`) against a writable copy of the checkout to confirm the `AllowContentEncoding` behavior described above.
