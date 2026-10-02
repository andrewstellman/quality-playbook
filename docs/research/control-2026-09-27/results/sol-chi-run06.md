model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:58:32 UTC; finished 2026-09-28 22:01:09 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local reproductions
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review of `middleware/` in chi `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

## Findings

1. **Medium — `middleware/route_headers.go:87`: Host routes do not match ordinary HTTP requests.** `Handler` reads every route key from `r.Header`, but Go stores the incoming Host header in `r.Host`, not `r.Header`. For a normal request with `Host: example.com`, the documented `Route("Host", "example.com", ...)` example at lines 12–21 skips the route and invokes the next handler or default route. The existing tests manually insert `Host` into `r.Header`, masking this. Use `r.Host` when the route key is `Host`; keep `r.Header.Get` for other headers. A local `httptest.NewRequest("GET", "http://example.com/", nil)` confirmed `r.Host == "example.com"`, `r.Header.Get("Host") == ""`, and no route match.

2. **Medium — `middleware/content_encoding.go:24–25`: A valid comma-separated Content-Encoding list is rejected.** HTTP permits `Content-Encoding: gzip, deflate` as a single field value. The whitelist loop treats that entire value as one encoding, so `AllowContentEncoding("gzip", "deflate")` returns 415. The test's comment at `middleware/content_encoding_test.go:16–20` explicitly says that combination is supported, but its test builds separate values using `Header.Set`, replacing each prior value. Split every field value on commas and validate each trimmed token. A local request with this field returned 415, while `gzip` alone returned 200.

3. **Medium — `middleware/content_charset.go:35–39`: Valid quoted charset parameters are rejected.** `contentEncoding` compares the raw parameter substring to allowed charset names. A request with `Content-Type: text/plain; charset="UTF-8"` and `ContentCharset("utf-8")` gets 415 because the parsed value retains its quotes. The middleware promises to allow requests whose charsets match (`middleware/content_charset.go:9–10`), and quoted parameter values are valid Content-Type syntax. Parse Content-Type with `mime.ParseMediaType` and compare the parsed `charset` parameter case-insensitively. The local reproduction returned 415.

4. **Medium — `middleware/compress.go:260–266`: A client that disallows gzip still receives it.** `matchAcceptEncoding` uses substring matching and ignores quality values. With `Accept-Encoding: gzip;q=0`, `Compress(5)` sends `Content-Encoding: gzip`, even though quality zero says gzip is unacceptable. This contradicts `Compress`'s promise to choose a data format based on `Accept-Encoding` (`middleware/compress.go:34–37`) and can make the response undecodable by the client. Parse encoding tokens and `q` parameters, reject `q=0`, and match exact tokens (including wildcard rules). The local reproduction produced `Content-Encoding: gzip` for `gzip;q=0`.

5. **Medium — `middleware/compress.go:406–411`: The `deflate` response uses raw DEFLATE instead of the documented zlib format.** `encoderDeflate` calls `flate.NewWriter`, which emits raw DEFLATE, while the comment at lines 114–116 explicitly says HTTP `deflate` is DEFLATE wrapped with zlib. A client using `zlib.NewReader` on a response to `Accept-Encoding: deflate` fails with `zlib: invalid header`; the current test uses `flate.NewReader` and therefore only verifies the nonstandard format. Use `compress/zlib.NewWriterLevel` for this encoder and adjust the decoder in the test.

## Verification

Ran a small Go program from `/private/tmp/qpb-control/sol-chi-run06/repro.go` against the checkout, with `GOPROXY=off` and a scratch `GOCACHE`. It reproduced all five findings. No checkout files were modified.

## Files read

`middleware/basic_auth.go`, `middleware/clean_path.go`, `middleware/client_ip.go`, `middleware/compress.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/throttle.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, `middleware/wrap_writer.go`, `middleware/content_encoding_test.go`, `middleware/route_headers_test.go`, `middleware/compress_test.go`, `middleware/get_head_test.go`.
