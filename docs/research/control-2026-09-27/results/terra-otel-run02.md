model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:57:31 UTC; finished 2026-09-28 23:00:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry review — `terra-otel-run02`

Reviewed commit: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`

## Findings

### 1. IPv6 authorities are split at their first colon

- **Severity:** medium
- **Files/lines:**
  - `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-111`
  - `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`
- **Failure:** A normal bracketed IPv6 URL such as `https://[2001:db8::1]:8443/path` is parsed as host `"[2001"` and has no port. The host-end scan treats the first `:` as a port delimiter, although it is inside the IPv6 literal. In Reactor Netty this feeds `ReactorNettyHttpClientAttributesGetter.getServerAddress()` and `getServerPort()`, so client spans record a corrupt `server.address` and, after the parser returns no port, the default `443` instead of explicit port `8443`. The incubator parser is used for URL path/peer mapping and likewise cannot correctly identify an IPv6 endpoint.
- **Why this is wrong:** Both parsers explicitly parse URL host and port components, and their existing tests establish that `host:port` must yield the host and numeric port. Bracketed IPv6 literals are valid URL authority hosts; a colon inside the brackets cannot denote the port separator.
- **Suggested fix:** When the authority begins with `[`, scan through the matching `]`, return the characters inside the brackets as the host, and treat only the colon immediately following `]` as the optional port separator. Add host/port/path tests for IPv6 URLs with and without an explicit port.

### 2. Reactor Netty generates an invalid absolute URL for failed IPv6 requests

- **Severity:** medium
- **File/line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:70-73`
- **Failure:** When a request fails before a usable request URL is available and the configured remote address is IPv6, `InetSocketAddress.getHostString()` is concatenated without brackets. For example, address `2001:db8::1`, port `8443`, and path `/docs` produces `https://2001:db8::1:8443/docs`, which is not a valid URL authority and is subsequently misparsed as server address `2001` with no explicit port. The failure path uses this proxy request specifically to create the error span, so those connection-error spans have incorrect URL/server attributes for IPv6 targets.
- **Why this is wrong:** The method comment says it constructs a full URL from the configured host and port. An IPv6 host in a URL authority must be enclosed in brackets; the output above has no unambiguous host/port boundary.
- **Suggested fix:** Detect an IPv6 literal (for example, an address containing `:` that is not already bracketed) and concatenate `[` + host + `]` before the optional port. Add a failed-request test using an IPv6 `InetSocketAddress`.

### 3. Server host extraction corrupts IPv6 `Host` / `:authority` / `Forwarded host` values

- **Severity:** medium
- **File/line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-93`
- **Failure:** `Host: [2001:db8::1]:8443` (and the equivalent `:authority` or `Forwarded: host="[2001:db8::1]:8443"`) sets the server address to `"[2001"` and attempts to parse the remaining IPv6 text as a port, leaving `server.port` unset. This extractor is installed as the HTTP server extractor's `serverAddressPortExtractor`, so the emitted server attributes are wrong for requests addressed to an IPv6 virtual host.
- **Why this is wrong:** The extractor intentionally supports the HTTP Host and HTTP/2 `:authority` forms, both of which use bracketed IPv6 literals to distinguish the host from an optional port. Splitting every value at the first colon cannot parse that defined form.
- **Suggested fix:** Add a bracketed-authority branch before the generic colon split: locate `]`, set the address from the enclosed literal, and parse a port only when `]:` follows. Add tests for IPv6 with and without a port across `Host`, `:authority`, and `Forwarded`.

### 4. `Forwarded` parameter lookup accepts an extension parameter ending in `host` as `host`

- **Severity:** low
- **File/line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:54-68`
- **Failure:** The raw substring lookup accepts `Forwarded: by=proxy;xhost=attacker.example` as though it contained a `host` parameter: `indexOf("host=")` starts at the `host=` portion of `xhost=`, then records `attacker.example` as the server address. `Forwarded` permits extension parameters, so `xhost` is a valid distinct parameter name. The same issue occurs for a string in another parameter value containing `host=`.
- **Why this is wrong:** The surrounding code says it is extracting the `host` member of the `Forwarded` header. A parameter is only `host` at a member/parameter boundary; matching a suffix of a different parameter changes the reported server identity even though no `host` member was supplied.
- **Suggested fix:** Tokenize comma-separated Forwarded elements and semicolon-separated parameters (respecting quoted strings), then compare each parameter name case-insensitively to `host`. At minimum, require a valid start/boundary before `host=` and stop at both `;` and `,`.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBiGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpMetricsAdvice.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- all Java sources under `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMakerTest.java`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParserTest.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
