model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:29:17 UTC; finished 2026-09-28 22:31:10 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OTel scoped code review

Checkout: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

1. **Medium — bracketed IPv6 authority is parsed as a one-character host in the incubator URL parser.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-110`. For `https://[::1]:8080/api`, `getHostEndIndexExclusive` treats the first colon inside the brackets as the port delimiter, so `getHost` returns `"["` and `getPort` returns `null`. `ServicePeerResolver.addMapping` uses these results to index configured peers, while `HttpClientServicePeerAttributesExtractor` uses the URL path for matching; a valid IPv6 peer cannot match as intended. The method's own comment says this scan finds the end of the *host*, but a colon inside an IPv6 literal is part of the host. Scan through a bracketed literal to its closing `]`, then recognize a port delimiter only after that bracket; normalize the address consistently with the address getter.

2. **Medium — the Reactor Netty URL parser loses IPv6 server address and explicit port.** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`. Its host scan has the same first-colon behavior: `https://[::1]:8443/` yields `getHost() == "["` and `getPort() == null`. `ReactorNettyHttpClientAttributesGetter.getServerAddress/getServerPort` calls these methods, so client telemetry records `server.address` as `[` and substitutes default port 443 for the actual 8443. The parser's comment identifies `:` as a *port* delimiter, which is false inside a bracketed IPv6 literal. Handle the `[...]` authority before searching for a port separator.

3. **Medium — forwarded IPv6 host values become `[` rather than the server address.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`. For `Forwarded: host="[::1]:8080"` (or `X-Forwarded-Host: [::1]:8080`), `extractHost` splits at the first colon in the IPv6 literal, stores `[` as the address, and cannot parse the remaining text as a port. This contradicts the extractor's role of deriving a server address and port from these headers; the nearby `HostAddressAndPortExtractor` explicitly handles `[...]` literals. Detect bracketed IPv6, read through `]`, and parse a following `:port` separately.

4. **Low — a slash in the query or fragment is reported as a URL path.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83`. For `https://example.com?next=/admin`, `getPath` searches for the first slash anywhere after the host and returns `/admin` even though the URL has no path. `ServicePeerResolver` and `HttpClientServicePeerAttributesExtractor` use this value for path-based service peer matching, so a query value can select a path-specific mapping incorrectly. The parser's own `getPathEndIndexExclusive` comment treats `?` and `#` as path terminators. Only accept `/` if it appears before the first `?` or `#` after the authority.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`: `CapturedHttpHeaders.java`, `ForwardedHostAddressAndPortExtractor.java`, `ForwardedUrlSchemeProvider.java`, `HeaderParsingHelper.java`, `HttpClientAttributesExtractor.java`, `HttpClientMetrics.java`, `HttpClientRequestResendCount.java`, `HttpCommonAttributesExtractor.java`, `HttpServerAddressAndPortExtractor.java`, `HttpServerAttributesExtractor.java`, `HttpServerMetrics.java`, `HttpServerRoute.java`, `HttpServerRouteBuilder.java`, `HttpServerRouteSource.java`, `HttpSpanNameExtractor.java`, `HttpStatusCodeConverter.java`, `internal/HostAddressAndPortExtractor.java`.
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/`: `net/internal/UrlParser.java`, `service/peer/internal/ServicePeerResolver.java`, `http/HttpClientServicePeerAttributesExtractor.java`.
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`: `ConnectionWrapper.java`, `DecoratorFunctions.java`, `FailedRequestWithUrlMaker.java`, `HttpClientConnectInstrumentation.java`, `HttpClientInstrumentation.java`, `HttpResponseReceiverInstrumenter.java`, `InstrumentationContexts.java`, `ReactorNettyHttpClientAttributesGetter.java`, `ReactorNettyInstrumentationModule.java`, `ReactorNettySingletons.java`, `ResponseReceiverInstrumentation.java`, `TransportConnectorInstrumentation.java`, `UrlParser.java`.
- Tests: `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`, `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`, `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`.
