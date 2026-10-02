# chi, classifier S2 (Claude Sonnet), blind

### chi-01
Oracle: RFC 7230 §6.1 defines `Connection` as a comma-separated list of connection-tokens (e.g. `keep-alive, Upgrade`), so testing for exact equality to `"Upgrade"` misses any list that also contains other tokens; the resulting `WriteHeader` call after a hijack is also flagged by net/http's own post-hijack misuse logging.
Type: known-external
Confidence: high

### chi-02
Oracle: `strings.LastIndex(path[base:], ".")` on a path with no `/` returns `base = -1` from the outer `LastIndex(path, "/")`, so `path[base:]` slices from `-1`, which Go's runtime rejects — this is a straightforward out-of-range panic.
Type: implicit
Confidence: high

### chi-03
Oracle: RFC 9110 §12.5.3 (Accept-Encoding) defines `q=0` as "not acceptable"; `matchAcceptEncoding` only checks for substring presence of the coding name and never parses/respects the `;q=` qvalue, so a client that explicitly refused gzip still receives it.
Type: known-external
Confidence: high

### chi-04
Oracle: `compressResponseWriter.WriteHeader` (compress.go:310-336) is the only place `compressible`/`Content-Encoding` get decided, and `compressible` starts `false` ("// determined in post-handler", compress.go:217). `Flush()` (compress.go:357-371) calls `cw.writer()` — which resolves to the raw `ResponseWriter` before `WriteHeader` has run — bypassing that decision and flushing headers early, so the later real `WriteHeader` call both fires the compression path and duplicates a header write net/http will reject as superfluous.
Type: in-repo
Confidence: high

### chi-05
Oracle: the code's own comment at compress.go:114-116 states "HTTP 1.1 'deflate' ... stands for DEFLATE data (RFC 1951) wrapped with zlib (RFC 1950)," but `encoderDeflate` (compress.go:406-411) uses `flate.NewWriter`, which emits raw RFC 1951 data with no zlib wrapper — the implementation contradicts the repo's own documented understanding of the encoding.
Type: in-repo
Confidence: high

### chi-06
Oracle: `isCompressible` (compress.go:296-297) cuts the Content-Type on `;` but never trims the result, unlike the sibling parsing helper `split` in content_charset.go:42-51, which trims whitespace after every `strings.Cut`. The established in-repo convention for parsing header values elsewhere in this package is to trim; this function skips it.
Type: in-repo
Confidence: medium

### chi-07
Oracle: chi's own router (mux.go:460-464, `routeHTTP`) prefers `r.URL.RawPath` over `r.URL.Path` when routing, but `PathRewrite` only mutates `r.URL.Path`, so a `RawPath`-carrying request is routed on the untouched original path.
Type: in-repo
Confidence: high

### chi-08
Oracle: same router logic as chi-07 (mux.go:460-464): the router itself falls back to `rctx.RoutePath`, then `r.URL.RawPath`, then `r.URL.Path`. `SupressNotFound` (supress_notfound.go:19) hardcodes `r.URL.Path`, so its look-ahead can diverge from what the router will actually match on for a raw-encoded path.
Type: in-repo
Confidence: high

### chi-09
Oracle: `HeaderRouter.Handler` (route_headers.go:86) iterates a Go `map[string][]HeaderRoute`; the Go language spec explicitly leaves map iteration order unspecified/randomized per run, so which header wins when a request matches two registered headers is nondeterministic by language design, not implementation intent.
Type: known-external
Confidence: high

### chi-10
Oracle: chi's router itself distinguishes "no route" (404, `NotFoundHandler`) from "route exists for a different method" (405, `MethodNotAllowedHandler`) — see mux.go:494-498 (`if rctx.methodNotAllowed { ...405...} else {...404...}`). `SupressNotFound` calls the method-agnostic `Routes.Match` (chi.go:131, mux.go:373), which only reports whether *any* method matches the path, collapsing the router's own 404/405 distinction into a blanket 404.
Type: in-repo
Confidence: medium

### chi-11
Oracle: RFC 9110 §5.3 states that multiple header field lines with the same name and a comma-separated list syntax are semantically equivalent to one line joining them with commas. `AllowContentEncoding` (content_encoding.go:17) iterates `r.Header["Content-Encoding"]` treating each header *line* as a single encoding token, so a legal single-line combined value like `deflate, gzip` is checked as one (unmatched) token instead of two.
Type: known-external
Confidence: high

### chi-12
Oracle: the package README/doc describes `CleanPath` as cleaning "double slashes" only, and `clean_path_test.go` only exercises that case. The actual implementation calls `path.Clean` (clean_path.go:23), whose documented stdlib behavior also strips a single trailing slash — an effect outside what the middleware advertises and that silently breaks routes registered with a required trailing slash.
Type: in-repo
Confidence: medium

### chi-13
Oracle: the Go `net/http` `Request` documentation states the Host header value is available in `r.Host`, not `r.Header`, because the net/http server deletes/moves it out of the header map — this is documented standard-library behavior, not chi-specific.
Type: known-external
Confidence: high

### chi-14
Oracle: the panic text itself, "Throttle expects backlogLimit to be positive" (throttle.go:50), asserts positivity, but the guarding condition is `opts.BacklogLimit < 0` (throttle.go:49), which allows exactly `0` — not positive. The message and the check disagree on their own terms, though this may be intentional (0 = "no backlog").
Type: in-repo
Confidence: low

### chi-15
Oracle: URLFormat's extension-detection guard `idx > 0` (url_format.go:62) is computed over `path[base:]`, a substring that still includes the leading `/` of the last segment. For a dotfile like `.env`, the dot lands at index 1 of that substring (right after the slash), so it still passes `idx > 0` even though there is no filename before the dot — the guard's own arithmetic doesn't achieve what it appears intended to guard against.
Type: in-repo
Confidence: medium

### chi-16
Oracle: same router preference established in mux.go:460-464 (RoutePath, then RawPath, then Path). `StripSlashes` (strip.go:16-22) falls back straight to `r.URL.Path` when `rctx.RoutePath` is empty, skipping `RawPath`, so it diverges from the router's own resolution order for raw-encoded paths.
Type: in-repo
Confidence: high

### chi-17
Oracle: RFC 9110 §5.6.6 (quoted-string) makes `charset="utf-8"` and `charset=utf-8` equivalent parameter values; `contentEncoding`'s `split` helper (content_charset.go:35-39) never strips quote characters, so it treats them as literal content and fails to match.
Type: known-external
Confidence: high

### chi-18
Oracle: Go's `net/http` documents that `http.TimeFormat` "is the time format to use ... generating times in this format requires the time to be in UTC"; `Sunset` (sunset.go:15-16) calls `sunsetAt.Format(http.TimeFormat)` directly on a `time.Time` that may carry a non-UTC location, so a non-UTC value formats with local wall-clock numbers but the literal, misleading `GMT` suffix baked into the layout string.
Type: known-external
Confidence: high

### chi-19
Oracle: RFC 9110 §15.4.5 and §15.3.5 specify that 204 and 304 responses must not have a message body, so compressing them is meaningless; `Close()` (compress.go:387-392) then writes gzip trailer bytes to a body-less response, and the resulting write error (`http.ErrBodyNotAllowed`, a documented net/http sentinel) is discarded (`return c.Close()` value never checked by the caller path via `defer cw.Close()` in Handler).
Type: implicit
Confidence: high

### chi-20
Oracle: `r.RequestURI` already includes the query string (documented on `http.Request.RequestURI`); `Profiler`'s handlers (profiler.go:27, 30) append `"/pprof/"`/`"/"` directly onto `r.RequestURI`, so for a request with a query string the appended path segment lands after the `?`, producing a `Location` where the intended path component is inside the query string — a malformed URL per RFC 3986 §3 (path precedes query).
Type: known-external
Confidence: high

### chi-21
Oracle: RFC 3986 §2.1/§3.3 — percent-encoding of reserved characters (`%2F`, `%3F`) changes their syntactic role once decoded (a decoded `%2F` becomes a path separator, a decoded `%3F` becomes a query delimiter). `RedirectSlashes` (strip.go:51-62) builds `Location` from the already-decoded path with no re-escaping, so `%3Fb` becomes a literal `?b` and `%2Fb` becomes an extra path segment in the redirect target.
Type: known-external
Confidence: high

### chi-22
Oracle: `rctx.Routes` is set exactly once, at the top-level `Mux.ServeHTTP` (mux.go:82-83, only when no existing route context is found), and is never reassigned when the request descends into a mounted sub-router. `GetHead` (get_head.go:29) calls `rctx.Routes.Match(tctx, "HEAD", routePath)` using the sub-router's *relative* `routePath` against the *parent* router's route table, which doesn't contain that relative pattern, so the look-ahead always fails to find the sub-router's own HEAD handler and falls through to GET.
Type: in-repo
Confidence: high

### chi-23
Oracle: RFC 9110 §15.2 defines 1xx responses as informational, separate from and preceding the final response; nothing in `WriteHeader` (compress.go:310-316) special-cases informational status codes, so calling it with `103` permanently sets `cw.wroteHeader = true` and locks in a compressibility decision made from headers that existed before the real, final response headers were set.
Type: known-external
Confidence: high

### chi-24
Oracle: `subtle.ConstantTimeCompare` exists specifically to avoid timing side channels in secret comparisons (its own doc: for comparing secret values); `BasicAuth` (basic_auth.go:19-20) short-circuits on a plain Go map lookup (`credUserOk`) before ever reaching the constant-time compare, so whether a username exists is observable via timing even though the password comparison itself is protected. Whether this rises to a practical defect is debatable since usernames aren't usually treated as secret.
Type: known-external
Confidence: low

### chi-25
Oracle: `Handler` (compress.go:219) explicitly checks `if encoder != nil` before using it, showing the code is aware an encoder can come back nil — but `selectEncoder` (compress.go:249-251) still returns the non-empty encoding *name* regardless of whether the constructor succeeded, and `WriteHeader` (compress.go:328) sets `Content-Encoding` purely from that non-empty name, not from whether an encoder was actually installed. The contradiction is visible directly between these two functions.
Type: in-repo
Confidence: high

### chi-26
Oracle: Go's `net/url` documentation for `URL.EscapedPath`/`RawPath` states RawPath is only honored when it is a valid encoding of Path, and downstream code is told to prefer `EscapedPath()` over reading `RawPath` directly. `StripSlashes` (strip.go:25-26) edits `r.URL.Path` but leaves `RawPath` untouched, so the invariant is only broken if some later code reads `RawPath` directly rather than through `EscapedPath()`; Go's own accessor is documented to self-correct in that case, which weakens confidence this is a live-impact defect.
Type: known-external
Confidence: low

### chi-27
Oracle: RFC 9110 §12.5.3 specifies `Accept-Encoding` tokens as exact content-coding names in a comma list; `matchAcceptEncoding` (compress.go:260-267) uses `strings.Contains`, a substring test, so any token that happens to contain the encoder name as a substring (`xgzip`, `x-gzip-foo`) is wrongly accepted.
Type: known-external
Confidence: high

### chi-28
Oracle: `Mux.Mount` (mux.go:295, specifically the `mountHandler` closure at mux.go:322-328) deliberately rewrites `rctx.RoutePath` to the *remainder* of the path past the mount prefix so the sub-router can match against its own relative patterns. `RedirectSlashes` (strip.go:44-49) builds its `Location` straight from that same relative `rctx.RoutePath`, so it necessarily loses the `/api` prefix that `Mount` stripped, producing a redirect to the wrong absolute URL.
Type: in-repo
Confidence: high

### chi-29
Oracle: `ContentCharset` (content_charset.go:13-15) lower-cases the caller-supplied `charsets` slice in place (`charsets[i] = strings.ToLower(c)`), mutating the caller's backing array as a side effect. The sibling middleware `AllowContentEncoding` (content_encoding.go:11-14) does the equivalent normalization by building a *new* map instead of touching the input slice — an established in-repo convention this function doesn't follow.
Type: in-repo
Confidence: medium

### chi-30
Oracle: `contentEncoding`/`split` (content_charset.go:35-39, 43-51) locate the charset parameter with a raw `strings.Cut(str, "charset=")`, a substring search with no boundary check for a preceding `;` or param-name match, so any string ending in `charset=` (`xcharset=`, `x-charset=`) is treated as the charset parameter. Visible directly from reading the parsing logic.
Type: in-repo
Confidence: high

### chi-31
Oracle: the IETF `Deprecation` HTTP header draft (draft-ietf-httpapi-deprecation-header) specifies the header's value as an IMF-fixdate, the same format as `Sunset`/`Date`; `Sunset` (sunset.go:16) using `http.TimeFormat` for both headers matches that expectation, so this observed behavior looks like it's actually spec-compliant rather than a defect — I can't point to anything that says it's wrong.
Type: known-external
Confidence: low

### chi-32
Oracle: `Mux.Match`'s own doc explicitly warns "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()" (mux.go:367-371, mirrored in chi.go:128-131). `SupressNotFound` (supress_notfound.go:18-19) ignores that warning and passes the *live* request `rctx` into `Match` for a look-ahead before real routing runs, so the look-ahead's own URLParam writes accumulate into the same context the real match later writes into — directly producing the doubled `URLParams.Keys` and the mount-related 404s.
Type: in-repo
Confidence: high

### chi-33
Oracle: `compressResponseWriter` in this same package tracks a `wroteHeader` bool specifically to guard against exactly this class of problem (compress.go:290, 310-316: "Allow multiple calls to propagate" only after checking `cw.wroteHeader`). `Timeout`'s deferred handler (timeout.go:36-41) has no equivalent tracking and unconditionally calls `w.WriteHeader(504)` on deadline expiry even if the handler already wrote a response — the established in-repo pattern for this exact hazard exists elsewhere in the package and isn't applied here.
Type: in-repo
Confidence: high

### chi-34
Oracle: RFC 9110 §8.3.1 states media type names are case-insensitive; `isCompressible` (compress.go:296-300) does a case-sensitive map lookup against `contentTypes`, and `defaultCompressibleContentTypes` (compress.go:16-32) are all lowercase, so a mixed-case `Content-Type` value or a mixed-case type passed to `NewCompressor` never matches.
Type: known-external
Confidence: high

### chi-35
Oracle: `ClientIPFromHeader`'s own doc comment (client_ip.go:19-41) frames it as being for headers your proxy "unconditionally OVERWRITES" and carrying a single IP, and states the fail-closed philosophy explicitly elsewhere in the same file for `ClientIPFromXFF` ("Fail-closed if the last value doesn't parse: no client IP is set"). A comma-embedded single header line failing to parse and yielding no IP is consistent with that documented fail-closed design rather than contradicting it, so I'm not confident this is a defect versus working-as-designed for a header contract that was never meant to carry a list.
Type: in-repo
Confidence: low

### chi-36
Oracle: `Route`/`RouteAny` (route_headers.go:49, 59) lower-case the header *name* before storing, but the match *value* passed to `NewPattern(match)` (route_headers.go:54, 66) is stored verbatim, while `Handler` (route_headers.go:91) lower-cases the incoming request's header value before comparing. The name-normalization and value-normalization are applied asymmetrically within the same small block of code, directly visible by reading it.
Type: in-repo
Confidence: high

---

The hardest to classify were the ones where the "bug" depends on reading intent rather than a clear contradiction: chi-31 (Deprecation header format actually looks spec-correct, so it may not be a defect at all), chi-14 (a docstring/message says "positive" but the code's `0`-allowing behavior may be deliberate), chi-26 and chi-35 (both technically deviate from a strict reading of a doc/invariant, but Go's own `net/url` self-correction and the package's own stated fail-closed philosophy respectively make it plausible the observed behavior is intended, not broken). chi-32 and chi-22 were conceptually the trickiest to trace (they required following `rctx.Routes`/`Mount`'s RoutePath rewriting through multiple files) but once traced, the in-repo contradiction was unambiguous, so confidence ended up high despite the extra work.
