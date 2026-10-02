# chi `middleware/` code review — opus-chi-run09

Repo: go-chi/chi @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc. Scope: `middleware/`.

Every defect below was reproduced with a throwaway Go test in a copy of the checkout (`/tmp/control-work/opus-chi-run09/chi/middleware/zz_review_test.go`, since deleted). The observed output is quoted with each finding.

---

## 1. SupressNotFound corrupts the live routing context. Mounted routes return 404 and URL params are duplicated

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** The middleware calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` with the request's real `*chi.Context`. `Mux.Find` (`mux.go:377-398`) writes to the context it is given: it appends URL params and route patterns. For a node with subroutes it also sets `rctx.RoutePath = mx.nextRoutePath(rctx)`. Routing then continues with that modified context:
  - With a sub-router mounted at `/api`, `GET /api/users/1` returns **404**. The top-level mux now routes on the leftover `RoutePath` `/users/1`, not on the full path. Observed: `/api/users/1 -> 404`.
  - On a plain route `/x/{a}`, the URL param keys come out as `a,a`, meaning every param is duplicated. Observed: `n=a,a`.
- **Why it is wrong:** The doc comment says the middleware only short-circuits requests that "are not going to match any routes anyway". Here it breaks requests that do match. `Mux.Find` itself warns: "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". `get_head.go:24` does exactly that with `tctx := chi.NewRouteContext()`.
- **Severity:** high. Any app that uses this middleware together with `Mount` gets 404s on every mounted route.
- **Fix:** Do the look-ahead on a fresh context: `tctx := chi.NewRouteContext(); match := rctx.Routes.Match(tctx, r.Method, path)`. Also compute `path` the way the mux does, not from `r.URL.Path` alone: use `rctx.RoutePath`, else `r.URL.RawPath`, else `r.URL.Path`.

## 2. Compress sends `Content-Encoding: gzip` on an uncompressed body when the encoder can't be built (for example, an invalid level)

- **File/line:** `middleware/compress.go:249-250`, `219-221`, `328-331`
- **What goes wrong:** `encoderGzip` and `encoderDeflate` return `nil` on error, and `EncoderFunc` documents that ("In case of failure, the function should return nil"). A nil first instance means the encoder isn't pooled. On each request `selectEncoder` then returns `fn(w, c.level)`, which is nil, along with the name `"gzip"`. `Handler` leaves `cw.w = w` because `encoder == nil` but still sets `cw.encoding = "gzip"`. `WriteHeader` then sets `Content-Encoding: gzip` and writes the raw body. With `Compress(42)` the response is `Content-Encoding: "gzip"` with body `"hello"` in plain text, so clients fail to decode it.
- **Why it is wrong:** The contract explicitly allows nil, but the handler doesn't account for it. The response header then misdescribes the body.
- **Severity:** medium. Reaching it takes a bad level or a custom encoder that fails, but the result is corrupted responses, not an error.
- **Fix:** In `selectEncoder`, skip an encoder whose `fn` returns nil and try the next one, or return `"", nil`. Also set `cw.encoding` only when `encoder != nil`. Optionally, panic in `SetEncoder` if the probe instance is nil.

## 3. Compress ignores `q=0` in Accept-Encoding and matches by substring

- **File/line:** `middleware/compress.go:260-266` (`matchAcceptEncoding`)
- **What goes wrong:** `strings.Contains(v, encoding)` treats `gzip;q=0` as acceptance. With `Accept-Encoding: gzip;q=0, deflate;q=0, identity` the response still comes back `Content-Encoding: "gzip"`. Substring matching also means that a token containing the name, such as a custom `x-gzip-foo`, counts as a match.
- **Why it is wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The doc comment says compression is "based on Accept-Encoding request header".
- **Severity:** medium
- **Fix:** Parse each element. Split on `;` and compare the trimmed coding token for equality. Parse `q=`, and reject the coding when q is 0. `*` can be honoured the same way.

## 4. RedirectSlashes inside a mounted sub-router redirects to the wrong URL (the mount prefix is dropped)

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** When `rctx.RoutePath` is set, the middleware builds the redirect `Location` from it. Inside a sub-router mounted at `/api`, `RoutePath` is the path relative to the mount point. `GET /api/users/` therefore redirects to `Location: /users`, not `/api/users`. Observed: `301 Location="/users"`.
- **Why it is wrong:** The doc says it will "redirect to the same path, less the trailing slash". `RoutePath` is right for routing (which is what `StripSlashes` uses it for) but not for building a client-facing URL.
- **Severity:** medium. The redirect sends clients to a different resource or to a 404.
- **Fix:** Use `r.URL.Path`, or `EscapedPath()`, to decide and build the redirect, and keep the existing backslash and leading-slash normalisation. `RoutePath` should at most decide whether there is a trailing slash.

## 5. RouteHeaders never matches a pattern that contains uppercase letters

- **File/line:** `middleware/route_headers.go:91` versus `135-139` and `141-146`
- **What goes wrong:** `Handler` lowercases the request header value before matching. `NewPattern` stores the pattern exactly as the caller wrote it. Any pattern with an uppercase letter, such as `Route("Origin", "https://App.example.com", mw)`, can therefore never match, and the request silently falls through to the default route. Observed: `hit=false` with an identical header value.
- **Why it is wrong:** The header name is normalised with `strings.ToLower(header)` in `Route`/`RouteAny`, which shows that case-insensitive matching is intended. Only the value side is lowercased, which is inconsistent. In the documented CORS example, this failure mode means a credentialed origin would get the public or default CORS policy.
- **Severity:** medium
- **Fix:** Lowercase the prefix and suffix in `NewPattern` with `strings.ToLower(value)`, or stop lowercasing the header value. The first option matches the existing intent.

## 6. AllowContentEncoding rejects a valid comma-separated Content-Encoding list

- **File/line:** `middleware/content_encoding.go:17-29`
- **What goes wrong:** `r.Header["Content-Encoding"]` returns raw field values. The standard form `Content-Encoding: deflate, gzip`, a single line listing both codings, is looked up as the single token `"deflate, gzip"`. With both `gzip` and `deflate` allowed, the request is still rejected with **415**. Observed: `code=415`.
- **Why it is wrong:** Content-Encoding is a list-valued header (RFC 9110 §8.4). The code's own comment says "All encodings in the request must be allowed", which means each coding should be checked individually.
- **Severity:** low to medium
- **Fix:** Split each value on `,`, then trim and lowercase each element before the map lookup.

## 7. ContentCharset rejects a quoted charset parameter, and it mutates the caller's slice

- **File/line:** `middleware/content_charset.go:35-40` and `13-15`
- **What goes wrong:**
  - `Content-Type: text/plain; charset="utf-8"` is legal (RFC 9110 §5.6.6: a parameter value may be a quoted-string). It is compared as `"\"utf-8\""` and rejected with **415** when `utf-8` is allowed. Observed: `code=415`.
  - `ContentCharset(charsets...)` lowercases `charsets[i]` in place. If a caller passes a slice with `ContentCharset(list...)`, their slice is modified.
- **Why it is wrong:** The first contradicts the HTTP parameter grammar. The second is an unexpected side effect on caller data.
- **Severity:** low
- **Fix:** Parse with `mime.ParseMediaType` and compare `params["charset"]` case-insensitively. Copy the slice before normalising it.

## 8. Timeout writes 504 even after the handler has already written the response

- **File/line:** `middleware/timeout.go:36-41`
- **What goes wrong:** The deferred `w.WriteHeader(http.StatusGatewayTimeout)` fires whenever `ctx.Err() == DeadlineExceeded`, even if the handler already wrote a response. A handler that finishes just after the deadline and writes `200 ok` sends a 200. Middleware then calls `WriteHeader(504)`, and on a real server that produces `http: superfluous response.WriteHeader call`. Any wrapping writer, such as `WrapResponseWriter` or the Logger, may record inconsistent state. Observed with httptest: final `code=200 body="ok"` while the 504 was attempted.
- **Why it is wrong:** The doc promises to "return a 504 Gateway Timeout error to the client" when it times out, which implies it only applies if nothing has been sent yet.
- **Severity:** low
- **Fix:** Wrap `w` (for example, with `NewWrapResponseWriter`) and write 504 only if `Status() == 0`.

## 9. Compress decides compressibility on the first WriteHeader call, even when that call is a 1xx informational response

- **File/line:** `middleware/compress.go:310-336`
- **What goes wrong:** A 103 Early Hints `WriteHeader(103)` sets `cw.wroteHeader = true` and evaluates `isCompressible()` before the handler has set the final `Content-Type`. The later 200 goes through the "Allow multiple calls to propagate" branch and is never compressed. Observed: `CE="" len=500` for a `text/plain` body with `Accept-Encoding: gzip`. `wrap_writer.go:84` handles 1xx codes specially, which shows the project is aware of this case.
- **Severity:** low
- **Fix:** In `WriteHeader`, forward 1xx codes other than 101 directly and return without setting `wroteHeader` or making the compression decision.

## 10. Compress labels bodiless responses (204/304) as `Content-Encoding: gzip`

- **File/line:** `middleware/compress.go:328-335`, `387-392`
- **What goes wrong:** On `WriteHeader(204)` with a compressible `Content-Type`, the response gets `Content-Encoding: gzip`, and `Close()` then writes gzip framing bytes to a response that must not have a body. net/http discards them and returns `ErrBodyNotAllowed`. Observed: `code=204 CE="gzip"`.
- **Severity:** low
- **Fix:** Skip compression for status codes that don't allow a body (1xx, 204, 304), and in that case don't set Content-Encoding or Vary.

---

## Checked and not reported (not confident these are defects)

- `ClientIPFrom*` / `walkXFF`: the right-to-left walk, fail-closed handling, Unmap and zone stripping all match their docs.
- `Throttle`: the token accounting and timer handling look correct.
- `wrap_writer.go`: ReadFrom tee/discard is handled without double-counting.
- `Recoverer`'s exact `Connection: Upgrade` comparison misses `keep-alive, Upgrade`. This is low impact and borderline, so it is left out.
- `StripSlashes` and `URLFormat` derive the path from `r.URL.Path` rather than `RawPath` when `RoutePath` is empty. That is an inconsistency with `mux.routeHTTP`, but I did not confirm a user-visible failure, so it is not reported.

## Files read

- middleware/: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go
- Context outside the scope: mux.go (the `Match`/`Find`/`routeHTTP`/`nextRoutePath` sections), go.mod, and the `Route(` lines of middleware/route_headers_test.go.
