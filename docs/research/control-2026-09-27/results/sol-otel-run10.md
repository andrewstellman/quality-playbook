model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:34:51 UTC; finished 2026-09-28 22:37:08 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review (78d71b585a77d7f2312c1b8751ff6c95a72722d7)

## Findings

1. **Medium — Comma-separated `Forwarded` elements contaminate `server.address`.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64`. For `Forwarded: for=1.2.3.4;host=example.com, for=5.6.7.8;host=proxy.example`, the extractor ends the `host` value only at `;`, so it records `example.com, for=5.6.7.8` as the server address. This contradicts the method's comment that it finds the end of the `host=<address>` section, and the adjacent `ForwardedUrlSchemeProvider.extractProto` explicitly treats a comma as a value terminator. Stop at the first unquoted comma or semicolon (and trim optional whitespace) before parsing the host.

2. **Medium — IPv6 host and port are parsed at the first colon.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87`. A valid `Forwarded: host="[2001:db8::1]:443"` (or `Host: [2001:db8::1]:443`) records address `[2001` and no port because the first IPv6 colon is treated as the host/port separator. This extractor supplies the HTTP server's `server.address` and `server.port` through `HttpServerAttributesExtractorBuilder.buildServerExtractor`; the neighboring `HostAddressAndPortExtractor` already handles bracketed IPv6. Parse the closing `]` first, strip brackets from the address, and parse a following `:port`.

3. **Medium — Reactor Netty records incorrect server host for IPv6 URLs.** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:82`. With `resourceUrl()` equal to `http://[::1]:8080/path`, `getHost` returns `[` and `getPort` attempts to parse `:1]:8080`, returning null; `ReactorNettyHttpClientAttributesGetter` then reports `server.address="["` and the default port 80 instead of the actual IPv6 host and port. The parser's own `getHostEndIndexExclusive` comment says `:` starts a port, but that is only true after a bracketed IPv6 literal. Skip colons until the closing `]`, then detect an optional port. The similar incubator parser at `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:110` has the same defect and should be fixed together.

4. **Low — A slash in the query or fragment is mistaken for a path.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73`. `getPath("https://example.com?next=/login")` returns `/login`, although the URL has no path; likewise a slash in the fragment becomes a path. The method's `getPathEndIndexExclusive` comment identifies `?` and `#` as path terminators, and the existing tests expect null for a URL with no path. Search for `/` only before the first `?` or `#` after the authority, or use a URI parser.

5. **Low — One-character `Forwarded` values are rejected as empty.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:60`. `Forwarded: host=a` has a nonempty host value, but `start == length - 1` makes this method reject it and use a later, less authoritative host header. The comment says only an empty value should be rejected. Use `start >= length`. The same off-by-one condition is present in `ForwardedUrlSchemeProvider.java:50` and `HttpServerAddressAndPortExtractor.java:57` for `proto` and `for` respectively.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`: `CapturedHttpHeaders.java`, `ForwardedHostAddressAndPortExtractor.java`, `ForwardedUrlSchemeProvider.java`, `HeaderParsingHelper.java`, `HttpClientAttributesExtractor.java`, `HttpClientAttributesExtractorBuilder.java`, `HttpClientRequestResendCount.java`, `HttpCommonAttributesExtractor.java`, `HttpServerAddressAndPortExtractor.java`, `HttpServerAttributesExtractor.java`, `HttpServerAttributesExtractorBuilder.java`, `HttpServerRoute.java`, `HttpServerRouteBuilder.java`, `HttpSpanNameExtractor.java`, `HttpSpanStatusExtractor.java`; `internal/HostAddressAndPortExtractor.java`.
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`.
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`: `ConnectionRequestAndContext.java`, `ConnectionWrapper.java`, `DecoratorFunctions.java`, `FailedRequestWithUrlMaker.java`, `HttpClientConnectInstrumentation.java`, `HttpClientInstrumentation.java`, `HttpResponseReceiverInstrumenter.java`, `InstrumentationContexts.java`, `ReactorNettyHttpClientAttributesGetter.java`, `ReactorNettyInstrumentationModule.java`, `ReactorNettySingletons.java`, `ResponseReceiverInstrumentation.java`, `TransportConnectorInstrumentation.java`, `UrlParser.java`.
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`, `ForwardedUrlSchemeProviderTest.java`.
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`.
