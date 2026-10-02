model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:56:44 UTC; finished 2026-09-28 23:00:05 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

### 1. Instrumentation suppresses `ResponseReceiver` implementations it cannot decorate

- **Severity:** medium
- **Location:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ResponseReceiverInstrumentation.java:102-110`
- **Failure:** The type matcher applies to every implementation of the public `HttpClient.ResponseReceiver` interface. For an implementation that is not also an `HttpClient` (or for which the transformed client is not a `ResponseReceiver`), `HttpResponseReceiverInstrumenter.instrument()` returns `null` (its explicit fallback at lines 30-56). `AdviceScope.start()` nevertheless creates `SkipMethodBodyAdviceScope`. The `skipOn = Runnable.class` advice therefore skips the original `response*` method body. `end()` finds `modifiedReceiver == null` and returns the uninitialized/skipped method return value, normally `null`, instead of executing the implementation.
- **Why this is wrong:** The nullable result from `instrument()` is the signal that no replacement receiver is available. The code only calls the original receiver method when that result is non-null (lines 112-116), but it already suppressed the original method in the null case. The broad `implementsInterface(HttpClient$ResponseReceiver)` matcher provides no restriction that would make the fallback unreachable.
- **Suggested fix:** Call `instrument()` before choosing the scope. Return a plain `AdviceScope` when it returns `null`; create `SkipMethodBodyAdviceScope` only for a non-null transformed receiver. Add a test with a minimal custom `HttpClient.ResponseReceiver` implementation that is not an `HttpClient`.

### 2. Server-address extraction corrupts bracketed IPv6 Host/Forwarded authorities

- **Severity:** medium
- **Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`
- **Failure:** With a standard bracketed IPv6 authority such as `Host: [2001:db8::1]:8443` (also valid in `Forwarded: host="[2001:db8::1]:8443"` and `:authority`), the first colon is the colon inside the literal. The extractor consequently records `server.address` as `[2001` and attempts to parse `db8::1]:8443` as a port, which fails. The port is omitted.
- **Why this is wrong:** This class is installed as the server address/port extractor by `HttpServerAttributesExtractorBuilder` (line 56). Its tests and normal branch treat a colon as a host/port separator, but an IPv6 authority is specifically bracketed so internal colons are not separators. The sibling client-address parser explicitly has a bracketed-IPv6 branch in `HttpServerAddressAndPortExtractor.java:91-100`, showing the required handling pattern.
- **Suggested fix:** Before searching for a colon, recognize a leading `[` and require a matching `]` within the value. Set the address from the bracket contents and parse a port only when a colon immediately follows `]`. Cover `Host`, `:authority`, `X-Forwarded-Host`, and quoted `Forwarded host` IPv6 examples.

### 3. Reactor Netty client URL parser does not parse IPv6 URLs

- **Severity:** medium
- **Location:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:20-25, 36-52, 74-86`
- **Failure:** For a legitimate request URL such as `http://[::1]:8080/path`, `getHostEndIndexExclusive()` stops at the first colon and `getHost()` returns `"["`. `getPort()` then tries to parse the remainder (`":1]:8080"`) as a number and returns null. `ReactorNettyHttpClientAttributesGetter` consumes these methods at lines 92-114, so spans report an invalid `server.address` and omit the explicit `server.port` for IPv6 targets.
- **Why this is wrong:** `HttpClientAttributesGetter#getUrlFull` defines the input as an RFC 3986 absolute URL. Bracketed IPv6 literals are valid URI authorities; treating every colon as the port delimiter contradicts that input contract. The parser's own unit tests cover host and port extraction but omit this valid authority form.
- **Suggested fix:** Parse a bracketed host as one authority component: find `]`, return its contents as the host, and parse a port only from a colon after `]`. Add tests for portless and ported IPv6 URLs (including path/query/fragment forms).

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpMetricsAdvice.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteSource.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
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

I also read the focused HTTP and Reactor Netty tests for the parsers and response instrumentation behavior, including `ForwardedHostAddressAndPortExtractorTest`, `ForwardedUrlSchemeProviderTest`, `UrlParserTest`, and `FailedRequestWithUrlMakerTest`.
