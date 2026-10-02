model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:55:47 UTC; finished 2026-09-28 21:58:23 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local reproductions; attempted full middleware tests
interruptions or errors: full tests blocked by sandbox TCP-listener restriction
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

Checkout: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`. Scope: `middleware/`.

## Findings

1. **Medium — Compression ignores an explicit refusal of an encoding.** `middleware/compress.go:260-266`. `matchAcceptEncoding` only looks for a substring, so `Accept-Encoding: gzip;q=0` selects gzip and sends a compressed response with `Content-Encoding: gzip`. An HTTP `q=0` value says the coding is unacceptable; the `Compress` comment also promises to choose based on `Accept-Encoding`. This can make responses unusable to clients that explicitly cannot decode gzip. Parse encoding tokens and quality values, require a positive quality, and match the coding name exactly. A local reproduction produced `Content-Encoding: gzip` and gzip bytes for `gzip;q=0`.

2. **Medium — Host header routes do not match real incoming requests.** `middleware/route_headers.go:86-88`. The package's `RouteHeaders` documentation explicitly shows `Route("Host", "example.com", ...)`, but Go's HTTP server stores the incoming Host in `r.Host`, not `r.Header`. Thus an ordinary request for `example.com` sees an empty value here and falls through to the default/next handler. The package test masks this by manually inserting `Header["Host"]`. Use `r.Host` when the configured header is `Host` (and account for port if the intended pattern is a hostname). A local `httptest.NewRequest("GET", "http://example.com/", nil)` reproduction did not invoke the configured Host route.

3. **Medium — Valid comma-separated request content codings are rejected.** `middleware/content_encoding.go:23-25`. `AllowContentEncoding("gzip", "br")` returns 415 for `Content-Encoding: gzip, br`, even though the comment says *all encodings in the request* must be allowed, and both are. The loop treats a whole header field value as one coding instead of splitting the HTTP comma-separated list. Split every field value on commas, trim each token, and check each coding separately. A local reproduction returned 415.

4. **Medium — A failed encoder produces a falsely encoded response.** `middleware/compress.go:249-250` and `middleware/compress.go:328-334`. `EncoderFunc` explicitly allows returning nil on failure (`middleware/compress.go:269-273`). `selectEncoder` nevertheless returns that nil writer with a nonempty encoding name. The handler then leaves `cw.w` pointing at the uncompressed response writer, while `WriteHeader` advertises `Content-Encoding` for the failed encoder. Clients cannot decode the plain body under that header. Treat nil as an unavailable encoder and try another accepted encoding or send the response without `Content-Encoding`. A local custom encoder returning nil produced `Content-Encoding: broken` with the plain body `hello`.

## Verification

Focused in-process reproductions were run from the scratch directory with `GOPROXY=off`; all four outcomes above were observed. `go test ./middleware` could not complete because this sandbox disallows the TCP listener opened by `httptest.NewServer` in `TestCompressor` (`listen tcp6 [::1]:0: bind: operation not permitted`). The checkout was not modified.

## Files read

All non-test Go files in `middleware/`: `basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, and `wrap_writer.go`. I also read `middleware/compress_test.go`, `middleware/route_headers_test.go`, and searched relevant lines in `middleware/content_charset_test.go` and `middleware/content_encoding_test.go`.
