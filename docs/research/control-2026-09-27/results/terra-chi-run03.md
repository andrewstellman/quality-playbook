model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:32:11 UTC; finished 2026-09-28 22:35:08 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran go test ./middleware (passed)
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Middleware review — chi `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

## Findings

### 1. A failed custom encoder is advertised as if it encoded the response

- **File / line:** `middleware/compress.go:249-250`, `middleware/compress.go:328-331`
- **Severity:** high
- **What goes wrong:** `EncoderFunc` explicitly permits a failure result of `nil`, but `selectEncoder` still returns that encoder's name. `Handler` retains the original response writer when `encoder == nil`; then `WriteHeader` sees the nonempty name, sets `Content-Encoding`, and writes the original, uncompressed bytes. For example, registering `SetEncoder("br", func(io.Writer, int) io.Writer { return nil })` and serving `text/html` to a request accepting `br` produces `Content-Encoding: br` with an identity body. Clients therefore attempt to decode bytes that were never encoded.
- **Why this is wrong:** the public `EncoderFunc` contract at lines 269-272 says an encoder returns `nil` on failure. The response must not claim that such a failed encoder produced the body.
- **Suggested fix:** treat a nil result from a non-pooled `EncoderFunc` as no selected encoder: return `nil, "", func(){}` (or otherwise suppress compression) before constructing the response writer. Also guard the pooled encoder creation path against a nil/non-resettable factory result.

### 2. `Accept-Encoding` parsing selects encodings the client explicitly rejects

- **File / line:** `middleware/compress.go:234-239`, `middleware/compress.go:260-266`
- **Severity:** medium
- **What goes wrong:** `matchAcceptEncoding` checks whether an arbitrary comma-delimited item merely contains the encoder name. Thus a request with `Accept-Encoding: gzip;q=0` receives gzip even though quality zero means it is unacceptable. It also treats unrelated tokens such as `xgzip` as acceptance of gzip. This can make clients receive a representation they declared they cannot decode.
- **Why this is wrong:** `Compress` is documented to choose the response data format from `Accept-Encoding` (lines 34-37), while the current predicate neither parses an encoding token nor honors its quality value.
- **Suggested fix:** parse each list item into an exact, case-insensitive coding token and parameters; ignore codings with `q=0`, and handle `*` and preference/precedence deliberately. Do not use substring matching.

### 3. Content-Encoding lists in one header field are rejected as a single unknown encoding

- **File / line:** `middleware/content_encoding.go:17-29`
- **Severity:** medium
- **What goes wrong:** For a body with `Content-Encoding: gzip, deflate`, `requestEncodings` has one element, `"gzip, deflate"`; the map lookup consequently fails even when both `gzip` and `deflate` were allowed. A sender using the normal comma-separated content-coding list receives an incorrect 415.
- **Why this is wrong:** the middleware promises that all request content encodings are checked against the whitelist (lines 8-9 and 23). A single Content-Encoding field can contain more than one coding; the existing test's repeated `Header.Set` calls do not test that form because each call overwrites the prior value.
- **Suggested fix:** split every header field value on commas, trim/lowercase each coding, and validate each individual coding (while retaining support for repeated field lines).

### 4. Header routing corrupts case-sensitive header values

- **File / line:** `middleware/route_headers.go:85-94`
- **Severity:** medium
- **What goes wrong:** `Handler` lowercases every header value before matching but retains the caller's `match` pattern unchanged. A route such as `Route("Authorization", "Bearer AbC123", ...)`, or one matching a case-sensitive API key, can never match its literal input. More generally, headers have case-insensitive names, but their values are not universally case-insensitive.
- **Why this is wrong:** `RouteHeaders` advertises routing based on a request header (lines 8-9), and `Route` stores the supplied match string unchanged (lines 48-55). Lowercasing only the received value changes what is being matched and makes exact literal routes unreliable.
- **Suggested fix:** preserve the received value and make `Pattern.Match` exact/case-sensitive by default. If case-insensitive matching is desired for selected headers, offer it explicitly or normalize both the configured pattern and value under a documented case-insensitive mode.

### 5. Matching precedence across different headers is nondeterministic

- **File / line:** `middleware/route_headers.go:85-98`
- **Severity:** medium
- **What goes wrong:** routes are grouped in a Go map and `Handler` ranges over that map. When a request satisfies routes for two different headers, the chosen middleware varies with Go's randomized map iteration order. For example, matching `Host: example.com` and `X-Mode: admin` can invoke either configured route, even if callers registered one before the other.
- **Why this is wrong:** the implementation comment promises to “find first matching header route” (line 85), but a map has no stable first entry. The fluent `Route` calls imply a configuration order, which the `HeaderRouter` representation discards.
- **Suggested fix:** preserve route registration order in a slice (or a separate ordered header-key list) and traverse that ordering in `Handler`; keep a map only as an optional lookup index.

## Validation

`go test ./middleware` passed.

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
- `middleware/route_headers_test.go`
- `middleware/throttle_test.go`
- `middleware/get_head_test.go`
- `middleware/clean_path_test.go`
- `middleware/path_rewrite_test.go`
