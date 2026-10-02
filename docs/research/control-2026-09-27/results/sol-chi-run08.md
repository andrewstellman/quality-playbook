model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:59:16 UTC; finished 2026-09-28 22:00:45 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; verification details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

Checkout: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`. Scope: `middleware/`.

## Findings

1. **Host routes do not work for ordinary HTTP requests** — `middleware/route_headers.go:87` (medium). `HeaderRouter.Handler` reads every configured field through `r.Header.Get(header)`. Go's HTTP server stores the incoming `Host` field in `r.Host` and removes it from `r.Header`, so a route registered with `Route("Host", "example.com", ...)` never matches a normal request and falls through to the default or next handler. The documented primary example at lines 11–21 explicitly routes by Host. Read `r.Host` for the Host route, and use `r.Header.Get` for other fields.

2. **Compression can be sent for an encoding the client explicitly rejects** — `middleware/compress.go:260-265` (medium). `matchAcceptEncoding` uses substring matching and ignores quality weights. For `Accept-Encoding: gzip;q=0`, it returns true for `gzip`, and `Compress` sets `Content-Encoding: gzip` at lines 328–331. The same happens for a token such as `xgzip`, which does not name the gzip coding. This contradicts `Compress`'s promise to base compression on the request's `Accept-Encoding`. Parse comma-delimited coding tokens and their `q` values, matching whole coding names and rejecting `q=0`.

3. **The `deflate` response uses the wrong wire format** — `middleware/compress.go:406-411` (medium). `encoderDeflate` uses `flate.NewWriter`, which emits raw DEFLATE, while the response is labelled `Content-Encoding: deflate`. The comment at lines 116–119 says HTTP `deflate` is DEFLATE data wrapped in zlib. A client using a zlib decoder for the advertised coding fails to decode the response. Use `compress/zlib.NewWriterLevel` for this encoder and update the test at `middleware/compress_test.go:238-240`, which currently decodes raw DEFLATE.

4. **A valid combined Content-Encoding field is rejected** — `middleware/content_encoding.go:23-29` (low). The middleware compares each complete header value to the whitelist instead of splitting comma-separated codings. With `AllowContentEncoding("gzip", "deflate")`, a request containing `Content-Encoding: gzip, deflate` receives 415 even though both codings are allowed. The comments in `middleware/content_encoding_test.go:15-19` explicitly list this form as supported; those tests use repeated `Header.Set`, which replaces the previous value and never exercises the combined form. Split each field value on commas and validate each trimmed coding.

## Files read

`middleware/basic_auth.go`, `middleware/client_ip.go`, `middleware/client_ip_test.go`, `middleware/clean_path.go`, `middleware/compress.go`, `middleware/compress_test.go`, `middleware/content_encoding.go`, `middleware/content_encoding_test.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/route_headers_test.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/throttle.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, `middleware/wrap_writer.go`.
