# Code review: go-chi/chi `middleware/` (commit 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc)

Reviewer: opus (run 10). Each finding marked "confirmed" was reproduced with a throwaway probe test run against a copy of the checkout (`go test -run Probe`). The probe file was deleted afterwards.

---

## 1. SupressNotFound corrupts the live routing context: mounted sub-routers return 404, URL params are duplicated. Confirmed.

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` and passes in the request's *live* routing context. `Mux.Find` (mux.go:380-397) changes that context. It appends URL params and sets `routePattern`, and for a mounted sub-router it rewrites `rctx.RoutePath` to the sub-path. When the real routing runs next, it uses the modified context.
  - `r.Use(SupressNotFound(r)); r.Mount("/api", sub)` where `sub.Get("/{id}")`: `GET /api/42` returns **404**. The top-level mux now routes `RoutePath="/42"`.
  - With `r.Get("/a/{id}")`, `GET /a/7` reaches the handler with `URLParams.Keys` of length 2 (`id` twice).
- **Why it is wrong:** mux.go:380-381 says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". `GetHead` (get_head.go:24) gets this right and uses a temporary `chi.NewRouteContext()`. The doc comment says the middleware 404s only when "the route is not found". Here it 404s routes that exist.
- **Severity:** high. Any app that uses this middleware together with `Mount` gets 404 on every mounted route.
- **Fix:** `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, path)`. Also use `RoutePath`/`RawPath` the same way `GetHead` does, not `r.URL.Path`.

## 2. Compress sends `Content-Encoding: gzip` over an uncompressed body when the encoder can't be built (for example, an invalid level). Confirmed.

- **File/line:** `middleware/compress.go:249-250` and `219-221`, `328-331`
- **What goes wrong:** `EncoderFunc` is documented to "return nil" on failure (line 272). `encoderGzip` and `encoderDeflate` do this for levels outside -2..9. `selectEncoder` returns `fn(w, level)` (nil) together with the name `"gzip"`. `Handler` skips `cw.w = encoder`, so `cw.w` stays the raw writer, but `cw.encoding` is still `"gzip"`. `WriteHeader` then sets `Content-Encoding: gzip` and writes plain bytes. With `Compress(10)` and `Accept-Encoding: gzip`, the response was `Content-Encoding: gzip` with body `hello hello ...`. Clients can't decode it.
- **Why it is wrong:** The header states an encoding that was never applied, which violates RFC 9110 §8.4. The code handles `encoder == nil` for the writer but not for the encoding name.
- **Severity:** medium. It needs an invalid level, but the failure is silent and breaks every compressible response.
- **Fix:** In `selectEncoder`, if `fn(w, c.level)` returns nil, skip to the next encoder (or return `nil, ""`). Or validate the level in `NewCompressor`/`SetEncoder` and panic early.

## 3. The "deflate" encoding writes raw DEFLATE, not zlib-wrapped data. Confirmed.

- **File/line:** `middleware/compress.go:406-411` (`encoderDeflate` uses `flate.NewWriter`)
- **What goes wrong:** With `Accept-Encoding: deflate`, the response is labelled `Content-Encoding: deflate` but the body is raw RFC 1951 data. `zlib.NewReader` on the body fails with `zlib: invalid header`.
- **Why it is wrong:** The file's own comment (lines 114-116) says: "HTTP 1.1 "deflate" (RFC 2616) stands for DEFLATE data (RFC 1951) wrapped with zlib (RFC 1950)." RFC 9110 §8.4.1.2 says the same. The comment then notes that only old browsers expect raw DEFLATE.
- **Severity:** low-medium. gzip has precedence, so this only affects clients that accept deflate but not gzip.
- **Fix:** Use `zlib.NewWriterLevel(w, level)` (it has `Reset`, so pooling still works).

## 4. Compress ignores q-values and matches encodings by substring. Confirmed.

- **File/line:** `middleware/compress.go:235, 260-267`
- **What goes wrong:** `matchAcceptEncoding` uses `strings.Contains(v, encoding)` on each comma-separated element. `Accept-Encoding: gzip;q=0, identity` still gets `Content-Encoding: gzip`. Substring matching also picks up unrelated tokens that contain the name, such as `x-gzip`.
- **Why it is wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The package doc says compression is "based on Accept-Encoding request header".
- **Severity:** medium. The server sends an encoding the client explicitly refused.
- **Fix:** Parse each element into a token and parameters. Compare the trimmed token exactly (case-insensitively), and treat `q=0` as a rejection. Optionally, honour `*`.

## 5. Compress sends gzip bytes under uncompressed headers when the handler flushes before its first write. Confirmed.

- **File/line:** `middleware/compress.go:357-370` together with `310-336`, `338-344`
- **What goes wrong:** Before any `WriteHeader`/`Write`, `compressible` is false, so `Flush()` calls the underlying `ResponseWriter.Flush()`. That commits a 200 response with no `Content-Encoding`. The next `Write` sees `!cw.wroteHeader` and calls `WriteHeader`. This decides the content is compressible, sets `Content-Encoding` too late ("superfluous response.WriteHeader" is logged), and switches to the gzip writer. Over a real server, the client got `Content-Encoding: ""` and a raw gzip body (`\x1f\x8b...`), which is corrupted output.
- **Why it is wrong:** The compression decision must be made before headers are committed. Once headers go out without `Content-Encoding`, the body must not be encoded.
- **Severity:** medium. The trigger is common in streaming handlers: set the type, flush headers, then stream.
- **Fix:** In `Flush`, call `cw.WriteHeader(http.StatusOK)` first if `!cw.wroteHeader`, so the decision happens before the flush. Same in `Hijack`/`Push` if needed.

## 6. Compress labels bodiless responses (204/304) as gzip and writes a gzip trailer into them. Confirmed for the header.

- **File/line:** `middleware/compress.go:310-336`, `387-392`
- **What goes wrong:** `WriteHeader(204)` with a compressible Content-Type sets `Content-Encoding: gzip` and `Vary`. The deferred `cw.Close()` then writes a gzip header and trailer into a response that can't have a body. The probe showed `Content-Encoding: gzip` on a 204. The body write fails with `http.ErrBodyNotAllowed`, and that error is ignored.
- **Why it is wrong:** RFC 9110 §15.3.5 says 204 carries no content, and a 304 has none either. Content-Encoding describes content that isn't there.
- **Severity:** low.
- **Fix:** In `WriteHeader`, don't enable compression for `code < 200`, 204 or 304.

## 7. RouteHeaders can never match `Host` (the documented example), and mixed-case patterns never match. Confirmed.

- **File/line:** `middleware/route_headers.go:87-93`, `48-54`, `135-139`
- **What goes wrong:**
  - The doc example routes on `Route("Host", "example.com", ...)`. On incoming server requests, Go moves the Host header into `r.Host` and deletes it from `r.Header`. `r.Header.Get("host")` is therefore always `""` and the route never fires; the probe confirmed this over a real server.
  - The handler lowercases the request header value (line 91) but `NewPattern` stores the pattern as given. `Route("Origin", "https://App.example.com", ...)` never matches, even with an identical Origin header; confirmed.
- **Why it is wrong:** It contradicts the function's own doc example. A case-normalisation step applied to only one side is a logic error.
- **Severity:** medium. Header routing silently falls through to the default route, which in the documented CORS use case means the wrong CORS policy.
- **Fix:** For the `host` key, read `r.Host`. Lowercase `prefix`/`suffix` in `NewPattern` (or stop lowercasing the value).
- **Related:** `for header, matchers := range hr` iterates a Go map. When routes are registered on more than one header, the "first matching header route" (line 85) is chosen at random per request. Iterate in a stable, registration order instead.

## 8. AllowContentEncoding rejects a valid comma-separated Content-Encoding list. Confirmed.

- **File/line:** `middleware/content_encoding.go:17, 24-29`
- **What goes wrong:** `r.Header["Content-Encoding"]` gives one element per header *line*, and each element is compared whole. `Content-Encoding: deflate, gzip` with both encodings allowed is compared as `"deflate, gzip"` and gets **415**.
- **Why it is wrong:** RFC 9110 §8.4 defines Content-Encoding as a comma-separated list (`#content-coding`). The code's comment says "All encodings in the request must be allowed", which implies checking each coding.
- **Severity:** low-medium.
- **Fix:** Split each header value on `,` and check each trimmed coding.

## 9. Sunset/Deprecation headers are wrong for any non-UTC time. Confirmed.

- **File/line:** `middleware/sunset.go:15-16`
- **What goes wrong:** `sunsetAt.Format(http.TimeFormat)` prints the wall-clock time in the value's own location but always appends the literal "GMT". `time.Date(2030,1,1,12,0,0,0, UTC+5)` is emitted as `Tue, 01 Jan 2030 12:00:00 GMT`. The correct value is 07:00 GMT, so the header is five hours off.
- **Why it is wrong:** The `http.TimeFormat` docs say "The time being formatted must be in UTC for Format to generate the correct format." RFC 8594 (cited in the doc comment) requires an HTTP-date, which is GMT.
- **Severity:** low-medium. Clients get an incorrect sunset instant.
- **Fix:** `sunsetAt.UTC().Format(http.TimeFormat)`. The same applies to the Deprecation header.

## 10. RedirectSlashes drops the mount prefix inside a mounted sub-router. Confirmed.

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** Inside a sub-router, `path` comes from `rctx.RoutePath`, which is relative to the mount point. With `r.Mount("/api", sub)` and `sub.Use(RedirectSlashes)`, `GET /api/items/` redirects with **301 to `/items`**, not `/api/items`.
- **Why it is wrong:** The doc says it redirects "to the same path, less the trailing slash". Using `RoutePath` makes sense for routing, but `Location` has to be the full request path.
- **Severity:** medium. Every trailing-slash request in a mounted sub-router is permanently redirected to a wrong URL.
- **Fix:** Build the redirect target from `r.URL.Path` (with the same backslash and leading-slash normalisation), not from `rctx.RoutePath`.

## 11. URLFormat panics on a path containing a dot but no slash. Confirmed.

- **File/line:** `middleware/url_format.go:58-60`
- **What goes wrong:** If `path` has a `.` at index > 0 and no `/`, `base` is -1 and `path[base:]` panics (`slice bounds out of range [-1:]`). The probe hit this with `r.URL.Path = "a.json"` and no chi context. That happens when the middleware is used outside chi, or with handler-level tests or requests built with relative paths.
- **Why it is wrong:** The index is used unchecked.
- **Severity:** low. Real servers normally give a leading `/`.
- **Fix:** `if base < 0 { base = 0 }`, or guard `strings.LastIndex` results.

## 12. PathRewrite has no effect on requests whose URL has a RawPath. Confirmed.

- **File/line:** `middleware/path_rewrite.go:12`
- **What goes wrong:** The middleware rewrites only `r.URL.Path`. chi's router prefers `r.URL.RawPath` when it is set (mux.go:462-463), so any request with an encoded path segment keeps routing on the old path. With `PathRewrite("/old/", "/new/")`, `GET /old/ab` gets 200 but `GET /old/a%2Fb` gets 404.
- **Why it is wrong:** The rewrite is silently skipped for a subset of requests.
- **Severity:** low-medium.
- **Fix:** Rewrite `RawPath` as well (or clear it and let `EscapedPath` recompute). `StripSlashes` (strip.go:25-26) has the same Path-only mutation when there is no chi context.

## 13. CleanPath removes trailing slashes and breaks routes registered with one. Confirmed.

- **File/line:** `middleware/clean_path.go:23`
- **What goes wrong:** `path.Clean` strips the trailing slash. With `r.Use(CleanPath); r.Get("/users/", ...)`, `GET /users/` returns **404**.
- **Why it is wrong:** The doc says the middleware cleans "double slash mistakes" and gives `/users//1` as the example. It doesn't mention changing trailing-slash semantics, which chi treats as significant.
- **Severity:** low.
- **Fix:** Re-append `/` when the original path ended in `/` and the cleaned path is not `/`.

## 14. Profiler redirect breaks when the request has a query string. Confirmed.

- **File/line:** `middleware/profiler.go:27, 30`
- **What goes wrong:** `r.RequestURI + "/pprof/"` includes the query string. `GET /debug?x=1` redirects to `/debug?x=1/pprof/`, so the path stays `/debug` and the query becomes garbage.
- **Severity:** low.
- **Fix:** Use `r.URL.Path`, and append `?RawQuery` after the suffix.

## 15. Recoverer's Upgrade check is case- and list-sensitive.

- **File/line:** `middleware/recoverer.go:39`
- **What goes wrong:** `r.Header.Get("Connection") != "Upgrade"` fails for `Connection: keep-alive, Upgrade` (sent by Firefox for WebSockets) or `upgrade`. After a panic on a hijacked WebSocket connection, the middleware then calls `WriteHeader(500)` on the hijacked connection, and net/http logs a misuse error.
- **Why it is wrong:** RFC 9110 §7.6.1 says Connection is a comma-separated, case-insensitive token list.
- **Severity:** low.
- **Fix:** Check the tokens case-insensitively, for example with `httpguts.HeaderValuesContainsToken(r.Header["Connection"], "upgrade")` or an equivalent split and `EqualFold`.

---

## Things checked and judged not defects (or not confident)

- `client_ip.go`: the XFF walk, trusted-proxy counting, v4-mapped folding and zone stripping match their documentation.
- `throttle.go`: token accounting is balanced on all paths.
- `wrap_writer.go`: the ReadFrom tee/discard path does not double-count bytes; 1xx handling is fine.
- `Timeout`: writing 504 after the handler already wrote gives a superfluous-WriteHeader log. That is a known design limitation of this middleware, not reported as a defect.
- `ThrottleWithOpts` with a zero `BacklogTimeout` gives an immediate timeout. This is undocumented but plausibly intended.

## Files read

- `middleware/`: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go
- Context: `mux.go` (the `Match`/`Find` and `routeHTTP` RawPath sections)
- Test files were not read line by line. The existing middleware test suite was run and passed.
