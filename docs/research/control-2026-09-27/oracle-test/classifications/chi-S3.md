# chi, classifier S3 (Claude Sonnet), blind

### chi-01
Oracle: RFC 9110 §7.6.1 defines `Connection` as a comma-separated list of case-insensitive connection-option tokens; the code instead does an exact string-equality check against the literal `"Upgrade"`, so a real-world value like `keep-alive, Upgrade` fails the check even though it contains the `Upgrade` token.
Type: known-external
Confidence: high

### chi-02
Oracle: `path[base:]` panics when `base == -1` (no `/` found) — an unrecovered slice-bounds-out-of-range panic.
Type: implicit
Confidence: high

### chi-03
Oracle: RFC 9110 §12.5.3 — an `Accept-Encoding` qvalue of `0` means that coding is explicitly unacceptable. `matchAcceptEncoding` (compress.go:264-267) only does `strings.Contains`, ignoring `;q=0`.
Type: known-external
Confidence: high

### chi-04
Oracle: reading `compressResponseWriter.Flush`/`Write`/`WriteHeader` together (compress.go:296-371): `Flush()` writes through the real `ResponseWriter` (sending status+headers) before `compressible` is ever computed, then the later implicit `WriteHeader` from `Write()` sets `Content-Encoding: gzip` too late and starts writing gzip bytes to a connection whose headers were already sent uncompressed.
Type: in-repo
Confidence: high

### chi-05
Oracle: the package's own comment at compress.go:114-116 ("HTTP 1.1 'deflate' ... stands for DEFLATE data (RFC 1951) wrapped with zlib (RFC 1950)") directly contradicts `encoderDeflate` (compress.go:406-411), which uses `flate.NewWriter` and emits raw, unwrapped DEFLATE.
Type: in-repo
Confidence: high

### chi-06
Oracle: `strings.Cut(contentType, ";")` (compress.go:298) keeps the leading part verbatim including trailing whitespace, then does a map lookup with no `TrimSpace`; the sibling `contentEncoding`/`split` helpers in content_charset.go:43-51 do call `strings.TrimSpace` on the same kind of parameter split, showing the intended handling exists elsewhere in the repo but wasn't applied here.
Type: in-repo
Confidence: high

### chi-07
Oracle: mux.go:460-468 (`routeHTTP`) explicitly prefers `r.URL.RawPath` over `r.URL.Path` when routing, but `PathRewrite` (path_rewrite.go:12) only rewrites `r.URL.Path`, so the router routes on the untouched original `RawPath`.
Type: in-repo
Confidence: high

### chi-08
Oracle: same as chi-07 — mux.go's actual routing logic prefers `RawPath`/`RoutePath`; `SupressNotFound` (supress_notfound.go:19) calls `Match` with the decoded `r.URL.Path`, so its look-ahead diverges from what the router will actually match on.
Type: in-repo
Confidence: high

### chi-09
Oracle: Go language specification — iteration order over a map is unspecified and randomized between range clauses; `HeaderRouter.Handler` (route_headers.go:86) ranges over the `map[string][]HeaderRoute` to pick the first matching header.
Type: known-external
Confidence: high

### chi-10
Oracle: mux.go:373-383 (`Match`)/`FindRoute` distinguishes "no route for any method" (404) from "route exists for a different method" (405, `rctx.methodNotAllowed`); `SupressNotFound`'s `Match(rctx, r.Method, ...)` (supress_notfound.go:19) only checks the current method, collapsing the 405 case into a 404.
Type: in-repo
Confidence: high

### chi-11
Oracle: RFC 7230 §3.2.2 — multiple header fields with the same name are semantically equivalent to one field with comma-separated values. `AllowContentEncoding` (content_encoding.go:17,24) iterates `r.Header["Content-Encoding"]` (one entry per header *line*) and checks each whole entry against the allow-set instead of splitting on commas.
Type: known-external
Confidence: high

### chi-12
Oracle: `CleanPath`'s own doc comment (clean_path.go:10-11) only promises collapsing of duplicate slashes; `path.Clean` (clean_path.go:23) also strips a non-root trailing slash, and the router (mux.go's `routeHTTP`) then fails to match a route explicitly registered as `/users/`.
Type: in-repo
Confidence: high

### chi-13
Oracle: Go's `net/http` server contract — the `Host` header is deliberately excluded from `Request.Header` and exposed only via `Request.Host`/`Request.URL.Host`; `HeaderRouter.Handler` (route_headers.go:87) reads `r.Header.Get(header)`, which is always empty for `"host"`.
Type: known-external
Confidence: high

### chi-14
Oracle: the panic message itself, throttle.go:49-50, `"Throttle expects backlogLimit to be positive"`, is issued only when `opts.BacklogLimit < 0`; that leaves `0` (not positive) accepted, contradicting the message.
Type: in-repo
Confidence: high

### chi-15
Oracle: none of the doc examples in url_format.go treat a leading-dot segment as an extension (they show `articles/1.json`, i.e. extension after a named resource); the code (`idx > 0` at url_format.go:62, where `idx` is measured relative to `path[base:]` and a dot immediately after `/` gives `idx == 1`) happens to treat `.env`/`.well-known` as "format = env / well-known". I can't point to anything that says this is *unintended*, only that it's surprising and undocumented.
Type: in-repo
Confidence: medium

### chi-16
Oracle: mux.go:460-468 prefers `RawPath` for routing when `RoutePath` is empty; `StripSlashes` (strip.go:16-22) instead reads `r.URL.Path` (decoded) when `rctx.RoutePath` is empty and, on a trailing slash, writes the decoded-and-trimmed value into `rctx.RoutePath`, which then *does* override the router's own RawPath preference — producing route mismatches for encoded-slash segments.
Type: in-repo
Confidence: high

### chi-17
Oracle: RFC 9110 §5.6.6 — media-type parameter values may be given as `quoted-string`, and quotes are not part of the value; `split`/`contentEncoding` (content_charset.go:35-51) never strips the surrounding `"..."`, so a legally-quoted `charset="utf-8"` never matches the configured `"utf-8"`.
Type: known-external
Confidence: high

### chi-18
Oracle: Go's `net/http` documents that `time.Time` values passed to `Format(http.TimeFormat)` must already be in UTC, since `TimeFormat` hard-codes the `GMT` suffix without converting the zone; `Sunset` (sunset.go:15-16) calls `sunsetAt.Format(http.TimeFormat)` directly on a caller-supplied `time.Time` without calling `.UTC()` first.
Type: known-external
Confidence: high

### chi-19
Oracle: RFC 9110 §6.4.1 / §15.4.5 — 204 and 304 responses must not carry a message body, so a `Content-Encoding`/body-shaped response for them is meaningless; `WriteHeader`/`Close` (compress.go:310-336, 387-392) never special-case the status code, and the resulting `http.ErrBodyNotAllowed` from `Close()`'s write is discarded rather than surfaced.
Type: known-external
Confidence: high

### chi-20
Oracle: RFC 3986 §3 — a URI's path component precedes its query component; `Profiler` (profiler.go:27,30) builds the redirect target as `r.RequestURI + "/pprof/"` where `RequestURI` already includes `?x=1`, so the resulting string has a path segment appended after the query string, which is not a well-formed reference to a distinct path.
Type: known-external
Confidence: high

### chi-21
Oracle: RFC 3986 §2.1/§3.3 — reserved characters (`?`, `/`, etc.) that were percent-encoded in the original path must stay percent-encoded when the path is re-serialized, or they change meaning; `RedirectSlashes` (strip.go:51-62) builds `Location` from the already-decoded `path` string with no re-escaping.
Type: known-external
Confidence: high

### chi-22
Oracle: `GetHead`'s own doc comment (get_head.go:9) — "automatically route **undefined** HEAD requests to GET handlers" — implies an explicitly registered HEAD handler must win; the look-ahead uses `rctx.Routes` (the outer/root router's context object established by mount traversal), so under `r.Mount("/api", sub)` the explicitly-registered `sub.Head("/hi", ...)` is not found and the GET handler runs anyway. The parent-router-405 half of the finding follows from the same mount/rctx interaction but I can't trace it as precisely.
Type: in-repo
Confidence: medium

### chi-23
Oracle: Go's `net/http` 1xx-informational-response support — a `WriteHeader` call with a 1xx code is not the final response header and a subsequent `WriteHeader` call determines the actual response; `compressResponseWriter.WriteHeader` (compress.go:310-316) instead latches `wroteHeader = true` and runs its one-time compressibility decision on the *first* call regardless of whether that call was a 1xx code.
Type: known-external
Confidence: medium

### chi-24
Oracle: the Go `crypto/subtle` package's documented purpose — its functions exist specifically so secret comparisons don't leak information through timing — is defeated by the `||` short-circuit in `BasicAuth` (basic_auth.go:19-20): `subtle.ConstantTimeCompare` only runs when the username is present, so a wrong-username request returns faster than a wrong-password request, leaking which usernames are valid.
Type: known-external
Confidence: medium

### chi-25
Oracle: `Compressor.selectEncoder` (compress.go:249-250) returns the encoder *name* (`"gzip"`) even when `fn(w, c.level)` returned `nil`; `Handler` (compress.go:207-212) only swaps in the encoder writer `if encoder != nil`, but `compressResponseWriter.WriteHeader` (compress.go:326-329) sets `Content-Encoding` purely from `cw.encoding`, independent of whether an actual encoder is in use — so the header is set while the body is written unencoded.
Type: in-repo
Confidence: high

### chi-26
Oracle: mux.go's `routeHTTP` (mux.go:460-465) reads `r.URL.RawPath` directly for routing without checking it's still a valid encoding of `r.URL.Path`; `StripSlashes`'s no-route-context branch (strip.go:25-26) mutates `r.URL.Path` but leaves `r.URL.RawPath` untouched, leaving the two fields inconsistent for any code (including chi's own router, if StripSlashes runs ahead of it) that reads `RawPath` directly rather than through `URL.EscapedPath()`.
Type: in-repo
Confidence: medium

### chi-27
Oracle: RFC 9110 §12.5.3 — `Accept-Encoding` codings are compared as whole tokens, not substrings; `matchAcceptEncoding` (compress.go:264-267) uses `strings.Contains`, so `"xgzip"` or `"x-gzip-foo"` falsely match the `"gzip"` coding.
Type: known-external
Confidence: high

### chi-28
Oracle: `RedirectSlashes`'s own doc comment (strip.go:36-37) promises a redirect "to the same path, less the trailing slash"; under `Mount`, `rctx.RoutePath` (per its doc at context.go:65-67, "used during the route search" for the current sub-router) is the mount-relative path, so building `Location` from it (strip.go:44-57) drops the `/api` prefix and violates "the same path."
Type: in-repo
Confidence: high

### chi-29
Oracle: I can't point to a documented contract that `ContentCharset`'s variadic `charsets` parameter is caller-owned and must not be mutated; `content_charset.go:12-15` lower-cases the slice in place, which is a real, observable side effect on the caller's backing array, but nothing in this repo states it's wrong.
Type: none
Confidence: low

### chi-30
Oracle: `split(ce, "charset=")` (content_charset.go:37) uses `strings.Cut`, which matches the substring `"charset="` anywhere, including inside `xcharset=` or `x-charset=`; it doesn't anchor on a parameter-name boundary (e.g. after `;` and optional whitespace), so a differently-named parameter is misread as `charset`.
Type: in-repo
Confidence: high

### chi-31
Oracle: I know the "Deprecation" HTTP header field is defined by an IETF draft (draft-ietf-httpapi-deprecation-header) that specifies its value format, but I can't quote the current wording precisely enough from memory to say whether IMF-fixdate is right or wrong for that field, or whether it should instead have been a boolean.
Type: fetch-external
Confidence: low

### chi-32
Oracle: `SupressNotFound` (supress_notfound.go:18-19) reuses the request's own live `rctx` for its look-ahead `Match` call, mutating its `URLParams`/`RoutePath` state before the real routing pass runs again on the same object; `GetHead` (get_head.go:24, `tctx := chi.NewRouteContext()`) shows the correct pattern elsewhere in this same package — allocate a disposable context for a look-ahead match rather than the live one.
Type: in-repo
Confidence: high

### chi-33
Oracle: Go's `net/http` `ResponseWriter` contract — calling `WriteHeader` after headers have already been sent is a no-op for the client (who keeps the original status) and logs "superfluous response.WriteHeader call"; `Timeout`'s deferred func (timeout.go:38-40) calls `w.WriteHeader(504)` unconditionally on deadline expiry with no check for whether the handler already wrote a response.
Type: known-external
Confidence: high

### chi-34
Oracle: RFC 9110 §8.3.1 — media type names are registered and compared case-insensitively; `isCompressible` (compress.go:296-300) does a bare map lookup on the raw-cased `Content-Type` value against `allowedTypes`, which is populated from case-sensitive input in `NewCompressor` (compress.go:72-95).
Type: known-external
Confidence: high

### chi-35
Oracle: `ClientIPFromHeader`'s own doc comment (client_ip.go:33-37) explicitly documents fail-closed behavior — "Fail-closed if the last value doesn't parse: no client IP is set" — and `parseHeaderAddr` (client_ip.go:268-273) calls `netip.ParseAddr`, which correctly rejects a comma-joined string like `"6.6.6.6, 1.2.3.4"`. The observed behavior matches the documented contract for an unparseable header value.
Type: in-repo
Confidence: low

### chi-36
Oracle: `Route`/`RouteAny` (route_headers.go:48-54, 58-70) lower-case the match key only when called via `Route(header, ...)` on the *header name*, but `NewPattern` (route_headers.go:135-138) stores the match *value* verbatim (mixed case), while `Handler` (route_headers.go:91) lower-cases the incoming request's header value before comparing — an exact-case pattern like `"https://App.example.com"` can never equal the lower-cased runtime value.
Type: in-repo
Confidence: high

---

Hardest to classify: **chi-15** (leading-dot "extension" handling) and **chi-29** (mutating the caller's `charsets` slice) — both are real, reproducible behaviors, but neither doc comment nor sibling code states what "correct" looks like, so I could only reason from silence and convention rather than point at something concrete. **chi-31** (Deprecation header format) and **chi-23** (1xx informational status and compressibility) were hard because I know there's an external contract (an IETF draft; Go's informational-response handling) but couldn't recall it precisely enough to be sure the observed behavior is wrong rather than compliant. **chi-22** and **chi-28** (both Mount-interaction bugs) were hard to fully trace through chi's `RouteContext`/mount machinery with certainty, though the doc-comment contradiction gave me enough to classify them in-repo. **chi-35** stood out as the one finding where reading the doc comment convinced me the described behavior is very likely *not* a defect at all, despite being phrased like the others.
