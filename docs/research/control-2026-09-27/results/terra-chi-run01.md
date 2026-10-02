model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:28:15 UTC; finished 2026-09-28 22:31:50 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

## Defects

### 1. `RouteHeaders` cannot route on `Host`

- **File / line:** `middleware/route_headers.go:87`
- **Severity:** medium
- **Trigger:** Configure the documented `Route("Host", "example.com", ...)` route and send a normal HTTP/1.1 request with `Host: example.com`.
- **What goes wrong:** The configured middleware is skipped. Go parses the Host field into `Request.Host` and removes it from `Request.Header`, so `r.Header.Get("host")` is empty.
- **Why this is wrong:** The package documentation's first `RouteHeaders` example explicitly says to route on the request `Host` header and configures `Route("Host", "example.com", ...)`. The implementation only consults `r.Header` at line 87. An in-process `http.ReadRequest` reproduction produced `req.Host == "example.com"`, `req.Header.Get("Host") == ""`, and did not invoke the selected route.
- **Suggested fix:** Special-case `Host` when retrieving the value (use `r.Host`), while retaining `r.Header.Get` for other fields. Normalize the selected value as today.

### 2. Compression is applied to encodings the client explicitly rejects

- **File / line:** `middleware/compress.go:260-266`
- **Severity:** medium
- **Trigger:** Request a compressible response with `Accept-Encoding: gzip;q=0`, or with an unrelated coding token such as `Accept-Encoding: xgzip`.
- **What goes wrong:** The response is gzip-compressed and labelled `Content-Encoding: gzip` in both cases. `gzip;q=0` explicitly makes gzip unacceptable, and `xgzip` is a different coding name.
- **Why this is wrong:** `Compress` promises to select the response format from the request's `Accept-Encoding` header. `matchAcceptEncoding` treats a coding as accepted whenever its name is a substring of a comma-delimited field, so it neither parses the coding token nor observes quality values. The reproduced requests both returned `Content-Encoding: gzip`.
- **Suggested fix:** Parse each `Accept-Encoding` item into an exact, case-insensitive coding token and parameters; only select a coding with a positive effective quality value. Handle `*` and explicit exclusions according to the header's normal matching rules.

### 3. A failing custom encoder produces a falsely labelled uncompressed response

- **File / line:** `middleware/compress.go:219-221`, `middleware/compress.go:249-250`, and `middleware/compress.go:325-334`
- **Severity:** medium
- **Trigger:** Register an encoder with `SetEncoder` whose `EncoderFunc` returns `nil` (the documented failure result), then request that accepted encoding for a compressible response. The built-in encoders exhibit the same failure mode if given a compression level they reject.
- **What goes wrong:** `selectEncoder` returns the selected encoding name even when the encoder is nil. `Handler` retains that name while leaving `cw.w` as the original writer. Later `WriteHeader` sets `Content-Encoding` and removes `Content-Length`, but `Write` emits the plain body. Clients attempt to decode data that was never encoded.
- **Why this is wrong:** `EncoderFunc` explicitly documents that it returns nil on failure. `Handler` checks for a nil encoder at lines 219-221, but does not clear the paired encoding name; `WriteHeader` then treats the response as compressible solely because `cw.encoding != ""`.
- **Suggested fix:** Have `selectEncoder` return an empty encoding whenever `fn` returns nil, or have `Handler` clear `encoding` when `encoder == nil`. Add a regression test using a nil-returning custom encoder.

### 4. `AllowContentEncoding` rejects a valid combined Content-Encoding field

- **File / line:** `middleware/content_encoding.go:23-29`
- **Severity:** medium
- **Trigger:** Install `AllowContentEncoding("gzip", "deflate")` and send a nonempty request with the single header field `Content-Encoding: gzip, deflate`.
- **What goes wrong:** The middleware returns 415, although every listed content coding is allowed.
- **Why this is wrong:** A Content-Encoding field can contain a comma-separated sequence of codings. The middleware iterates header fields, rather than the codings within those fields, and performs one lookup for the entire string `"gzip, deflate"`. Its own test comment in `middleware/content_encoding_test.go:16-20` says it supports `Content-Encoding: gzip, deflate`, but the test only uses repeated `Header.Set`, which overwrites earlier values instead of exercising that form. An in-process request with that one field returned 415.
- **Suggested fix:** Split every `Content-Encoding` field on commas, trim each coding, and require each individual coding to be present in `allowedEncodings`. Add coverage for a single combined field and for multiple field values.

## Validation

I ran focused in-process reproductions for all four findings. The repository's `go test ./middleware` began successfully but the environment forbids `httptest.NewServer` from binding a local TCP port, so the existing package suite cannot complete here; it failed at listener creation rather than an assertion.

## Files read

- `middleware/basic_auth.go`
- `middleware/clean_path.go`
- `middleware/client_ip.go`
- `middleware/compress.go`
- `middleware/content_charset.go`
- `middleware/content_encoding.go`
- `middleware/content_type.go`
- `middleware/get_head.go`
- `middleware/heartbeat.go`
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
- `middleware/strip.go`
- `middleware/sunset.go`
- `middleware/supress_notfound.go`
- `middleware/terminal.go`
- `middleware/throttle.go`
- `middleware/timeout.go`
- `middleware/url_format.go`
- `middleware/value.go`
- `middleware/wrap_writer.go`
- `middleware/compress_test.go`
- `middleware/content_charset_test.go`
- `middleware/content_encoding_test.go`
- `middleware/get_head_test.go`
- `middleware/route_headers_test.go`
