# chi `middleware/` review — opus-chi-run08

Repo: chi @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc, scope `middleware/`.

I confirmed every defect below by running a throwaway Go test in a copy of the checkout (`/tmp/control-work/opus-chi-run08/chi/middleware/zz_probe*_test.go`). I've deleted that copy since. Observed outputs are quoted for each one.

---

## 1. Compress: calling Flush before the first Write sends a gzip body without `Content-Encoding`

- **File/line:** `middleware/compress.go:357-371` (Flush), together with `:310-336` (WriteHeader) and `:346-351` (writer)
- **What goes wrong:** Suppose the handler sets a compressible `Content-Type` (e.g. `text/html`), calls `Flush()` and only then writes. `wroteHeader` is still false at that point, so `cw.writer()` returns the raw `ResponseWriter`. Flush is passed straight to it, and net/http commits a `200` header block that has no `Content-Encoding`. On the next `Write`, `cw.WriteHeader(200)` runs, sets `compressible = true` and adds `Content-Encoding: gzip` to a header map that has already been sent. The body is then gzip-compressed. The client gets raw gzip bytes labelled as plain `text/html`, and net/http logs "superfluous response.WriteHeader call … compress.go:336".
- **Observed:** `flush-first: CE="" body[:10]="\x1f\x8b\b\x00..."`
- **Why it's wrong:** The header decision in `WriteHeader` has to happen before anything is committed. Flush bypasses it. Flushing early is a normal thing for streaming handlers to do.
- **Severity:** high (the response is corrupt)
- **Fix:** At the top of `Flush()`, call `cw.WriteHeader(http.StatusOK)` if `!cw.wroteHeader`, as `Write` already does. Do the same in `Hijack`/`Push` if needed.

## 2. Compress: an encoder that fails (returns nil) still advertises `Content-Encoding`, and the body goes out uncompressed

- **File/line:** `middleware/compress.go:249-250` (selectEncoder), `:219-221` and `:328-331` (Handler/WriteHeader), `:398-412` (encoders return nil on error)
- **What goes wrong:** `Compress(10)` (any level flate rejects) makes `encoderGzip`/`encoderDeflate` return nil. `selectEncoder` still returns `(nil, "gzip", …)`. `Handler` leaves `cw.w = w` because `encoder == nil`, but `cw.encoding` is `"gzip"`. `WriteHeader` then sets `Content-Encoding: gzip` and writes the plain body.
- **Observed:** `badlevel: CE="gzip" … gzipErr=gzip: invalid header`
- **Why it's wrong:** The `EncoderFunc` doc (`compress.go:271-272`) says "In case of failure, the function should return nil". So nil is a documented outcome, and the caller mishandles it.
- **Severity:** medium (only happens with a misconfigured level or a custom encoder that fails, but the output is corrupt)
- **Fix:** In `selectEncoder`, when `fn(w, c.level)` returns nil, move on to the next candidate, or return `nil, "", noop`. Better still, validate the level in `NewCompressor`/`SetEncoder` (panic if `fn(io.Discard, level)` returns nil).

## 3. Compress: `Accept-Encoding` q-values are ignored, so `gzip;q=0` still gets gzip

- **File/line:** `middleware/compress.go:260-267` (`matchAcceptEncoding` uses `strings.Contains`)
- **What goes wrong:** With `Accept-Encoding: gzip;q=0, identity`, the response is gzip-encoded. Substring matching also accepts tokens such as `x-gzip-foo`.
- **Observed:** `q0: CE="gzip"`
- **Why it's wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The `SetEncoder` doc points to the MDN Accept-Encoding page, which describes the same semantics.
- **Severity:** low/medium
- **Fix:** Parse each element into token plus params. Compare the token exactly, after trimming and lowercasing. Treat `q=0` as a rejection, and optionally honour `*`.

## 4. Compress: an informational status (1xx, e.g. 103 Early Hints) makes the compression decision too early

- **File/line:** `middleware/compress.go:310-316`
- **What goes wrong:** `WriteHeader(103)` sets `wroteHeader = true` and runs `isCompressible()` before the handler has set the final `Content-Type`. The real `WriteHeader(200)` then goes through the "already wrote" branch, so the final response is never compressed. Compare `wrap_writer.go:84-87`, which handles 1xx separately for exactly this reason.
- **Observed:** `103: CE="" body="hello hello hello"` (text/html, gzip accepted, but not compressed)
- **Severity:** low
- **Fix:** For `100 <= code < 200 && code != 101`, pass the code through without setting `wroteHeader` or deciding compressibility.

## 5. SupressNotFound corrupts the live routing context: mounted routes return 404 and URL params are duplicated

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** It calls `rctx.Routes.Match(rctx, …)` with the request's real routing context. `Mux.Find` mutates that context: it appends URL params and route patterns, and for mounted subrouters it sets `rctx.RoutePath` (`mux.go:397`). When the real router then runs, it uses the altered `RoutePath` and state.
  - A request to a route under `r.Mount("/api", sub)` gets 404 even though `Match` returned true.
  - On ordinary param routes, `URLParams.Keys` has two entries for a single `{a}`.
- **Observed:** `supress /api/5: 404 "404 page not found"`; `supress /x/7: 200 "a=7 n=2"`
- **Why it's wrong:** `mux.go:380-381` says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". `GetHead` (`get_head.go:24`) does this correctly with a temporary context.
- **Severity:** high (valid routes break whenever the middleware is used together with Mount)
- **Fix:** Use `tctx := chi.NewRouteContext(); rctx.Routes.Match(tctx, r.Method, path)`. Also pick the path the way GetHead does (RoutePath, then RawPath, then Path) instead of always using `r.URL.Path`.

## 6. RedirectSlashes inside a mounted subrouter redirects to the wrong URL (the mount prefix is dropped)

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** Inside a subrouter, `rctx.RoutePath` is the path relative to the mount point, and the middleware builds the `Location` from it. `GET /api/users/` on `r.Mount("/api", sub)` with `sub.Use(RedirectSlashes)` redirects to `/users` instead of `/api/users`.
- **Observed:** `redirect mounted: 301 loc="/users"`
- **Why it's wrong:** The doc says it will "redirect to the same path, less the trailing slash". `RoutePath` is a routing-internal suffix, not the request URL. That is fine for `StripSlashes`, which just keeps routing, but not for an external redirect.
- **Severity:** medium
- **Fix:** Always build the redirect target from `r.URL.Path` (or `r.URL.EscapedPath()`). Use `rctx.RoutePath` only to decide whether a trailing slash is present.

## 7. AllowContentEncoding rejects valid comma-separated `Content-Encoding` lists

- **File/line:** `middleware/content_encoding.go:17, 24-28`
- **What goes wrong:** `r.Header["Content-Encoding"]` returns one element per header line. A single line `Content-Encoding: deflate, gzip` is therefore checked as the literal string `"deflate, gzip"`, which is never in the allow-list. The request gets 415 even though every encoding in it is allowed.
- **Observed:** `CE list: status=415` with allow-list `gzip, deflate`
- **Why it's wrong:** Content-Encoding is a list-valued header (RFC 9110 §8.4). The code's own comment says "All encodings in the request must be allowed", which implies checking each coding.
- **Severity:** medium
- **Fix:** Split each header value on `,` and check every trimmed, lowercased token. Skip empty tokens.

## 8. RouteHeaders: patterns aren't lowercased (so mixed-case patterns never match), and the order across headers is random

- **File/line:** `middleware/route_headers.go:48-68` (patterns stored as given), `:86-98` (`range hr` over a map, request value lowercased at `:91`)
- **What goes wrong:**
  - (a) The request header value is lowercased before matching, but `NewPattern(match)` keeps the pattern's case. So `Route("Origin", "https://App.example.com", …)` can never match. Observed: falls through to the default.
  - (b) The handler promises to "find first matching header route". But it loops over a Go map, so when more than one configured header matches, the winner is random per request. Observed over 200 requests: `map[host:169 origin:31]`.
- **Severity:** medium for (b), because routing (e.g. which CORS policy applies) becomes non-deterministic; low for (a)
- **Fix:** Lowercase `match` in `Route`/`RouteAny`. Keep header routes in an ordered slice (insertion order) and iterate that, not the map.

## 9. ContentCharset rejects quoted charset parameters

- **File/line:** `middleware/content_charset.go:35-39`
- **What goes wrong:** `Content-Type: text/plain; charset="utf-8"` with `ContentCharset("utf-8")` returns 415, because the quotes are never stripped.
- **Observed:** `charset quoted: 415`
- **Why it's wrong:** A parameter value can be a token or a quoted-string, and `charset="utf-8"` is equivalent to `charset=utf-8` (RFC 9110 §5.6.6 / §8.3.1).
- **Severity:** low
- **Fix:** Parse with `mime.ParseMediaType` and compare `params["charset"]`. Keep the empty-charset behaviour for a missing header or parameter. As a side issue, the function also lowercases the caller's variadic slice in place (`charsets[i] = …`, line 14), which mutates a slice passed with `...`. Copy it first.

---

## Considered, not reported (not confident enough, or by design)

- `Timeout` writes 504 after the handler returns even if it already wrote a response. This is documented behaviour and only produces a "superfluous WriteHeader" log.
- `RealIP` spoofing is documented as deprecated and vulnerable.
- `Recoverer` compares `Connection` to `"Upgrade"` exactly. It's minor and I didn't test it.
- `Profiler` redirects by appending to `r.RequestURI`, so a query string ends up in the middle of the redirect path. Real, but trivial.
- `PathRewrite` doesn't touch `RawPath`, so on percent-encoded paths chi routes on `RawPath` and ignores the rewrite. I didn't test this.

## Files read

`middleware/`: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go. Context: `mux.go` (Match/Find, around lines 370-410, plus the RoutePath/RawPath handling). Test files were listed but not read.
