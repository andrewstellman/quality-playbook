model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:08:42 UTC; finished 2026-09-28 23:11:12 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — run 08

Reviewed commit: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`.

## Findings

### 1. Valid comma-separated `Forwarded` values corrupt `server.address` and lose `server.port`

- **Severity:** medium
- **Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64-68,87-92`
- **Failure:** A valid header such as `Forwarded: host=example.com:8443, for=192.0.2.1` is parsed with `end` at the end of the whole header because the code only looks for `;`. `extractHost` then sets `server.address` to `example.com` but passes `8443, for=192.0.2.1` to `Integer.parseInt`, so no port is recorded. When the host has no explicit port (`host=example.com, for=...`), it records the invalid address `example.com, for=...`.
- **Why this is wrong:** The extractor explicitly says it is finding the `host=<address>` section, while the nearby `HttpServerAddressAndPortExtractor.extractClientInfo` already treats a comma as the end of a `Forwarded` element. A comma is a valid separator between `Forwarded` elements, so parsing past it consumes the next parameter as part of the host.
- **Suggested fix:** Bound the host parameter at the first unquoted `;` *or* `,`, and parse quoted values before searching for delimiters. Add coverage for comma-separated values both with and without an explicit port. The same parser should also recognize bracketed IPv6 host values instead of treating their first colon as a port separator.

### 2. The incubator URL parser cannot parse bracketed IPv6 authorities

- **Severity:** medium
- **Location:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-111`
- **Failure:** For a valid URL such as `https://[2001:db8::1]:8443/orders`, `getHost` returns `[` and `getPort` attempts to parse `db8::1]:8443`, returning `null`. Consequently, `ServicePeerResolver.addMapping` (lines 90-94) cannot construct a host/port mapping for a configured IPv6 peer, so a normal `server.address=2001:db8::1`, `server.port=8443` request never resolves that peer mapping.
- **Why this is wrong:** The helper is used to split URL authorities into host and port for service-peer resolution, but `getHostEndIndexExclusive` unconditionally treats the first colon as the port separator. In URI authority syntax, colons inside `[ ... ]` are part of an IPv6 literal; only the colon after `]` introduces a port.
- **Suggested fix:** Detect a `[` at the authority start, require a closing `]`, return the enclosed address as the host, and inspect only the character immediately after `]` for a port separator. Add IPv6 host, port, and path tests.

### 3. Reactor Netty reports an invalid server address and default port for IPv6 requests

- **Severity:** medium
- **Location:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86` (used by `ReactorNettyHttpClientAttributesGetter.java:92-114`)
- **Failure:** A Reactor Netty request whose `resourceUrl()` is `http://[::1]:8080/path` gets `server.address="["`; `UrlParser.getPort` returns `null`, so `getServerPort` falls back to `80` rather than the configured `8080`.
- **Why this is wrong:** `ReactorNettyHttpClientAttributesGetter` relies on this parser for the `server.address` and `server.port` semantic-convention fields. The parser treats the first colon within the bracketed IPv6 literal as a port separator, which is not valid URI authority parsing.
- **Suggested fix:** Implement bracketed-IPv6 parsing in this parser (or share a corrected common parser) and add an instrumentation/unit test for `http://[::1]:8080/`.

### 4. Failed IPv6 Reactor Netty requests are given an invalid reconstructed URL

- **Severity:** medium
- **Location:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:66-73`
- **Failure:** On a connection/request failure without an absolute URI or `baseUrl`, an `InetSocketAddress` for `::1:8080` is reconstructed as `http://::1:8080<uri>`. That is not a valid URI authority: an IPv6 literal must be bracketed. The proxy then returns this value from `resourceUrl()`, so the failed-request span has an invalid `url.full` and the downstream server-address parser cannot recover the actual target.
- **Why this is wrong:** This code is specifically a workaround to supply a correct `resourceUrl()` for a failed Reactor Netty request, but it concatenates `InetSocketAddress.getHostString()` directly into an authority. Unlike a DNS name, an IPv6 host contains colons and requires `[host]` in a URL.
- **Suggested fix:** When the configured host string contains an IPv6 literal (or the address is an `Inet6Address`), wrap it in brackets before appending the port. Add a failure-path test with an IPv6 remote address.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`: `CapturedHttpHeaders.java`, `ForwardedHostAddressAndPortExtractor.java`, `ForwardedUrlSchemeProvider.java`, `HeaderParsingHelper.java`, `HttpClientAttributesExtractor.java`, `HttpClientAttributesExtractorBuilder.java`, `HttpClientMetrics.java`, `HttpClientRequestResendCount.java`, `HttpCommonAttributesExtractor.java`, `HttpCommonAttributesGetter.java`, `HttpMetricsAdvice.java`, `HttpServerAddressAndPortExtractor.java`, `HttpServerAttributesExtractor.java`, `HttpServerAttributesExtractorBuilder.java`, `HttpServerAttributesGetter.java`, `HttpServerMetrics.java`, `HttpServerRoute.java`, `HttpServerRouteBuilder.java`, `HttpServerRouteSource.java`, `HttpSpanNameExtractor.java`, `HttpSpanNameExtractorBuilder.java`, `HttpStatusCodeConverter.java`, and `internal/HostAddressAndPortExtractor.java`.
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java` and `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`.
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`: `ConnectionRequestAndContext.java`, `ConnectionWrapper.java`, `DecoratorFunctions.java`, `FailedRequestWithUrlMaker.java`, `HttpClientConnectInstrumentation.java`, `HttpClientInstrumentation.java`, `HttpClientRequestHeadersSetter.java`, `HttpResponseReceiverInstrumenter.java`, `InstrumentationContexts.java`, `ReactorContextKeys.java`, `ReactorNettyHttpClientAttributesGetter.java`, `ReactorNettySingletons.java`, `ResponseReceiverInstrumentation.java`, `TransportConnectorInstrumentation.java`, and `UrlParser.java`.
- Tests consulted: `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`, `HttpServerAddressAndPortExtractorTest.java`; `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`; and Reactor Netty `UrlParserTest.java` search results.
