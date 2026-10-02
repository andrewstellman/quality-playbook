model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:17:28 UTC; finished 2026-09-28 22:19:30 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

1. **Medium — bracketed IPv6 hosts are parsed as `[` in HTTP server attributes.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`. A valid `Host: [::1]:8080`, `:authority: [::1]:8080`, or `Forwarded: host="[::1]:8080"` reaches `extractHost`, whose first-colon search stops *inside* the IPv6 literal. It sets `server.address` to `[` and fails to parse `server.port`. The extractor is specifically used to populate the server address/port (`HttpServerAttributesExtractorBuilder.java:56,282-284`), and its existing tests expect `host=example.com:42` to yield the complete address and port. Fix by recognizing bracketed literals, finding the matching `]`, and parsing a port only after that bracket.

2. **Medium — the URL parsers split IPv6 authority at its first colon.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-110` and `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:77-87`. For `https://[::1]:8443/api`, both `getHost` methods return `[` and both `getPort` methods return null: the host end scan treats the first colon of the bracketed literal as the port separator, then attempts to parse the remainder as an integer. The Reactor Netty getter uses these values for `server.address` and `server.port` (`ReactorNettyHttpClientAttributesGetter.java:90-115`); the incubator parser feeds service-peer matching (`ServicePeerResolver.java:90-106`). Fix both parsers by scanning through a bracketed IPv6 literal before looking for an optional port separator, returning the actual host and port consistently.

3. **Medium — a slash in a query or fragment is reported as a URL path.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83`. `getPath("https://example.com?next=/admin")` returns `/admin`, even though the URL has no path. The parser searches for `/` anywhere after the authority, without first stopping at `?` or `#`. Existing `UrlParserTest` cases establish that a URL with only a query or fragment should have a null path; the returned path is used in HTTP client service-peer matching (`HttpClientServicePeerAttributesExtractor.java:89-96`), so a mapping for `/admin` can match a request whose real path is empty. Fix by finding the end of the authority first, and only treating a slash before the first query/fragment delimiter as the start of a path.

4. **Medium — a comma-separated second `Forwarded` entry contaminates the first host.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68`. For `Forwarded: for=1.2.3.4;host=example.com, for=5.6.7.8`, `extractFromForwardedHeader` searches only for `;` after `host=`; with no later semicolon, it passes `example.com, for=5.6.7.8` to `extractHost` and records that whole string as `server.address`. This contradicts the extractor's intent to use the forwarded host and the adjacent `HttpServerAddressAndPortExtractor` logic, which treats a comma as the end of a forwarded address (`:115-123`). Fix by ending the host value at the first top-level comma or semicolon, while respecting quoted values.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParserTest.java`
