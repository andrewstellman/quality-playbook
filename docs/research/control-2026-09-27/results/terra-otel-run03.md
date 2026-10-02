model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:00:19 UTC; finished 2026-09-28 23:03:50 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry Java instrumentation review

Reviewed commit: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

### 1. `getPort` throws for an authority that ends at the end of the URL

**Severity:** medium  
**Locations:**

- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:46-57`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:41-52`

For a valid URL without an explicit port or trailing path/query/fragment, such as
`https://localhost`, `getHostEndIndexExclusive` returns `url.length()`. The condition at line
46 (line 41 in the Reactor Netty copy) then falls through because it only rejects a non-colon
character when the index is *less* than the length. The method advances to `length + 1` and calls
`substring(length + 1, length)`, which throws `StringIndexOutOfBoundsException` rather than
returning `null`.

This contradicts the incubator parser's own test contract:
`UrlParserTest.testGetPort` expects `UrlParser.getPort("https://localhost")` to be null (lines
86-102). In the Reactor Netty path, `ReactorNettyHttpClientAttributesGetter.getServerPort` calls
this parser before its default-port fallback (lines 99-114), so a resource URL in this form aborts
attribute extraction instead of recording port 443/80.

**Suggested fix:** require the host terminator to exist and be a colon before calculating the
port start, e.g. `if (hostEndIndexExclusive >= url.length() || url.charAt(hostEndIndexExclusive)
!= ':') return null;`, in both copies. Add a regression test for the end-of-string authority in
the Reactor Netty copy as well.

### 2. Server address extraction corrupts IPv6 authorities

**Severity:** medium  
**Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`

`extractHost` treats the first `:` as the host/port delimiter. For a normal HTTP authority such
as `Host: [2001:db8::1]:443` (and likewise for `:authority`, `X-Forwarded-Host`, or a quoted
`Forwarded` `host=` value), the first colon is inside the bracketed IPv6 literal. It therefore
sets `server.address` to `[2001` and attempts to parse `db8::1]:443` as a port, which fails.

The extractor is the server-address source installed by
`HttpServerAttributesExtractorBuilder` (lines 53-57), so this affects ordinary server spans.
The scoped `HostAddressAndPortExtractor` explicitly handles bracketed IPv6 and its tests require
`[2001:db8::1]` to yield `2001:db8::1` (the corresponding test is
`internal/HostAddressAndPortExtractorTest.java:75-90`), establishing the intended authority
behavior that this parallel parser fails to provide.

**Suggested fix:** add a bracketed-host branch before searching for `:`, locate `]`, set the
address to the characters inside the brackets, and parse a port only when the following character
is `:`. Reuse the same helper for all four header sources and add bracketed IPv6 cases to
`ForwardedHostAddressAndPortExtractorTest`.

### 3. `Forwarded` host parsing consumes later list elements as part of the host

**Severity:** medium  
**Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68`

For a multi-element header where `host` is the final parameter of an element, for example
`Forwarded: for=192.0.2.1;host=example.com, for=198.51.100.2`, the code looks only for `;` to end
the `host=` value. With no subsequent semicolon, it passes the remainder of the field to
`extractHost`, which records `example.com, for=198.51.100.2` as `server.address`.

That is inconsistent with the same package's `for=` parser, which treats a comma as an address
terminator in `HttpServerAddressAndPortExtractor` (lines 113-122), and with
`ForwardedUrlSchemeProvider`, which ends `proto=` at either `,` or `;` (lines 70-79). The local
comment at lines 63-64 also says this operation finds the end of the `host=<address>` section;
letting the next forwarded element become part of the address violates that behavior.

**Suggested fix:** end the `host=` value at the first unquoted `;` or `,` (and preserve quoted
value handling), then add a multi-element `Forwarded` regression case.

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
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBiGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteSource.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionRequestAndContext.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/InstrumentationContexts.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorContextKeys.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyInstrumentationModule.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettySingletons.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ResponseReceiverInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractorTest.java`
