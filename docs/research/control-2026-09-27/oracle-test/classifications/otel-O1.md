# otel, classifier O1 (Claude Opus), blind

### otel-01
Oracle: The guard's own comment at HttpServerAddressAndPortExtractor.java:51 says `// the value after for= must not be empty`, but `start >= forwarded.length() - 1` also rejects a one-character value when it ends the header. The same file's `extractClientInfo` (lines 76-78, 116-118) is where empty values are actually rejected, and it accepts one-character values.
Type: in-repo
Confidence: high

### otel-02
Oracle: The sibling `HostAddressAndPortExtractor.java:35-45` in `semconv/http/internal` handles a `Host` header starting with `[`: it strips the brackets and parses the port after `]:`. `HttpServerAddressAndPortExtractor.java:91-101` does the same for `Forwarded: for=`. `extractHost` takes the first `:`, so it returns `"["` for `[::1]:8080`. RFC 3986 / RFC 7230 IP-literal Host syntax is a second, external oracle.
Type: in-repo
Confidence: high

### otel-03
Oracle: `UrlParserTest.java:164-172` asserts `getPath("https://localhost?query")` and `getPath("https://localhost#")` are `null`: when the URL has no path, the result is null. The `getPath` search (`url.indexOf('/', hostEnd)`) does not stop at `?` or `#`, even though `getPathEndIndexExclusive` treats those characters as delimiters. RFC 3986 §3.3-3.5 is the external backup.
Type: in-repo
Confidence: high

### otel-04
Oracle: Same off-by-one as otel-01. The comment at ForwardedHostAddressAndPortExtractor.java:60 says the value `must not be empty`, but `start >= forwarded.length() - 1` rejects `host=a`. The test file already covers the empty case (`"host="` → null, ForwardedHostAddressAndPortExtractorTest.java:54), and `extractHost` handles emptiness at line 72.
Type: in-repo
Confidence: high

### otel-05
Oracle: The in-repo parsers that handle IPv6 (`HostAddressAndPortExtractor.java:35-45`, `HttpServerAddressAndPortExtractor.java:91-101`, and `RedisServerTarget.java:279-281`, which re-brackets IPv6 "so that the port stays unambiguous") treat `[...]` as one host unit. `getHostEndIndexExclusive` stops at the first `:` inside the brackets. RFC 3986 §3.2.2 IP-literal is the external oracle.
Type: in-repo
Confidence: high

### otel-06
Oracle: Same bug as otel-05, in the copied reactor-netty `UrlParser.getHostEndIndexExclusive`, and the same in-repo IPv6 handlers apply. `getPort` returns null, so the fallback in `ReactorNettyHttpClientAttributesGetter.java:108-113` substitutes 80, compounding a wrong address with a wrong port (RFC 3986 §3.2.2 external).
Type: in-repo
Confidence: high

### otel-07
Oracle: The sibling extractors cut a Forwarded value at `,`. `HttpServerAddressAndPortExtractor.java:115` does this, and its test `for=[::1], for=1.2.3.4` → `::1` shows it. `ForwardedUrlSchemeProvider.java:72` also does it (test `proto=xyz,` → `xyz`). `extractHost` only stops at `;` (line 64) or `:` (line 87). RFC 7239 §4 (comma-separated forwarded-elements) and the X-Forwarded-Host list convention are the external backups.
Type: in-repo
Confidence: high

### otel-08
Oracle: Same off-by-one as otel-01/04. The comment at ForwardedUrlSchemeProvider.java:50 says the value `must not be empty` (it was copy-pasted and still says "for="), but the check also rejects `proto=h` at the end of the header. `extractProto` (lines 64-65, 73-74) already handles the truly empty case. The practical impact is low because real schemes are longer than one character.
Type: in-repo
Confidence: medium

### otel-09
Oracle: In the same `AdviceScope.start`, the nested-call path (lines 103-105) builds a non-skip `AdviceScope(callDepth, null)` so that the "original method body [is] executed". A null receiver is therefore expected to mean "run the original". Wrapping a null `instrument()` result in `SkipMethodBodyAdviceScope` skips the body, and `end()` returns the default `null`, which will likely NPE callers. The comment in `HttpResponseReceiverInstrumenter.java:31-32` says the receiver "should always be" an HttpClientFinalizer, so reachability is doubtful. That is why confidence is lower.
Type: in-repo
Confidence: medium

### otel-10
Oracle: RFC 3986 §3.2 defines authority as `[userinfo "@"] host [":" port]`, so the host starts after `@`. `getHostStartIndex` returns `scheme + 3` and never skips userinfo. In-repo, `RedisServerTarget.java:347` (`authority.lastIndexOf('@')`) strips credentials before taking the host, but that is a different parser, so I'd rely on the RFC.
Type: known-external
Confidence: medium

### otel-11
Oracle: Same as otel-10 in the reactor-netty copy of `UrlParser`: RFC 3986 §3.2 puts userinfo before `@`. The port fallback in `ReactorNettyHttpClientAttributesGetter.java:108-113` then replaces the real port 9000 with 80. Whether reactor-netty's `resourceUrl()` ever includes userinfo is a library contract I would have to check. That limits confidence.
Type: known-external
Confidence: medium

### otel-12
Oracle: The shared helper `HttpProtocolUtil.formatVersion` (instrumentation-api/.../internal/HttpProtocolUtil.java:42-45) collapses `X.0` to `X` only when `majorVersion > 1`. Its test `HttpProtocolUtilTest.java:26` asserts `argumentSet("HTTP 1.0", 1, 0, "1.0")`. The reactor-netty getter (and Netty/AsyncHttpClient siblings with the same pattern) collapses 1.0 to "1".
Type: in-repo
Confidence: high

The hardest ones were otel-09 through otel-11. For otel-09 there is an in-repo signal: the nested-call path treats a null receiver as "run the original body". But a comment says the null case should never occur, so it is unclear whether the behavior is reachable or intended. For otel-10 and otel-11 the clearest oracle is RFC 3986 authority syntax, not anything in the repo. `RedisServerTarget`'s userinfo stripping is only an analogy from a different parser. For otel-11 I also can't confirm from the checkout whether reactor-netty's `resourceUrl()` ever carries userinfo. I also weighed otel-08 carefully: the off-by-one is clearly real by the code's own comment, but a one-character scheme is unrealistic, so I lowered its confidence. The IPv6 findings (02, 05, 06) could have been `known-external` on RFC 3986. I chose `in-repo` because sibling extractors in the same package already parse brackets correctly.
