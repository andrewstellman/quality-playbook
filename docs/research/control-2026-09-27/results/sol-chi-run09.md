model: gpt-6-sol
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:01:02 UTC; finished 2026-09-28 22:03:42 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; verification performed, details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review — `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

Scope: `middleware/`. All reproductions used the supplied checkout with `GOPROXY=off`; the checkout was not modified.

## Findings

1. **`middleware/compress.go:260-264` — explicitly refused response encoding is selected (medium).** `matchAcceptEncoding` uses substring matching, so `Accept-Encoding: gzip;q=0` matches `gzip`. A local request to `Compress(5)` returned `Content-Encoding: gzip` and a gzip body for that header. An accept quality of zero means the client does not accept that coding, contradicting `Compress`'s promise to base the response format on `Accept-Encoding`. Parse coding tokens and quality values, require an exact coding match with positive quality, and honor explicit exclusions when processing a wildcard.

2. **`middleware/compress.go:219-220` and `:239-250` — failed custom encoder labels raw bytes as encoded (medium).** `EncoderFunc` explicitly documents that it may return `nil` on failure (`compress.go:269-273`). With a custom `broken` encoder returning `nil`, `Handler` leaves `cw.w` as the original writer but retains `encoding="broken"`; `WriteHeader` sets `Content-Encoding: broken`. The reproduced response body was plain `hello`. On encoder failure, clear the selected encoding and use the original writer, or fail the request before headers are written.

3. **`middleware/content_encoding.go:17-25` — valid comma-separated Content-Encoding values are rejected (medium).** Each header field value is compared as a single token. With `AllowContentEncoding("gzip", "deflate")`, `Content-Encoding: gzip, deflate` returned 415, although the code comment says all encodings must be allowed and the existing test names this format as supported. Split each field value on commas, trim each coding, and check every token.

4. **`middleware/route_headers.go:86-87` — documented Host routing never matches an ordinary server request (medium).** `RouteHeaders` documents `Route("Host", "example.com", ...)`, but an incoming Go request stores the authority in `r.Host`, not `r.Header`. A request with `Host: x` represented by `httptest.NewRequest("GET", "http://x/", nil)` took the fallback handler instead of `Route("Host", "x", ...)`. Read `r.Host` when the configured header is `Host`; use `r.Header.Get` for other headers.

5. **`middleware/supress_notfound.go:19` — the preliminary match mutates the live route context (medium).** `Mux.Match` documents that it updates the supplied `Context` (`mux.go:368-373`), yet `SupressNotFound` passes the same context that the router then uses for its real match. For `GET /users/1` routed as `/users/{id}`, the handler observed `URLParams.Keys == [id id]` and `Values == [1 1]`. Look ahead with a fresh `chi.NewRouteContext()` and preserve the routing overrides needed for the match.

6. **`middleware/supress_notfound.go:19-22` — a method mismatch becomes 404 instead of 405 (medium).** With only `GET /users/{id}` registered, `POST /users/1` returned 404 under `SupressNotFound`. Without this middleware, `Mux.routeHTTP` handles a path found under another method with `MethodNotAllowedHandler` (`mux.go:490-499`). The middleware comment says it should shortcut routes that are *not found*; this path exists. Let the router process method mismatches so it can return 405 and its `Allow` header.

7. **`middleware/supress_notfound.go:19` — route path rewrites are ignored by the preliminary match (medium).** The middleware checks `r.URL.Path` even when earlier middleware has set `rctx.RoutePath`. With `CleanPath` followed by `SupressNotFound`, `GET /a//b` returned 404 for a registered `/a/b` route; `CleanPath` documents that this input should route as `/a/b` (`clean_path.go:10-11`). Match the effective routing path, following the same `RoutePath`/`RawPath`/`Path` precedence as `Mux.routeHTTP`.

## Files read

`middleware/basic_auth.go`, `middleware/clean_path.go`, `middleware/client_ip.go`, `middleware/compress.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/throttle.go`, `middleware/timeout.go`, `middleware/url_format.go`, `middleware/value.go`, `middleware/wrap_writer.go`, `middleware/compress_test.go`, `middleware/route_headers_test.go`, `middleware/content_charset_test.go`, `middleware/content_encoding_test.go`, `mux.go` (selected sections), `context.go` (selected sections), `go.mod`, `README.md` (matching search lines).
