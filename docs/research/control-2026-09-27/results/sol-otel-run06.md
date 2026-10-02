model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:23:53 UTC; finished 2026-09-28 22:26:10 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: otel `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

1. **Medium — Reactor Netty loses IPv6 server addresses and explicit ports.** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-85` treats the first colon in an authority as the port delimiter. For a valid URL such as `http://[::1]:8080/`, `getHost()` returns `[` and `getPort()` returns `null`; `ReactorNettyHttpClientAttributesGetter.java:92-112` consequently records `server.address="["` and the default port 80 rather than the actual endpoint. The parser's own comment says it is finding the end of the host, and the getter uses its result for server address and port. Skip colons inside a bracketed IPv6 literal, consume the closing bracket, and parse a port only after that bracket.

2. **Medium — A query or fragment slash is mistaken for a URL path.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83` searches for the first slash after the host without stopping at `?` or `#`. For `https://example.com?next=/admin`, `getPath()` returns `/admin` even though the URL has no path. `HttpClientServicePeerAttributesExtractor.java:89-96` passes this value into path-based service peer resolution, so a rule for `/admin` can match a request whose only mention of `/admin` is in a query parameter. The parser's `getPathEndIndexExclusive` comment correctly defines `?` and `#` as path terminators, and existing `UrlParserTest` cases expect no path on query-only and fragment-only URLs. Restrict the search for a path-start slash to the authority section before the first `?` or `#`.

3. **Medium — Forwarded host parsing breaks valid IPv6 authorities.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-93` splits on the first colon, including a colon inside `[::1]`. A `Host`, `:authority`, `X-Forwarded-Host`, or `Forwarded` host value of `[::1]:8080` produces `server.address="["` and no port. `HttpServerAttributesExtractorBuilder.java:53-56` uses this parser for the HTTP server's address and port, and the extractor explicitly handles the `Host` and HTTP/2 authority headers at lines 39-51. Find the closing `]` for a bracketed literal and only recognize a colon after it as the port separator.

4. **Low — Single-character Forwarded values are silently ignored.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java:49-52`, `ForwardedHostAddressAndPortExtractor.java:59-62`, and `HttpServerAddressAndPortExtractor.java:50-53` reject a value when its start index is `length - 1`. A syntactically nonempty value such as `Forwarded: proto=x`, `Forwarded: host=a`, or `Forwarded: for=a` is therefore skipped, despite each comment saying only an *empty* value must be rejected. Change the boundary check to `start >= length`; normal parsing can then decide whether the value is useful.

5. **Medium — A comma-separated Forwarded host list becomes one bogus server address.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68` ends `host=` only at a semicolon. For `Forwarded: host=first.example, host=second.example`, it sets the address to `first.example, host=second.example`. The same repository's `HttpServerAddressAndPortExtractor.java:115-123` treats a comma as a separator for a Forwarded address, establishing the intended first-entry behavior. Stop the host value at a comma as well as a semicolon, with quoted-value handling so a delimiter inside quotes is not misread.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/InstrumentationContexts.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
