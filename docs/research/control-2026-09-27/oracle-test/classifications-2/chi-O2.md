chi-01 | line | Line 39 compares the whole `Connection` header to exactly `"Upgrade"`, but that header is a comma-separated, case-insensitive token list, so the equality check is visibly too narrow.
chi-02 | line | Line 59 never checks whether `strings.LastIndex(path, "/")` returned -1 before using it in `path[base:]`, so a path with no slash can panic.
chi-03 | input | The reviewer has to think of an `Accept-Encoding` value with `q=0` to see that the q-values are never parsed and a refused encoding still counts as accepted.
chi-04 | input | The reviewer has to follow a handler that calls `Flush()` before its first write: `writer()` still returns the raw writer, the headers go out without `Content-Encoding`, and the later `WriteHeader` switches to gzip.
chi-05 | nearby | The long comment at compress.go:114-128 says HTTP "deflate" means zlib-wrapped data, while `encoderDeflate` uses raw `flate.NewWriter`; the mismatch shows only when the two are compared.
chi-06 | line | Lines 297-300 look up the text before `;` without trimming it, so a missing `TrimSpace` is visible on the lines themselves.
chi-07 | trace | The reviewer needs to know that `mux.routeHTTP` routes on `RawPath` when it is set, so a rewrite of `Path` alone is ignored for encoded paths.
chi-08 | nearby | Comparing with `GetHead` and `CleanPath` in sibling files shows that they pick `RoutePath`, then `RawPath`, then `Path`, while this look-ahead uses only `r.URL.Path`.
chi-09 | line | The comment says "find first matching header route", but the loop ranges over a Go map, so the order is visibly nondeterministic.
chi-10 | trace | The reviewer has to read `Mux.Match`/`Find` in mux.go to learn that a path registered only for another method returns false, which turns the router's 405 into a 404.
chi-11 | input | Each `Content-Encoding` header line is compared as a whole, and that looks fine until you try a single line carrying a comma-separated list such as `deflate, gzip`.
chi-12 | input | The reviewer has to think of a route registered with a trailing slash and recall that `path.Clean` strips it, which goes beyond the doc comment's "double slash" promise.
chi-13 | nearby | The doc comment in the same file advertises `Route("Host", ...)`, and comparing that with `r.Header.Get(header)` needs the fact that net/http moves Host out of `r.Header` into `r.Host`.
chi-14 | line | The panic message says "positive" but the condition `< 0` accepts zero, so condition and message disagree on the same two lines.
chi-15 | input | The reviewer has to try a last segment that starts with a dot (`/files/.env`): `path[base:]` begins with `/`, so any dot has idx > 0 and gets treated as an extension.
chi-16 | nearby | When `RoutePath` is empty this falls back to the decoded `r.URL.Path`, while sibling `CleanPath`, `GetHead` and the router fall back to `RawPath` first; the comparison exposes the inconsistency.
chi-17 | input | The reviewer has to try a quoted parameter (`charset="utf-8"`) to see that `split` trims whitespace but never removes quotes.
chi-18 | line | `Format(http.TimeFormat)` is called without `.UTC()`, and TimeFormat hard-codes "GMT", so a non-UTC time is visibly mislabelled.
chi-19 | input | The reviewer has to think of a bodyless status (204 or 304) with a compressible `Content-Type`; `WriteHeader` never checks the status code, and `Close` then writes gzip framing.
chi-20 | line | `r.RequestURI + "/pprof/"` visibly appends a path suffix to a string that may carry a query.
chi-21 | input | The reviewer has to try an encoded character in the path (`%3F`, `%2F`) to see that the redirect `Location` is built from the decoded path without re-escaping.
chi-22 | trace | The reviewer needs to know that a mounted subrouter shares the root's route context, so `rctx.Routes.Match` looks ahead against the parent mux, not the subrouter.
chi-23 | input | The reviewer has to think of a 1xx `WriteHeader` call before the final status, which sets `wroteHeader` and fixes compressibility too early.
chi-24 | line | The `!credUserOk ||` short-circuit visibly skips `ConstantTimeCompare` for unknown users.
chi-25 | nearby | The `EncoderFunc` doc says encoders return nil on failure, but `selectEncoder` returns `fn(w, level)` plus the encoding name without a nil check; `Handler` then keeps the plain writer while the name still gets advertised.
chi-26 | line | Line 26 assigns only `r.URL.Path` and leaves `r.URL.RawPath` untouched, so the two visibly fall out of sync.
chi-27 | line | `strings.Contains(v, encoding)` is a substring match where a token match is needed.
chi-28 | trace | The reviewer needs to know that `Mount` rewrites `rctx.RoutePath` to the path below the mount point, so a redirect built from it loses the `/api` prefix.
chi-29 | line | `charsets[i] = strings.ToLower(c)` visibly writes into the caller's variadic slice.
chi-30 | line | `split(ce, "charset=")` is a substring cut, not a parameter-name match, so `xcharset=` also matches.
chi-31 | line | Nothing else in the repo would reveal this; it is wrong on these lines only for a reviewer who knows the Deprecation header's spec defines a different value format from Sunset's HTTP-date.
chi-32 | nearby | The `Mux.Find` doc warns that it mutates the context and to use `NewRouteContext()`, and sibling `GetHead` does exactly that; this look-ahead passes the live request context instead.
chi-33 | line | The deferred `WriteHeader(504)` runs whenever the deadline has passed, with no check for a response already written.
chi-34 | line | The media type used as a map key is never lower-cased, neither in `NewCompressor` nor in `isCompressible`, even though media types are case-insensitive.
chi-35 | nearby | `walkXFF`, a few lines below in the same file, splits comma-joined values, but `ClientIPFromHeader` parses the last header line whole; the comparison exposes the gap.
chi-36 | line | Line 91 lower-cases the request value while `NewPattern` (137) stores the pattern as given, so the asymmetry is visible across the cited lines.
