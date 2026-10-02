chi-01 | input | The reviewer has to think of a `Connection: keep-alive, Upgrade` request, since the exact-match `!= "Upgrade"` looks plausible on its own.
chi-02 | line | `strings.LastIndex(path, "/")` can return -1, and `path[base:]` is then sliced with no guard, which is visible on the cited lines.
chi-03 | input | The reviewer needs to know Accept-Encoding q-values exist and try `gzip;q=0`, because nothing in the code parses q at all.
chi-04 | nearby | Compare `Flush` with `Write`, which calls `WriteHeader` first while `Flush` does not, so a flush before any write sends headers without the encoding decision.
chi-05 | nearby | The comment at compress.go:114-122 says deflate means zlib-wrapped data, while `encoderDeflate` uses raw `flate.NewWriter`.
chi-06 | input | The reviewer must try a `Content-Type` with whitespace before `;`, since the code cuts at `;` and looks up without a `TrimSpace`, and it reads as fine otherwise.
chi-07 | nearby | Compare with `CleanPath` and `GetHead`, which handle `RawPath`, to see that only `URL.Path` is rewritten here; this also needs some knowledge of the router.
chi-08 | nearby | Compare with `GetHead` and `CleanPath`, which take `RawPath` or `RoutePath` for the lookup, against `r.URL.Path` used here.
chi-09 | line | The "first matching" loop ranges over a map (`for header, matchers := range hr`), so the order is nondeterministic on inspection.
chi-10 | trace | The reviewer has to follow `Routes.Match` returning only a bool into the mux's own 405 logic, in a different file.
chi-11 | input | The reviewer needs to try a comma-joined `Content-Encoding` value; the loop over `Header[...]` entries looks correct for the multi-line case.
chi-12 | input | The reviewer needs to know that `path.Clean` strips trailing slashes and then try a route registered with one.
chi-13 | nearby | The doc example in the same file routes on `"Host"`, but the code reads `r.Header.Get`, and Go stores the server-side Host in `r.Host`, not in the header map.
chi-14 | line | The error message says "positive" but the check is `< 0`, so zero is accepted; the mismatch shows in the two cited lines.
chi-15 | input | The reviewer must try a dotfile as the last path segment such as `/files/.env`, since the `idx > 0` logic looks deliberate.
chi-16 | nearby | Compare with `GetHead` and `CleanPath`, which prefer `RawPath`, to see that `StripSlashes` falls back to the decoded path.
chi-17 | input | The reviewer needs to try a quoted charset value, which the trimming and splitting do not handle.
chi-18 | line | `Format(http.TimeFormat)` is called without `.UTC()` while the format hardcodes "GMT", which is wrong on inspection for anyone who knows Go's time formatting.
chi-19 | input | The reviewer must think of 204 and 304 responses, which the `WriteHeader` and `Close` logic never considers.
chi-20 | input | The reviewer must try a request URI with a query string, since `RequestURI` includes it and the suffix is appended after it.
chi-21 | input | The reviewer needs to try an escaped character such as `%3F` or `%2F` in a path with a trailing slash.
chi-22 | trace | The reviewer has to follow behaviour across `Mount`, the sub-router's route context and the parent router's method matching, which is spread over several files.
chi-23 | input | The reviewer must try a 1xx informational status before the final one, since the code assumes `WriteHeader` is called once with the final code.
chi-24 | line | The `||` short-circuit skips `ConstantTimeCompare` when the user is absent, which is visible on the cited line.
chi-25 | nearby | Compare `selectEncoder`, `Handler` (`if encoder != nil`) and the `EncoderFunc` doc saying nil means failure, to see that the name is still set when the encoder is nil.
chi-26 | line | The `rctx == nil` branch updates only `r.URL.Path` while the rest of the file deals with `RawPath` and `RoutePath`, which is visible on the lines themselves.
chi-27 | line | `strings.Contains` is used on the token where an equality match is needed, which is wrong on its face.
chi-28 | trace | The reviewer must follow how a mounted sub-router sets `RoutePath` to the tail, so the redirect drops the mount prefix.
chi-29 | line | The loop assigns into the caller's variadic slice (`charsets[i] = ...`), which is an obvious in-place mutation.
chi-30 | input | The reviewer needs to try a parameter name that merely ends in `charset=`, because `Cut` matches the substring anywhere.
chi-31 | nearby | This needs outside knowledge that `Deprecation` uses a different date syntax from `Sunset`; the identical two lines and the RFC 8594 comment (which covers only Sunset) are the only clue.
chi-32 | trace | The reviewer has to follow how `Match` mutates the route context (URLParams, patterns) that the real routing then reuses, across mux, tree and mount.
chi-33 | input | The reviewer must think of the handler having already written its response before the deadline fires, since the deferred code checks only `ctx.Err()`.
chi-34 | input | The reviewer needs to try mixed-case media types, because the map lookup is case-sensitive and there is no `ToLower` on either side.
chi-35 | nearby | The doc comment discusses multiple header values, and `parseHeaderAddr` in the same file takes a single address, so a comma-joined single line fails; the reviewer must compare the two.
chi-36 | nearby | Compare `Handler`, which lower-cases the request value, with `NewPattern`, which stores the pattern as given; the mismatch spans `Route` and `Handler`.
