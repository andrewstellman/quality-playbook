# Code review: chi `middleware/` (commit 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc)

Reviewer: opus, run07. Method: read every non-test source file in `middleware/`, plus `mux.go` (Match/Find) for context. I checked each suspicion with a throwaway Go test file in a copy of the checkout (Go 1.25.1). The observed output is quoted under each finding. The work directory has since been deleted.

---

## D1. SupressNotFound corrupts the live routing context. Mounted sub-router routes return 404, and URL params get duplicated
- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` with the **live** request routing context. `Mux.Find` (mux.go:380-398) says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". It appends URL params, sets `routePattern`, and for mounted sub-routers it sets `rctx.RoutePath` to the sub-path. Routing then runs with that polluted state:
  - `r.Use(SupressNotFound(r)); r.Mount("/api", sub); sub.Get("/users/{id}", ...)`, then `GET /api/users/5` gives **404**. The top-level mux sees `RoutePath="/users/5"` and routes that path.
  - `r.Get("/x/{id}", ...)`, then `GET /x/7` gives `URLParams.Keys = [id id]`. The param is duplicated.
- **Why it's wrong:** The doc says the middleware only short-circuits "if the route is not found". Here it breaks routes that exist. `GetHead` in the same package does this correctly with a temporary context (`tctx := chi.NewRouteContext()`, get_head.go:24).
- **Also:** it uses `r.URL.Path` rather than `RawPath`/`RoutePath`, which is inconsistent with how the mux routes (mux.go:460-463).
- **Severity:** high. Valid routes under `Mount` become unreachable.
- **Fix:** `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, routePath)`. Compute `routePath` the way GetHead does.

## D2. Compress ignores `q=0` and does substring matching on Accept-Encoding
- **File/line:** `middleware/compress.go:235, 260-267` (`matchAcceptEncoding`)
- **What goes wrong:** `strings.Contains(v, encoding)` on each comma-separated element. `Accept-Encoding: gzip;q=0, identity` still selects gzip. Observed: `Content-Encoding: gzip`. Any token that merely contains the name also matches.
- **Why it's wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The server sends an encoding the client explicitly refused.
- **Severity:** medium.
- **Fix:** Parse each element into a coding token and a q parameter. Compare the token exactly (case-insensitive). Skip entries with `q=0`. Ideally also honour `*` and pick by q-value.

## D3. Compress writes a gzip body without `Content-Encoding` when the handler calls Flush before writing
- **File/line:** `middleware/compress.go:357-371` (Flush), together with `310-344`
- **What goes wrong:** Before any Write or WriteHeader, `cw.compressible` is false, so `Flush()` flushes the underlying ResponseWriter. That commits a 200 header with no `Content-Encoding`. The next `Write` still runs `cw.WriteHeader`, which now decides the response is compressible and sends gzip bytes. The header change is too late. Observed: response `Content-Encoding=""` with a body starting `\x1f\x8b` (gzip magic), plus "superfluous response.WriteHeader" logged from compress.go:336.
- **Why it's wrong:** The client receives a compressed body labelled as identity, so the response is corrupted. This is a common pattern in streaming handlers: set Content-Type, flush early, then stream.
- **Severity:** medium.
- **Fix:** In `Flush()`, call `cw.WriteHeader(http.StatusOK)` if `!cw.wroteHeader`, so compressibility is decided and headers are set before anything is flushed.

## D4. A failing EncoderFunc (nil return) still advertises `Content-Encoding` and sends the body uncompressed
- **File/line:** `middleware/compress.go:209-221, 249-250, 328-330`
- **What goes wrong:** `EncoderFunc` is documented as "In case of failure, the function should return nil" (line 272). The built-in `encoderGzip` and `encoderDeflate` do return nil on an invalid level. `selectEncoder` still returns `encoding="gzip"` with a nil writer. `Handler` then leaves `cw.w = w`, and `WriteHeader` sets `Content-Encoding: gzip` because `cw.encoding != ""`. With `Compress(42)`, observed: `Content-Encoding="gzip"` and body `"hello hello hello"` (plain text).
- **Why it's wrong:** The documented failure signal is not handled. The client gets a body labelled gzip that is not gzip.
- **Severity:** medium. A misconfigured level silently corrupts every compressible response rather than failing loudly.
- **Fix:** In `selectEncoder`, when `fn(w, level)` returns nil, skip to the next encoding (or return `nil, ""`). Alternatively, validate the level in `NewCompressor`/`SetEncoder` and panic, since it already probes `fn(io.Discard, c.level)`.

## D5. Compress sets `Content-Encoding` on bodiless responses (304/204/HEAD)
- **File/line:** `middleware/compress.go:310-336`
- **What goes wrong:** `WriteHeader` never checks the status code. A handler that returns `304 Not Modified` with a compressible Content-Type gets `Content-Encoding: gzip`, observed. `Close()` then also tries to write the gzip header and trailer to a response that allows no body. That write fails and the error is ignored.
- **Why it's wrong:** On a 304, headers describe the selected representation. Sending `Content-Encoding: gzip` when the cached representation may be identity can mislabel it for caches. There is no body to encode.
- **Severity:** low.
- **Fix:** Skip compression for `code < 200`, `204`, `304`, and HEAD requests.

## D6. Compress content-type matching is case- and whitespace-sensitive
- **File/line:** `middleware/compress.go:296-307`; also `88` (user types stored verbatim)
- **What goes wrong:** `Content-Type: Text/HTML; charset=utf-8` or `text/html ; charset=utf-8` (space before `;`) yields `"Text/HTML"` / `"text/html "`, which isn't found in the allow-list, so the response isn't compressed. The same happens if the caller passes `"Text/HTML"` to `NewCompressor`.
- **Why it's wrong:** RFC 9110 §8.3.1 says type and subtype are case-insensitive. The sibling `AllowContentType` does lowercase and trim (content_type.go:35).
- **Severity:** low.
- **Fix:** `strings.ToLower(strings.TrimSpace(...))` both the header value and the configured types.

## D7. RedirectSlashes redirects to the wrong URL inside a mounted sub-router, and un-escapes the path
- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:**
  1. Inside a sub-router mounted at `/api`, `rctx.RoutePath` is relative to the mount. `GET /api/users/` redirects to `Location: /users`, dropping `/api`. Observed.
  2. The path comes from the decoded `r.URL.Path`/RoutePath and is placed into `Location` without re-escaping. `GET /a%3Fb/` gives `Location: /a?b`. Observed. The encoded `?` becomes a query delimiter, which changes the target resource.
- **Why it's wrong:** The doc says it should "redirect to the same path, less the trailing slash". Neither result is the same path.
- **Severity:** medium.
- **Fix:** Build the redirect from `r.URL` (the full request path, using `EscapedPath()`), trimming the trailing slash there. Do not build it from the mount-relative RoutePath.

## D8. AllowContentEncoding rejects allowed encodings sent as a comma-separated list
- **File/line:** `middleware/content_encoding.go:17, 24-28`
- **What goes wrong:** Each `r.Header["Content-Encoding"]` element is looked up as a whole. `Content-Encoding: deflate, gzip` with both allowed returns **415**. Observed.
- **Why it's wrong:** Content-Encoding is a list header (RFC 9110 §8.4: `#content-coding`). The code's own comment says "All encodings in the request must be allowed", implying each coding is checked.
- **Severity:** low-medium.
- **Fix:** Split each header value on `,` and trim/lowercase each token before the lookup.

## D9. ContentCharset rejects quoted charset values and mutates the caller's slice
- **File/line:** `middleware/content_charset.go:13-15, 35-40`
- **What goes wrong:**
  1. `Content-Type: text/plain; charset="utf-8"` with `ContentCharset("utf-8")` returns 415. Observed. The parsed value is `"utf-8"` including the quotes.
  2. The loop `charsets[i] = strings.ToLower(c)` writes into the variadic backing array. A caller doing `ContentCharset(myList...)` has `myList` lowercased in place. Observed: `[UTF-8]` becomes `[utf-8]`.
- **Also:** matching on the substring `charset=` means a parameter such as `x-charset=utf-8` is accepted as the charset.
- **Why it's wrong:** RFC 9110 §5.6.6/§8.3.1 says parameter values may be a token or a quoted-string, and the two forms are equivalent. Silently mutating an argument is an API-contract bug.
- **Severity:** low.
- **Fix:** Parse with `mime.ParseMediaType` and compare `params["charset"]`. Copy `charsets` into a new slice before lowercasing.

## D10. RouteHeaders: patterns aren't lowercased, and "first matching" is non-deterministic across headers
- **File/line:** `middleware/route_headers.go:48-56, 58-70, 86-98`
- **What goes wrong:**
  1. The header value is lowercased (line 91) but the pattern from `NewPattern(match)` is not. `Route("Origin", "https://App.example.com", mw)` can never match, even for an identical header value. Observed: `hit: false`.
  2. The routes are stored in a Go map, and `Handler` iterates it with `range hr`. When routes exist for more than one header and a request matches several, the middleware chosen is random per request, even though the comment says "find first matching header route".
- **Severity:** low-medium. Point 2 can nondeterministically pick, for example, a credentialed CORS handler versus a public one.
- **Fix:** Lowercase `match` in `Route`/`RouteAny`. Keep an ordered slice of (header, route) in insertion order and iterate that.

## D11. Sunset: `Deprecation` header uses the wrong format
- **File/line:** `middleware/sunset.go:16`
- **What goes wrong:** It emits `Deprecation: <IMF-fixdate>`. RFC 9745 (the Deprecation HTTP header field) defines it as a Structured Field Date, e.g. `Deprecation: @1688169599`. Conforming parsers reject the HTTP-date form. `Sunset` (RFC 8594) correctly uses HTTP-date.
- **Severity:** low.
- **Fix:** `w.Header().Set("Deprecation", "@"+strconv.FormatInt(sunsetAt.Unix(), 10))`.

---

## Considered and not reported
- **Timeout:** after the deadline it calls `WriteHeader(504)` even if the handler already wrote. This produces a "superfluous" log line (observed) but no wrong status. The doc already requires handlers to cooperate.
- **URLFormat:** it would panic on a path with no `/` and a dot (`path[base:]` with base -1). Such paths can't reach it through normal server routing.
- **PathRewrite and StripSlashes:** they change `URL.Path` without `RawPath` (the no-rctx branch). This is an edge case with encoded paths; I didn't verify impact through chi routing.
- **ClientIP\*:** I checked it carefully. The walk logic, fail-closed handling, v4-mapped folding and zone stripping match their docs.
- **wrap_writer:** Status 0 when nothing was written matches the interface doc. `http2FancyWriter` lacks the ReadFrom its comment mentions. This is doc-only.

## Files read
- middleware/basic_auth.go
- middleware/clean_path.go
- middleware/client_ip.go
- middleware/compress.go
- middleware/content_charset.go
- middleware/content_encoding.go
- middleware/content_type.go
- middleware/get_head.go
- middleware/heartbeat.go
- middleware/logger.go
- middleware/maybe.go
- middleware/middleware.go
- middleware/nocache.go
- middleware/page_route.go
- middleware/path_rewrite.go
- middleware/profiler.go
- middleware/realip.go
- middleware/recoverer.go
- middleware/request_id.go
- middleware/request_size.go
- middleware/route_headers.go
- middleware/strip.go
- middleware/sunset.go
- middleware/supress_notfound.go
- middleware/terminal.go
- middleware/throttle.go
- middleware/timeout.go
- middleware/url_format.go
- middleware/value.go
- middleware/wrap_writer.go
- mux.go (Match/Find and routing path selection, for context)
- go.mod

The existing `middleware` test suite passes at this commit (`go test ./middleware/`: ok). The probes were in a temporary `zz_probe_test.go` in the work copy only.
