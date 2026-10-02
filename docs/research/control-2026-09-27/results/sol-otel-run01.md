model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:11:02 UTC; finished 2026-09-28 22:12:57 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: OpenTelemetry Java instrumentation (78d71b585a77d7f2312c1b8751ff6c95a72722d7)

## Findings

1. **Forwarded IPv6 hosts are recorded as `[` instead of the address** — **medium**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`. For `Forwarded: host="[::1]:8080"` (also `Host: [::1]:8080` or `:authority: [::1]:8080`), `extractHost` treats the first colon inside the IPv6 literal as the port separator. It sets `server.address` to `[` and leaves `server.port` unset. The class explicitly handles those three HTTP host sources, and the neighboring `internal/HostAddressAndPortExtractor.java:35-44` demonstrates the intended bracketed-IPv6 handling. Recognize an opening `[`, find its matching `]`, extract the enclosed address, and parse a port only after the closing bracket.

2. **A comma-separated `Forwarded` value corrupts the host** — **medium**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64-68`. For the valid value `host=example.com, for=192.0.2.1`, the parser looks only for `;`, passes the entire remainder to `extractHost`, and records `server.address="example.com, for=192.0.2.1"`. Its own tests expect the first forwarded host to win when multiple header values are supplied (`ForwardedHostAddressAndPortExtractorTest.java:71-75`); a comma-separated field is another way to supply multiple Forwarded elements, and the client address parser in this package treats a comma as a terminator. Stop the host parameter at the first unquoted `;` or `,`.

3. **IPv6 URLs are parsed with a one-character host** — **medium**. `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-110` and `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`. Both implementations treat the first colon after `//` as a port delimiter, even within brackets. For `https://[::1]:8443/path`, `getHost` returns `[` and `getPort` returns null. The Reactor Netty getter uses those methods for `server.address` and `server.port` (`ReactorNettyHttpClientAttributesGetter.java:90-104`); the incubator parser is used by service-peer mapping. Parse bracketed IPv6 authority specially, using `]` as the host end and accepting a port only after it.

4. **A slash in a query is mistaken for the URL path** — **medium**. `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83`. `getPath("https://example.com?next=/account")` searches for `/` anywhere after the host and returns `/account`, although the URL has no path component. The method's own comment says `?` and `#` start a non-path component (`getHostEndIndexExclusive`, lines 105-110), and `HttpClientServicePeerAttributesExtractor.java:89-96` passes this result to service-peer path matching. Determine the end of the authority first; return a path only if the next character is `/`, before any `?` or `#`.

5. **A single-character `Forwarded` parameter value is discarded** — **low**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:59-61`, `HttpServerAddressAndPortExtractor.java:50-52`, and `ForwardedUrlSchemeProvider.java:49-51`. Each requires `start < length - 1` after the equals sign, rejecting a nonempty final one-character value such as `host=a`, `for=a`, or `proto=a`; the latter is a syntactically valid one-letter URI scheme. Their comments say only empty values must be rejected, and the extraction routines already handle one-character ranges. Change the check to `start >= length` (while continuing to reject empty values before separators).

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionRequestAndContext.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientInstrumentation.java` (partial tool output)
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ResponseReceiverInstrumentation.java` (partial tool output)
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java` (selected lines)
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java` (selected lines)
