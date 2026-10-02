model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:38:16 UTC; finished 2026-09-28 22:41:36 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: go-chi/chi `middleware/`

Reviewed commit: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

## Defects

### 1. Disabled content codings (`q=0`) are still selected

- **File and line:** `middleware/compress.go:260-266`
- **Severity:** Medium
- **What goes wrong:** A request with `Accept-Encoding: gzip;q=0` receives a gzip-compressed response with `Content-Encoding: gzip`. `q=0` means that the client does not accept that coding. The same substring test also mistakes unrelated tokens containing an encoder name for that encoder.
- **Why it is wrong:** `selectEncoder` is responsible for choosing an encoder from the request's `Accept-Encoding` header (lines 230-250), but `matchAcceptEncoding` only calls `strings.Contains` on each raw comma-delimited field. It never parses the coding token or its quality value, so a forbidden `gzip;q=0` is treated as an accepted gzip coding.
- **Suggested fix:** Parse each Accept-Encoding element into its coding name and parameters, compare the coding name exactly (case-insensitively), and ignore codings with an effective quality of zero. Handle `*` according to its quality and the explicitly listed codings.

### 2. A failed custom encoder produces a response falsely labelled as compressed

- **File and line:** `middleware/compress.go:249-250`, `middleware/compress.go:211-221`, `middleware/compress.go:328-331`
- **Severity:** High
- **What goes wrong:** If a custom encoder registered through `SetEncoder` returns `nil`, a request accepting that coding gets a `Content-Encoding` header for the coding but its body is written uncompressed to the original response writer. Clients then try to decode plaintext as the advertised format and fail.
- **Why it is wrong:** `EncoderFunc` explicitly documents at lines 269-273 that it returns `nil` on failure. `selectEncoder` nevertheless returns the coding name even when `fn(w, c.level)` is nil. `Handler` leaves `cw.w` as the original writer when `encoder == nil`, while `WriteHeader` sees the nonempty coding name and sets `compressible` plus `Content-Encoding`. This creates an invalid response.
- **Suggested fix:** When an encoder factory returns nil, return an empty encoding (and no-op cleanup) from `selectEncoder`, or continue looking for another acceptable encoder. Only set the response encoding after a non-nil encoder has been obtained.

### 3. `AllowContentEncoding` rejects valid comma-separated encoding lists

- **File and line:** `middleware/content_encoding.go:23-29`
- **Severity:** Medium
- **What goes wrong:** `AllowContentEncoding("gzip", "deflate")` rejects a nonempty request with the standard header `Content-Encoding: gzip, deflate`, returning 415 even though every listed coding is allowed.
- **Why it is wrong:** The middleware promises that “All encodings in the request must be allowed” (line 23), and its own test describes support for `Content-Encoding: gzip, deflate`. The implementation iterates header field values but never splits an individual field at commas. It therefore checks the single literal value `"gzip, deflate"` against the allowlist and rejects it.
- **Suggested fix:** For each Content-Encoding header value, split on commas, trim and normalize every coding token, then validate each token independently. Preserve rejection of any unknown token.

## Validation

I ran the existing package tests with `go test ./middleware` successfully. I also ran a temporary overlay test without modifying the checkout; it reproduced all three cases: `gzip;q=0` was labelled gzip, a nil custom encoder was labelled with its coding, and `Content-Encoding: gzip, deflate` returned 415.

## Files read

- `middleware/basic_auth.go`
- `middleware/clean_path.go`
- `middleware/client_ip.go`
- `middleware/client_ip_test.go`
- `middleware/compress.go`
- `middleware/compress_test.go`
- `middleware/content_charset.go`
- `middleware/content_charset_test.go`
- `middleware/content_encoding.go`
- `middleware/content_encoding_test.go`
- `middleware/content_type.go`
- `middleware/content_type_test.go`
- `middleware/get_head.go`
- `middleware/get_head_test.go`
- `middleware/heartbeat.go`
- `middleware/heartbeat_test.go`
- `middleware/logger.go`
- `middleware/maybe.go`
- `middleware/middleware.go`
- `middleware/nocache.go`
- `middleware/page_route.go`
- `middleware/path_rewrite.go`
- `middleware/profiler.go`
- `middleware/realip.go`
- `middleware/recoverer.go`
- `middleware/request_id.go`
- `middleware/request_size.go`
- `middleware/route_headers.go`
- `middleware/route_headers_test.go`
- `middleware/strip.go`
- `middleware/sunset.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`
- `middleware/throttle.go`
- `middleware/timeout.go`
- `middleware/url_format.go`
- `middleware/url_format_test.go`
- `middleware/value.go`
- `middleware/wrap_writer.go`
- `middleware/wrap_writer_test.go`
