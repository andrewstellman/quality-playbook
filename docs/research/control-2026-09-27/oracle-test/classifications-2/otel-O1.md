otel-01 | line | Line 51 rejects a value when `start >= length - 1`, but its own comment only says the value must not be empty; that off-by-one is visible on the line itself.
otel-02 | input | extractHost splits on the first ':' and looks fine until you try an IPv6 host like `[::1]:8080` and see the split lands inside the brackets.
otel-03 | input | Searching for '/' from the end of the host looks reasonable until you try a URL with no path whose query or fragment contains '/'.
otel-04 | line | This is the same `start >= forwarded.length() - 1` off-by-one as otel-01 at line 60, and its comment ("must not be empty") contradicts it on the same line.
otel-05 | input | The host-end scan stops at ':' and looks fine until you try a bracketed IPv6 literal, where the first ':' is inside the brackets.
otel-06 | input | The reviewer has to try an IPv6 URL on the local UrlParser copy; the getter's fallback to port 80 when getPort returns null (visible in the same getter) then explains `server.port=80`.
otel-07 | nearby | Unlike its sibling parsers (extractClientInfo in HttpServerAddressAndPortExtractor, extractProto in ForwardedUrlSchemeProvider), extractHost does not stop at ','; comparing them shows the missing list-separator handling.
otel-08 | line | The same `start >= forwarded.length() - 1` check sits at line 50, and its comment says only that the value must not be empty; a one-character value is wrongly rejected.
otel-09 | trace | The reviewer has to know that HttpResponseReceiverInstrumenter.instrument is @Nullable, in another file, and that ByteBuddy's `skipOn = Runnable.class` skips the body even when the scope holds null. Then end() returns the null result of the skipped body.
otel-10 | input | Treating everything after "://" up to ':' as the host looks fine until you try a URL with `user:pw@` userinfo.
otel-11 | input | Same as otel-10 on the reactor-netty copy of UrlParser: try a userinfo URL, and the getter's port-80 fallback then explains the recorded port.
otel-12 | input | "Drop the minor version when it is 0" looks right for HTTP/2.0 and only shows up as wrong when you try HTTP/1.0.
