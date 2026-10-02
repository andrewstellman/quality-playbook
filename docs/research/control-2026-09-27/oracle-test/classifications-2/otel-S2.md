otel-01 | line | The comment says the value after `for=` must not be empty, but the check `start >= forwarded.length() - 1` also rejects a one-character value, an off-by-one visible on that line.
otel-02 | input | The reviewer has to try a bracketed IPv6 host, since the first-`:` split on `[::1]:8080` looks fine until that case is run.
otel-03 | input | The reviewer has to try a URL with no path and `/` in the query or fragment, because `indexOf('/', hostEnd)` reads fine until then.
otel-04 | line | It has the same off-by-one as otel-01: the comment says the value must not be empty, but `length() - 1` rejects a one-character value.
otel-05 | input | The reviewer has to try an IPv6 literal, because the host-end scan stopping at the first `:` only shows up as wrong with `[::1]`.
otel-06 | input | It is the same IPv6 case as otel-05 in a duplicated parser. The reviewer also has to see how the getter uses the parser to get `port=80`.
otel-07 | input | The reviewer has to try a header with a comma-separated list, since neither extractor splits on `,` and the single-value code looks fine.
otel-08 | line | It has the same off-by-one as otel-01, and the comment even says "for=" in the `proto=` method, a copy-paste sign on that line.
otel-09 | trace | The reviewer has to follow `instrument()` (which may return null) through the `skipOn` advice mechanism and the skipped original body to see that the call returns null.
otel-10 | input | The reviewer has to try a URL with userinfo (`user:pw@`), because host start is taken as right after `//` with no `@` handling.
otel-11 | input | It is the same userinfo case as otel-10 in the reactor-netty parser, plus the getter's fallback to port 80.
otel-12 | input | The reviewer has to try HTTP/1.0 and know the semantic convention wants "1.0". The `minorVersion()==0` shortcut is right for HTTP/2 and only fails for 1.0.
