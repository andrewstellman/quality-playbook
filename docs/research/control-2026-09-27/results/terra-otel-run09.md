model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:11:25 UTC; finished 2026-09-28 23:15:11 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — terra-otel-run09

Reviewed revision: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`.

## Findings

### 1. Forwarded `host` parsing consumes the next forwarded-element

- **Severity:** medium
- **Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64-68`
- **What goes wrong:** For a normal multi-element `Forwarded` header such as `for=192.0.2.1;host=public.example, for=10.0.0.1`, the extractor only stops the `host` value at a semicolon. It therefore records `server.address` as `public.example, for=10.0.0.1` instead of `public.example`.
- **Why this is wrong:** The method is explicitly extracting a `host=<address>` section, but line 64 treats only `;` as its terminator. A comma separates `Forwarded` elements, so it is also outside the `host` value. The resulting value is not a host and is used as the server-address extractor by `HttpServerAttributesExtractorBuilder` (line 56).
- **Suggested fix:** Parse the header as forwarded-elements and parameters, or at minimum terminate an unquoted `host` parameter on either `;` or `,`, while honoring quoted-string escaping.

### 2. Forwarded host extraction cannot parse the required bracketed IPv6 form

- **Severity:** medium
- **Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-93`
- **What goes wrong:** With `Forwarded: for=192.0.2.1;host="[2001:db8::1]:8443"`, the extractor sets the address to `[2001` and fails to set the port. The first colon inside the IPv6 literal is treated as the host/port separator.
- **Why this is wrong:** The adjacent `HttpServerAddressAndPortExtractor` documents that RFC 7239 represents IPv6 in `Forwarded` quoted and bracketed (lines 66-73), and the internal `HostAddressAndPortExtractor` has dedicated bracketed-IPv6 handling. This extractor is the server-address source installed by `HttpServerAttributesExtractorBuilder` (line 56), so valid proxied IPv6 requests produce corrupt `server.address` data.
- **Suggested fix:** Before searching for a colon separator, detect `[` at the beginning of the (possibly unquoted) host value, locate the closing `]`, set the address to the contents, and parse a port only from a following colon.

### 3. Both URL parsers split IPv6 literals at their first colon

- **Severity:** medium
- **Locations:**
  - `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-111`
  - `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`
- **What goes wrong:** For `https://[2001:db8::1]:8443/path`, both `getHost` methods return `[2001`, and `getPort` returns `null` because it tries to parse `db8::1]:8443` as the port. In Reactor Netty, `ReactorNettyHttpClientAttributesGetter` then reports the malformed server address and falls back to port 443 for an HTTPS URL despite the explicit 8443 port (lines 92-114). The incubator parser also prevents service-peer mappings containing IPv6 endpoints from being resolved correctly (`ServicePeerResolver` lines 90-106).
- **Why this is wrong:** A bracketed IPv6 literal is a valid URL authority. The parsers' own comments label every `:` as the start of a port (incubator line 107; Reactor Netty line 76), which is false inside such a literal.
- **Suggested fix:** Recognize an authority beginning with `[`, find its matching `]`, return the bracket contents as the host, and treat only a colon immediately after `]` as the port separator. Add equivalent IPv6 tests for both parser copies.

### 4. Failed Reactor Netty IPv6 requests are reconstructed as invalid URLs

- **Severity:** medium
- **Location:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:67-73`
- **What goes wrong:** When a request fails before a usable request URL is available and its configured remote address is IPv6, `InetSocketAddress.getHostString()` is concatenated directly after `http://` or `https://`. For example, `::1` on port 8080 becomes `http://::1:8080/...`, which is not a valid URL authority; it must be `http://[::1]:8080/...`. The proxy then supplies that malformed value from `resourceUrl()` to the HTTP attribute extractor.
- **Why this is wrong:** This class exists specifically to provide a correct `resourceUrl()` for failed requests (lines 121-125 of `HttpResponseReceiverInstrumenter`). The reconstructed string does not preserve a valid host/port boundary for IPv6 and consequently also triggers the parser failure above.
- **Suggested fix:** When the `InetSocketAddress` host is an IPv6 literal, wrap it in `[` and `]` before appending the port. Cover a failed IPv6 connection with and without the default port.

## Files read

- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpMetricsAdvice.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractorTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionRequestAndContext.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientRequestHeadersSetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/InstrumentationContexts.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorContextKeys.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyInstrumentationModule.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettySingletons.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ResponseReceiverInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/AbstractReactorNettyHttpClientTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParserTest.java`
