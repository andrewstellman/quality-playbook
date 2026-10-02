# chi `middleware/` code review — opus-chi-run02

Checkout: `/tmp/control/chi` @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc. Scope: `middleware/`.

I checked each defect below with a small throwaway Go test (`zz_review_test.go`, run in a copy under `/tmp/control-work/opus-chi-run02/chi`, then deleted). The observed output is quoted for each one.

---

## 1. SupressNotFound corrupts the live routing context and sends mounted-subrouter requests to the wrong handler

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` on the request's real routing context. `Mux.Find` (mux.go:380-398) changes that context. For a mounted subrouter it sets `rctx.RoutePath = mx.nextRoutePath(rctx)`, which is the path left over after the mount prefix. `FindRoute` (tree.go:396-402) also appends to `URLParams` and `RoutePatterns`. The real routing then runs on the changed context.
  - Router with `r.Get("/users", root)` and `r.Mount("/api", sub)` where `sub.Get("/users", api)`:
    - `GET /api/users` returns **200 "root-users"**, so the root handler serves it instead of the subrouter's handler.
    - `GET /api/items/5` returns **404**, even though `sub` defines `/items/{id}`.
  - Without a mount, `GET /items/5` ends up with `URLParams.Keys = [id id]` and `RoutePatterns = [/items/{id} /items/{id}]`, so both are duplicated.
- **Why it is wrong:**
  - The doc comment says the middleware only short-circuits requests that "are not going to match any routes anyway". Matched requests should be routed normally.
  - `Mux.Find` itself warns: "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()".
  - The sibling `GetHead` (get_head.go:24) does exactly that with a temporary `tctx`.
  - Sending a request to a different handler can skip the subrouter's middlewares, such as auth.
- **Severity:** high
- **Fix:** Match against a fresh context: `tctx := chi.NewRouteContext(); if !rctx.Routes.Match(tctx, r.Method, r.URL.Path) { ... }`.

## 2. Compress sends gzip bytes without `Content-Encoding` if the handler flushes before its first write

- **File/line:** `middleware/compress.go:357-371` (Flush), plus `310-336`
- **What goes wrong:** Scenario: a handler sets `Content-Type: text/html`, calls `Flush()`, then writes.
  - `Flush()` runs before `WriteHeader`. At that point `compressible` is false, so `writer()` is the underlying ResponseWriter, and flushing it commits a 200 with no `Content-Encoding`.
  - The next `Write` sees `wroteHeader == false`, so it runs `WriteHeader`. That sets `Content-Encoding: gzip` on headers that were already sent (the change is lost) and sets `compressible = true`.
  - The body is then gzip-compressed. Observed over a real server: `CE="" body="\x1f\x8b\b..."`, plus the log line "superfluous response.WriteHeader call from ...compressResponseWriter.WriteHeader".
- **Why it is wrong:** The client receives a compressed body that the headers don't declare, so the response is corrupt. Flushing early to send headers is a normal streaming pattern.
- **Severity:** medium
- **Fix:** In `Flush`, call `cw.WriteHeader(http.StatusOK)` first if `!cw.wroteHeader`, so the compression decision is made before anything is committed. Same idea as `basicWriter.flush` calling `maybeWriteHeader`.

## 3. Compress declares `Content-Encoding` when the encoder could not be created, so the body is sent uncompressed with a gzip header

- **File/line:** `middleware/compress.go:249-250` (selectEncoder), `219-221`, `328-331`
- **What goes wrong:**
  - `EncoderFunc` is documented as "In case of failure, the function should return nil". `encoderGzip` and `encoderDeflate` do return nil for an invalid level, e.g. `Compress(42)`.
  - `selectEncoder` still returns `name` ("gzip") with a nil writer. `Handler` leaves `cw.w = w`, and `WriteHeader` sets `Content-Encoding: gzip` because `cw.encoding != ""`.
  - Observed: `CE="gzip" body="hello"`; `gzip.NewReader` on the body fails with `unexpected EOF`.
- **Why it is wrong:** The code ignores the nil-on-failure contract it documents itself. The response claims gzip but contains plain bytes.
- **Severity:** medium (needs a bad level or a failing custom encoder, but the corruption is silent)
- **Fix:** In `selectEncoder`, if `fn(w, c.level)` returns nil, `continue` to the next encoding, or return `nil, "", func(){}`. Optionally also validate `level` in `NewCompressor`.

## 4. Compress ignores `q=0` in Accept-Encoding and matches by substring

- **File/line:** `middleware/compress.go:260-267` (`matchAcceptEncoding`)
- **What goes wrong:** The check is `strings.Contains(v, encoding)`.
  - `Accept-Encoding: gzip;q=0, deflate;q=0` still gets `Content-Encoding: gzip` (observed).
  - Any token that merely contains the name, such as `x-gzip-foo`, also matches.
- **Why it is wrong:** RFC 9110 §12.5.3 / §12.4.2: a qvalue of 0 means "not acceptable". The Compress doc says it compresses "based on Accept-Encoding request header".
- **Severity:** low–medium
- **Fix:** Parse each element: token = trimmed text before `;`, compare it to the encoding for equality, and skip entries whose `q` parameter is 0. Ideally also honour `*` and pick the highest q.

## 5. AllowContentEncoding rejects a valid comma-separated Content-Encoding list

- **File/line:** `middleware/content_encoding.go:17, 24-28`
- **What goes wrong:** `r.Header["Content-Encoding"]` holds raw field values. A request with one header line `Content-Encoding: gzip, deflate` gives the single element `"gzip, deflate"`, which is looked up as one key. With `AllowContentEncoding("gzip","deflate")` it returns **415** (observed).
- **Why it is wrong:**
  - Content-Encoding is a comma-separated list (RFC 9110 §8.4), and that one-line form is the normal way to send it.
  - The test file header (`content_encoding_test.go:15-19`) lists "Content-Encoding: gzip, deflate" as supported.
  - The test never exercises it: it uses `r.Header.Set` in a loop, so only the last value survives.
- **Severity:** medium
- **Fix:** Split each header value on `,` and trim each token before the lookup.

## 6. RedirectSlashes redirects to the wrong URL when used inside a mounted subrouter

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** Inside a subrouter, `rctx.RoutePath` is the path relative to the mount point, and the redirect target is built from it.
  - Setup: `sub.Use(RedirectSlashes); sub.Get("/users",...)`; `r.Mount("/api", sub)`.
  - `GET /api/users/` → `301 Location: /users` (observed). The `/api` prefix is lost, so the client goes to a different or non-existent resource.
- **Why it is wrong:** The doc says it redirects "to the same path, less the trailing slash". `RoutePath` is right to use for StripSlashes, which re-routes internally, but not for an external redirect.
- **Severity:** medium
- **Fix:** Build the redirect from `r.URL.Path` (keeping the existing backslash and leading-slash sanitising). Use `rctx.RoutePath` only to decide whether a trailing slash is present.

## 7. RouteHeaders: patterns containing uppercase letters never match

- **File/line:** `middleware/route_headers.go:54, 66` vs `91`
- **What goes wrong:** Header values are lowercased before matching (line 91), but patterns are stored as given (`NewPattern(match)`). `Route("Origin", "https://App.Example.com", mw)` never fires, even for an identical header value (observed `hit=false`).
- **Why it is wrong:** The code clearly intends case-insensitive matching, since it lowercases the header name and value. Only one side of the comparison is normalised.
- **Severity:** low
- **Fix:** `NewPattern(strings.ToLower(match))` in `Route` and `RouteAny`.

## 8. RouteHeaders: which route wins across different headers is nondeterministic

- **File/line:** `middleware/route_headers.go:85-98`
- **What goes wrong:** Routes are stored in a `map[string][]HeaderRoute` and iterated with `range`. Go randomises map order. If routes exist for two headers (e.g. `Host` and `Origin`) and a request matches both, a different middleware can run on each request.
- **Why it is wrong:** The code comment says "find first matching header route", which implies a defined order. Registration order is lost.
- **Severity:** low
- **Fix:** Keep an ordered slice of header names (or of routes) in registration order and iterate that.

## 9. Profiler redirects are wrong when the request has a query string

- **File/line:** `middleware/profiler.go:27, 30`
- **What goes wrong:** The redirect target is `r.RequestURI + "/pprof/"` or `r.RequestURI + "/"`, and `RequestURI` includes the query. `GET /debug/pprof?x=1` → `Location: /debug/pprof?x=1/` (observed). The path is never fixed, and the query value is corrupted.
- **Severity:** low
- **Fix:** Append to `r.URL.Path` (i.e. the escaped path) and re-attach `r.URL.RawQuery`.

## 10. ContentCharset rejects quoted charset values and mutates the caller's slice

- **File/line:** `middleware/content_charset.go:13-15, 35-39`
- **What goes wrong:**
  - (a) `Content-Type: text/plain; charset="utf-8"` with `ContentCharset("utf-8")` gets **415** (observed), because the quotes are kept in the comparison. RFC 9110 §5.6.6 lets parameter values be quoted strings, and §8.3.2 says `charset="utf-8"` is equivalent to `charset=utf-8`.
  - (b) The loop `charsets[i] = strings.ToLower(c)` writes into the variadic slice. When the caller passes `cs...`, their slice is modified (observed `[UTF-8]` → `[utf-8]`).
- **Severity:** low
- **Fix:**
  - (a) Strip surrounding quotes from the parsed value, or use `mime.ParseMediaType` and read `params["charset"]`.
  - (b) Lowercase into a newly allocated slice.

## 11. URLFormat treats a dotfile name as a format extension

- **File/line:** `middleware/url_format.go:58-69`
- **What goes wrong:** For `/files/.htaccess`, `idx` is 1 within the last segment, so `format = "htaccess"` and the route path is rewritten to `/files/` (observed: format `htaccess`, wildcard param `files/`). The requested resource name disappears from routing.
- **Why it is wrong:** The doc says it "parses the url extension from a request path". A leading-dot name has no extension. `idx > 0` is meant to exclude that case, but `idx` is measured from the `/`, so it is always at least 1.
- **Severity:** low
- **Fix:** Require `idx > 1` (the dot is not the first character after the slash), i.e. `if idx > 1`.

---

## Reviewed with no confident defects found

- `basic_auth.go`, `clean_path.go`, `client_ip.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`, `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`, `realip.go` (deprecated; spoofing is documented), `recoverer.go`, `request_id.go`, `request_size.go`, `sunset.go`, `terminal.go`, `throttle.go`, `timeout.go`, `value.go`, `wrap_writer.go`.

## Files actually read

**`middleware/`, all non-test sources:**
- `basic_auth.go`, `clean_path.go`, `client_ip.go`, `compress.go`, `content_charset.go`
- `content_encoding.go`, `content_type.go`, `get_head.go`, `heartbeat.go`, `logger.go`
- `maybe.go`, `middleware.go`, `nocache.go`, `page_route.go`, `path_rewrite.go`
- `profiler.go`, `realip.go`, `recoverer.go`, `request_id.go`, `request_size.go`
- `route_headers.go`, `strip.go`, `sunset.go`, `supress_notfound.go`, `terminal.go`
- `throttle.go`, `timeout.go`, `url_format.go`, `value.go`, `wrap_writer.go`

**Tests:** `middleware/content_encoding_test.go`, plus grep-level looks at `strip_test.go`, `route_headers_test.go`, `compress_test.go`

**Outside the scope, for context:** `mux.go` (Match/Find), `tree.go` (FindRoute), `context.go` (NewRouteContext/Reset), `go.mod`
