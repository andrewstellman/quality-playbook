# chi `middleware/` code review (opus-chi-run05)

Repo: chi @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc. Scope: `middleware/`.

I confirmed every finding below by running a small Go test in a scratch copy of the repo. I added `zz_probe_test.go` and `zz_probe2_test.go` in the work directory; the checkout was not modified. The existing `middleware` test suite passes.

---

## 1. SupressNotFound corrupts the live routing context: mounted subrouters 404 and URL params are duplicated
- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` with the request's *live* route context.
  - `Mux.Find` sets `rctx.RoutePath = mx.nextRoutePath(rctx)` when it descends into a subrouter (`mux.go:397`).
  - `FindRoute` appends to `rctx.URLParams` and `rctx.RoutePatterns` (`tree.go:396-402`).
  - Real routing then runs on this mutated state.
- **Reproduced:**
  - Router with `r.Use(SupressNotFound(r))` and `r.Mount("/api", sub)` where `sub.Get("/x", …)`: `GET /api/x` returns **404** (routing restarts from `RoutePath="/x"` at the top level).
  - For `r.Get("/u/{id}")`, `GET /u/7` ends with `URLParams.Keys = [id id]` and `RoutePatterns = [/u/{id} /u/{id}]`.
- **Why wrong:** `Mux.Find`'s doc says: "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". `GetHead` (`get_head.go:24`) follows that advice with a temporary `tctx`. SupressNotFound's own doc says it should only short-circuit routes that "are not going to match any routes anyway", but here it breaks every mounted subrouter.
- **Severity:** high. Every request to a mounted subrouter becomes a 404.
- **Fix:** Use `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, routePath)`. Compute `routePath` the same way the mux does: `rctx.RoutePath`, otherwise `RawPath`, otherwise `Path`.

## 2. Compress sends a gzip body without `Content-Encoding` when the handler flushes before its first write
- **File/line:** `middleware/compress.go:357-371` (with `346-351` and `310-336`)
- **What goes wrong:**
  - Before the first `Write`/`WriteHeader`, `wroteHeader` is false, so `writer()` returns the raw `ResponseWriter`.
  - `Flush()` therefore flushes the underlying writer, which commits a 200 status and the headers *without* `Content-Encoding`.
  - The next `Write` calls `cw.WriteHeader`, which marks the response compressible and sets `Content-Encoding` on a header map that has already been sent. The body is then written as gzip.
- **Reproduced:** A handler that sets `Content-Type: text/plain`, calls `Flush()`, then writes. Over a real server the client receives `Content-Encoding: ""` and a gzip body (`\x1f\x8b…`). The log also shows "superfluous response.WriteHeader call from …compress.go:336". This is a common streaming/SSE pattern (flush headers early).
- **Why wrong:** The headers and the body contradict each other, so the client gets a corrupted response.
- **Severity:** high. The data is silently corrupted.
- **Fix:** In `Flush`, call `cw.WriteHeader(http.StatusOK)` first if `!cw.wroteHeader`, so the compression decision is made before anything is committed. Then flush the encoder and the underlying writer.

## 3. Compress labels the response with `Content-Encoding` but sends it uncompressed when the encoder is nil
- **File/line:** `middleware/compress.go:209-221` and `249-250` (with `398-411` and `182-193`)
- **What goes wrong:**
  - `EncoderFunc` is documented as "In case of failure, the function should return nil". The built-in `encoderGzip`/`encoderDeflate` do return nil for an invalid level (for example `Compress(10)`).
  - A nil encoder is not poolable, so `SetEncoder` puts it in `c.encoders`. `selectEncoder` then returns `(nil, "gzip", …)`.
  - `Handler` keeps `cw.w = w` but keeps `encoding = "gzip"`. `WriteHeader` sets `Content-Encoding: gzip`, and the body is written through `cw.w` uncompressed.
- **Reproduced:** `Compress(10)` with `Accept-Encoding: gzip` gives `Content-Encoding: gzip` and the plain-text body `"hello"`.
- **Why wrong:** The code ignores the nil-on-failure contract it documents. Clients will fail to decode the body.
- **Severity:** medium. It needs an invalid level or a failing custom encoder, but the result is a corrupted response.
- **Fix:** In `selectEncoder`, skip an encoder whose `fn(w, level)` returns nil and continue to the next one. Or in `Handler`, clear `encoding` when `encoder == nil`. Also consider rejecting such encoders in `SetEncoder`, where the probe `fn(io.Discard, level)` already detects the failure.

## 4. Compress ignores `q=0` in Accept-Encoding and matches encodings by substring
- **File/line:** `middleware/compress.go:235` and `260-267`
- **What goes wrong:** `matchAcceptEncoding` uses `strings.Contains(v, encoding)` on each comma-separated item, so `gzip;q=0` counts as accepting gzip.
- **Reproduced:** `Accept-Encoding: gzip;q=0, deflate;q=0, identity` still gives `Content-Encoding: gzip`.
- **Why wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The client explicitly refused the encoding.
- **Severity:** medium.
- **Fix:** Parse each item as `token[;q=value]`. Trim the token and compare it exactly (case-insensitively). Treat `q=0` as a rejection, and optionally honour `*`.

## 5. RouteHeaders cannot route on `Host`, which is the headline example in its doc
- **File/line:** `middleware/route_headers.go:483` (doc example at `route_headers.go:12-21`)
- **What goes wrong:** `Handler` reads `r.Header.Get(header)`. The `net/http` server removes `Host` from `r.Header` and moves it to `r.Host`, so `Route("Host", …)` never matches on a real server.
- **Reproduced:** Over `httptest.NewServer` with `req.Host = "example.com"` and `Route("Host", "example.com", …)`, the default handler runs (`r.Header.Get("Host") == ""`).
- **Why the tests miss it:** The package tests set `req.Header.Set("Host", …)` by hand (`route_headers_test.go:54, 80, 111, 176`), which a real server never does.
- **Why wrong:** The doc comment's first example routes subdomains by `"Host"`, and that cannot work.
- **Severity:** medium. The documented use case silently falls through to the default route.
- **Fix:** When `header == "host"`, use `r.Host` instead of `r.Header.Get`.

## 6. RouteHeaders patterns containing uppercase letters never match
- **File/line:** `middleware/route_headers.go:450`, `462` and `487`
- **What goes wrong:** The request header value is lowercased (line 487), but the match patterns go to `NewPattern` unchanged.
- **Reproduced:** `Route("Host", "Example.com", …)` against a header value of `Example.com` falls through to the default handler.
- **Why wrong:** The code clearly intends case-insensitive matching, since it lowercases both the header name and the value. Only the pattern side was missed, so any pattern with a capital letter (for example an Origin) is dead.
- **Severity:** low.
- **Fix:** Use `NewPattern(strings.ToLower(match))` in both `Route` and `RouteAny`.

## 7. AllowContentEncoding rejects valid comma-separated Content-Encoding lists
- **File/line:** `middleware/content_encoding.go:17-29`
- **What goes wrong:** Each header *line* is compared as a whole against the allow-list. `Content-Encoding: deflate, gzip` is a single line that is not split.
- **Reproduced:** `AllowContentEncoding("gzip","deflate")` with `Content-Encoding: deflate, gzip` returns 415.
- **Why wrong:** Content-Encoding is a comma-separated list (RFC 9110 §8.4). The code's own comment says "All encodings in the request must be allowed", and here every encoding is allowed.
- **Severity:** low.
- **Fix:** Split each header value on `,`, then trim and lowercase each element before the lookup.

## 8. URLFormat treats a dotfile name as an extension, which breaks routing
- **File/line:** `middleware/url_format.go:58-69`
- **What goes wrong:**
  - `idx := strings.LastIndex(path[base:], ".")` is relative to the slice that starts *at* the `/`, so `idx > 0` is true even when the dot comes straight after the slash.
  - For `/files/.env`, format becomes `"env"` and `RoutePath` becomes `/files/`, so the `{name}` route no longer matches.
  - For `/.well-known`, `RoutePath` becomes `""`, which makes the mux fall back to the full URL path.
- **Reproduced:** With `r.Get("/files/{name}")`, `GET /files/.env` returns 404.
- **Why wrong:** The intent is to strip a suffix extension from a basename, which is why there is an `idx > 0` guard. A leading-dot name has no extension.
- **Severity:** low.
- **Fix:** Require `idx > 1`, meaning at least one character between the `/` and the `.`.

## 9. RedirectSlashes in a mounted subrouter redirects to a path without the mount prefix
- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** Inside a mounted subrouter, `rctx.RoutePath` is the *sub*-path. The redirect is built from it, so the mount prefix is lost.
- **Reproduced:** `r.Mount("/api", sub)` with `sub.Use(RedirectSlashes)`: `GET /api/users/` returns 301 with `Location: /users`.
- **Why wrong:** The doc says it redirects "to the same path, less the trailing slash". Instead the client is sent to a different, usually nonexistent, resource.
- **Severity:** medium.
- **Fix:** Build the redirect target from `r.URL.Path` (or `EscapedPath()`), not from `rctx.RoutePath`. `RoutePath` can still decide *whether* to redirect.

## 10. StripSlashes ignores `RawPath` and so changes which route matches for encoded paths
- **File/line:** `middleware/strip.go:18-29`
- **What goes wrong:** When `rctx.RoutePath` is empty, the path is taken from the decoded `r.URL.Path` and written into `rctx.RoutePath`. The mux itself routes on `r.URL.RawPath` when it is set (`mux.go:460-466`), as do `CleanPath` and `GetHead`.
- **Reproduced:** With `r.Get("/a/{x}")`, `GET /a/b%2Fc` gives 200 `x=b%2Fc`, but `GET /a/b%2Fc/` under StripSlashes gives **404** (it routes on the decoded `/a/b/c`).
- **Why wrong:** Stripping a trailing slash should not change how the rest of the path is interpreted. It is inconsistent with the mux's own path selection.
- **Severity:** low.
- **Fix:** Use `RawPath` when it is non-empty, as `CleanPath` and `GetHead` do.

## 11. Compress makes its compression decision at a 1xx informational WriteHeader
- **File/line:** `middleware/compress.go:310-336`
- **What goes wrong:** The first `WriteHeader` call sets `wroteHeader = true` and decides compressibility, even if that call is a 1xx status such as `103 Early Hints`. The final status's headers (usually including `Content-Type`) are never considered.
- **Why wrong:** 1xx responses are not the final response. The package's own `basicWriter.WriteHeader` (`wrap_writer.go:84-87`) explicitly passes 1xx statuses through without latching.
- **Severity:** low. Compression is silently skipped, but the response is not corrupted.
- **Fix:** For `100 <= code <= 199 && code != 101`, pass the call through to the `ResponseWriter` and return without latching `wroteHeader`.

## 12. ClientIPFromHeader does not handle an appended value in a single header line, contrary to its doc
- **File/line:** `middleware/client_ip.go:46-49` (doc at `33-38`)
- **What goes wrong:** The doc says that if the header reaches us with multiple values ("misconfigured proxy that appends"), the LAST value wins. Only separate header *lines* are handled. A proxy that appends in the usual way (`X-Real-IP: 6.6.6.6, 1.2.3.4`) makes the parse fail, and no IP is set.
- **Reproduced:** The header `"6.6.6.6, 1.2.3.4"` gives `GetClientIP == ""`.
- **Why wrong:** The code does not do what the doc says. It fails closed, so this is not a security issue.
- **Severity:** low.
- **Fix:** Take the last comma-separated element of the last value (for example with `walkXFF`'s logic) before parsing.

---

## Files actually read
- All non-test files in `middleware/`: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go
- `middleware/route_headers_test.go` (grep only)
- `mux.go` (Match/Find/routeHTTP sections) and `tree.go` (FindRoute)
