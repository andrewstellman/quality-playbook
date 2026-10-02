model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:59:16 UTC; finished 2026-09-28 22:01:37 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local scratch Go reproductions
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

## Findings

1. **Medium — `RouteHeaders` does not route on the HTTP Host field.** In `middleware/route_headers.go:87`, `r.Header.Get("Host")` is empty for ordinary server requests because Go stores the HTTP Host field in `r.Host`. A route configured exactly as the function's documented Host example (lines 11–21) therefore falls through to `next` or the default route. A local `httptest.NewRequest("GET", "http://example.com/", nil)` returned the fallback status 200 instead of the Host route's 201. Use `r.Host` when the configured header is `Host`, and retain `r.Header.Get` for other fields. Add a test that does not manually inject `Host` into `r.Header`.

2. **Medium — `Compress` selects an encoding that the client explicitly forbids.** `middleware/compress.go:260–265` uses substring matching rather than parsing `Accept-Encoding` tokens and quality values. For `Accept-Encoding: gzip;q=0`, it sends `Content-Encoding: gzip`, even though quality zero means gzip is unacceptable. It also treats `xgzip` as permission for `gzip`. The code's own `selectEncoder` comment says it selects from accepted algorithms (lines 230–237). Parse comma-separated coding tokens and their `q` parameters, require an exact coding or valid wildcard match, and reject `q=0`. A local check reproduced both cases.

3. **Medium — flushing before the first write sends compressed data without an encoding header.** `middleware/compress.go:357–369` delegates `Flush` to the underlying response writer while `cw.wroteHeader` is still false. That commits the HTTP headers. A later `Write` calls `WriteHeader`, sets `Content-Encoding: gzip` too late, and emits gzip bytes. The middleware promises compression based on `Accept-Encoding` (lines 27–30), but the client receives an unlabeled compressed body. A local recorder check showed an empty sent `Content-Encoding` with 29 bytes of gzip output for `hello`. Call `cw.WriteHeader(http.StatusOK)` before flushing, then flush the selected writer and underlying writer as appropriate.

4. **Medium — a failed custom encoder labels plain response bytes as encoded.** `middleware/compress.go:249–250` returns a custom encoder's nil result with its encoding name. `Handler` retains the raw response writer when `encoder == nil` (lines 219–221), while `WriteHeader` still sets that encoding (lines 328–334). `EncoderFunc` explicitly documents nil as the failure result (lines 269–273). With an encoder returning nil and `Accept-Encoding: broken`, a local check produced `Content-Encoding: broken` and the unencoded body `hello`. If the encoder returns nil, clear the selected encoding and serve the identity body (or fail the response before writing headers).

## Files read

`go.mod`; `middleware/basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, `wrap_writer.go`; `middleware/client_ip_test.go` (lines 1–300), `compress_test.go`, `route_headers_test.go`.
