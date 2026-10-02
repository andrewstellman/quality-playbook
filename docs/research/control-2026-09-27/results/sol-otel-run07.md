model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:26:22 UTC; finished 2026-09-28 22:28:57 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local Java probe
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# otel code review — run 07

Checkout: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`.

## Findings

1. **Medium — URL path can be read from a query or fragment.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73` calls `indexOf('/')` without bounding the search to the authority or stopping at `?`/`#`. For `https://example.com?next=/foo`, `getPath()` returns `/foo`, although the URL has no path. The parser's own tests at `UrlParserTest.java:168-178` establish that a URL with a query or fragment and no path should return `null`. `HttpClientServicePeerAttributesExtractor.java:96` passes this result into path-based service-peer matching, so a query or fragment can spuriously select a mapping. **Fix:** find the first authority delimiter (`/`, `?`, or `#`) and only parse a path when that delimiter is `/`.

2. **Medium — bracketed IPv6 URL hosts are truncated.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:109-110` and `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:82` treat every colon as the start of a port, including colons inside `[...]`. For `https://[::1]:8080`, both `getHost()` methods return `[` and both `getPort()` methods return `null`. The Reactor Netty getter uses these methods for `server.address` and `server.port` (`ReactorNettyHttpClientAttributesGetter.java:94,104`); the incubator resolver uses them to index service-peer mappings (`ServicePeerResolver.java:92-94`). The input is a valid URL authority, and both callers require the actual host and port. **Fix:** when the authority begins with `[`, scan to the closing `]`, then recognize a port only after that bracket; normalize the host to the expected IP-address representation.

3. **Medium — HTTP server forwarded-host parsing corrupts IPv6 addresses.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92` splits at the first colon regardless of brackets. For `Host: [::1]:8080`, `:authority: [::1]:8080`, or `Forwarded: host="[::1]:8080"`, it sets `server.address` to `[` and omits `server.port`. The extractor is the server's default address extractor (`HttpServerAttributesExtractorBuilder.java:56`), while the adjacent `HostAddressAndPortExtractorTest.java:74-89` explicitly treats bracketed IPv6 as a host with an optional port. **Fix:** parse the bracketed address through `]` and parse a following `:port`; use the same handling for all four header sources.

4. **Low — a one-character `Forwarded` host is discarded.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:60` rejects a value when `start == forwarded.length() - 1`. Thus `Forwarded: host=a` is treated as missing and the extractor falls back to another header, even though `a` is a nonempty host value. The comment on line 60 says only an empty value must be rejected, and the neighboring `host=` test confirms the empty case. **Fix:** reject only `start >= forwarded.length()`; let `extractHost` validate the remaining value.

## Verification

A standalone local Java probe compiled a copy of the incubator parser in the scratch directory. It returned `path=/foo` for `https://example.com?next=/foo` and `host=[, port=null` for `https://[::1]:8080`. The checkout was not modified.

## Files read

- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java` (relevant excerpts)
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/{CapturedHttpHeaders,ForwardedHostAddressAndPortExtractor,ForwardedUrlSchemeProvider,HeaderParsingHelper,HttpClientAttributesExtractor,HttpClientAttributesExtractorBuilder,HttpClientRequestResendCount,HttpCommonAttributesExtractor,HttpServerAddressAndPortExtractor,HttpServerAttributesExtractor,HttpServerAttributesExtractorBuilder,HttpServerRoute,HttpServerRouteBuilder,HttpServerRouteSource}.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/{ForwardedHostAddressAndPortExtractorTest,internal/HostAddressAndPortExtractorTest}.java` (latter via search excerpts)
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/{ConnectionWrapper,DecoratorFunctions,HttpResponseReceiverInstrumenter,InstrumentationContexts,ReactorNettyHttpClientAttributesGetter,TransportConnectorInstrumentation,UrlParser}.java`
