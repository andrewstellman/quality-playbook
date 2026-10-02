model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:41:47 UTC; finished 2026-09-28 22:45:50 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran middleware suite and scratch regression cases
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# go-chi middleware review

Reviewed commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, limited to `middleware/`.

## Findings

### 1. `Accept-Encoding` values that explicitly forbid an encoding still select it

- **File/line:** `middleware/compress.go:260-266`
- **Severity:** medium
- **What goes wrong:** A client sending `Accept-Encoding: gzip;q=0` receives a response with `Content-Encoding: gzip`. A `q=0` value means that coding is unacceptable. The substring check also accepts unrelated tokens containing a supported name, such as `notgzip`.
- **Why this is wrong:** `Compress` promises to select a response format based on the request's `Accept-Encoding` header (`middleware/compress.go:26-29`). `matchAcceptEncoding` uses `strings.Contains` on each comma-delimited value and never parses the token or quality value, so `gzip;q=0` matches `gzip` at lines 261-264.
- **Suggested fix:** Parse each `Accept-Encoding` element into an exact coding token and its parameters. Only select an exact supported coding with an effective quality greater than zero; handle `*` according to the header's wildcard rules. Add regression coverage for `gzip;q=0`, nonmatching names containing `gzip`, and weighted alternatives.

### 2. `AllowContentEncoding` rejects valid comma-separated coding chains

- **File/line:** `middleware/content_encoding.go:17-29`
- **Severity:** medium
- **What goes wrong:** With `AllowContentEncoding("gzip", "deflate")`, a nonempty request carrying `Content-Encoding: gzip, deflate` receives 415, although both codings are allowed. The loop treats the complete field value `"gzip, deflate"` as one coding name.
- **Why this is wrong:** The middleware's test explicitly says it supports `Content-Encoding: gzip, deflate` and `Content-Encoding: deflate, gzip` (`middleware/content_encoding_test.go:15-19`), while the implementation checks each header-field value only once at lines 24-25. A Content-Encoding field is a comma-separated list of content codings, so the documented form never reaches the handler.
- **Suggested fix:** Split every `Content-Encoding` field value on commas, trim each resulting coding, and validate every nonempty token against `allowedEncodings`. Keep handling repeated header fields as additional list members. Add a test that uses a single header value containing `gzip, deflate` (rather than replacing the header with successive `Set` calls).

### 3. A documented failed custom encoder is advertised despite emitting an unencoded body

- **File/line:** `middleware/compress.go:219-220,249-250`
- **Severity:** medium
- **What goes wrong:** An `EncoderFunc` is documented to return `nil` on failure. If a registered non-pooled encoder does so for a request, `selectEncoder` still returns its encoding name. The handler leaves `cw.w` as the original response writer because `encoder == nil`, but `WriteHeader` sees a nonempty encoding and sets `Content-Encoding`. Clients then attempt to decode plain bytes as that coding.
- **Why this is wrong:** The public `EncoderFunc` contract expressly permits failure by returning nil (`middleware/compress.go:269-273`). `selectEncoder` returns `fn(w, c.level), name` unconditionally at line 250; the handler only substitutes the writer when it is nonnil at line 219. This produces a response whose metadata contradicts its body.
- **Suggested fix:** After invoking an encoder function, treat a nil result as unavailable: continue selecting another acceptable encoder or return no encoder and an empty encoding name. Do not set `Content-Encoding` unless a usable writer was obtained. Add a regression test with a custom encoder that returns nil.

## Validation

`go test ./middleware` passes on the unmodified checkout. Three temporary regression tests in the assigned scratch copy fail as described above: `gzip;q=0` is compressed, `gzip, deflate` is rejected, and a nil custom encoder is advertised.

## Files read

Production files:

`middleware/basic_auth.go`, `middleware/clean_path.go`, `middleware/client_ip.go`, `middleware/compress.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`, `middleware/middleware.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/throttle.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, and `middleware/wrap_writer.go`.

Test files:

`middleware/basic_auth_test.go`, `middleware/clean_path_test.go`, `middleware/client_ip_bench_test.go`, `middleware/client_ip_example_test.go`, `middleware/client_ip_test.go`, `middleware/compress_test.go`, `middleware/content_charset_test.go`, `middleware/content_encoding_test.go`, `middleware/get_head_test.go`, `middleware/heartbeat_test.go`, `middleware/logger_test.go`, `middleware/middleware_test.go`, `middleware/path_rewrite_test.go`, `middleware/realip_test.go`, `middleware/request_id_test.go`, `middleware/route_headers_test.go`, `middleware/strip_test.go`, `middleware/sunset_test.go`, `middleware/terminal_test.go`, `middleware/throttle_test.go`, `middleware/url_format_test.go`, `middleware/value_test.go`, and `middleware/wrap_writer_test.go`.
