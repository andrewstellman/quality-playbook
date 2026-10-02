model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:35:44 UTC; finished 2026-09-28 22:38:03 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran go test ./middleware (passed)
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review — terra run 05

## Findings

### 1. `Compress` selects encodings the client explicitly declined

- **File/line:** `middleware/compress.go:260-266`
- **Severity:** medium
- **What goes wrong:** `matchAcceptEncoding` uses substring matching and never interprets quality values.  A request with `Accept-Encoding: gzip;q=0` receives `Content-Encoding: gzip` even though `q=0` makes gzip unacceptable.  Likewise, a token such as `xgzip` is treated as accepting `gzip` because it contains the string `gzip`.  A client that does not support the emitted encoding consequently receives a response it cannot decode.
- **Why this is wrong:** `selectEncoder` says it parses the accepted algorithm names (line 234) and `Compress` promises to choose a format based on `Accept-Encoding`.  HTTP content codings are comma-separated tokens with optional parameters; substring containment is neither token matching nor acceptance negotiation.
- **Suggested fix:** Parse each comma-separated coding into a normalized token plus parameters, compare coding names exactly, and skip entries with `q=0`.  Implement the wildcard/quality precedence rules as part of selection (or use a tested parser); return no encoder when no supported coding is acceptable.

### 2. A failing custom encoder causes a raw response to be labelled as compressed

- **File/line:** `middleware/compress.go:249-250`, `middleware/compress.go:211-221`, `middleware/compress.go:328-334`
- **Severity:** medium
- **What goes wrong:** An `EncoderFunc` is documented to return `nil` on failure (lines 269-273).  When such a function is selected, `selectEncoder` still returns its encoding name.  `Handler` leaves `cw.w` pointing at the original response writer because the encoder is nil, but `WriteHeader` sees the nonempty name and sets `Content-Encoding`.  The body is therefore sent uncompressed with a compression header, so clients attempt to decode ordinary bytes and fail.  Invalid flate levels reach this path through the built-in encoder functions as well.
- **Why this is wrong:** The documented nil-on-failure contract requires an unsuccessful encoder not to be used.  Here its name survives independently of the nil writer and marks a body that was never encoded.
- **Suggested fix:** After calling a non-pooled encoder, check the returned writer.  If it is nil, continue looking for another acceptable encoder or return `(nil, "", no-op cleanup)`.  Only return/set an encoding name alongside a non-nil encoder.

### 3. `AllowContentEncoding` rejects valid multi-coding header fields

- **File/line:** `middleware/content_encoding.go:17-29`
- **Severity:** medium
- **What goes wrong:** A request with `Content-Encoding: gzip, deflate` is rejected with 415 even when both `gzip` and `deflate` are allowed.  The loop validates each header field value as one encoding, rather than splitting the comma-separated list in that value.  This affects ordinary clients that send a content-coding chain in a single field line.
- **Why this is wrong:** The test's own comment says the middleware supports `Content-Encoding: gzip, deflate`, but the implementation only succeeds when encodings arrive as separate `Header` values.  `Content-Encoding` represents a list of codings, so a field value containing two supported codings must validate each coding separately.
- **Suggested fix:** For every header field value, split on commas, trim and lowercase each coding token, then check every token against `allowedEncodings`.

### 4. `ContentCharset` rejects valid quoted charset parameters

- **File/line:** `middleware/content_charset.go:35-39`
- **Severity:** low
- **What goes wrong:** With `ContentCharset("utf-8")`, a request whose content type is `application/json; charset="UTF-8"` receives 415.  The parser returns the literal value including quotes (`"utf-8"`), which cannot match the configured `utf-8`.
- **Why this is wrong:** The middleware promises to allow requests whose charset matches one of its supplied values.  A media-type parameter value may be a quoted string, so the quoted and unquoted UTF-8 forms denote the same charset.  The manual string splitting does not parse that form.
- **Suggested fix:** Parse the media type with `mime.ParseMediaType` and compare the normalized `charset` parameter, or correctly handle quoted parameter values (including escapes) before comparison.

## Validation

`go test ./middleware` passed.

## Files read

Source: `middleware/basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`, `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, and `wrap_writer.go`.

Tests: `middleware/compress_test.go`, `content_charset_test.go`, `content_encoding_test.go`, `content_type_test.go`, `get_head_test.go`, `route_headers_test.go`, `throttle_test.go`, `wrap_writer_test.go`, and `client_ip_test.go`.
