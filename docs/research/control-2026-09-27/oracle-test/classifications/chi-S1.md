# chi, classifier S1 (Claude Sonnet), blind

### chi-01
Oracle: RFC 7230 §6.1 defines `Connection` as a comma-separated list of tokens, so an upgrade request can legitimately arrive as `keep-alive, Upgrade`; the exact-string check at recoverer.go:39 only matches the bare token `Upgrade`, and the resulting net/http "WriteHeader on hijacked conn" log is the observable symptom.
Type: known-external
Confidence: high

### chi-02
Oracle: it panics (`slice bounds out of range`).
Type: implicit
Confidence: high

### chi-03
Oracle: RFC 9110 §12.5.3 — an Accept-Encoding coding with `q=0` is explicitly "not acceptable." `matchAcceptEncoding` (compress.go:260-267) does a plain `strings.Contains` on the raw token and never looks at `;q=`, so `gzip;q=0` is treated as accepting gzip.
Type: known-external
Confidence: high

### chi-04
Oracle: `Write` (compress.go:338-344) explicitly calls `cw.WriteHeader` before writing if `!cw.wroteHeader`, but `Flush` (compress.go:357-371) never does — it calls the underlying writer's Flush directly, which lets net/http implicitly send a 200 without ever running `cw.WriteHeader`'s compressibility/`Content-Encoding` logic. That in-repo asymmetry between `Write` and `Flush` is the tell.
Type: in-repo
Confidence: high

### chi-05
Oracle: the same file's own comment at compress.go:114-122 states HTTP "deflate" (RFC 2616) "stands for DEFLATE data... wrapped with zlib," but `encoderDeflate` (compress.go:406-411) calls `flate.NewWriter`, which produces raw DEFLATE, not zlib-wrapped data — a direct contradiction between the file's documented intent and its implementation.
Type: in-repo
Confidence: high

### chi-06
Oracle: `defaultCompressibleContentTypes` (compress.go:16-32) stores canonical, untrimmed strings like `"text/html"`; `isCompressible` (compress.go:294-308) only does `strings.Cut(contentType, ";")` and never trims the result, so `"text/html "` fails the map lookup against the sibling list in the same file.
Type: in-repo
Confidence: high

### chi-07
Oracle: chi's own router (mux.go:462-463) prefers `r.URL.RawPath` over `r.URL.Path` when routing; `PathRewrite` (path_rewrite.go:12) only rewrites `r.URL.Path`, leaving `RawPath` (and thus the router's view of the path) untouched.
Type: in-repo
Confidence: high

### chi-08
Oracle: same as chi-07 — mux.go:462-463 shows the router routes on `RawPath` when present; `SupressNotFound`'s look-ahead (supress_notfound.go:19) always passes `r.URL.Path`, so its decision can diverge from what the router will actually do.
Type: in-repo
Confidence: high

### chi-09
Oracle: Go's map iteration order is unspecified by the language spec; `HeaderRouter.Handler` (route_headers.go:86) ranges directly over the `map[string][]HeaderRoute`, so which header "wins" when two match is not deterministic. Nothing in the doc comment promises an order, so whether this counts as a defect (vs. an unsupported/undocumented case) is debatable.
Type: known-external
Confidence: medium

### chi-10
Oracle: mux.go:221-223 documents "[t]he default handler returns a 405 with an empty body" when a path matches a different method. `SupressNotFound` (supress_notfound.go:19) only calls `Match`, which reports path-existence, not method-match, so it substitutes its own 404 before the router ever reaches its documented 405 path.
Type: in-repo
Confidence: high

### chi-11
Oracle: `r.Header["Content-Encoding"]` (content_encoding.go:17) yields one string per header *line*, not per comma-separated token (RFC 7230 §3.2.2 treats repeated header lines as equivalent to one comma-joined field, but doesn't collapse a single line's own comma list into a slice); the code never splits on `,`, so one combined line fails the per-name lookup that two separate lines pass.
Type: known-external
Confidence: high

### chi-12
Oracle: the doc comment on `CleanPath` (clean_path.go:10-11) says it's for "double slash mistakes" (e.g. `//users////1` → `/users/1`); `path.Clean` (clean_path.go:23) also collapses a legitimate single trailing slash, which is outside what the comment documents and breaks routes registered with a trailing slash.
Type: in-repo
Confidence: high

### chi-13
Oracle: Go's `net/http` server strips the `Host` header into `r.Host` and does not populate it in `r.Header` — well-known stdlib `Request` contract. `HeaderRouter.Handler` (route_headers.go:87) reads `r.Header.Get(header)`, so a `"Host"` route can never match a real server request.
Type: known-external
Confidence: high

### chi-14
Oracle: the panic text itself, "`Throttle expects backlogLimit to be positive`" (throttle.go:50), says "positive," but the guard is `opts.BacklogLimit < 0` (throttle.go:49), which accepts `0` — the message and the enforced constraint disagree. This may be intentional loose wording rather than a real defect.
Type: in-repo
Confidence: medium

### chi-15
Oracle: the doc example for `URLFormat` (url_format.go:23-32) illustrates extensions on named resources (`articles/1.json`), implying a basename before the dot; the index arithmetic at url_format.go:58-60 (`base := strings.LastIndex(path, "/")`, then searching `path[base:]`, which still includes the leading `/`) doesn't actually exclude a dot immediately after the slash, so dotfiles like `.env` or `.well-known` get misparsed as `name + extension`. The intended exclusion is inferable from the code's own `idx > 0` guard but the guard doesn't achieve it given the off-by-slice.
Type: in-repo
Confidence: low

### chi-16
Oracle: same pattern as chi-07/08/26 — mux.go:462-463 shows the router's own preference for `RawPath`; `StripSlashes` (strip.go:16-29) falls back to the decoded `r.URL.Path` when `rctx.RoutePath` is empty, producing route-path/actual-routing divergence for escaped slashes.
Type: in-repo
Confidence: high

### chi-17
Oracle: RFC 9110 §5.6.4 / media-type parameter grammar allows a parameter value to be a `quoted-string`; a compliant charset comparison should strip quotes before matching. `split`/`contentEncoding` (content_charset.go:35-50) only trims whitespace, never quotes, so `charset="utf-8"` never equals `"utf-8"`.
Type: known-external
Confidence: high

### chi-18
Oracle: Go's `http.TimeFormat`/`time.Format` documentation is explicit that the time must already be in UTC for `Format` to render GMT correctly — `Format` does not itself convert timezones. `Sunset` (sunset.go:15-16) calls `sunsetAt.Format(http.TimeFormat)` directly without `.UTC()`, so a non-UTC `time.Time` prints its local wall-clock value mislabeled `GMT`.
Type: known-external
Confidence: high

### chi-19
Oracle: RFC 9110 §6.4.1/§15.3.5 forbid a message body on 204/304 responses; `compressResponseWriter.WriteHeader`/`Close` (compress.go:310-336, 387-392) set `Content-Encoding`/`Vary` and later write gzip framing regardless of status code, and `Handler`'s `defer cw.Close()` (compress.go:224) discards the `error` that `Close()` (compress.go:387-392) itself is typed to return.
Type: known-external
Confidence: high

### chi-20
Oracle: a correct redirect must place the path suffix inside the path component, before any query string (RFC 3986 URI syntax: path precedes query). `Profiler` (profiler.go:27, 30) builds the Location by string-appending `"/pprof/"` directly onto `r.RequestURI`, which already includes `?x=1`, producing a syntactically malformed target.
Type: known-external
Confidence: high

### chi-21
Oracle: percent-encoded reserved characters (`%2F`, `%3F`) change meaning if decoded and re-emitted unescaped in a URI (RFC 3986 §2.2/§6.2.2.2); `RedirectSlashes` (strip.go:51-62) builds `Location` from the already-decoded path without re-escaping, so `%3F` becomes a literal `?`.
Type: known-external
Confidence: high

### chi-22
Oracle: `Mux.ServeHTTP` (mux.go:70-74) explicitly reuses the parent's routing `Context` when one already exists on the request ("Check if a routing context already exists from a parent router") rather than resetting `rctx.Routes = mx` for the mounted sub-router. `GetHead`'s look-ahead (get_head.go:29, `rctx.Routes.Match(...)`) therefore searches the *parent's* route tree even when running as sub-router middleware, missing a HEAD handler registered only on the sub-router (or matching a same-path HEAD route on the parent instead).
Type: in-repo
Confidence: high

### chi-23
Oracle: `WriteHeader` (compress.go:310-316) sets `cw.wroteHeader = true` on the very first call and computes `isCompressible()`/sets `Content-Encoding` only on that first call; any later call (including the real final status) takes the `if cw.wroteHeader { ...; return }` branch and never re-evaluates. A 1xx interim response is not supposed to finalize the real response's processing (RFC 9110 §15.2), but the code's own early-return branch is what locks in the decision.
Type: in-repo
Confidence: high

### chi-24
Oracle: standard timing-side-channel/constant-time-comparison practice — comparing against a known-invalid credential without running the constant-time comparison lets an attacker distinguish "valid username" from "invalid username" by response timing. `BasicAuth` (basic_auth.go:20) only calls `subtle.ConstantTimeCompare` when `credUserOk` is true.
Type: known-external
Confidence: medium

### chi-25
Oracle: `selectEncoder` (compress.go:249-250) returns `(fn(w, c.level), name, ...)` unconditionally once a name matches `encodingPrecedence`, even though `fn` (here `encoderGzip`) can itself return `nil` for an invalid level (compress.go:398-404); `Handler` (compress.go:219) only swaps in the encoder `if encoder != nil`, so `cw.w` stays the plain writer while `cw.encoding` is still `"gzip"` — an internal invariant break between the returned name and the returned writer, visible entirely within compress.go.
Type: in-repo
Confidence: high

### chi-26
Oracle: same RawPath-preference contract shown at mux.go:462-463; `StripSlashes` with no route context (strip.go:25-26) mutates `r.URL.Path` only, leaving `r.URL.RawPath` (and thus the router's actual routing input) unchanged.
Type: in-repo
Confidence: high

### chi-27
Oracle: RFC 9110 §12.5.3 — Accept-Encoding codings are compared as whole tokens (case-insensitively), not substrings. `matchAcceptEncoding` (compress.go:260-267) uses `strings.Contains(v, encoding)`, so `"xgzip"` or `"x-gzip-foo"` spuriously match `"gzip"`.
Type: known-external
Confidence: high

### chi-28
Oracle: `Mux.Mount`'s `mountHandler` (mux.go:323-327) shifts `rctx.RoutePath` to be relative to the sub-router (`mx.nextRoutePath`), stripping the mount prefix. `RedirectSlashes` (strip.go:44-49) builds its `Location` from that already-shifted `rctx.RoutePath` rather than the external `r.URL.Path`, so a redirect issued from inside a mounted sub-router loses the `/api` prefix that the client actually needs.
Type: in-repo
Confidence: high

### chi-29
Oracle: Go slices/variadic-slice semantics — `charsets ...string` shares the backing array with a caller-passed slice, so in-place mutation (`charsets[i] = strings.ToLower(c)` at content_charset.go:13-14) is visible to the caller. Well-known Go language behavior, not something the chi docs discuss.
Type: known-external
Confidence: high

### chi-30
Oracle: RFC 9110 §8.3.1 defines media-type parameters as discrete `name=value` pairs; a correct parser must match the parameter name exactly (`charset`), not any string that happens to end in `charset=`. `split(ce, "charset=")` (content_charset.go:37) is an unanchored substring cut, so `"xcharset=utf-8"` or `"x-charset=utf-8"` are misread as the `charset` parameter.
Type: known-external
Confidence: high

### chi-31
Oracle: RFC 9745 (the Deprecation HTTP header field spec) itself specifies the Deprecation value as an IMF-fixdate, the same format as Sunset's RFC 8594 — so emitting both headers in the same `http.TimeFormat` (sunset.go:16) actually matches the external spec rather than violating it.
Type: known-external
Confidence: low

### chi-32
Oracle: `Mux.Find`'s doc comment (mux.go:380-381) is explicit: "the `*Context` state is updated during execution, so manage the state carefully or make a `NewRouteContext()`." `SupressNotFound` (supress_notfound.go:19) calls `rctx.Routes.Match(rctx, ...)` using the *request's own* `rctx` instead of a fresh one, directly against that documented warning — which is exactly what produces the duplicated `URLParams.Keys` and the mount-interaction 404.
Type: in-repo
Confidence: high

### chi-33
Oracle: it's a superfluous/duplicate `WriteHeader` call after a response has already been committed — `net/http` itself detects and logs this (observable "superfluous WriteHeader" error), and the client already received the original `200` regardless of the later `w.WriteHeader(504)` call (timeout.go:39).
Type: implicit
Confidence: high

### chi-34
Oracle: RFC 9110 §8.3.1 — media type and subtype tokens are case-insensitive. `isCompressible` (compress.go:296-300) does an exact, case-sensitive map lookup against `contentTypes`/`contentWildcards`, so `"Text/HTML"` never matches `"text/html"`.
Type: known-external
Confidence: high

### chi-35
Oracle: the function's own doc comment (client_ip.go:19-38) describes this as a "single-IP header" contract and explicitly documents "fail-closed if the last value doesn't parse: no client IP is set." A comma-joined value like `"6.6.6.6, 1.2.3.4"` simply fails `netip.ParseAddr` and falls into that documented fail-closed path — this looks like intended behavior for a misused/misconfigured header rather than a defect.
Type: in-repo
Confidence: low

### chi-36
Oracle: `HeaderRouter.Route` (route_headers.go:48-49) lowercases the header *name* but never the `match` value passed into `NewPattern`; `Handler` (route_headers.go:91) then lowercases the incoming `headerValue` before comparing it against that still-original-case stored pattern — a direct, visible inconsistency within the same file/struct.
Type: in-repo
Confidence: high

---

The hardest to classify were chi-31 and chi-35: both read, on the surface, like the rest of the list (a specific, concretely observed behavior), but tracing them against what I actually know of the relevant spec (RFC 9745 for Deprecation) and against the function's own documented contract (the "single-IP header, fail-closed" doc comment for `ClientIPFromHeader`) suggests they may not be defects at all, just correct-but-surprising behavior — which made me uncertain whether "type" should describe the oracle for the *described* behavior or an oracle that argues the behavior is fine. chi-09 (map iteration order) and chi-24 (timing side channel) were also awkward: both have a real, nameable oracle (Go spec unspecified iteration order; constant-time-comparison practice), but neither the code nor the docs states an explicit requirement that the observed behavior violates, so confidence sits at medium rather than high. chi-15 and chi-22 required tracing multi-step control flow (index arithmetic in URLFormat; routing-context reuse across `Mount`) rather than pointing at a single line, which made pinning down a precise, quotable oracle slower and lower-confidence than the more mechanical mismatches (e.g. chi-06, chi-36).
