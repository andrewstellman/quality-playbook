chi-01 | line | The exact `!= "Upgrade"` comparison on a multi-valued `Connection` header is visibly too strict.
chi-02 | input | Reviewer must try a slash-free path such as `a.json` to see `LastIndex` return -1 and `path[-1:]` panic.
chi-03 | line | `matchAcceptEncoding` is a bare substring check and never looks at q-values, so it cannot honor `q=0`.
chi-04 | input | Reviewer must trace the order Flush, then Write, then WriteHeader, where `writer()` still returns the raw writer at Flush time and commits headers before the compression decision.
chi-05 | nearby | The file's own comment says HTTP "deflate" is zlib-wrapped, but `encoderDeflate` uses raw `flate.NewWriter`.
chi-06 | line | `strings.Cut(contentType, ";")` is followed by no `TrimSpace` before the map lookup.
chi-07 | trace | Reviewer must know the router prefers `RawPath` over `Path` and that `PathRewrite` only edits `Path`.
chi-08 | nearby | Sibling middlewares (`get_head.go`, `clean_path.go`) use the `RoutePath` then `RawPath` then `Path` precedence that this one skips.
chi-09 | line | The `for header, matchers := range hr` loop over a map returns on the first match, so order is random.
chi-10 | trace | Reviewer must know `Routes.Match` returns false on a method mismatch, where the router would respond 405.
chi-11 | input | Reviewer must picture a comma-joined single header line, which is compared as a whole string against the allowed set.
chi-12 | input | Reviewer must run `/users/` through `path.Clean` to see the trailing slash disappear.
chi-13 | nearby | The doc comment advertises `Route("Host", ...)`, but the handler reads `r.Header`, and Go keeps the server-side host in `r.Host`.
chi-14 | line | The check is `< 0` while the message says "positive", so 0 slips through.
chi-15 | input | Reviewer must try a last segment that starts with a dot, such as `/files/.env`, since `idx > 0` is measured relative to the slice starting at the slash.
chi-16 | nearby | It uses decoded `r.URL.Path` where siblings prefer `RawPath`, and the consequence only shows once the router's use of `RawPath` is compared.
chi-17 | input | Reviewer must try a quoted charset value, since the parser never strips quotes.
chi-18 | line | `sunsetAt.Format(http.TimeFormat)` is called without `.UTC()`, while the layout hard-codes a GMT suffix.
chi-19 | input | Reviewer must think of 204 and 304 responses, where `WriteHeader` sets compression headers regardless of the status code.
chi-20 | input | Reviewer must try a request URI that carries a query string, since `RequestURI` includes it and the suffix is appended after it.
chi-21 | input | Reviewer must try an escaped `%3F` or `%2F` in the path, which the decoded-path redirect then emits raw.
chi-22 | trace | Reviewer must follow how `GetHead` inside a mounted sub-router interacts with the parent's route context and the Mount routing.
chi-23 | input | Reviewer must try a 1xx informational `WriteHeader` call followed by a later 200, since `wroteHeader` is latched on the first call.
chi-24 | line | The `!credUserOk ||` short-circuit visibly skips `ConstantTimeCompare` for unknown users.
chi-25 | nearby | The `EncoderFunc` doc says an encoder returns nil on failure, but `selectEncoder` returns the name anyway and `Handler` then sets `cw.encoding` with no encoder.
chi-26 | line | With `rctx == nil` only `r.URL.Path` is assigned and `RawPath` is left stale.
chi-27 | line | `strings.Contains(v, encoding)` is a substring test where a token match is needed.
chi-28 | trace | Reviewer must know that inside a mounted sub-router `RoutePath` lacks the mount prefix, so the redirect target drops it.
chi-29 | line | `charsets[i] = strings.ToLower(c)` writes into the caller's variadic slice.
chi-30 | line | `split(ce, "charset=")` is a substring cut that matches `xcharset=`.
chi-31 | nearby | Both headers reuse the same `TimeFormat` line, and only outside knowledge of the Deprecation header's format (a structured date) shows that the second is wrong.
chi-32 | trace | Reviewer must follow how the shared route context is mutated by the look-ahead `Match` and then reused by the real routing, including under Mount.
chi-33 | input | Reviewer must consider a handler that has already written its response before the deadline fires, since the deferred `WriteHeader(504)` is unconditional.
chi-34 | line | The map lookup uses the raw Content-Type, and neither the lookup nor `NewCompressor` lower-cases anything.
chi-35 | nearby | The doc comment describes multi-value handling, but the code only splits separate header lines and never a comma-joined single line.
chi-36 | nearby | `Handler` lower-cases the request value, while `Route` and `NewPattern` lower-case only the header name and not the pattern, so both sites must be compared.
