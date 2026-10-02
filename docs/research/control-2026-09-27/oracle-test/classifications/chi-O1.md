# chi, classifier O1 (Claude Opus), blind

### chi-01
Oracle: RFC 9110 §7.6.1 says `Connection` is a comma-separated list of tokens that are matched case-insensitively. So `keep-alive, Upgrade` and `upgrade` are upgrade requests too, but recoverer.go:39 only exempts the exact string `"Upgrade"`. The net/http Hijacker contract (don't use the ResponseWriter after Hijack) is the second oracle.
Type: known-external
Confidence: medium

### chi-02
Oracle: The code panics. When `path` has no `/`, `strings.LastIndex` returns -1, and `path[base:]` at url_format.go:60 slices with a negative index.
Type: implicit
Confidence: high

### chi-03
Oracle: RFC 9110 §12.5.3 says a coding with `q=0` is "not acceptable". matchAcceptEncoding (compress.go:260-267) ignores q-values, so it still picks gzip.
Type: known-external
Confidence: high

### chi-04
Oracle: compress.go:328-331 shows the rule the code intends: whenever the body goes through the encoder, `Content-Encoding` is set first. Calling Flush before any write sends the headers through the plain writer. The later Write then marks the response compressible and gzips the body after the headers have gone out. The result is a gzip body with no `Content-Encoding`, which clients can't decode (RFC 9110 §8.4), plus net/http's superfluous-WriteHeader log.
Type: in-repo
Confidence: high

### chi-05
Oracle: RFC 9110 §8.4.1.2 defines `deflate` as zlib-wrapped data (RFC 1950), and the repo's own comment at compress.go:114-116 says the same. `flate.NewWriter` produces raw DEFLATE instead. The same comment also admits old browsers expected raw data, and compress_test.go's `decodeResponseBody` decodes with `flate.NewReader`, so the repo contradicts itself here.
Type: known-external
Confidence: medium

### chi-06
Oracle: RFC 9110 §8.3.1 / §5.6.6 allow optional whitespace (OWS) before `;` in a media type. The unparsed `"text/html "` never matches the allowed-types map. Other parsers in the repo (content_charset.go:43-50 `split`) trim whitespace; this one doesn't.
Type: known-external
Confidence: medium

### chi-07
Oracle: The router routes on `r.URL.RawPath` whenever it is set (mux.go:460-466). PathRewrite rewrites only `Path`, so the router still routes on the stale `RawPath` and the rewrite is lost for escaped paths.
Type: in-repo
Confidence: medium

### chi-08
Oracle: The router picks its path from `rctx.RoutePath`, then `RawPath`, then `Path` (mux.go:460-466). The sibling GetHead (get_head.go:13-20) copies that logic. SupressNotFound uses only `r.URL.Path`, so its look-ahead can disagree with the real routing.
Type: in-repo
Confidence: high

### chi-09
Oracle: The comment at route_headers.go:85 ("find first matching header route") implies one deterministic winner. But the loop ranges over a Go map, and the Go spec leaves map iteration order unspecified (and the runtime randomizes it).
Type: known-external
Confidence: medium

### chi-10
Oracle: The router answers 405 when the path exists under another method (mux.go:494-495, `methodNotAllowed`). The docstring (supress_notfound.go:9) scopes the middleware to "if the route is not found". `Match` returns false for a method mismatch, so the middleware turns a 405 into a 404.
Type: in-repo
Confidence: medium

### chi-11
Oracle: RFC 9110 §5.3 / §8.4 say a comma-separated list on one header line means the same as the same values on separate lines. The loop at content_encoding.go:24-29 treats the whole comma-joined line as a single encoding. The repo's own `walkXFF` (client_ip.go:226-247) shows the correct merge-and-split handling.
Type: known-external
Confidence: high

### chi-12
Oracle: The docstring (clean_path.go:9-10) scopes CleanPath to "clean out double slash mistakes". `path.Clean` also strips the trailing slash, which makes a registered `/users/` route unreachable.
Type: in-repo
Confidence: medium

### chi-13
Oracle: The type's own docstring (route_headers.go:12-19) gives `Route("Host", "example.com", ...)` as the headline example. But net/http moves the Host header into `r.Host` and deletes it from `r.Header` on server requests, so that example can never match.
Type: in-repo
Confidence: high

### chi-14
Oracle: `Throttle()` (throttle.go:33) itself passes `BacklogLimit: 0`, so accepting 0 is correct. The only flaw is the panic message: it says "positive" but the check is `< 0` (it should say non-negative).
Type: in-repo
Confidence: low

### chi-15
Oracle: The code seems to mean to exclude leading-dot names, but the guards don't work. The `idx > 0` guard at url_format.go:62 is dead because `path[base:]` always starts with `/`, so `idx >= 1` whenever there's a dot. That suggests a dot at the start of the segment was meant to be excluded. Still, "extension" is not defined anywhere in the repo, and Go's `path.Ext(".env")` returns `.env`.
Type: in-repo
Confidence: low

### chi-16
Oracle: The router routes on `RawPath` when `RoutePath` is empty (mux.go:462-463), and GetHead (get_head.go:15-20) does the same. StripSlashes falls back to the decoded `r.URL.Path`, so escaped paths route inconsistently depending on whether there's a trailing slash.
Type: in-repo
Confidence: high

### chi-17
Oracle: RFC 9110 §5.6.6 says a parameter value may be a token or a quoted-string, and the two forms are equivalent (`charset="utf-8"` equals `charset=utf-8`). contentEncoding keeps the quotes.
Type: known-external
Confidence: medium

### chi-18
Oracle: The net/http `TimeFormat` docs say the time "must be in UTC" to produce correct output. The layout hard-codes `GMT`, so a non-UTC time gets a wrong instant. sunset.go:15-16 never calls `.UTC()`.
Type: known-external
Confidence: high

### chi-19
Oracle: RFC 9110 §15.3.5 / §15.4.5 say 204 and 304 carry no content. Declaring `Content-Encoding` on them and then writing gzip framing is wrong. net/http rejects the write with `ErrBodyNotAllowed`, and the code silently discards that error.
Type: known-external
Confidence: medium

### chi-20
Oracle: net/http documents `RequestURI` as the unmodified request-target, query included. RFC 3986 §3 puts the path before `?query`. So appending `/pprof/` to `RequestURI` (profiler.go:27, 30) produces a malformed target.
Type: known-external
Confidence: high

### chi-21
Oracle: RFC 3986 §2.2 says reserved characters that are data must stay percent-encoded. Writing the decoded path into `Location` turns an encoded `?` into a query delimiter and `%2F` into a path separator, which changes the resource. The router itself routes on `RawPath` (mux.go:462), a second oracle.
Type: known-external
Confidence: medium

### chi-22
Oracle: The GetHead docstring (get_head.go:9) says it routes only *undefined* HEAD requests to GET. Inside a mounted sub-router, `rctx.Routes` is the top-level mux (it is set only at mux.go:83). The look-ahead therefore runs against the wrong tree with a path relative to the sub-router, and misses the defined `headHandler`.
Type: in-repo
Confidence: high

### chi-23
Oracle: The net/http `ResponseWriter.WriteHeader` contract says 1xx informational codes may be sent any number of times before the final status. compress.go:310-316 treats the 103 as the final header and makes the compressibility decision there, including `wroteHeader = true`.
Type: known-external
Confidence: medium

### chi-24
Oracle: The use of `subtle.ConstantTimeCompare` shows the code intends timing-safe checking, and the standard practice is to compare even for unknown users. But the timing difference here is tiny, and nothing in the repo promises the username check is constant-time.
Type: known-external
Confidence: low

### chi-25
Oracle: The `EncoderFunc` doc (compress.go:269-273) says "In case of failure, the function should return nil". Handler (compress.go:219-221) handles a nil encoder by keeping the plain writer, but selectEncoder still returns the name `gzip`. So the response declares gzip over an uncompressed body.
Type: in-repo
Confidence: high

### chi-26
Oracle: The chi router prefers `RawPath` over `Path` (mux.go:462-463). If StripSlashes sits outside a chi mux, it trims `Path` and leaves a stale `RawPath` that still ends in `/`, and a downstream chi router would route on that. (Go's `URL.EscapedPath` would drop the inconsistent `RawPath`, but chi reads the field directly.)
Type: in-repo
Confidence: low

### chi-27
Oracle: RFC 9110 §12.5.3 says `Accept-Encoding` entries are codings matched as whole tokens (case-insensitively), not by substring. `strings.Contains` at compress.go:262 accepts `xgzip`.
Type: known-external
Confidence: medium

### chi-28
Oracle: The RedirectSlashes docstring (strip.go:36-37) says it redirects "to the same path, less the trailing slash". Inside a mount, `rctx.RoutePath` is relative to the sub-router, so the `/api` prefix is lost and the redirect goes to a different resource.
Type: in-repo
Confidence: high

### chi-29
Oracle: The sibling `AllowContentEncoding` (content_encoding.go:11-14) normalizes into a fresh map and leaves the caller's arguments alone. ContentCharset writes into the caller's variadic backing array. No doc forbids this, so it's a convention argument.
Type: in-repo
Confidence: low

### chi-30
Oracle: RFC 9110 §5.6.6 says parameters are `name=value` pairs, with names matched as whole tokens. Splitting on the substring `charset=` (content_charset.go:37) matches parameters named `xcharset` and `x-charset`.
Type: known-external
Confidence: medium

### chi-31
Oracle: As far as I know, RFC 9745 (the Deprecation header) defines the value as a Structured Field Date (`@<unix-seconds>`), not an IMF-fixdate. Only `Sunset` (RFC 8594, cited at sunset.go:10) uses IMF-fixdate. I'd want to re-read RFC 9745 to be sure, and earlier drafts used a different format.
Type: known-external
Confidence: medium

### chi-32
Oracle: The `Mux.Find` doc (mux.go:380-381) says "the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()". GetHead follows that advice with `tctx := chi.NewRouteContext()` (get_head.go:24). SupressNotFound passes the live request context instead, which corrupts `RoutePath` and `URLParams`.
Type: in-repo
Confidence: high

### chi-33
Oracle: Under the net/http `ResponseWriter` contract, WriteHeader after the response has started is a no-op and gets logged as superfluous. The docstring's promise to "return a 504 ... to the client" (timeout.go:9-10) can't hold once the handler has written. The deferred call should check whether a response was already written.
Type: known-external
Confidence: medium

### chi-34
Oracle: RFC 9110 §8.3.1 says type and subtype are case-insensitive. The map lookup at compress.go:300 is exact, and NewCompressor stores caller types as given. For comparison, `SetEncoder` (compress.go:168) lower-cases its key.
Type: known-external
Confidence: medium

### chi-35
Oracle: The docstring (client_ip.go:33-38) says that with multiple values "the LAST value wins", and `walkXFF` (client_ip.go:226-228) treats comma-joined values as a list per the RFC. A comma-joined single line gives nothing instead of the last entry. But the same docstring's "fail-closed" wording could be read as allowing this result.
Type: in-repo
Confidence: medium

### chi-36
Oracle: The code normalizes one side of the comparison but not the other. `Route`/`RouteAny` lower-case the header *name* (route_headers.go:49, 59), and `Handler` lower-cases the request *value* (line 91), but `NewPattern` stores the match value unchanged. Any pattern with an upper-case letter can never match, which is an internal inconsistency.
Type: in-repo
Confidence: high

The hardest to classify were chi-15, chi-31, chi-05, chi-35 and chi-14.

- **chi-15:** Whether a dotfile has an "extension" isn't defined anywhere. The only oracle is the dead `idx > 0` guard, which hints at intent but proves nothing.
- **chi-31:** It depends on an RFC (9745) I can name but am not certain enough to quote. It's on the border between known-external and fetch-external.
- **chi-05:** The repo contradicts itself. The comment describes zlib-wrapped deflate, but the test decodes raw flate, so the current behaviour may be deliberate.
- **chi-35:** The docstring supports both "last comma entry wins" and "fail closed", so whether this is a defect depends on intent I can't recover.
- **chi-14:** The behaviour is correct and only the panic message is wrong, which makes "defect" a stretch.
