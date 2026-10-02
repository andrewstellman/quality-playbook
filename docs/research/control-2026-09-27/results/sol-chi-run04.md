model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:56:08 UTC; finished 2026-09-28 21:58:49 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; verification details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

Reviewed checkout `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, scope `middleware/`. The reproductions below used a standalone Go program in the assigned scratch directory; the checkout was not changed.

## Findings

1. **High — A flush before the first write can send gzip bytes without a gzip header.** `middleware/compress.go:357` calls the underlying writer's `Flush` while `cw.wroteHeader` is still false. That commits the response headers before `WriteHeader` at line 310 can add `Content-Encoding`; a later `Write` nevertheless sets `cw.compressible` and sends gzip bytes. With `Content-Type: text/plain`, `Accept-Encoding: gzip`, and a handler that calls `w.(http.Flusher).Flush()` before `w.Write([]byte("hello"))`, the wire header has no `Content-Encoding` while the body begins with the gzip magic bytes. This contradicts `Compress`'s promise at lines 34–42 to encode the response according to the request and makes the response unreadable to ordinary clients. **Fix:** call `cw.WriteHeader(http.StatusOK)` at the start of `Flush`, then flush the selected encoder and underlying writer.

2. **Medium — Documented Host routes never match normal HTTP requests.** `middleware/route_headers.go:87` retrieves every value from `r.Header`. Go's HTTP server stores the Host field in `r.Host`, not in `r.Header`, so the documented `Route("Host", "example.com", ...)` example at lines 11–21 falls through to the default/next handler. A local `httptest.NewRequest("GET", "http://example.com/", nil)` has `r.Host == "example.com"` and `r.Header.Get("Host") == ""`, and the route does not match. **Fix:** special-case `Host` to read `r.Host`; retain `r.Header.Get` for other fields.

3. **Medium — Compression ignores explicit rejection of an encoding.** `middleware/compress.go:260–266` uses substring matching for each `Accept-Encoding` item and never parses quality values. `Accept-Encoding: gzip;q=0` therefore selects gzip even though the client explicitly rejects it; the local probe confirmed a gzip response. It also treats an unrelated token such as `xgzip` as permission for `gzip`. This conflicts with the `selectEncoder` comment at lines 230–237 that the selected algorithm must be accepted. **Fix:** parse comma-separated coding tokens and their `q` parameters, match coding names exactly, and exclude `q=0`; then select among acceptable encodings by quality and server preference.

4. **Medium — The advertised `deflate` representation uses the wrong wire format.** `middleware/compress.go:406–411` constructs a raw `compress/flate` writer. The comment at lines 114–116 explicitly states that HTTP `deflate` is DEFLATE data wrapped with zlib; raw flate output lacks that wrapper and fails in clients that decode `Content-Encoding: deflate` as zlib. **Fix:** use `compress/zlib.NewWriterLevel` for the `deflate` encoder and update the decoding test to use `zlib.NewReader`.

5. **Medium — A valid list of request content codings is rejected.** `middleware/content_encoding.go:17–25` treats each header field value as one coding. For `Content-Encoding: gzip, deflate` and `AllowContentEncoding("gzip", "deflate")`, it looks up the whole string and returns 415; the local probe confirmed that status. The test's stated supported forms at `middleware/content_encoding_test.go:15–20` include exactly that comma-separated value, although its loop uses `Header.Set` repeatedly and thus only tests the last value. **Fix:** split each header field value on commas, trim each coding, and validate every coding separately; test both a combined field and repeated fields with `Header.Add`.

6. **Low — Uncompressed variants lack `Vary: Accept-Encoding`.** `middleware/compress.go:328–335` adds `Vary` only when this request selected an encoding. For a compressible `text/plain` response to a request without `Accept-Encoding`, the response has no `Vary`, so a shared cache may reuse that uncompressed variant for a subsequent client that accepts gzip. The same endpoint's response selection demonstrably depends on `Accept-Encoding` (the `Compress` contract at lines 34–36). **Fix:** add `Vary: Accept-Encoding` for every response whose content type is eligible for compression, regardless of whether this request selected an encoder.

## Files read

`middleware/basic_auth.go`, `middleware/clean_path.go`, `middleware/client_ip.go`, `middleware/compress.go`, `middleware/compress_test.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_encoding_test.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`, `middleware/middleware.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/route_headers_test.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/throttle.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, `middleware/wrap_writer.go`, `go.mod`.
