model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:39:35 UTC; finished 2026-09-28 22:42:21 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran go test ./middleware and local reproducers
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: `middleware/`

## Findings

### 1. `Compress` ignores `Accept-Encoding` quality exclusions

- **File / line:** `middleware/compress.go:260`
- **Severity:** medium
- **What goes wrong:** A request with `Accept-Encoding: gzip;q=0` receives a response with `Content-Encoding: gzip`. A client can use `q=0` specifically to declare an encoding unacceptable, so it may be unable or unwilling to decode the returned response. The same substring check can also treat unrelated tokens such as `xgzip` as acceptance of `gzip`.
- **Why this is wrong:** `selectEncoder` is responsible for choosing a response encoding from the request's `Accept-Encoding` header (lines 232–251), but `matchAcceptEncoding` only calls `strings.Contains(v, encoding)`. It never parses the encoding token or its `q` parameter. A local reproducer returned `q-zero-content-encoding gzip` for an `Accept-Encoding: gzip;q=0` request.
- **Suggested fix:** Parse the comma-separated `Accept-Encoding` members into exact coding tokens and quality values. Select only supported codings with a positive quality value, honoring wildcard handling and the server precedence order among equally acceptable codings.

### 2. `AllowContentEncoding` rejects a valid multi-coding `Content-Encoding` field

- **File / line:** `middleware/content_encoding.go:24`
- **Severity:** medium
- **What goes wrong:** With `AllowContentEncoding("gzip", "deflate")`, a nonempty request carrying `Content-Encoding: gzip, deflate` receives `415 Unsupported Media Type`, although both declared codings are allowed. That prevents clients from sending a body encoded through more than one permitted coding.
- **Why this is wrong:** The middleware iterates header field values and looks each complete value up verbatim (lines 24–25); it does not split a field value on commas. The package's own test comment says this middleware supports `Content-Encoding: gzip, deflate` and `Content-Encoding: deflate, gzip` (`middleware/content_encoding_test.go:13–16`). A local reproducer produced status `415` for `Content-Encoding: gzip, deflate`.
- **Suggested fix:** For every `Content-Encoding` header field value, split its comma-separated coding list, trim and case-normalize each coding, and require every individual coding to be present in `allowedEncodings`.

### 3. `RouteHeaders` chooses among matching configured headers in random map order

- **File / line:** `middleware/route_headers.go:86`
- **Severity:** medium
- **What goes wrong:** If a request matches routes registered for two different headers, the selected middleware is nondeterministic. For example, after registering a matching `X-First` route followed by a matching `X-Second` route, a request containing both headers can take either branch from one request to the next. This can produce inconsistent routing or select the wrong policy middleware.
- **Why this is wrong:** `HeaderRouter` is a map (`type HeaderRouter map[string][]HeaderRoute`), and `Handler` ranges directly over that map while returning after its first match. Go intentionally does not preserve a map's insertion order, despite the code comment saying it will “find first matching header route” (line 85). A 1,000-request local reproducer selected both branches (`first:873`, `second:127`) for the same input.
- **Suggested fix:** Preserve route registration order in an ordered slice (while optionally retaining a map for lookup), and iterate that slice in `Handler`. Define that the first registered matching route wins.

## Validation

`go test ./middleware` passes. The issues above were reproduced with a standalone local program importing this checkout; the checkout was not modified.

## Files read

- `middleware/basic_auth.go`
- `middleware/clean_path.go`, `middleware/clean_path_test.go`
- `middleware/client_ip.go`, `middleware/client_ip_test.go`
- `middleware/compress.go`, `middleware/compress_test.go`
- `middleware/content_charset.go`, `middleware/content_charset_test.go`
- `middleware/content_encoding.go`, `middleware/content_encoding_test.go`
- `middleware/content_type.go`
- `middleware/get_head.go`, `middleware/get_head_test.go`
- `middleware/heartbeat.go`, `middleware/heartbeat_test.go`
- `middleware/logger.go`
- `middleware/maybe.go`, `middleware/middleware.go`, `middleware/nocache.go`
- `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/path_rewrite_test.go`
- `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`
- `middleware/request_id.go`, `middleware/request_id_test.go`, `middleware/request_size.go`
- `middleware/route_headers.go`, `middleware/route_headers_test.go`
- `middleware/strip.go`, `middleware/strip_test.go`
- `middleware/sunset.go`, `middleware/sunset_test.go`
- `middleware/supress_notfound.go`, `middleware/terminal.go`
- `middleware/throttle.go`, `middleware/throttle_test.go`
- `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`
- `middleware/wrap_writer.go`, `middleware/wrap_writer_test.go`
