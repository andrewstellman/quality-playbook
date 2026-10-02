model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:08:00 UTC; finished 2026-09-28 23:11:21 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: OpenTelemetry Java instrumentation (`78d71b585a77d7f2312c1b8751ff6c95a72722d7`)

## Findings

### 1. Valid IPv6 authorities are parsed as `[` (and lose their port)

- **Severity:** medium
- **Files/lines:**
  - `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:81-83, 104-108`
  - `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/ReactorNettyHttpClientAttributesGetter.java:92-114`
- **What goes wrong:** A normal Reactor Netty request to an IPv6 URI such as `http://[2001:db8::1]:8080/path` produces `server.address="["` and no parsed explicit port. The parser treats the first colon inside the bracketed literal as the host/port delimiter, so `getHost()` returns the substring before it and `getPort()` attempts to parse `db8::1]:8080`.
- **Why this is wrong:** `ReactorNettyHttpClientAttributesGetter` directly uses these results for `server.address` and `server.port`. The shared HTTP `HostAddressAndPortExtractor` explicitly handles bracketed IPv6 and its tests establish the expected address `2001:db8::1` and port `42` for `[2001:db8::1]:42` (`HostAddressAndPortExtractor.java:35-44`, `HostAddressAndPortExtractorTest.java:74-92`).
- **Suggested fix:** Teach the Reactor Netty URL parser to recognize an authority that begins with `[`, locate its closing `]`, return the enclosed IPv6 literal as the host, and parse a port only when a colon follows that bracket. Add cases with and without an explicit port.

### 2. The failed-request URL builder emits an invalid URL for IPv6 remote addresses

- **Severity:** medium
- **File/line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:67-73`
- **What goes wrong:** When a request fails before Reactor Netty can provide a usable request URL and the configured remote address is IPv6, `InetSocketAddress.getHostString()` is concatenated without brackets. For example, `2001:db8::1` with port 8080 becomes `https://2001:db8::1:8080/docs`, which is not an RFC 3986 authority and is subsequently misparsed by the client getter.
- **Why this is wrong:** This proxy is specifically used to supply `resourceUrl()` on the connection-error path (`HttpResponseReceiverInstrumenter.java:121-125`). The getter contract says `getUrlFull()` returns an absolute RFC 3986 URL (`HttpClientAttributesGetter.java:26-33`), so the substitute request must preserve a valid authority. IPv6 literals in a URI authority require brackets; the existing tests only cover DNS hostnames (`FailedRequestWithUrlMakerTest.java:52-82`).
- **Suggested fix:** Detect IPv6 host strings (or use the address form that renders a URI host) and enclose them in `[` and `]` before appending an optional port. Add a failed-request test with an IPv6 `InetSocketAddress`.

### 3. Server address extraction cannot parse bracketed IPv6 Host/Forwarded host values

- **Severity:** medium
- **File/line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:71-93`
- **What goes wrong:** For a server request with `Host: [2001:db8::1]:8443`, `:authority` of the same form, or `Forwarded: host="[2001:db8::1]:8443"`, the first colon is interpreted as the host/port separator. The extractor records `server.address="["` and cannot parse the remaining port.
- **Why this is wrong:** `HttpServerAttributesExtractorBuilder` installs this extractor as the server-address source (`HttpServerAttributesExtractorBuilder.java:56, 282-284`). The repository's other Host-header extractor has an explicit bracketed-IPv6 branch and tests the required result (`HostAddressAndPortExtractor.java:35-44`; `HostAddressAndPortExtractorTest.java:74-92`). The absence of that branch here makes HTTP server telemetry incorrect for valid IPv6 authorities.
- **Suggested fix:** In `extractHost`, handle a leading `[` before searching for `:`: find `]`, set the enclosed address, and parse the port only if the next character is `:`. Cover Host, `:authority`, `X-Forwarded-Host`, and quoted `Forwarded host` inputs.

### 4. `Forwarded` host parsing consumes later forwarding elements as part of the address

- **Severity:** medium
- **File/line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68`
- **What goes wrong:** A single, valid multi-element header such as `Forwarded: host=public.example, for=10.0.0.1` reaches `extractHost` with `end == forwarded.length()`, because the code recognizes only `;` as a terminator. It emits `server.address="public.example, for=10.0.0.1"` instead of `public.example`. With an explicit port, the port substring likewise includes the later element and fails numeric parsing.
- **Why this is wrong:** The adjacent client-address parser explicitly treats `,` as an element terminator (`HttpServerAddressAndPortExtractor.java:103-128`) and its tests include `for=[::1], for=1.2.3.4` (`HttpServerAddressAndPortExtractorTest.java:62-84`). `ForwardedHostAddressAndPortExtractor` is the corresponding source for the server address, so it must stop at the same forwarding-element boundary rather than attach untrusted proxy metadata to the address attribute.
- **Suggested fix:** End the `host=` parameter at the first unquoted `;` or `,` (and parse quoted values within that element). Add tests for comma-separated elements with hosts both with and without ports.

### 5. The shared URL parser also mishandles valid bracketed IPv6 URLs used by service-peer mappings

- **Severity:** medium
- **File/line:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-116`
- **What goes wrong:** `UrlParser.getHost("https://[2001:db8::1]:8443/api")` returns `"["`, and `getPort` returns `null`. Consequently a `service_peer_mapping` for `[2001:db8::1]:8443` is indexed under the wrong host and cannot match the normal extracted address/port.
- **Why this is wrong:** `ServicePeerResolver.addMapping` constructs an HTTPS URL and obtains its host/port through this parser before indexing the mapping (`ServicePeerResolver.java:90-106`). As in the Reactor parser, the colon scanner does not account for bracketed literals. The repository's Host extractor demonstrates the expected parsing behavior for `[2001:db8::1]:42` (`HostAddressAndPortExtractor.java:35-44`).
- **Suggested fix:** Share or implement bracket-aware authority parsing in this URL parser, including IPv6 literals with and without ports, and add service-peer or parser regression tests for those cases.

## Files read

- `AGENTS.md`
- `CONTRIBUTING.md`
- `.github/agents/knowledge/README.md`
- `.github/agents/knowledge/semconv-conformance.md`
- `.github/agents/knowledge/javaagent-advice-patterns.md`
- `.github/agents/knowledge/javaagent-virtual-fields.md`
- All Java files in `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- Relevant HTTP semantic-convention tests under `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/http/HttpClientServicePeerAttributesExtractor.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
- All Java files in `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`
- Reactor Netty unit tests `UrlParserTest.java` and `FailedRequestWithUrlMakerTest.java`
