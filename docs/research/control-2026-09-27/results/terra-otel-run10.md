model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:11:43 UTC; finished 2026-09-28 23:15:04 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry Java Instrumentation review

Reviewed commit `78d71b585a77d7f2312c1b8751ff6c95a72722d7` in the requested paths. I found the following defects.

## 1. `Forwarded: proto=` rejects every one-character scheme

- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java:50`
- **Severity:** medium
- **What goes wrong:** A valid one-character `Forwarded` protocol value, such as `Forwarded: proto=h`, is discarded. `start` points at the `h`, but `start >= forwarded.length() - 1` is true when that value is the final character, so the method returns `null`. The server extractor consequently falls back to the transport scheme instead of the forwarded scheme.
- **Why it is wrong:** The comment says the check only rejects an empty value. `proto=h` is nonempty, and the existing `extractProto` method already handles a one-character token correctly. The immediately adjacent `X-Forwarded-Proto` path accepts the same value through that method.
- **Suggested fix:** Change the guard to `if (start >= forwarded.length())`, preserving rejection only when there is no character after `proto=`. Add a test for `proto=h`.

## 2. `Forwarded: host=` rejects every one-character host

- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:60`
- **Severity:** medium
- **What goes wrong:** `Forwarded: host=a` does not populate the server address and causes the extractor to try later headers. The same off-by-one condition treats the final `a` as if the value were empty.
- **Why it is wrong:** The comment on line 60 states that the code is checking for an empty value, but `host=a` contains a valid nonempty host token. `extractHost` itself accepts a one-character host when called directly, so the validation is inconsistent with its parser.
- **Suggested fix:** Use `start >= forwarded.length()` instead. Add `host=a` (and ideally quoted `host="a"`) to the forwarded-header tests.

## 3. IPv6 authorities are parsed as `[` by the forwarded-host fallback

- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`
- **Severity:** medium
- **What goes wrong:** For ordinary IPv6 authorities such as `Host: [2001:db8::1]:8443`, `:authority: [2001:db8::1]:8443`, `X-Forwarded-Host: [2001:db8::1]:8443`, or `Forwarded: host="[2001:db8::1]:8443"`, the first colon is treated as the port separator. The extractor records `server.address` as `[` and cannot parse the port.
- **Why it is wrong:** The fallback is constructed by `HttpServerAttributesExtractorBuilder` for the server-address/port attributes. The sibling `HostAddressAndPortExtractor` explicitly handles a leading `[` and extracts the bracketed IPv6 literal before parsing an optional port (lines 35-44), establishing the required handling for exactly this HTTP authority syntax.
- **Suggested fix:** Before searching for `:`, detect a leading `[`, locate the matching `]`, set the address to the contents, and parse a port only if the following character is `:`. Add coverage for every source accepted by this extractor, at least `Host` and `Forwarded`.

## 4. Reactor Netty records invalid server attributes for RFC 3986 IPv6 URLs

- **File and line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86` (used by `ReactorNettyHttpClientAttributesGetter.java:92-114`)
- **Severity:** medium
- **What goes wrong:** For a valid request URL such as `http://[2001:db8::1]:8080/path`, `getHost` returns `[` and `getPort` tries to parse `db8::1]:8080`, returning `null`. The getter then emits `server.address="["` and falls back to port 80/443 according to scheme, instead of `2001:db8::1` and 8080.
- **Why it is wrong:** `HttpClientAttributesGetter#getUrlFull` documents that this value is an absolute RFC 3986 URL. Bracketed IPv6 literals are valid authorities in that format, and the getter uses this parser specifically to supply `server.address` and `server.port`.
- **Suggested fix:** Parse the authority as a bracketed IP literal when it begins with `[`: use the closing `]` as the host boundary and treat only a colon following it as the port delimiter. Add URL-parser tests for bracketed IPv6 with and without an explicit port.

## 5. Service-peer mappings with IPv6 endpoints never match normal server attributes

- **File and line:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-117`
- **Severity:** medium
- **What goes wrong:** A configured service-peer mapping such as `[2001:db8::1]:8080` is prefixed with `https://` by `ServicePeerResolver` and parsed by this class. The parser returns `[` as its host and `null` as its port. The resolver indexes the mapping under that wrong host, while instrumentations report the server address as `2001:db8::1` and port 8080; the configured mapping therefore cannot resolve.
- **Why it is wrong:** `ServicePeerResolver.addMapping` explicitly parses the configured peer into host, port, and path (lines 90-106) so it can match separately reported `server.address` and `server.port`. The parser's colon-at-first-character rule does not implement the bracketed IPv6 authority form and breaks that stated matching path.
- **Suggested fix:** Share a correct authority parser (or add the same bracket-aware logic as above) for host, port, and path boundary detection. Add service-peer resolver coverage for an IPv6 endpoint with an explicit port.

## Files read

Primary reviewed files:

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ConnectionWrapper.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/DecoratorFunctions.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientConnectInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpClientInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/HttpResponseReceiverInstrumenter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/InstrumentationContexts.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettySingletons.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ResponseReceiverInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/TransportConnectorInstrumentation.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`

Context and test files read:

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/network/internal/ClientAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/network/internal/ServerAddressAndPortExtractor.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorTest.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParserTest.java`
