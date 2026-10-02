model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:31:49 UTC; finished 2026-09-28 22:35:28 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Middleware review — chi `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

## Findings

### 1. `Accept-Encoding` entries with `q=0` are still selected

- **File / line:** `middleware/compress.go:260-264`
- **Severity:** Medium
- **What goes wrong:** A response is gzip-compressed for `Accept-Encoding: gzip;q=0, deflate`, even though `q=0` explicitly makes gzip unacceptable. The same substring check also treats a different token such as `xgzip` as permission to use `gzip`. In both cases a client can receive an encoding it did not accept.
- **Why this is wrong:** `selectEncoder` is documented to find a supported encoder from the request's accepted encodings (lines 230-239), but `matchAcceptEncoding` uses `strings.Contains` on the entire comma item and never parses the encoding token or quality parameter. A reproducer using the public `Compress` middleware received `Content-Encoding: gzip` for the header above.
- **Suggested fix:** Parse `Accept-Encoding` as comma-separated coding entries, compare the coding token exactly (case-insensitively), and honor `q` values, excluding a coding when `q=0`. Select among the remaining acceptable codings according to the documented precedence.

### 2. An encoder-construction failure produces an uncompressed body labelled as compressed

- **File / line:** `middleware/compress.go:209-220, 249-250, 328-331`
- **Severity:** Medium
- **What goes wrong:** `middleware.Compress(100, "text/plain")` accepts the invalid flate level. `encoderGzip` returns `nil`, but `selectEncoder` still returns the encoding name `gzip`. `Handler` leaves `cw.w` as the original response writer when the encoder is nil, while `WriteHeader` sets `Content-Encoding: gzip`. The response therefore contains plain bytes that any conforming client will attempt, and fail, to decompress.
- **Why this is wrong:** `EncoderFunc` explicitly says that it returns `nil` on failure (`middleware/compress.go:269-273`). The caller does not turn that failure into either a construction error or “no encoding”; it advertises compression solely because the name is non-empty. The isolated reproduction confirmed that a gzip reader cannot decode the body while the response header says `gzip`.
- **Suggested fix:** Validate the compression level when creating the compressor, or have `selectEncoder` return an empty encoding whenever the selected `EncoderFunc` returns nil. Do not set `Content-Encoding` unless there is a usable encoder.

### 3. `AllowContentEncoding` rejects a valid comma-separated encoding chain even when every coding is allowed

- **File / line:** `middleware/content_encoding.go:23-27`
- **Severity:** Medium
- **What goes wrong:** With `AllowContentEncoding("gzip", "deflate")`, a body sent with the ordinary single header `Content-Encoding: gzip, deflate` receives 415. The implementation treats the entire field value as one encoding rather than testing both codings.
- **Why this is wrong:** The code's own comment says “All encodings in the request must be allowed” (line 23), and `middleware/content_encoding_test.go` explicitly lists support for `Content-Encoding: gzip, deflate`. Iterating header field values is insufficient because one field value can contain the comma-separated chain. The current test happens to use `Header.Set` repeatedly, which overwrites earlier values and does not exercise its documented comma-list case.
- **Suggested fix:** Split every `Content-Encoding` field value on commas, trim each coding, and reject only when an individual coding is absent from `allowedEncodings`. Add a regression test that sets one header to `gzip, deflate`.

### 4. `ContentCharset` rejects valid quoted charset parameters

- **File / line:** `middleware/content_charset.go:35-39`
- **Severity:** Medium
- **What goes wrong:** `ContentCharset("utf-8")` returns 415 for a non-empty request with `Content-Type: text/plain; charset="UTF-8"`. Quoted parameter values are valid Content-Type syntax, but the parser preserves the quotation marks and compares `"utf-8"` to `utf-8`.
- **Why this is wrong:** The middleware promises to allow requests whose charset matches one of the provided charsets (lines 9-11), and lowercases both values. Its ad hoc splitting does not parse the header's parameter grammar, so an otherwise equivalent charset is rejected. The isolated reproduction returns 415 for the header above.
- **Suggested fix:** Parse the media type with `mime.ParseMediaType` and compare the normalized `charset` parameter, or extend the parser to correctly handle quoted parameter values and escapes. Add a quoted-charset regression test.

## Validation

The existing `go test ./middleware` could not complete in this sandbox because tests that call `httptest.NewServer` cannot bind a local listener. The non-network `TestContentEncodingMiddleware` passes. An isolated scratch-module test reproduced all four findings with `httptest.NewRecorder`.

## Files read

- `middleware/basic_auth.go`
- `middleware/clean_path.go`, `middleware/clean_path_test.go`
- `middleware/client_ip.go`
- `middleware/compress.go`, `middleware/compress_test.go`
- `middleware/content_charset.go`
- `middleware/content_encoding.go`, `middleware/content_encoding_test.go`
- `middleware/content_type.go`
- `middleware/get_head.go`, `middleware/get_head_test.go`
- `middleware/heartbeat.go`
- `middleware/logger.go`
- `middleware/maybe.go`, `middleware/middleware.go`, `middleware/nocache.go`
- `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`
- `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`
- `middleware/route_headers.go`
- `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`
- `middleware/terminal.go`, `middleware/throttle.go`, `middleware/throttle_test.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, `middleware/wrap_writer.go`
