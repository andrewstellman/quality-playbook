model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:42:40 UTC; finished 2026-09-28 22:45:29 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran go test ./middleware (passed)
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi `middleware/` review

`go test ./middleware` passed. The following defects are present despite that
test result.

## High — flushing a compressible streaming response corrupts the body

**File:** `middleware/compress.go:357-370`

`compressResponseWriter.Flush` forwards the flush without first committing the
wrapper's headers.  For a handler that sets `Content-Type: text/plain`, calls
`Flush`, and subsequently calls `Write`, the first flush causes the underlying
writer to send an implicit uncompressed 200 response. `cw.wroteHeader` is still
false. The later `Write` calls `cw.WriteHeader`, which sets the wrapper's
`Content-Encoding: gzip` and makes the body go through the gzip writer, but the
header can no longer reach the client. The client therefore receives gzip bytes
with no `Content-Encoding` header.

This contradicts `Compress`'s documented behavior of compressing the response
body according to `Accept-Encoding` (`middleware/compress.go:34-42`) and breaks
common streaming/SSE-style handlers.

**Suggested fix:** Have `Flush` call `cw.WriteHeader(http.StatusOK)` when no
header has been written, before choosing and flushing `cw.writer()`. This
commits the same encoding decision and headers as `Write` before the underlying
writer is flushed.

## Medium — `Accept-Encoding` parsing sends encodings explicitly refused by the client

**File:** `middleware/compress.go:260-266`

`matchAcceptEncoding` accepts an encoder whenever a comma-separated member
*contains* its name. Consequently `Accept-Encoding: gzip;q=0` selects gzip,
even though quality zero explicitly makes gzip unacceptable. It also treats an
unrelated token such as `xgzip` as permission to send gzip. A client that has
disabled gzip can thus receive a response it said it cannot decode.

The code comments say `SetEncoder` takes a standardized encoding identifier
(`middleware/compress.go:144-147`), but this matcher does not compare encoding
tokens or honor their parameters.

**Suggested fix:** Parse each member into an exact, trimmed coding token and
parameters; reject entries with `q=0`, and implement wildcard/quality selection
according to the HTTP `Accept-Encoding` semantics.

## Medium — documented Host routes never match normal server requests

**File:** `middleware/route_headers.go:86-92`

`HeaderRouter.Handler` obtains every routed field with `r.Header.Get(header)`.
For an incoming Go HTTP server request, the `Host` field is represented by
`r.Host`, not `r.Header`. Thus the package's own documented example using
`Route("Host", "example.com", ...)` (`middleware/route_headers.go:11-21`) does
not route requests received by a real server; it falls through to the default
or next handler. The unit test masks this by manually adding a `Host` entry to
the request header (`middleware/route_headers_test.go:52-55`).

**Suggested fix:** Special-case the normalized header name `host` and match
against `r.Host`; continue using `r.Header` for actual header fields.

## Medium — `CleanPath` panics when used with an ordinary `http.Handler`

**File:** `middleware/clean_path.go:14-24`

`CleanPath` immediately dereferences `chi.RouteContext(r.Context())`. That
value is nil for a request served directly by an ordinary `http.Handler` (for
example, `middleware.CleanPath(http.DefaultServeMux)`), so every request
panics at `rctx.RoutePath`. Its public signature and comment describe a generic
middleware and do not restrict it to a chi router. In contrast,
`StripSlashes` explicitly handles a nil route context
(`middleware/strip.go:17-29`).

**Suggested fix:** Guard `rctx != nil`. When it is nil, clean and replace
`r.URL.Path` (and preserve the existing chi `RoutePath` behavior only when a
route context exists).

## Medium — `AllowContentEncoding` rejects valid multi-coding request bodies

**File:** `middleware/content_encoding.go:23-29`

The middleware compares each whole `Content-Encoding` header value to the
allow-list. A valid request header such as `Content-Encoding: gzip, deflate`
is therefore compared as the single string `"gzip, deflate"` and rejected with
415, even if both `gzip` and `deflate` were allowed. The test's own setup says
these combined encodings are supported (`middleware/content_encoding_test.go:15-20`),
but it uses `Header.Set` repeatedly (`:66-68`), so it never puts the combined
header on a request.

**Suggested fix:** Split every field value on commas, trim and normalize each
coding token, then require every individual token to be in `allowedEncodings`.

## Medium — `NoCache` silently removes conditional request preconditions

**File:** `middleware/nocache.go:43-48`

`NoCache` deletes `If-Match`, `If-None-Match`, `If-Unmodified-Since`, and other
conditional request headers before the application handler sees them. For
example, a `PUT` protected by `If-Match` becomes an unconditional overwrite,
which defeats an application's optimistic-concurrency check. This is unrelated
to the middleware's documented purpose of setting response headers to prevent
caching (`middleware/nocache.go:31-39`) and changes the request's semantics.

**Suggested fix:** Do not alter request headers. Set the no-cache response
headers only; if an ETag response header must be suppressed, do so on the
response writer rather than deleting request preconditions.

## Files read

Production files: `middleware/basic_auth.go`, `clean_path.go`,
`client_ip.go`, `compress.go`, `content_charset.go`, `content_encoding.go`,
`content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`,
`middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`,
`profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`,
`route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`,
`terminal.go`, `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, and
`wrap_writer.go`.

Test files: `middleware/clean_path_test.go`, `client_ip_test.go`,
`compress_test.go`, `content_encoding_test.go`, `get_head_test.go`,
`route_headers_test.go`, and `strip_test.go`.
