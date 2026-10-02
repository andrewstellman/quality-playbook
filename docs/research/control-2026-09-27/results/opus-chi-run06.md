# chi `middleware/` code review — opus-chi-run06

Repo: go-chi/chi at 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc, scope `middleware/`.

Method: read every non-test source file in `middleware/`, plus the relevant parts of `mux.go` and `tree.go`. Every defect below was reproduced with a throwaway test (`zz_probe_test.go`) in a copy of the checkout. The existing test suite passes (`go test ./middleware/`).

---

## 1. SupressNotFound corrupts the live routing context and 404s every mounted or sub-routed path

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` using the request's **live** route context. `Mux.Find` (mux.go:377-408) mutates that context:
  - it sets `rctx.RoutePath = mx.nextRoutePath(rctx)` when it descends into a subrouter;
  - `FindRoute` (tree.go:396-402) appends to `URLParams` and `RoutePatterns`.
  
  Real routing then runs against this polluted context.
- **Reproduced:**
  - `r.Use(SupressNotFound(r)); r.Route("/api", …Get("/users/{id}"))`: `GET /api/users/7` returns **404**. The top-level mux routes the leftover `RoutePath` `/users/7`.
  - On a plain route `/x/{id}`, `RoutePattern()` returns `/x/{id}/x/{id}` and `URLParams.Keys` is `[id id]`.
- **Why it's wrong:**
  - The doc says it only answers 404 "if the route is not found"; here the route exists.
  - `Mux.Find`'s own comment says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()".
  - `GetHead` (get_head.go:24) does the right thing and uses a temporary `chi.NewRouteContext()`.
- **Severity:** high. The middleware breaks every mounted subrouter and corrupts the route patterns that loggers and metrics use.
- **Fix:** `match := rctx.Routes.Match(chi.NewRouteContext(), r.Method, path)`. Take `path` from `RoutePath`, falling back to `RawPath` and then `Path`, the same way `GetHead` does.

## 2. Compress sends `Content-Encoding: gzip` over an uncompressed body when the encoder can't be built (e.g. an invalid level)

- **File/line:** `middleware/compress.go:219-221` (Handler), `249-250` (selectEncoder), `328-331` (WriteHeader)
- **What goes wrong:**
  - `EncoderFunc` is documented to return nil on failure (compress.go:271-272), and `encoderGzip` and `encoderDeflate` do so for an out-of-range level.
  - `selectEncoder` still returns `name` ("gzip").
  - `Handler` only skips assigning `cw.w` when `encoder == nil`, and leaves `cw.encoding = "gzip"`.
  - `WriteHeader` then sets `Content-Encoding: gzip` while `cw.w` is the raw ResponseWriter.
- **Reproduced:** with `Compress(42)` and `Accept-Encoding: gzip`, the response has `Content-Encoding="gzip"` and body `"hello world"` in plaintext. Clients fail to decode it.
- **Severity:** medium. The trigger is a misconfigured level, but the result is corrupt responses with no error raised.
- **Fix:**
  - In `selectEncoder`, if `fn(w, c.level)` returns nil, skip to the next encoder (or return `nil, ""`).
  - In `Handler`, clear `encoding` when `encoder == nil`.
  - Better still, validate the level in `NewCompressor` and panic there.

## 3. Compress ignores `q=0` in Accept-Encoding and does substring matching

- **File/line:** `middleware/compress.go:235`, `260-267` (`matchAcceptEncoding`)
- **What goes wrong:** The match is `strings.Contains(v, encoding)` on each comma-separated token, so it ignores quality values. `Accept-Encoding: gzip;q=0, identity` still gets `Content-Encoding: gzip` (reproduced).
- **Why it's wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". Substring matching can also match unrelated tokens that contain the encoding name.
- **Severity:** medium. The client explicitly refused gzip and receives it anyway.
- **Fix:**
  - Parse each element into a token and parameters, trim it, and compare the token exactly (case-insensitive).
  - Treat `q=0` as a refusal, and handle `*`.

## 4. Compress: calling Flush before the first Write sends compressed bytes without a Content-Encoding header

- **File/line:** `middleware/compress.go:357-371` (Flush), `338-344`, `310-336`
- **What goes wrong:**
  - `Flush()` does not ensure `WriteHeader` has run. Before the first write, `cw.compressible` is false, so `writer()` is the raw ResponseWriter, and its `Flush()` commits a 200 with no `Content-Encoding`.
  - The next `Write` calls `cw.WriteHeader(200)`, which now decides the type is compressible. It sets `Content-Encoding` on an already-sent header map and switches to the gzip writer.
- **Reproduced:** a handler sets `Content-Type: text/html`, calls `Flush()`, then writes. The real HTTP response has `Content-Encoding=""` but the body starts with `\x1f\x8b` (gzip). The server also logs "superfluous response.WriteHeader call … compress.go:336".
- **Severity:** medium. Flushing first is a normal streaming pattern, and it produces a corrupt response.
- **Fix:** at the top of `Flush()`, run `if !cw.wroteHeader { cw.WriteHeader(http.StatusOK) }`. The encoding decision is then made before anything is committed.

## 5. StripSlashes routes on the decoded `Path` and ignores `RawPath`, so escaped paths 404 once a trailing slash is stripped

- **File/line:** `middleware/strip.go:16-29`
- **What goes wrong:**
  - When `rctx.RoutePath` is empty, the new route path is built from `r.URL.Path` (decoded).
  - chi's mux routes on `RawPath` when it is set, and `CleanPath` and `GetHead` both honour `RawPath`.
  - So StripSlashes turns `/files/a%2Fb/` into RoutePath `/files/a/b`, which changes the segment structure.
- **Reproduced:** `/files/a%2Fb` returns 200 `name=a%2Fb`, but `/files/a%2Fb/` returns **404**.
- **Why it's wrong:** the doc says it will "strip [the trailing slash] from the path and continue routing". Stripping must not change how the rest of the path is routed.
- **Severity:** low-medium.
- **Fix:** use `r.URL.RawPath` when it is non-empty (same fallback as `CleanPath`/`GetHead`).

## 6. RedirectSlashes builds Location from the decoded path, and from the sub-path when mounted

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:**
  - **(a) Decoded path.** The redirect target comes from the decoded `r.URL.Path` and is not re-escaped:
    - `/a%3Fb/` redirects to `Location: /a?b`, which turns part of the path into a query string;
    - `/a%2Fb/` redirects to `/a/b`, which changes the segments.
  - **(b) Mounted subrouter.** Inside a subrouter, `rctx.RoutePath` is the path relative to the mount point. `r.Route("/api", …Use(RedirectSlashes)…)` with `GET /api/users/` redirects to `Location: /users`, which drops `/api` (reproduced).
- **Why it's wrong:** the doc says it redirects "to the same path, less the trailing slash". Both cases redirect to a different resource.
- **Severity:** medium. Both are reproducible, and the redirect is a 301, which clients cache permanently.
- **Fix:**
  - Build the target from `r.URL.EscapedPath()` (after the existing backslash and leading-slash normalisation).
  - Always use the full request path for the Location header, never `rctx.RoutePath`. Use `RoutePath` only to decide whether a trailing slash is present.

## 7. RouteHeaders: patterns aren't lowercased, but header values are, so any uppercase pattern never matches

- **File/line:** `middleware/route_headers.go:54`, `66` (`NewPattern(match)`), vs `91` (`headerValue = strings.ToLower(headerValue)`)
- **What goes wrong:** Header values are lowercased before matching, but the match patterns are stored as given. `Route("Origin", "https://App.example.com", mw)` never fires, even for the exact header value `https://App.example.com` (reproduced: no hit).
- **Severity:** low.
- **Fix:** lowercase `match` in `Route` and `RouteAny`, or inside `NewPattern`.

## 8. RouteHeaders: "first matching header route" depends on random map iteration order

- **File/line:** `middleware/route_headers.go:85-98`
- **What goes wrong:** `HeaderRouter` is a `map[string][]HeaderRoute`, and `Handler` ranges over it. When routes on more than one header can match, the chosen middleware is random per request.
- **Reproduced:** 200 identical requests carrying Origin, X-A and X-B split 151/26/23 between the three routes.
- **Why it's wrong:** the code comment says "find first matching header route". Routing must be deterministic, and in the CORS example in the doc this picks different CORS policies at random.
- **Severity:** medium when more than one header is routed; otherwise none.
- **Fix:** record registration order (a slice of `{header, route}`) and iterate over that.

## 9. AllowContentEncoding rejects valid comma-separated Content-Encoding lists

- **File/line:** `middleware/content_encoding.go:17`, `24-29`
- **What goes wrong:** `r.Header["Content-Encoding"]` returns raw field lines, and each line is compared whole. `Content-Encoding: deflate, gzip`, with both encodings allowed, returns **415** (reproduced).
- **Why it's wrong:** Content-Encoding is a list-valued header (RFC 9110 §8.4). The code's own comment says "All encodings in the request must be allowed", but it never splits a line into its individual encodings.
- **Severity:** low.
- **Fix:** split each header line on `,`, trim each element, and check every element.

## 10. URLFormat panics on a path with a dot but no slash

- **File/line:** `middleware/url_format.go:58-60`
- **What goes wrong:**
  - The guard is `strings.Index(path, ".") > 0`. If `path` contains no `/`, `base` is -1 and `path[base:]` panics with "slice bounds out of range [-1:]" (reproduced with `URL.Path = "a.json"`).
  - This is reachable without a chi route context. For example, after `middleware.StripPrefix("/v1")` (a thin wrapper over `http.StripPrefix`), a request for `/v1x.json` becomes `x.json`.
- **Severity:** low. The panic is per-request and Recoverer catches it, but it is still a crash on client input.
- **Fix:** `base := strings.LastIndex(path, "/"); if base < 0 { base = 0 }`, or equivalently search `path[base+1:]` and adjust the index.

---

## Checked and not reported

These were considered and left out, either as intended behaviour or as not confident enough:

- Timeout writing a 504 after the handler has already written.
- Logger logging status 0 when the handler never writes.
- Recoverer's exact-match `Connection: Upgrade` check.
- Throttle's Retry-After truncation.
- ClientIPFromHeader rejecting a comma-joined single header line (fails closed, consistent with the docs).
- Missing `Vary` header on uncompressed responses of compressible types.
- ContentCharset mutating the caller's `charsets` slice.

## Files read

- `middleware/`:
  - `basic_auth.go`
  - `clean_path.go`
  - `client_ip.go`
  - `compress.go`
  - `content_charset.go`
  - `content_encoding.go`
  - `content_type.go`
  - `get_head.go`
  - `heartbeat.go`
  - `logger.go`
  - `maybe.go`
  - `middleware.go`
  - `nocache.go`
  - `page_route.go`
  - `path_rewrite.go`
  - `profiler.go`
  - `realip.go`
  - `recoverer.go`
  - `request_id.go`
  - `request_size.go`
  - `route_headers.go`
  - `strip.go`
  - `sunset.go`
  - `supress_notfound.go`
  - `terminal.go`
  - `throttle.go`
  - `timeout.go`
  - `url_format.go`
  - `value.go`
  - `wrap_writer.go`
- `mux.go`: `Match`/`Find`, lines ~373-408
- `tree.go`: `FindRoute`, lines ~383-406
- `go.mod`
- Test files: only grepped for coverage; not read in full.
