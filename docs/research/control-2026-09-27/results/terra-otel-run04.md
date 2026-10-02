model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:00:42 UTC; finished 2026-09-28 23:03:41 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — terra / otel / run 04

Reviewed commit: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

### 1. Forwarded server hosts containing IPv6 literals are parsed as a truncated hostname

- **Severity:** medium
- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-93`
- **What goes wrong:** A server request with `Host: [2001:db8::1]:8443`, `:authority: [2001:db8::1]:8443`, or `Forwarded: host="[2001:db8::1]:8443"` records `server.address` as `"[2001"` and no usable port. The first colon is always treated as the host/port separator.
- **Why this is wrong:** This extractor is the server address source installed by `HttpServerAttributesExtractorBuilder` (line 56), including for ordinary `Host` and HTTP/2 `:authority` headers (lines 39-50). Bracketed IPv6 is the required authority syntax, while the neighboring `HttpServerAddressAndPortExtractor` explicitly handles this form at lines 91-100.
- **Suggested fix:** Before searching for a colon, recognize a value beginning with `[`, find the matching `]`, store the contents as the address, and parse a port only from a colon immediately following that bracket. Apply that after quote removal so it covers all four header sources.

### 2. A comma-separated `Forwarded` header corrupts `server.address`

- **Severity:** medium
- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64-68`
- **What goes wrong:** For the valid multi-element header `Forwarded: host=first.example, for=192.0.2.1`, the extractor uses the end of the whole header because it only looks for `;`. It consequently writes `server.address = "first.example, for=192.0.2.1"` instead of `first.example`. A colon later in the next element can also be misread as the port separator.
- **Why this is wrong:** `Forwarded` elements are comma-separated. The sibling client-address extractor already treats both `,` and `;` as address terminators at `HttpServerAddressAndPortExtractor.java:103-128`; this implementation claims to parse the same `Forwarded` header but does not stop at the element delimiter.
- **Suggested fix:** End the `host=` value at the earlier of `;` and `,` (and retain the existing quoted-value handling), then parse only that slice.

### 3. The generic URL parser cannot parse valid bracketed IPv6 URL authorities

- **Severity:** medium
- **File and line:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:91-96`
- **What goes wrong:** `UrlParser.getHost("https://[2001:db8::1]:8443/path")` returns `"[2001"`; `getPort` then attempts to parse `"db8::1]:8443"` and returns `null`. This breaks service-peer matching and HTTP client service/peer attribute resolution for IPv6 targets, whose callers use this parser in `ServicePeerResolver` and `HttpClientServicePeerAttributesExtractor`.
- **Why this is wrong:** The parser advertises `getHost` and `getPort` for a URL authority, and its tests cover host/port authorities. A bracketed IPv6 literal is a valid URL host authority; treating its first colon as a port delimiter contradicts that format.
- **Suggested fix:** Have host-end detection recognize an opening `[`, locate `]`, and treat it as the host boundary; only accept a port colon after `]`. Return the literal without brackets, consistent with the existing address extractors.

### 4. Reactor Netty client telemetry loses the server endpoint for normal IPv6 URLs

- **Severity:** medium
- **File and line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`
- **What goes wrong:** For a Reactor Netty request whose `resourceUrl()` is `http://[::1]:8080/path`, `getHost` returns `"["` and `getPort` returns `null`. `ReactorNettyHttpClientAttributesGetter` uses those results for `server.address` and `server.port` at lines 92-114, so IPv6 client spans have an invalid/missing endpoint.
- **Why this is wrong:** This is a duplicate simplified authority parser, and it has the same first-colon logic as the generic parser. The resulting value is neither the IPv6 address nor a usable host, despite `ReactorNettyHttpClientAttributesGetter` directly exposing it as server endpoint telemetry.
- **Suggested fix:** Implement bracketed IPv6 authority handling here as well, preferably by sharing the fixed parser with the incubator implementation so the two implementations cannot drift.

### 5. Connection-error URLs constructed for IPv6 addresses are invalid

- **Severity:** medium
- **File and line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:70-73`
- **What goes wrong:** When a request fails before a usable request URL is available and the configured remote address is IPv6, `InetSocketAddress.getHostString()` returns an unbracketed literal such as `2001:db8::1`. The code constructs `http://2001:db8::1:8080/path`, which is not a valid URL authority. The failed-request proxy is then used to create the connection-error span (`HttpResponseReceiverInstrumenter.java:121-125`), so its `url.full`, server address, and port are malformed or unavailable.
- **Why this is wrong:** The constructed value is intended to be the full URL returned from `resourceUrl()` (the special proxy only overrides that method at lines 39-42). IPv6 literals must be bracketed in a URL authority; without brackets neither a URL parser nor the local `UrlParser` can distinguish host colons from the port separator.
- **Suggested fix:** If the host string contains `:` and is not already bracketed, wrap it in `[` and `]` before appending the port and path. Add a connection-failure test using an IPv6 `InetSocketAddress`.

## Files read

Main source inspected:

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- all source files under `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`.

Tests and callers inspected:

- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/AbstractReactorNettyHttpClientTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyConnectionSpanTest.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
