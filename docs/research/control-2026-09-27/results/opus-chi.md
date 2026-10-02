# Code review: go-chi/chi `middleware/` @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc

Reviewer: opus (control run). Each defect below marked **[reproduced]** was confirmed with a throwaway Go test (`middleware/zz_review_test.go`) run with Go 1.25.1 in a copy at `/tmp/control-work/opus-chi/chi`. The existing `go test ./middleware/` suite passes at this commit.

---

## 1. SupressNotFound corrupts the live routing context, so every mounted sub-router returns 404 — HIGH [reproduced]

- **File/line:** `middleware/supress_notfound.go:19` (`rctx.Routes.Match(rctx, r.Method, r.URL.Path)`)
- **What goes wrong:** the look-ahead passes the request's own `*chi.Context` into `Mux.Match`. `Mux.Find` (mux.go:382-408) writes to the context it is given. It sets `rctx.RoutePath = mx.nextRoutePath(rctx)` when the match goes through a mounted sub-router, and `FindRoute` (tree.go:396-402) appends to `URLParams` and `RoutePatterns`. After the look-ahead succeeds, the real routing pass then runs with a `RoutePath` that has already been rewritten to the sub-router's path.
  - `r.Use(SupressNotFound(r)); r.Mount("/api", sub)`, where `sub` has `/users/{id}`. `GET /api/users/1` returns **404**, although the route exists.
  - `GET /hello/bob` on a plain route returns 200, but `rctx.URLParams.Keys` is `[name name]`: every parameter is duplicated.
- **Why it's wrong:** the doc comment says the middleware only responds 404 "if the route is not found". `Mux.Find` itself warns: "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". `GetHead` (get_head.go:24) does it correctly with `tctx := chi.NewRouteContext()`.
- **Fix:** match against a fresh context: `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, path)`. Take the path the same way `GetHead` does (`rctx.RoutePath`, then `r.URL.RawPath`, then `r.URL.Path`), because `r.URL.Path` alone ignores RawPath routing.

## 2. Compress: a Flush before the first Write sends a gzip body without `Content-Encoding` — MEDIUM [reproduced]

- **File/line:** `middleware/compress.go:357-371` (Flush), together with `310-336` (WriteHeader) and `338-344` (Write)
- **What goes wrong:** before any `Write` or `WriteHeader`, `cw.compressible` is false. So `Flush()` calls the underlying `ResponseWriter.Flush()`, which commits status 200 and the headers without `Content-Encoding`. The next `Write` calls `cw.WriteHeader(200)`, which decides the response is compressible, sets `Content-Encoding: gzip` in a header map that has already been sent, and switches the body to the gzip writer.
  - A handler that sets `Content-Type: text/html`, calls `Flush()`, then writes gets back a response with **no** `Content-Encoding` header and a raw gzip body (`\x1f\x8b...`). The server also logs "superfluous response.WriteHeader call … compress.go:336".
  - Streaming handlers that flush early (to send headers quickly) produce a corrupt body for clients that send `Accept-Encoding: gzip`.
- **Why it's wrong:** the compression decision must be made before headers are committed. `Flush` bypasses `cw.WriteHeader`, which is the only place that decision is made.
- **Fix:** at the top of `Flush`, do `if !cw.wroteHeader { cw.WriteHeader(http.StatusOK) }`, mirroring `Write`. `Hijack` and `Push` are fine as they are.

## 3. Compress ignores `q=0` in Accept-Encoding and compresses with an encoding the client refused — MEDIUM [reproduced]

- **File/line:** `middleware/compress.go:231-267` (`selectEncoder` / `matchAcceptEncoding`)
- **What goes wrong:** acceptance is decided by `strings.Contains(v, encoding)` on each comma-separated token. The qvalue is never parsed. With `Accept-Encoding: gzip;q=0, identity`, the response is sent as `Content-Encoding: gzip`.
- **Why it's wrong:** RFC 9110 §12.4.2 and §12.5.3 say a qvalue of 0 means "not acceptable". The `Compress` doc says it compresses "based on Accept-Encoding request header". Substring matching also accepts any token that merely contains the name.
- **Fix:** parse each element as `token[;q=value]`, trim and compare the token exactly (case-insensitively), and skip any element whose q is 0. Optionally honour `*`.

## 4. AllowContentEncoding rejects a valid comma-separated Content-Encoding list — MEDIUM [reproduced]

- **File/line:** `middleware/content_encoding.go:17-29`
- **What goes wrong:** each header *line* is compared whole against the allow-list. `Content-Encoding: deflate, gzip` sent as one header line (the normal wire form) is looked up as the string `"deflate, gzip"`, so `AllowContentEncoding("gzip","deflate")` returns **415**.
- **Why it's wrong:** Content-Encoding is a comma-separated list (RFC 9110 §8.4). The test file's own comment lists `Content-Encoding: gzip, deflate` and `deflate, gzip` as supported. The test never exercises that form: it calls `Header.Set` in a loop, so only the last value survives.
- **Fix:** split each header value on `,`, trim each element, lower-case it, and check each element: `for _, v := range r.Header.Values("Content-Encoding") { for _, e := range strings.Split(v, ",") { ... } }`. Ignore empty elements.

## 5. RedirectSlashes redirects to the wrong URL when used inside a sub-router — MEDIUM [reproduced]

- **File/line:** `middleware/strip.go:41-62` (RoutePath chosen at :46)
- **What goes wrong:** the path used to build the `Location` is `rctx.RoutePath` whenever that is set. Inside `r.Route("/api", …)` or `Mount`, `RoutePath` is relative to the mount point. `GET /api/users/` therefore redirects to `Location: /users` instead of `/api/users`, which sends the client to a different resource (usually a 404).
- **Why it's wrong:** the doc says it will "redirect to the same path, less the trailing slash". `RoutePath` is right for re-routing (as in `StripSlashes`) but wrong for a client-facing redirect.
- **Fix:** trigger on `RoutePath` if you like, but build the redirect target from `r.URL.Path`: strip the trailing slash(es) from `r.URL.Path`, then apply the existing backslash and leading-slash normalisation.

## 6. RouteHeaders: the documented `Host` routing never matches on a real server — MEDIUM [reproduced]

- **File/line:** `middleware/route_headers.go:17-18` (doc example) and `:87` (`r.Header.Get(header)`)
- **What goes wrong:** Go's `net/http` server moves the Host header into `r.Host` and deletes it from `r.Header`. `r.Header.Get("host")` is therefore always empty, and the `Route("Host", "example.com", …)` / `Route("Host", "*.example.com", …)` example in the doc comment never fires. Through `httptest.NewServer` with `req.Host = "example.com"`, the route middleware was not hit.
- **Why it's wrong:** the function's own doc comment presents Host-based routing as the primary example.
- **Fix:** special-case the key: `if header == "host" { headerValue = r.Host } else { headerValue = r.Header.Get(header) }`.

## 7. RouteHeaders: patterns are not lower-cased, but header values are — LOW [reproduced]

- **File/line:** `middleware/route_headers.go:91` (`headerValue = strings.ToLower(headerValue)`) vs `:54`/`:66`/`:135-139` (`NewPattern(match)` stores the pattern as given)
- **What goes wrong:** `Route("Origin", "https://App.example.com", mw)` can never match, even when the request carries exactly `Origin: https://App.example.com`, because the value is lower-cased before comparison and the pattern is not.
- **Fix:** lower-case the pattern in `NewPattern` (or in `Route`/`RouteAny`) so both sides are compared the same way.

## 8. RouteHeaders: "first matching route" depends on random map order — LOW

- **File/line:** `middleware/route_headers.go:86` (`for header, matchers := range hr`)
- **What goes wrong:** routes are stored in a `map[string][]HeaderRoute` keyed by header name, and Go randomises map iteration. If routes are registered on two different headers and a request matches both, the middleware chosen changes from request to request.
- **Why it's wrong:** the code comment says "find first matching header route", which implies a deterministic, registration-ordered choice.
- **Fix:** keep an ordered slice of header names (or of `(header, route)` entries) alongside the map, and iterate in registration order.

## 9. Profiler redirects break (and loop) when the request has a query string — LOW [reproduced]

- **File/line:** `middleware/profiler.go:27` and `:30` (`r.RequestURI+"/pprof/"`, `r.RequestURI+"/"`)
- **What goes wrong:** `RequestURI` includes the query string, so the suffix is appended after the query. `GET /debug?x=1` → `Location: /debug?x=1/pprof/`, and `GET /debug/pprof?debug=1` → `Location: /debug/pprof?debug=1/`. Following either redirect hits the same handler again, giving an endless 301 loop.
- **Fix:** build the target from `r.URL.Path` and re-append `r.URL.RawQuery` if it is non-empty, e.g. `u := *r.URL; u.Path += "/pprof/"; http.Redirect(w, r, u.RequestURI(), 301)`.

## 10. ContentCharset rejects a quoted charset parameter — LOW

- **File/line:** `middleware/content_charset.go:35-40` (`contentEncoding`)
- **What goes wrong:** `Content-Type: text/plain; charset="utf-8"` is valid (RFC 9110 §5.6.6: parameter values may be a quoted-string). The parser extracts `"utf-8"` with the quotes still on, so `ContentCharset("utf-8")` answers 415.
- **Fix:** use `mime.ParseMediaType` and read `params["charset"]`. This also handles parameter order and whitespace properly.

## 11. Recoverer's WebSocket/upgrade check misses list-valued `Connection` headers — LOW

- **File/line:** `middleware/recoverer.go:39` (`if r.Header.Get("Connection") != "Upgrade"`)
- **What goes wrong:** the check is an exact, case-sensitive comparison. `Connection` is a comma-separated, case-insensitive token list: Firefox sends `Connection: keep-alive, Upgrade`, and some clients send `upgrade`. For those clients, a panic after the connection has been hijacked still calls `w.WriteHeader(500)` on the hijacked connection, which the comment's own guard was meant to prevent. The result is an "http: response.WriteHeader on hijacked connection" error log instead of a clean recovery.
- **Fix:** check whether any comma-separated token equals `upgrade` case-insensitively, e.g. using `httpguts.HeaderValuesContainsToken(r.Header["Connection"], "upgrade")` or an equivalent local helper.

## 12. Sunset middleware emits `Deprecation` in a non-standard format — LOW

- **File/line:** `middleware/sunset.go:16`
- **What goes wrong:** `Deprecation` is written as an IMF-fixdate (`http.TimeFormat`). The standardised Deprecation header (RFC 9745) is a Structured Field Date, `Deprecation: @1688169599`. Conforming parsers reject or ignore the HTTP-date form. (`Sunset` correctly uses HTTP-date per RFC 8594.)
- **Fix:** `w.Header().Set("Deprecation", "@"+strconv.FormatInt(sunsetAt.Unix(), 10))`.

---

## Checked and not reported

- `client_ip.go` (walkXFF, trusted-proxy counting, v4-mapped and zone handling)
- `throttle.go` (token accounting)
- `wrap_writer.go` (1xx handling, ReaderFrom tee/discard path)
- `request_id.go`, `get_head.go`, `clean_path.go`, `url_format.go`, `content_type.go`, `nocache.go`, `logger.go`, `timeout.go`, `request_size.go`

Nothing in these rose to "confident defect". Two minor points are left out on purpose:

- `Timeout` issues a superfluous `WriteHeader(504)` after a handler has already written; this only produces log noise.
- `realip.go` is already deprecated for its known spoofing issues.

## Files read

middleware/: basic_auth.go, clean_path.go, client_ip.go, client_ip_test.go (partial), compress.go, content_charset.go, content_encoding.go, content_encoding_test.go (partial), content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go.

Outside scope, for context: mux.go (`Match`/`Find`), context.go (`Reset`), tree.go (`FindRoute`), go.mod.
