# chi `middleware/` code review — opus, run 03

Repo: chi @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc, scope `middleware/`.

Method: I read every non-test source file in `middleware/`. I checked `mux.go` and `tree.go` for how `Mux.Match` and `Mux.Find` behave. I ran the existing test suite, which passes. Then I wrote throwaway probe tests in a scratch copy to confirm each finding below marked "Confirmed". The scratch copy has since been deleted.

---

## 1. `SupressNotFound` corrupts the live routing context, so mounted subrouters return 404 and URL params are duplicated
- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` with the request's real routing context. `Mux.Find` (`mux.go:380-398`) changes that context:
  - It appends to `URLParams` and `RoutePatterns`.
  - When the route goes through a `Mount`, it sets `rctx.RoutePath` to the sub-path.

  The mux then routes the request using that changed context.
- **Confirmed:**
  - With `r.Use(SupressNotFound(r)); r.Mount("/api", sub); sub.Get("/{id}", …)`, the request `GET /api/7` returns **404**. The top-level router now routes on `RoutePath="/7"`.
  - With `r.Get("/u/{name}", …)`, the request `GET /u/bob` returns 200, but `rctx.URLParams.Keys == ["name","name"]`, so the params are duplicated.
- **Why it's wrong:**
  - The doc says it should only short-circuit routes that are *not* found. Instead it breaks routes that exist.
  - `mux.go:380-381` warns: "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()".
  - `GetHead` (`get_head.go:24`) does this correctly by using a temporary `chi.NewRouteContext()`.
- **Severity:** high. Any app that uses this middleware together with `Mount` gets 404s on valid routes.
- **Fix:** `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, r.URL.Path)`. Using `rctx.RoutePath`, when it is set, would also be more correct inside subrouters.

## 2. `Compress` labels uncompressed bodies as `Content-Encoding: gzip` when the encoder fails to build (for example, an invalid level)
- **File/line:** `middleware/compress.go:219-221` together with `249-250` and `328-331`
- **What goes wrong:**
  - `EncoderFunc` is documented to "return nil" on failure (`compress.go:272`), and `encoderGzip`/`encoderDeflate` do this for an invalid level.
  - `selectEncoder` still returns the encoding name (`"gzip"`) together with a nil writer.
  - `Handler` only skips `cw.w = encoder` when the writer is nil, and leaves `cw.encoding` set.
  - `WriteHeader` then sets `Content-Encoding: gzip` and writes the plain bytes through `cw.w == w`.
- **Confirmed:** `Compress(10)` plus a request with `Accept-Encoding: gzip` gives `Content-Encoding: "gzip"` with body `"hello world"` in plain text. Clients fail to decode it.
- **Severity:** medium. The trigger is a misconfigured level or a custom encoder that returns nil, as its contract allows, and the result is a response clients can't read.
- **Fix:**
  - In `selectEncoder`, treat a nil result from `fn(w, level)` as "no match" and continue to the next encoder.
  - Or in `Handler`, clear `encoding` when `encoder == nil`.
  - Optionally, validate the level in `NewCompressor`.

## 3. `Compress` ignores `q=0` in `Accept-Encoding` and matches by substring
- **File/line:** `middleware/compress.go:235, 260-267` (`matchAcceptEncoding`)
- **What goes wrong:** Each comma-separated token is tested with `strings.Contains(v, encoding)`. `q` values are never parsed, so `gzip;q=0` counts as acceptance of gzip.
- **Confirmed:** `Accept-Encoding: gzip;q=0, deflate;q=0, identity` still gives `Content-Encoding: gzip`.
- **Why it's wrong:**
  - RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable".
  - The middleware's own doc says it chooses the format "based on Accept-Encoding request header".
- **Severity:** medium. The server sends an encoding the client explicitly refused.
- **Fix:**
  - Parse each token as `name[;q=x]`.
  - Compare the trimmed name exactly (and handle `*`).
  - Skip entries where `q == 0`.

## 4. `Compress`: calling `Flush()` before the first `Write` sends a gzip body without a `Content-Encoding` header
- **File/line:** `middleware/compress.go:357-371` (`Flush`), `338-343` (`Write`), `310-336` (`WriteHeader`)
- **What goes wrong:**
  1. `Flush()` runs while `cw.wroteHeader == false`, so `writer()` is the underlying ResponseWriter.
  2. Flushing it commits a 200 status with the current headers, which have no Content-Encoding.
  3. The next `Write` calls `cw.WriteHeader(200)`. That sets `Content-Encoding` on headers that were already sent, marks the writer `compressible = true`, and makes a superfluous `WriteHeader` call.
  4. The body is then gzip-compressed.
- **Confirmed:** In a real `httptest.Server`, a handler that sets `Content-Type: text/html`, calls `Flush()`, then calls `Write` sends a response with `Content-Encoding: ""` and a body starting with the gzip magic bytes `\x1f\x8b`. The server also logs "superfluous response.WriteHeader call … compress.go:336".
- **Severity:** medium. Streaming handlers that flush early send corrupted output to clients.
- **Fix:** In `Flush`, call `cw.WriteHeader(http.StatusOK)` first when `!cw.wroteHeader`, so the compression decision and headers are settled before anything is flushed.

## 5. `Compress` makes its compression decision on 1xx informational headers
- **File/line:** `middleware/compress.go:310-316`
- **What goes wrong:**
  - The first `WriteHeader` call of any kind sets `wroteHeader = true` and decides compressibility, even for a 1xx code such as `WriteHeader(103)` (Early Hints).
  - For a 103 sent before `Content-Type` is set, the final 200 response is never compressed.
  - For a 103 sent after `Content-Type` is set, `Content-Encoding`/`Vary` are added to the header map at 103 time.
- **Confirmed:** A handler that sends 103 → sets `Content-Type: text/html` → sends 200 → writes gets an uncompressed body.
- **Why it's wrong:** The package's own `basicWriter.WriteHeader` (`wrap_writer.go:84-87`) passes 1xx codes through without treating them as the final header. `compressResponseWriter` doesn't do the same.
- **Severity:** low.
- **Fix:** When `code >= 100 && code < 200 && code != 101`, pass the code through to `cw.ResponseWriter.WriteHeader(code)` and return without setting `wroteHeader`.

## 6. `RedirectSlashes` inside a mounted subrouter redirects to a path without the mount prefix
- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** When `rctx.RoutePath` is set (which is always the case inside a mounted subrouter), the redirect target is built from `RoutePath`. That value is relative to the mount point.
- **Confirmed:** `r.Mount("/api", sub)` with `sub.Use(RedirectSlashes)` and `GET /api/items/` gives `301 Location: /items` instead of `/api/items`.
- **Why it's wrong:** The doc says it will "redirect to the same path, less the trailing slash". The client instead lands on a different resource, which is usually a 404.
- **Severity:** medium.
- **Fix:** Always build the redirect location from `r.URL.Path` (or `EscapedPath()`), even though `RoutePath` may still be used to decide whether a trailing slash is present.

## 7. `AllowContentEncoding` rejects comma-separated `Content-Encoding` values
- **File/line:** `middleware/content_encoding.go:17, 24-28`
- **What goes wrong:** `r.Header["Content-Encoding"]` gives raw header field values. A single field `Content-Encoding: gzip, deflate` is one string, `"gzip, deflate"`, and that string is not in the whitelist.
- **Confirmed:** `AllowContentEncoding("gzip","deflate")` with `Content-Encoding: gzip, deflate` gives **415**, even though both codings are allowed.
- **Why it's wrong:**
  - Content-Encoding is a list-valued header (RFC 9110 §8.4). Sending one field with commas is equivalent to sending several fields.
  - The code comment says "All encodings in the request must be allowed", which implies per-coding checks.
- **Severity:** low-medium.
- **Fix:** Split each value on `,`, trim each part, and check each non-empty coding.

## 8. `ContentCharset` rejects quoted charset parameters and mutates the caller's slice
- **File/line:** `middleware/content_charset.go:13-15` and `35-39`
- **What goes wrong:**
  - **(a)** `Content-Type: text/plain; charset="utf-8"` extracts `"utf-8"` with the quotes included. It never matches `utf-8`, so the response is **415**. Confirmed. RFC 9110 §5.6.6 allows a parameter value to be a quoted-string, and it is equivalent to the token form.
  - **(b)** `charsets[i] = strings.ToLower(c)` writes into the variadic slice. When the caller passes `ContentCharset(list...)`, the caller's own slice gets rewritten. Confirmed: `[]string{"UTF-8"}` became `[utf-8]`.
- **Severity:** low.
- **Fix:**
  - Parse with `mime.ParseMediaType` and use `params["charset"]`.
  - Lowercase into a newly allocated slice.

## 9. `RouteHeaders` never matches patterns that contain uppercase characters, and picks among headers in random order
- **File/line:** `middleware/route_headers.go:54, 66` (patterns stored as given), `91` (value lowercased), `86` (map iteration)
- **What goes wrong:**
  - **(a)** The request header value is lowercased before matching, but `NewPattern(match)` keeps the pattern's case. Any pattern with an uppercase letter can therefore never match. Confirmed: `Route("Origin","https://App.example.com",…)` with that exact Origin fell through to `next`.
  - **(b)** "find first matching header route" (line 85) iterates over a Go map. When routes are registered on two different headers and a request matches both, which middleware runs changes randomly from request to request.
- **Severity:** low-medium. (a) silently disables a route. (b) makes routing non-deterministic.
- **Fix:**
  - Lowercase `match` in `Route`/`RouteAny`, or compare with `EqualFold`.
  - Keep the header names in insertion order (a slice), and iterate over that slice.

## 10. `Recoverer` checks the `Connection` header by exact string equality
- **File/line:** `middleware/recoverer.go:39`
- **What goes wrong:** `r.Header.Get("Connection") != "Upgrade"` only recognises the exact value `Upgrade`. Connection is a case-insensitive, comma-separated token list; Firefox, for example, sends `keep-alive, Upgrade` for WebSockets. For a panic after such a connection has been upgraded and hijacked, `w.WriteHeader(500)` is called on a hijacked connection, and net/http logs "response.WriteHeader on hijacked connection".
- **Severity:** low.
- **Fix:** Tokenise the header and compare each token with `strings.EqualFold(tok, "upgrade")`, or use `httpguts.HeaderValuesContainsToken`.

## 11. `Profiler` redirects break when the request has a query string
- **File/line:** `middleware/profiler.go:27, 30`
- **What goes wrong:** The redirect appends to `r.RequestURI`, which includes the query. `GET /debug?x=1` redirects to `/debug?x=1/pprof/`, and `/debug/pprof?seconds=5` redirects to `/debug/pprof?seconds=5/`. Both put the path suffix inside the query, so the redirect loops or lands on the wrong resource.
- **Severity:** low.
- **Fix:** Build the target from `r.URL.Path`, then re-append `"?"+r.URL.RawQuery` if the query is non-empty.

---

## Considered and not reported
These are either intended behaviour or not a defect I can confirm:
- The small race in `Timeout`, where the deadline fires right after the handler has written.
- `CleanPath` not cleaning an already-set `RoutePath`.
- `NoCache` deleting request conditional headers.
- `RealIP` spoofing, which is already documented as deprecated.
- `Throttle` with a zero `BacklogTimeout` via `ThrottleWithOpts`.
- `Logger` logging status 000 when a handler writes nothing. This matches the documented `Status()` contract.
- The `URLFormat` edge cases.

## Files actually read
- `middleware/`: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go
- Outside the scope, for context: `mux.go` (Match/Find), `tree.go` (FindRoute), `go.mod`
- I ran the existing tests in `middleware/` (they pass) plus my own throwaway probe tests. I did not read the existing `*_test.go` files in detail.
