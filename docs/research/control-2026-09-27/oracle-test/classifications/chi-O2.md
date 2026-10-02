# chi, classifier O2 (Claude Opus), blind

### chi-01
Oracle: RFC 9110 §7.6.1 says `Connection` is a comma-separated list of tokens that are not case-sensitive. The exact-string check `r.Header.Get("Connection") != "Upgrade"` (recoverer.go:39) misses `keep-alive, Upgrade` and `upgrade`. The visible symptom is only a net/http log line about WriteHeader on a hijacked connection.
Type: known-external
Confidence: medium

### chi-02
Oracle: With no `/` in the path, `strings.LastIndex(path, "/")` returns -1, so `path[base:]` at url_format.go:60 panics with slice bounds out of range.
Type: implicit
Confidence: high

### chi-03
Oracle: RFC 9110 §12.5.3 says `q=0` marks a coding as "not acceptable". `matchAcceptEncoding` (compress.go:260-267) ignores q-values and only does a substring match on each token.
Type: known-external
Confidence: high

### chi-04
Oracle: RFC 9110 §8.4 requires a compressed body to be declared by `Content-Encoding`. Here the headers go out on the uncompressed path during `Flush`, and the body is then gzip. The repo's own `WriteHeader` (compress.go:328-331) always sets `Content-Encoding` whenever `compressible=true`, and that pairing breaks here. The net/http "superfluous WriteHeader" log confirms it.
Type: known-external
Confidence: high

### chi-05
Oracle: The comment at compress.go:114-116 says HTTP "deflate" means "DEFLATE data (RFC 1951) wrapped with zlib (RFC 1950)". `encoderDeflate` uses raw `flate.NewWriter` with no zlib wrapper; RFC 9110 §8.4.1.2 says the same thing as the comment. The existing test (compress_test.go, reading with `flate.NewReader`) locks in the raw behaviour.
Type: in-repo
Confidence: high

### chi-06
Oracle: RFC 9110 §8.3.1 allows optional whitespace before `;` in a media type. `strings.Cut(contentType, ";")` at compress.go:297 is not trimmed, so `"text/html "` misses the lookup. By contrast, the sibling `split()` in content_charset.go:43-50 does trim.
Type: known-external
Confidence: medium

### chi-07
Oracle: chi routes on `r.URL.RawPath` when it is set (mux.go:461-464), and sibling middlewares (get_head.go:16-20, clean_path.go:18-22) check RawPath too. PathRewrite (path_rewrite.go:12) rewrites only `Path`, so encoded requests route on the old path. Go's `url.URL` contract also says RawPath must be kept consistent with Path.
Type: in-repo
Confidence: high

### chi-08
Oracle: The router picks its routing path as `rctx.RoutePath`, then `RawPath`, then `Path` (mux.go:460-465), and GetHead (get_head.go:14-21) copies that order for its look-ahead. SupressNotFound's look-ahead (supress_notfound.go:19) uses `r.URL.Path` only, so it can disagree with the router.
Type: in-repo
Confidence: high

### chi-09
Oracle: The comment at route_headers.go:85 says "find first matching header route", but `HeaderRouter` is a map. Go map iteration order is randomized (a Go language rule), so there is no stable "first" across headers.
Type: in-repo
Confidence: medium

### chi-10
Oracle: The docstring says it responds 404 "if the route is not found". Here the route exists and only the method differs, which the router itself answers with 405 (mux.go:494-495, `methodNotAllowed`). `Match` returns false for a method mismatch, so the 405 becomes a 404.
Type: in-repo
Confidence: medium

### chi-11
Oracle: Under RFC 9110 §8.4, `Content-Encoding` is a `#content-coding` list, and §5.3 says one comma-joined line means the same as several lines. content_encoding.go:24-25 treats each header line as a single token. The comment "All encodings in the request must be allowed" shows each coding was meant to be checked separately.
Type: known-external
Confidence: high

### chi-12
Oracle: The docstring (clean_path.go:10-11) says CleanPath cleans "double slash mistakes". `path.Clean` also drops trailing slashes (Go stdlib contract), which makes a registered `/users/` route unreachable.
Type: in-repo
Confidence: high

### chi-13
Oracle: The RouteHeaders docstring's main example (route_headers.go:11-21) routes on `Route("Host", "example.com", ...)`. But net/http moves `Host` into `r.Host` and removes it from `r.Header` on server requests, so `r.Header.Get("host")` is empty. The test only passes because it sets `req.Header.Set("Host", ...)` by hand (route_headers_test.go:54).
Type: in-repo
Confidence: high

### chi-14
Oracle: The check is `< 0`, so 0 is allowed on purpose, and TestThrottleRetryAfter (throttle_test.go:208) uses `BacklogLimit: 0`. The only problem is that the panic text says "positive" when it means "non-negative". That is a wording issue, not a behaviour defect.
Type: none
Confidence: low

### chi-15
Oracle: I can't point to anything that says a leading-dot segment is not an extension. Go's `path.Ext("/files/.env")` also returns `.env`, and the docstring only says it "parses the url extension".
Type: none
Confidence: low

### chi-16
Oracle: The router uses `RawPath` when `RoutePath` is empty (mux.go:461-464), as do the siblings GetHead and CleanPath. StripSlashes (strip.go:18-22) falls back to the decoded `r.URL.Path`, so `%2F` paths route differently.
Type: in-repo
Confidence: high

### chi-17
Oracle: RFC 9110 §5.6.6 allows a parameter value to be a quoted-string, so `charset="utf-8"` is the same as `charset=utf-8`. `contentEncoding` (content_charset.go:35-39) never removes the quotes.
Type: known-external
Confidence: high

### chi-18
Oracle: The net/http docs for `http.TimeFormat` say to make sure the time is in UTC before formatting, because the layout hard-codes "GMT". RFC 9110 §5.6.7 IMF-fixdate is also GMT. sunset.go:15-16 never calls `.UTC()`.
Type: known-external
Confidence: high

### chi-19
Oracle: RFC 9110 §15.3.5 and §15.4.5 say 204 and 304 carry no content. Adding `Content-Encoding`/`Vary` and then writing gzip framing is wrong, and the resulting `http.ErrBodyNotAllowed` is dropped. The client-visible effect is only the extra headers.
Type: known-external
Confidence: medium

### chi-20
Oracle: net/http documents `Request.RequestURI` as the unmodified request-target, query string included, so appending `/pprof/` to it lands after the query. The sibling RedirectSlashes (strip.go:59-61) builds path and query separately.
Type: known-external
Confidence: high

### chi-21
Oracle: RFC 3986 §2.2 says reserved characters like `?` and `/` change meaning when decoded. Putting the decoded path into `Location` (strip.go:57-62) turns `%3F` into a query separator and `%2F` into a path separator. The router itself routes on `RawPath` (mux.go:461-464).
Type: known-external
Confidence: high

### chi-22
Oracle: The docstring says "GetHead automatically route undefined HEAD requests to GET handlers". Here HEAD is defined but GET runs. The cause: in a mounted sub-router, `rctx.Routes` is still the parent mux, because `Mux.ServeHTTP` (mux.go:71-74) reuses the existing rctx, so get_head.go:29 looks up the wrong router.
Type: in-repo
Confidence: high

### chi-23
Oracle: net/http's ResponseWriter contract allows 1xx informational `WriteHeader` calls before the final status. compress.go:310-316 sets `wroteHeader` and decides compressibility on the 1xx call. The comment "Allow multiple calls to propagate" suggests multiple calls were expected.
Type: known-external
Confidence: medium

### chi-24
Oracle: The code uses `subtle.ConstantTimeCompare`, which shows constant-time checking was intended, and skipping it for unknown usernames (basic_auth.go:20) creates a timing difference. The leak is small, though: the map lookup dominates, and `ConstantTimeCompare` already returns early when lengths differ.
Type: in-repo
Confidence: low

### chi-25
Oracle: The `EncoderFunc` contract (compress.go:271) says "In case of failure, the function should return nil". `Handler` (compress.go:219-221) handles a nil encoder by writing plaintext, but `selectEncoder` still returns the encoding name. The result is a plaintext body labelled `Content-Encoding: gzip`.
Type: in-repo
Confidence: high

### chi-26
Oracle: Go's `url.URL` contract says `RawPath` is only a hint that must stay a valid encoding of `Path`. Trimming `Path` alone (strip.go:25-26) leaves the two out of sync, so `EscapedPath()` quietly drops RawPath. I can't point to a concrete failure this causes outside chi.
Type: known-external
Confidence: low

### chi-27
Oracle: RFC 9110 §12.5.3 treats Accept-Encoding entries as whole content-coding tokens, so `xgzip` is not `gzip`, yet compress.go:262 uses `strings.Contains`. One caveat: RFC 9110 §8.4.1.3 does make `x-gzip` a real alias for gzip, so part of the example is actually correct.
Type: known-external
Confidence: medium

### chi-28
Oracle: The docstring (strip.go:36-37) says it redirects "to the same path, less the trailing slash". Inside a mounted sub-router it uses the sub-relative `rctx.RoutePath`, so the `/api` prefix is lost and the redirect points at a different resource.
Type: in-repo
Confidence: high

### chi-29
Oracle: Nothing in the repo says ContentCharset must not change its arguments. The only basis is the Go rule that a variadic called with `slice...` shares the caller's backing array, plus the general expectation that functions don't mutate their inputs.
Type: none
Confidence: low

### chi-30
Oracle: Under RFC 9110 §5.6.6, parameter names are whole tokens, so `xcharset` is a different parameter from `charset`. `split(ce, "charset=")` at content_charset.go:37 matches a substring. The docstring's "if none of the charsets match" means the charset parameter specifically.
Type: known-external
Confidence: medium

### chi-31
Oracle: RFC 9745 defines `Deprecation` as a Structured Field Date (`@<unix-seconds>`), not an IMF-fixdate. It also means the deprecation date, which is not the same thing as the sunset date. The in-repo test (sunset_test.go:40) locks in the current format, so the repo contradicts the RFC.
Type: known-external
Confidence: medium

### chi-32
Oracle: The `Find` doc note (mux.go:380-381) says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". GetHead does make a fresh context (get_head.go:24). SupressNotFound passes the live rctx, which corrupts `RoutePath`/`URLParams`.
Type: in-repo
Confidence: high

### chi-33
Oracle: net/http's ResponseWriter contract says `WriteHeader` after headers are sent does nothing and logs "superfluous". timeout.go:36-41 calls it anyway once the deadline has passed. The client still gets the correct 200, so the only harm is the log line and a misleading docstring.
Type: known-external
Confidence: medium

### chi-34
Oracle: RFC 9110 §8.3.1 says media type and subtype are not case-sensitive. compress.go:88 and 300 compare exactly. Sibling code does normalize case: `SetEncoder` lower-cases at compress.go:168, and AllowContentEncoding does too.
Type: known-external
Confidence: medium

### chi-35
Oracle: The code is doing what the repo says it should. The docstring (client_ip.go:19-20) says this is for a "single-IP header", and the test case `{"multiple_ips", "100.100.100.100,200.200.200.200", ""}` (client_ip_test.go:26) explicitly expects no IP (fail-closed). Nothing I can find calls it a defect.
Type: none
Confidence: low

### chi-36
Oracle: `Handler` lower-cases the request value (route_headers.go:91) and `Route` lower-cases the header name (route_headers.go:49), so case-insensitive matching is clearly intended. `NewPattern` stores the match value as given, so a mixed-case pattern can never match. RFC 3986 host case-insensitivity points the same way.
Type: in-repo
Confidence: high

**Hardest to classify.** The hardest were the ones where an in-repo test locks in the flagged behaviour against an outside rule:
- **chi-05:** raw DEFLATE is tested with `flate.NewReader`, but the repo's own comment defines "deflate" as zlib-wrapped.
- **chi-31:** the IMF-fixdate `Deprecation` value is tested, but RFC 9745 says otherwise.
- **chi-35:** a comma-joined header value yields no IP, and that is tested as the intended fail-closed behaviour.

In these cases the repo contradicts itself or the RFC, so "in-repo" can point either way. I chose based on which source actually defines "correct".

A second group was hard because the mechanism is clear but nothing says the result is wrong:
- **chi-15:** Go's `path.Ext` also treats dotfiles as extensions.
- **chi-29:** changing the caller's slice in place.
- **chi-24:** a timing leak that `ConstantTimeCompare`'s early return on length mismatch already weakens.
- **chi-26:** RawPath out of sync with no concrete consumer shown to fail.

chi-09 and chi-13 were close calls between in-repo and known-external, because the docstring and comment give the intent while the Go/net/http rules explain the failure.
