model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 21:56:49 UTC; finished 2026-09-28 21:58:53 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran offline scratch Go reproductions with GOPROXY=off
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review

Checkout: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`  
Scope: `middleware/`

## Findings

1. **Host routes do not match ordinary server requests** — `middleware/route_headers.go:87` — **Medium**. `Handler` reads `r.Header.Get("Host")`, but Go's HTTP server stores the request authority in `r.Host` and removes it from `r.Header`. Consequently, the documented `Route("Host", "example.com", ...)` example at lines 11–21 falls through to `next` or the default route for a normal request to `example.com`. A request created with `httptest.NewRequest("GET", "http://example.com/", nil)` reproduces this: `r.Host` is `example.com`, `r.Header.Get("Host")` is empty, and the route is skipped. **Fix:** When the configured header is `Host`, match against `r.Host`; use `r.Header.Get` for other headers.

2. **Compression ignores explicit encoding rejection** — `middleware/compress.go:260–265` — **Medium**. `matchAcceptEncoding` accepts any token containing the algorithm name, without parsing its quality value or token boundary. A request with `Accept-Encoding: gzip;q=0` receives `Content-Encoding: gzip` despite explicitly refusing gzip. `Accept-Encoding: xgzip` also selects gzip even though it names a different coding. The `Compress` contract says it chooses a format based on `Accept-Encoding`; these outcomes violate that negotiation. Both reproduce with `Compress(5)` and a `text/plain` response. **Fix:** Parse comma-separated coding tokens and optional `q` values, use exact case-insensitive coding matches, reject `q=0`, and handle the `*` token according to HTTP encoding negotiation rules.

3. **Allowed stacked content codings are rejected when sent in one header** — `middleware/content_encoding.go:24–25` — **Medium**. `AllowContentEncoding("gzip", "br")` checks each raw header field as one string. The valid field `Content-Encoding: gzip, br` is therefore looked up as `"gzip, br"` and returns 415, although the inline comment at line 23 says all encodings in the request must be allowed and both are. The same codings in two header fields are accepted. Reproduced with a nonempty POST body. **Fix:** Split every header field on commas, trim each coding, and check each token against the whitelist.

4. **Quoted charset values are rejected** — `middleware/content_charset.go:35–39` — **Low**. `ContentCharset("utf-8")` returns 415 for `Content-Type: text/plain; charset="utf-8"` on a nonempty body because the parser compares the literal `"utf-8"` against `utf-8`. Quoted parameter values are valid media-type syntax; the function's comment at lines 9–10 promises to allow matching charsets. Reproduced with a POST request. **Fix:** Parse the media type and its parameters with `mime.ParseMediaType`, then compare the decoded `charset` parameter case-insensitively.

5. **Competing header routes are selected in random map order** — `middleware/route_headers.go:85–94` — **Medium**. `HeaderRouter` is a map (`line 46`), and `Handler` ranges over it. When two configured header routes both match a request, either middleware may run, independently of the order in which `Route` was called. This contradicts the comment at line 85 that it finds the *first* matching header route and makes routing policy unstable for requests containing both headers. **Fix:** Preserve insertion order of header routes in a slice, and evaluate that ordered list; keep a separate default route.

## Verification

A small `go run` reproduction under `/private/tmp/qpb-control/sol-chi-run05/` produced: Host route unmatched, `gzip;q=0` and `xgzip` both selected gzip, a `gzip, br` content-encoding field returned 415, and a quoted UTF-8 charset returned 415. No files in the checkout were modified. Network package fetching was disabled.

## Files read

`go.mod`; `middleware/basic_auth.go`; `middleware/clean_path.go`; `middleware/client_ip.go`; `middleware/client_ip_test.go`; `middleware/compress.go`; `middleware/compress_test.go`; `middleware/content_charset.go`; `middleware/content_encoding.go`; `middleware/content_type.go`; `middleware/get_head.go`; `middleware/heartbeat.go`; `middleware/logger.go`; `middleware/middleware.go`; `middleware/nocache.go`; `middleware/page_route.go`; `middleware/path_rewrite.go`; `middleware/profiler.go`; `middleware/realip.go`; `middleware/recoverer.go`; `middleware/request_id.go`; `middleware/request_size.go`; `middleware/route_headers.go`; `middleware/route_headers_test.go`; `middleware/strip.go`; `middleware/sunset.go`; `middleware/supress_notfound.go`; `middleware/terminal.go`; `middleware/throttle.go`; `middleware/timeout.go`; `middleware/url_format.go`; `middleware/value.go`; `middleware/wrap_writer.go`.
