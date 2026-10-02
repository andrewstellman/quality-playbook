chi-01 | line | `r.Header.Get("Connection") != "Upgrade"` is an exact string compare on a header that is a comma-separated token list; the lines alone show it.
chi-02 | line | `strings.LastIndex(path, "/")` is used as a slice index with no -1 check; an unguarded index is visible on the lines.
chi-03 | input | The reviewer has to try an Accept-Encoding value with `q=0`; the substring match looks acceptable until a zero q-value is considered.
chi-04 | nearby | Compare `Flush` with its sibling `Write`: `Write` forces `WriteHeader` when `!wroteHeader`, `Flush` doesn't, so it flushes and commits headers before the compress decision is made.
chi-05 | nearby | The comment in `NewCompressor` (lines 102–117) says HTTP "deflate" means zlib-wrapped data, while `encoderDeflate` uses raw `flate.NewWriter`.
chi-06 | input | The reviewer has to try a Content-Type with whitespace before `;` to see that the untrimmed `Cut` result misses the map lookup.
chi-07 | trace | The reviewer has to know the chi router routes on `RawPath` when it is set, which is in mux.go, not in this one-line middleware.
chi-08 | nearby | Compare with `GetHead` and `CleanPath` in the same package, which prefer `RoutePath`, then `RawPath`, then `Path`; `SupressNotFound` uses the decoded `r.URL.Path` directly.
chi-09 | line | "Find first matching header route" is implemented as `range` over a Go map, whose iteration order is randomised.
chi-10 | trace | The reviewer has to know that `Routes.Match` returns false on a method mismatch and that the router itself would answer 405; both live in the router, not this file.
chi-11 | input | The reviewer has to try a single header line such as `deflate, gzip`; iterating `r.Header[...]` treats each line as one encoding instead of splitting the tokens.
chi-12 | line | `path.Clean` is well known to strip a trailing slash, and it is applied to the whole route path.
chi-13 | nearby | The doc-comment example routes on `"Host"`; set against line 87's `r.Header.Get`, it shows the advertised use can't work, because net/http moves Host into `r.Host`.
chi-14 | line | The panic message says "positive", but the check is `< 0`, so zero is accepted; the mismatch is on lines 49–50.
chi-15 | input | The reviewer has to try a path whose last segment starts with a dot (`/files/.env`); because `path[base:]` starts with "/", `idx > 0` is always true.
chi-16 | nearby | Compare with `GetHead` and `CleanPath`, which fall back to `RawPath` before `Path`; `StripSlashes` falls back straight to the decoded `r.URL.Path`.
chi-17 | input | The reviewer has to try a quoted parameter, `charset="utf-8"`; the split-and-trim code keeps the quotes.
chi-18 | line | `http.TimeFormat` is only correct for UTC times, and the code formats `sunsetAt` without calling `.UTC()`.
chi-19 | input | The reviewer has to think of a no-body status (204/304) with a compressible type; `WriteHeader` never looks at `code`.
chi-20 | line | `r.RequestURI` includes the query string, so appending a path suffix to it is wrong on sight.
chi-21 | input | The reviewer has to try an escaped path such as `%3F` or `%2F`; the decoded path goes straight into `Location` without re-escaping.
chi-22 | trace | The reviewer has to follow how a mounted sub-router's route context and `Routes` interact with the parent router's method dispatch.
chi-23 | input | The reviewer has to think of an informational 1xx `WriteHeader` before the real status; the one-shot `wroteHeader` latch fires on the 1xx.
chi-24 | line | `!credUserOk ||` short-circuits and skips `ConstantTimeCompare` for unknown users, which is visible on line 20.
chi-25 | nearby | The `EncoderFunc` comment (line 272) says the function returns nil on failure; `selectEncoder` returns that nil together with the encoding name, and nothing checks it.
chi-26 | line | Line 26 assigns `r.URL.Path` without touching `r.URL.RawPath`, a recognisable net/url pitfall.
chi-27 | line | `strings.Contains(v, encoding)` is a substring match where a token match is needed.
chi-28 | trace | The reviewer has to know that `Mount` leaves `rctx.RoutePath` holding only the sub-router-relative remainder, so the redirect drops the mount prefix.
chi-29 | line | `charsets[i] = strings.ToLower(c)` writes into the caller's variadic slice.
chi-30 | line | `split(ce, "charset=")` is a substring match on the parameter name, so `xcharset=` also matches.
chi-31 | line | Line 16 formats `Deprecation` exactly like `Sunset`; spotting the problem takes knowing that the Deprecation header uses a different date format.
chi-32 | nearby | Compare with `GetHead`, which looks ahead using a fresh `chi.NewRouteContext()`; `SupressNotFound` passes the live `rctx`, so `Match` mutates it.
chi-33 | input | The reviewer has to picture a handler that writes its response and then outlives the deadline; the deferred `WriteHeader(504)` never checks whether anything was written.
chi-34 | input | The reviewer has to try a mixed-case media type; both the stored allow-list and the looked-up Content-Type are used without case folding.
chi-35 | nearby | The doc comment ("misconfigured proxy that appends… LAST value wins") and the sibling `walkXFF`, which splits on commas, both show that `ClientIPFromHeader` should split a comma-joined line.
chi-36 | nearby | Compare `Route`/`NewPattern` (pattern stored as given) with `Handler` line 91 (request value lower-cased); the mismatch only shows when the two are read together.
