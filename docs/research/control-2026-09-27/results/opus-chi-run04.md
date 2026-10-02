# chi `middleware/` defect review — opus-chi-run04

Repo: go-chi/chi @ 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc. Scope: `middleware/`.

I confirmed every defect below by running a probe test (a throwaway `zz_probe_test.go` in a copy of the checkout under the work directory, using Go 1.25.1). The observed output is quoted with each finding.

---

## 1. SupressNotFound corrupts the live routing context, which breaks sub-routers and duplicates URL params (HIGH)

- **File/line:** `middleware/supress_notfound.go:18-19`
- **What goes wrong:** `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` runs the lookahead on the request's real `*chi.Context`. `Mux.Find` (`mux.go:382-408`) changes the context it is given. `FindRoute` appends route params and sets `routePattern`. For mounted sub-routers it also sets `rctx.RoutePath = mx.nextRoutePath(rctx)`. The router then routes the request using this modified context.
  - `r.Route("/api", ...)` with `GET /api/x` defined, then request `GET /api/x` → **404** (the route exists). The lookahead left `RoutePath="/x"`, and the root mux routes that path.
  - `GET /u/{id}` → the handler sees `URLParams.Keys = [id id]` (duplicated).
  - It also returns 404 instead of 405 for a known path with the wrong method: `POST`-only `/p`, request `GET /p` → 404, where the plain router gives 405.
  - Observed: `supress GET /api/x: 404`, `supress GET /u/1: 200 "keys=[id id]"`, `supress GET /p: 404`.
- **Why wrong:** The doc says it responds 404 only "if the route is not found". `GetHead` in the same package (`get_head.go:23-29`) shows the intended pattern: look ahead with a temporary `chi.NewRouteContext()`.
- **Fix:** `tctx := chi.NewRouteContext(); if !rctx.Routes.Match(tctx, r.Method, path) { ... }`. Compute `path` the way `GetHead` does (RoutePath, then RawPath, then Path). Consider matching method-agnostically, or letting 405 fall through.

## 2. Compress ignores `q=0` in Accept-Encoding and uses substring matching (MEDIUM)

- **File/line:** `middleware/compress.go:231-267` (`selectEncoder`, `matchAcceptEncoding`)
- **What goes wrong:** Each accepted token is tested with `strings.Contains(v, encoding)`. A client that explicitly refuses gzip still gets gzip.
  - Observed: `Accept-Encoding: gzip;q=0, deflate;q=0, identity` → response `Content-Encoding: gzip`.
  - Substring matching also means any token that merely contains the name counts as a match.
- **Why wrong:** RFC 9110 §12.5.3 says a qvalue of 0 means "not acceptable". The Compressor doc says it picks the encoding "based on Accept-Encoding request header".
- **Fix:** Parse each element: split on `;`, trim, and compare the coding name exactly (case-insensitive). Skip entries whose `q` parameter parses to 0. Optionally honour `*`.

## 3. Compress sends `Content-Encoding: gzip` with an uncompressed body when the encoder can't be built (MEDIUM)

- **File/line:** `middleware/compress.go:249-250` and `219-221`, `328-330`
- **What goes wrong:** `EncoderFunc` is documented to return nil on failure (line 272). `encoderGzip` and `encoderDeflate` do return nil for an invalid level, e.g. `Compress(42)`, or any level outside -2..9.
  - `selectEncoder` still returns the encoding name with a nil writer. `Handler` then leaves `cw.w = w` but keeps `cw.encoding = "gzip"`.
  - `WriteHeader` sets `Content-Encoding: gzip` and `compressible = true`, and the raw bytes are written.
  - Observed: `badlevel: CE="gzip" body="hello"`. Clients fail to decode the response.
- **Why wrong:** The response header claims an encoding the body doesn't have. The nil-return contract in the code's own doc is never checked.
- **Fix:** In `selectEncoder`, if `fn(w, level)` returns nil, skip that encoding (`continue`) instead of returning its name. Optionally validate `level` in `NewCompressor`.

## 4. Compress: calling Flush before the first Write sends headers without Content-Encoding, then gzip bytes (MEDIUM)

- **File/line:** `middleware/compress.go:357-371` (with `338-351`)
- **What goes wrong:** `Flush()` doesn't call `WriteHeader` first. Before any write, `cw.compressible` is false, so `writer()` returns the underlying ResponseWriter. Flushing it commits a 200 with no `Content-Encoding`.
  - The next `Write` calls `cw.WriteHeader(200)`. That now marks the response compressible and sets `Content-Encoding` too late, since the headers are already on the wire. The body then goes out gzip-compressed.
  - Observed (real `httptest.Server`): `flushfirst: CE="" body="\x1f\x8b\b..."`, plus `http: superfluous response.WriteHeader call ... compress.go:336`.
  - This is a common streaming pattern: set Content-Type, flush, then stream.
- **Why wrong:** The client receives a gzip stream labelled as identity-encoded, so the body is corrupted.
- **Fix:** At the top of `Flush()`, `if !cw.wroteHeader { cw.WriteHeader(http.StatusOK) }`. This mirrors `basicWriter.flush()` in `wrap_writer.go:123-128`, which calls `maybeWriteHeader()`.

## 5. RedirectSlashes inside a sub-router redirects to a path without the mount prefix (MEDIUM)

- **File/line:** `middleware/strip.go:44-62`
- **What goes wrong:** Inside a sub-router, `rctx.RoutePath` holds the path relative to the mount point, and the redirect `Location` is built from it.
  - Observed: `r.Route("/api", func(sr){ sr.Use(RedirectSlashes); sr.Get("/users", ...) })`, request `GET /api/users/` → `301 Location: /users`, which is a different resource (or a 404).
- **Why wrong:** The doc says it will "redirect to the same path, less the trailing slash". The mount prefix is lost.
- **Fix:** Use `RoutePath` only to decide whether there is a trailing slash. Build the redirect from `r.URL.Path`, keeping the existing backslash normalisation, `strings.Trim` and RawQuery handling. Alternatively, prepend the part of `r.URL.Path` that precedes `RoutePath`.

## 6. AllowContentEncoding rejects a valid comma-separated Content-Encoding list (LOW)

- **File/line:** `middleware/content_encoding.go:17-29`
- **What goes wrong:** Each raw header value is looked up whole in the allow-list.
  - Observed: `Content-Encoding: deflate, gzip`, with both allowed → **415**.
- **Why wrong:** Content-Encoding is a comma-separated list (RFC 9110 §8.4). The package's own test comment (`content_encoding_test.go:18-19`) lists `Content-Encoding: gzip, deflate` as the case being tested. The test only passes because it sends separate header lines.
- **Fix:** Split each value on `,`, trim each token, lowercase it, and skip empty tokens before the lookup.

## 7. RouteHeaders: patterns containing uppercase letters never match (LOW)

- **File/line:** `middleware/route_headers.go:48-54`, `58-68`, `91`, `135-139`
- **What goes wrong:** `Handler` lowercases the incoming header value (line 91), but `NewPattern` stores the pattern as given.
  - Observed: `Route("Host", "Example.com", mw)` with `Host: Example.com` → no match.
- **Why wrong:** The code clearly intends case-insensitive matching, since it lowercases the header name and the value. Lowercasing only one side makes any mixed-case pattern dead.
- **Fix:** Lowercase `value` in `NewPattern`, or in `Route` and `RouteAny`, before building the pattern.

## 8. URLFormat treats a leading-dot segment as a format extension (LOW)

- **File/line:** `middleware/url_format.go:58-69`
- **What goes wrong:** `idx` is the index of the last `.` within `path[base:]`, and that slice always starts with `/`. So `idx > 0` holds even when the dot is the first character of the segment.
  - For `/.well-known` the format becomes `"well-known"` and RoutePath is rewritten to `/`.
  - Observed: `r.Get("/.well-known", ...)` → **404** with `URLFormat` enabled.
- **Why wrong:** A dot-file segment has no extension. The `idx > 0` check appears meant to exclude that case but is off by one because of the leading `/`.
- **Fix:** `if idx > 1 { ... }`, i.e. require at least one character between the `/` and the `.`.

## 9. ContentCharset rejects a quoted charset parameter (LOW)

- **File/line:** `middleware/content_charset.go:35-40`
- **What goes wrong:**
  - Observed: `Content-Type: text/plain; charset="utf-8"` with `ContentCharset("utf-8")` → **415**.
  - The same string parsing also matches parameters that merely end in `charset=`, e.g. `xcharset=`.
- **Why wrong:** RFC 9110 §5.6.6 allows parameter values as quoted-strings, and `charset="utf-8"` is equivalent to `charset=utf-8`.
- **Fix:** Parse with `mime.ParseMediaType` and compare `strings.ToLower(params["charset"])`.

## 10. Sunset sets the `Deprecation` header in the wrong format (LOW)

- **File/line:** `middleware/sunset.go:16`
- **What goes wrong:** `Deprecation` is written as an IMF-fixdate (`http.TimeFormat`).
- **Why wrong:** RFC 9745 defines `Deprecation` as a Structured Field Date, e.g. `Deprecation: @1688169599`. An HTTP-date is not a valid value. (The `Sunset` header correctly uses HTTP-date per RFC 8594.)
- **Fix:** `w.Header().Set("Deprecation", "@"+strconv.FormatInt(sunsetAt.Unix(), 10))`. Ideally also let callers pass a separate deprecation time, since deprecation usually comes before sunset.

---

## Examined and not reported

These looked plausible but I judged them not to be real defects, or too speculative to report:
- `Timeout` writing 504 after the handler returns (documented behaviour).
- `realip.go` spoofing (deprecated and documented).
- `ClientIPFrom*` walk and counting logic (checked; matches its docs).
- `Throttle` token and timer handling.
- `wrap_writer.go` ReadFrom/tee/discard paths.
- `BasicAuth`.
- `Recoverer` stack parsing.

## Files read

- `middleware/`: basic_auth.go, clean_path.go, client_ip.go, compress.go, content_charset.go, content_encoding.go, content_type.go, get_head.go, heartbeat.go, logger.go, maybe.go, middleware.go, nocache.go, page_route.go, path_rewrite.go, profiler.go, realip.go, recoverer.go, request_id.go, request_size.go, route_headers.go, strip.go, sunset.go, supress_notfound.go, terminal.go, throttle.go, timeout.go, url_format.go, value.go, wrap_writer.go
- `middleware/content_encoding_test.go` (grepped)
- `middleware/compress_test.go` and `url_format_test.go` (grepped only)
- `mux.go` (`Find`/`Match`, lines 382-408)
- `go.mod`
