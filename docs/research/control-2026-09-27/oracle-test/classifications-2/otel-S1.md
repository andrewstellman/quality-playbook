otel-01 | line | The comparison `start >= forwarded.length() - 1` on the cited line drops a valid one-character value, and the adjacent comment says the check is only for an empty value.
otel-02 | input | The reviewer has to try a bracketed IPv6 Host value, because `extractHost` splitting at the first ':' looks reasonable for `host:port`.
otel-03 | input | The reviewer has to try a URL with no path and a '/' in the query or fragment, because `indexOf('/')` is not bounded by '?' or '#' and looks fine for ordinary URLs.
otel-04 | line | It has the same off-by-one `length() - 1` check as otel-01, and its comment says the value must not be empty.
otel-05 | input | The reviewer has to run a bracketed IPv6 URL through `getHostEndIndexExclusive`, which stops at the first ':' and looks fine for ordinary hosts.
otel-06 | input | It needs the same IPv6 URL scenario as otel-05, and the wrong port 80 also needs the fallback in the getter (`ReactorNettyHttpClientAttributesGetter.java:104-115`) to be read.
otel-07 | input | The reviewer has to try a multi-valued or comma-separated `Forwarded` or `X-Forwarded-Host` header, because the code has no list handling and nothing on the page hints that it is missing.
otel-08 | line | It has the same off-by-one check as otel-01, and the comment even says `for=` in a `proto=` method, which marks it as copy-pasted.
otel-09 | trace | The reviewer has to follow the `skipOn` and `Runnable` skip-body mechanism, plus `HttpResponseReceiverInstrumenter.instrument` (which can return null) in another file, to see that a skipped body returns null.
otel-10 | input | The reviewer has to try a URL with userinfo, because `getHostStartIndex` just returns the index after "//" and looks correct for plain hosts.
otel-11 | input | It needs the same userinfo URL scenario as otel-10, with the getter's default-port fallback also read.
otel-12 | nearby | The reviewer has to know the semconv value format for `network.protocol.version` (HTTP/1.0 is "1.0") or compare it with sibling getters, because the `minorVersion() == 0` shortcut is only right for HTTP/2 and 3.
