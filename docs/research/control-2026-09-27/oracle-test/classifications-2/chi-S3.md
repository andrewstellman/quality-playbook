chi-01 | line | The exact-match `!= "Upgrade"` comparison is visible in the cited line, and a reviewer who knows `Connection` can be a token list would flag it.
chi-02 | input | A reviewer would need to try a path with a dot and no slash. Then `LastIndex` returns -1 and `path[-1:]` panics.
chi-03 | line | `matchAcceptEncoding` does a bare `Contains` with no q-value parsing, so `q=0` cannot be honoured. A reviewer needs to know HTTP q-values, but the code is visibly missing that parsing.
chi-04 | input | A reviewer would need to run the scenario of `Flush()` before any write or `WriteHeader`. Only then does the implicit 200 go out before the compression headers are set.
chi-05 | nearby | The comment block at compress.go:114-122 says "deflate" means zlib-wrapped data, while `encoderDeflate` uses raw `flate.NewWriter`.
chi-06 | line | `strings.Cut(contentType, ";")` is used with no `TrimSpace` before the map lookup.
chi-07 | trace | A reviewer would need to know the router routes on `RawPath` when it is set. That is behaviour in a different component, and the rewrite touches only `Path`.
chi-08 | nearby | `GetHead` and `CleanPath` prefer `RawPath` and `RoutePath`, so a reviewer comparing `SupressNotFound` against those siblings would see it uses `Path` only.
chi-09 | line | A `for header, matchers := range hr` loop over a map with a "first match wins" comment is visibly nondeterministic.
chi-10 | trace | A reviewer would need to know the mux `Match` returns false on a method mismatch, and that the router itself would have answered 405.
chi-11 | input | A reviewer would need to try a comma-joined `Content-Encoding: deflate, gzip` value. The code only checks each header line as one whole token.
chi-12 | input | The lines look reasonable until you run `/users/` through `path.Clean` and see the trailing slash removed.
chi-13 | nearby | The docstring in the same file uses `Route("Host", ...)` as its example, while the code reads `r.Header.Get`. A reviewer also needs to know Go stores Host in `r.Host`.
chi-14 | line | The check is `< 0` but the panic message says the limit must be "positive", so the guard and message disagree on the cited lines.
chi-15 | input | A reviewer would need to try a last segment that starts with a dot, such as `/files/.env`. Only then does the `idx > 0` logic show up as wrong.
chi-16 | nearby | `GetHead` and `CleanPath` prefer `RawPath` when building the route path, while `StripSlashes` falls back to the decoded `Path`.
chi-17 | input | A reviewer would need to try a quoted charset value, since the parser never strips quotes.
chi-18 | line | `Format(http.TimeFormat)` is applied without `.UTC()`, and the time layout hard-codes a literal `GMT`.
chi-19 | input | A reviewer would need to think of a 204 or 304 response with a compressible content type. `WriteHeader` has no status-code check.
chi-20 | input | A reviewer would need to try a request with a query string. `RequestURI` includes the query, so the suffix lands after it.
chi-21 | input | A reviewer would need to try an escaped path such as `/a%3Fb/`. Only the decoded path is used to build `Location`.
chi-22 | trace | A reviewer would need to follow how `rctx.Routes` behaves under `Mount`, and how the parent router's look-ahead interacts with the subrouter's `GetHead`.
chi-23 | input | A reviewer would need to try a `WriteHeader(103)` followed by a later 200. The one-shot `wroteHeader` flag then fixes the compressibility decision early.
chi-24 | line | The `!credUserOk ||` short-circuit skips `ConstantTimeCompare` for unknown users, which is visible on the line.
chi-25 | nearby | The `EncoderFunc` doc says a nil return means failure, but `selectEncoder` returns `fn(w, c.level)` without a nil check. A reviewer would need to compare the two.
chi-26 | nearby | Sibling middlewares (`CleanPath`, `GetHead`) handle `RawPath`, so a reviewer comparing against them would see `StripSlashes` leave it untouched in the no-route-context branch.
chi-27 | line | `strings.Contains(v, encoding)` is a substring match where a token match is needed.
chi-28 | trace | A reviewer would need to follow `RoutePath` inside a mounted subrouter. The redirect target then lacks the mount prefix.
chi-29 | line | `charsets[i] = strings.ToLower(c)` writes into the caller's variadic slice.
chi-30 | line | `split(ce, "charset=")` is a substring cut with no check that `charset` starts a parameter name.
chi-31 | nearby | The `Sunset` line has a sibling `Deprecation` line using the same format, and the doc links only to RFC 8594. A reviewer would need to know that `Deprecation` uses a different format.
chi-32 | trace | A reviewer would need to know that `Match` mutates the passed route context. They would also have to follow how that shared context feeds the later real routing, including under `Mount`.
chi-33 | input | A reviewer would need to think of a handler that writes a response and then lets the deadline pass. The deferred `WriteHeader(504)` runs regardless.
chi-34 | line | The content-type map lookups are done with no case folding, in contrast to `SetEncoder`, which does lower-case.
chi-35 | input | A reviewer would need to try a comma-joined value in a single header line. `Header.Values` returns one string and `parseHeaderAddr` fails on it.
chi-36 | nearby | Line 91 lower-cases the request value, but `NewPattern` at lines 54, 66 and 135 stores the match string as given. A reviewer would need to compare the two in the same file.
