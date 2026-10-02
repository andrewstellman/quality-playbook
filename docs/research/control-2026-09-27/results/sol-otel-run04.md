model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:19:50 UTC; finished 2026-09-28 22:21:31 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review (78d71b585a77d7f2312c1b8751ff6c95a72722d7)

## Findings

1. **Medium — IPv6 authority is truncated in server attributes.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87–92` splits every host at the first colon. For a valid `Host: [2001:db8::1]:8443` (or equivalent `Forwarded`/`:authority`/`X-Forwarded-Host` value), it records `server.address="[2001"` and no `server.port`. This contradicts the extractor's purpose of obtaining server address and port, and `HttpServerAttributesExtractorBuilder.java:56,282–284` passes its output directly to `InternalServerAttributesExtractor`, which emits those attributes. Recognize bracketed IPv6 literals, take the address through `]`, and parse a port only after `]:`.

2. **Medium — a comma-separated `Forwarded` value contaminates the host.** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63–68` searches only for `;` when finding the end of `host=`. For `Forwarded: host=example.com, for=192.0.2.1`, it emits `server.address="example.com, for=192.0.2.1"`; for `host=example.com:443, for=...`, it loses the port as well. The code's own comment says this boundary is the end of the `host=<address>` section; the comma starts another forwarded element. Stop at the first unquoted semicolon **or comma**, and parse only the first element's host.

3. **Medium — the incubator URL parser misparses bracketed IPv6 hosts.** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105–110` treats the first `:` inside `[2001:db8::1]` as the port separator. For `https://[2001:db8::1]:8443/`, `getHost` returns `[2001`, and `getPort` returns null. `ServicePeerResolver.java:90–106` uses both results to index configured service peer mappings, so an IPv6 endpoint will not match its intended host and port. Scan through a matching `]` before looking for a port separator, and return the host consistently with the lookup representation.

4. **Medium — Reactor Netty client spans report a truncated IPv6 server.** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74–86` has the same first-colon split. For a request URL `https://[2001:db8::1]:8443/path`, `ReactorNettyHttpClientAttributesGetter.java:90–105` gets `server.address="[2001"` and falls back to port 443 instead of 8443. Its own `getHost`/`getPort` methods and the getter show the intended values. Parse bracketed IPv6 authority as a unit, then parse the optional port after `]`.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/network/internal/InternalServerAttributesExtractor.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/InstrumentationContexts.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
