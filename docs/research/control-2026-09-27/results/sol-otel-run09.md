model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:31:27 UTC; finished 2026-09-28 22:34:39 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: otel 78d71b585a77d7f2312c1b8751ff6c95a72722d7

## Findings

1. **High — ordinary host-only URLs throw during port extraction.** Files: `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:46-57` and `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:41-52`. With `https://localhost`, the host ends at `url.length()`; the code computes `portStartIndex = length + 1` and calls `substring(length + 1, length)`, throwing `StringIndexOutOfBoundsException`. The incubator's `UrlParserTest.testGetPort` explicitly expects null for this input; the Reactor Netty getter calls its parser to produce HTTP `server.port`. Fix: return null if the host end is at the string end before seeking a port.

2. **Medium — Reactor Netty splits IPv6 hosts at an internal colon.** File: `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`. For `http://[::1]:8080/`, `getHost` returns `[` and `getPort` returns null: the first colon is mistaken for the port delimiter. `ReactorNettyHttpClientAttributesGetter.getServerAddress/getServerPort` uses these outputs for server attributes. Fix: consume a bracketed host through `]` and check for a colon afterward.

3. **Medium — the incubator URL parser also splits IPv6 hosts at an internal colon.** File: `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-110`. For `https://[::1]:8080/path`, `getHost` returns `[` and `getPort` returns null. `ServicePeerResolver.addMapping` uses these methods to index configured peers, so it cannot match this peer by its real address and port. Fix: parse the complete bracketed host before checking for a port.

4. **Medium — forwarded IPv6 host and authority values become `[`.** File: `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`. For `Forwarded: host="[::1]:8080"`, `X-Forwarded-Host: [::1]:8080`, or `:authority: [::1]:8080`, the first colon lies inside the IPv6 address. The code sets `server.address` to `[` and fails to parse the port. `HttpServerAttributesExtractorBuilder` uses this extractor for server address and port, and the adjacent client-address extractor explicitly recognizes bracketed IPv6. Fix: consume a leading bracketed address through `]` before looking for an optional port.

5. **Low — a one-character Forwarded host is discarded.** File: `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:59-61`. For `Forwarded: host=a`, `start == forwarded.length() - 1` and the empty-value check rejects the nonempty host, falling back to lower-priority headers. The same extractor accepts one-character values from Host, and its comment says only empty values are invalid. Fix: use `start >= forwarded.length()`; `extractHost` already rejects empty ranges.

6. **Medium — a slash in a URL query becomes the path.** File: `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83`. `getPath("https://example.com?redirect=/admin")` returns `/admin` despite the URL having no path. `ServicePeerResolver` and `HttpClientServicePeerAttributesExtractor` use this output for path-based peer mapping, so a query value can satisfy a configured path. The parser's comments and tests distinguish `?` and `#` from the path. Fix: search for a slash only before the first query or fragment delimiter.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`: ForwardedHostAddressAndPortExtractor.java, ForwardedUrlSchemeProvider.java, HttpServerAddressAndPortExtractor.java, HeaderParsingHelper.java, HttpCommonAttributesExtractor.java, HttpServerAttributesExtractor.java, HttpClientAttributesExtractor.java, HttpServerAttributesExtractorBuilder.java, HttpServerRoute.java, HttpSpanNameExtractor.java; `internal/HostAddressAndPortExtractor.java`.
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/`: semconv/net/internal/UrlParser.java, semconv/service/peer/internal/ServicePeerResolver.java, semconv/http/HttpClientServicePeerAttributesExtractor.java.
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`: HttpClientInstrumentation.java, ResponseReceiverInstrumentation.java, TransportConnectorInstrumentation.java, HttpResponseReceiverInstrumenter.java, ReactorNettyHttpClientAttributesGetter.java, UrlParser.java, FailedRequestWithUrlMaker.java, InstrumentationContexts.java, ConnectionWrapper.java.
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/`: ForwardedHostAddressAndPortExtractorTest.java, HttpServerAddressAndPortExtractorTest.java, ForwardedUrlSchemeProviderTest.java.
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`.
