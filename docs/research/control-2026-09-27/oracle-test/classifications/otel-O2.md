# otel, classifier O2 (Claude Opus), blind

### otel-01
Oracle: The guard's own comment at HttpServerAddressAndPortExtractor.java:51 says "the value after for= must not be empty". A one-character value is not empty, yet `start >= forwarded.length() - 1` rejects it (off by one). `extractClientInfo` already has a correct `start >= end` empty check at :76.
Type: in-repo
Confidence: high

### otel-02
Oracle: The sibling `internal/HostAddressAndPortExtractor.java` (the `host.startsWith("[")` branch) parses the same `Host` value by stripping the brackets and reading the port after `]:`. Its tests `ipv6HostAndPort` in HostAddressAndPortExtractorTest.java:84-92 expect `[2001:db8::1]:42` to give address `2001:db8::1` and port 42. `HttpServerAddressAndPortExtractor.java:92` handles `[` the same way. RFC 3986 §3.2.2 IP-literal also applies.
Type: in-repo
Confidence: high

### otel-03
Oracle: RFC 3986 §3 says the path is the part between the authority and the first `?` or `#`, so a URL with nothing between the host and `?`/`#` has an empty path. `/` inside the query or fragment is not a path. The repo's own `getPathEndIndexExclusive` comment ("'?', '#' ==> end of path") agrees, but `getPath` searches for `/` past those delimiters.
Type: known-external
Confidence: high

### otel-04
Oracle: Same off-by-one as otel-01. The comment at ForwardedHostAddressAndPortExtractor.java:60 says "the value after host= must not be empty", but a one-character value is rejected. `extractHost` already has a correct `start >= end` empty check at :72.
Type: in-repo
Confidence: high

### otel-05
Oracle: RFC 3986 §3.2.2 says a bracketed IP-literal is the host, and the `:` characters inside the brackets are not the port separator. In-repo, `HostAddressAndPortExtractor` handles brackets and has tests for it, but this parser's own test file (UrlParserTest) has no IPv6 cases.
Type: known-external
Confidence: high

### otel-06
Oracle: RFC 3986 §3.2.2 (bracketed IPv6 host) plus §3.2.3 (an explicit port overrides the scheme default). The correct values are `server.address=::1` and `server.port=8080`. The `getServerPort` fallback to 80 at ReactorNettyHttpClientAttributesGetter.java:111-113 is meant for URLs with no port, and turns the parse failure into a wrong value rather than a missing one.
Type: known-external
Confidence: high

### otel-07
Oracle: The sibling parsers stop at `,`: `HttpServerAddressAndPortExtractor.extractClientInfo` (:115) and `ForwardedUrlSchemeProvider.extractProto` (:72) both terminate on `','`. `ForwardedHostAddressAndPortExtractor.extractHost` does not. RFC 7239 §4 defines `Forwarded` as a comma-separated list of elements. For `X-Forwarded-Host`, the first-value convention is de facto, not a spec.
Type: in-repo
Confidence: high

### otel-08
Oracle: Same off-by-one as otel-01 and otel-04. The comment at ForwardedUrlSchemeProvider.java:50 reads "the value after for= must not be empty" (copy-pasted, it should say proto=). A one-character value is not empty, and `extractProto` already returns null for a truly empty value.
Type: in-repo
Confidence: medium (the behaviour contradicts the comment, but a real one-letter proto is unlikely)

### otel-09
Oracle: The comments in `AdviceScope.start` (ResponseReceiverInstrumentation.java:104/107) and the `end()` fallback `return returnValue` show the intent: skip the original body only when a modified receiver exists. When `HttpResponseReceiverInstrumenter.instrument` returns null, the body is still skipped and the intercepted method returns null. That breaks the Reactor API contract (non-null Mono/Flux), and callers will then throw NullPointerExceptions, which is the implicit failure mode.
Type: in-repo
Confidence: medium (HttpResponseReceiverInstrumenter.java:31-32 says the receiver "should always be an HttpClientFinalizer", so this path may be rare)

### otel-10
Oracle: RFC 3986 §3.2 defines authority as `[ userinfo "@" ] host [ ":" port ]`, so the host is `host` and the port is 9000. In-repo, `RedisServerTarget.java:347` strips credentials with `authority.lastIndexOf('@')`, and `UrlSanitizer.java:21` acknowledges userinfo in `url.full`.
Type: known-external
Confidence: high

### otel-11
Oracle: Same as otel-10 (RFC 3986 §3.2): the correct values are `server.address=host` and `server.port=9000`. The fallback to 80 in `getServerPort` records a confidently wrong port. It also puts the `user` part of the credentials into an attribute.
Type: known-external
Confidence: high

### otel-12
Oracle: Sibling getters return `"1.0"` for HTTP/1.0: OkHttpAttributesGetter.java:92-93, OkHttp2HttpAttributesGetter.java:68-69, Vertx4/5HttpAttributesGetter, and ApacheHttpClientHttpAttributesGetter.java:88. The OTel semconv `network.protocol.version` examples include "1.0". The `minorVersion()==0` shortcut is only right for HTTP/2 and HTTP/3. The Netty client/server getters and AsyncHttpClientHttpAttributesGetter copy the same pattern, so the repo is not unanimous.
Type: in-repo
Confidence: high

**Hardest to classify:** otel-09 and otel-12 were the hardest.
- **otel-09:** the oracle mixes three things: in-repo comments showing intent, an implicit NPE that would only show up downstream, and a comment saying the null path "should" never happen. Whether it is a real defect depends on how reachable that path is, and I couldn't settle that without running the code.
- **otel-12:** in-repo evidence points both ways. Several client getters return "1.0", but the Netty and AsyncHttpClient getters share the exact "1" pattern. The tie-breaker is the external semconv spec rather than the repo alone.
- **URL parser findings (otel-03, 05, 06, 10, 11):** the choice between `in-repo` and `known-external` was a judgement call. Sibling code (HostAddressAndPortExtractor, RedisServerTarget) supports them, but RFC 3986 is the oracle I'd actually rely on.
