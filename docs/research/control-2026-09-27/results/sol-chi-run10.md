model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:01:19 UTC; finished 2026-09-28 22:03:34 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local reproductions
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: chi `middleware/` at `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

## Findings

1. **`middleware/compress.go:260–266` — forbidden or unrelated encodings are selected. Severity: medium.** `matchAcceptEncoding` checks whether each raw header item *contains* the encoder name. A request with `Accept-Encoding: gzip;q=0` therefore receives a gzip response even though the client explicitly refused gzip; `Accept-Encoding: xgzip` also selects gzip. The `Compress` contract says compression is based on the client's `Accept-Encoding`, and the header's quality parameter and coding token determine that acceptance. A local reproduction returned `Content-Encoding: gzip` for both inputs. **Fix:** parse comma-separated coding tokens and their `q` parameters, compare complete tokens case-insensitively, reject `q=0`, and handle `*` and `identity` according to HTTP negotiation rules.

2. **`middleware/compress.go:406–411` — `deflate` sends the wrong wire format. Severity: medium.** `encoderDeflate` uses `flate.NewWriter`, which emits a raw DEFLATE stream. The file's own comment at lines 114–116 correctly says HTTP `Content-Encoding: deflate` requires DEFLATE wrapped in zlib; the existing test at `middleware/compress_test.go:238–239` decodes with `flate.NewReader`, reinforcing the implementation's mismatch. Standards-compliant consumers using a zlib decoder will fail to read such responses. **Fix:** use `compress/zlib.NewWriterLevel` and update the test decoder to `zlib.NewReader`.

3. **`middleware/compress.go:249–250, 328–350` — invalid compression level mislabels an uncompressed body. Severity: medium.** `Compress(100)` is accepted during setup. The gzip encoder returns `nil` when `gzip.NewWriterLevel` rejects that level, but `selectEncoder` still returns the name `gzip`. The response writer then sets `Content-Encoding: gzip` while its `w` remains the original writer, so the plain body is sent with a gzip label. A local reproduction produced `Content-Encoding: gzip` and body `hello`. This contradicts the encoder contract at lines 269–272, which explicitly allows an encoder to return `nil` on failure. **Fix:** validate the level at construction, or treat a nil encoder result as no selected encoding (and likewise handle a nil custom encoder result).

4. **`middleware/route_headers.go:85–88` — documented `Host` routing fails for ordinary server requests. Severity: medium.** The examples at lines 11–21 route on `Host`, but Go's server puts the Host value in `r.Host`, removing it from `r.Header`. `r.Header.Get("Host")` is therefore empty and the route never matches unless code manually injects an extra `Host` header. A local reproduction with `httptest.NewRequest("GET", "http://example.com/", nil)` yielded `r.Host == "example.com"`, an empty header value, and no match. **Fix:** read `r.Host` when the configured header is `Host`; continue using `r.Header.Get` for other headers.

5. **`middleware/content_encoding.go:23–29` — a valid list of allowed content codings is rejected. Severity: medium.** The comment says all encodings in the request must be allowed, and `middleware/content_encoding_test.go:15–19` explicitly lists `Content-Encoding: gzip, deflate` as supported. The implementation iterates header *lines*, not the comma-separated tokens within each line, so it compares the whole string `gzip, deflate` against individual allowed names and returns 415. A local reproduction using `AllowContentEncoding("gzip", "deflate")` returned 415. **Fix:** split each header line on commas, trim and normalize each coding, then validate every token.

## Verification

The first, third, fourth, and fifth findings were reproduced with a standalone Go program in `/private/tmp/qpb-control/sol-chi-run10/repro.go`, run against this checkout with `GOPROXY=off`. The deflate finding follows directly from `flate.NewWriter` and the code's own HTTP wire-format comment.

## Files read

`go.mod`; `middleware/basic_auth.go`; `middleware/client_ip.go`; `middleware/clean_path.go`; `middleware/compress.go`; `middleware/compress_test.go`; `middleware/content_encoding.go`; `middleware/content_encoding_test.go`; `middleware/content_type.go`; `middleware/get_head.go`; `middleware/heartbeat.go`; `middleware/logger.go`; `middleware/maybe.go`; `middleware/nocache.go`; `middleware/page_route.go`; `middleware/path_rewrite.go`; `middleware/profiler.go`; `middleware/realip.go`; `middleware/recoverer.go`; `middleware/request_id.go`; `middleware/request_size.go`; `middleware/route_headers.go`; `middleware/route_headers_test.go`; `middleware/strip.go`; `middleware/sunset.go`; `middleware/supress_notfound.go`; `middleware/terminal.go`; `middleware/throttle.go`; `middleware/timeout.go`; `middleware/url_format.go`; `middleware/value.go`; `middleware/wrap_writer.go`.
