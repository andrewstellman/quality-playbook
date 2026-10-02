model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:04:22 UTC; finished 2026-09-28 23:07:41 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# OpenTelemetry Java Instrumentation Review

Reviewed commit `78d71b585a77d7f2312c1b8751ff6c95a72722d7` in the requested scope. I found the following confirmed defects.

## 1. Valid one-character `Forwarded` parameter values are rejected

- **Files and lines:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java:51`; `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:60`; `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java:50`
- **Severity:** medium
- **What goes wrong:** Each parser treats a value whose final character is immediately after `for=`, `host=`, or `proto=` as empty. For example, `Forwarded: for=a`, `Forwarded: host=a`, and `Forwarded: proto=h` are all valid nonempty parameter values, but the respective extractor/provider rejects them and either falls back to a lower-priority source or omits the attribute.
- **Why this is wrong:** The comments say the value “must not be empty,” but `start` has already been advanced past the equals sign. The current `start >= forwarded.length() - 1` therefore rejects the last character as well. The adjacent tests establish that these methods are meant to parse `Forwarded` parameters and accept values up to the end of the header (for example `host=example.com` and `proto=xyz`).
- **Suggested fix:** Change each guard to `start >= forwarded.length()` (or, more directly, let the downstream range parser reject an empty range). Add tests for one-character values that end the header.

## 2. `Forwarded` host parsing does not stop at an element separator

- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:64-68`
- **Severity:** medium
- **What goes wrong:** A valid header with a `host` parameter followed by another forwarded element, such as `Forwarded: host=example.com,for=192.0.2.1`, sets `server.address` to `example.com,for=192.0.2.1`. The code only recognizes `;` as the end of the parameter value.
- **Why this is wrong:** The same package’s `HttpServerAddressAndPortExtractor.extractClientInfo` explicitly treats both `,` and `;` as forwarding-field delimiters (`HttpServerAddressAndPortExtractor.java:115`). `ForwardedHostAddressAndPortExtractor` is intended to extract the host field from the same header but consumes text after the comma as if it were part of the authority.
- **Suggested fix:** End the host parameter at the first `;` *or* `,` after `host=` (whichever comes first), before passing the range to `extractHost`. Add a multiple-element `Forwarded` test.

## 3. Forwarded/Host authorities containing IPv6 are split at their first colon

- **File and line:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-93`
- **Severity:** medium
- **What goes wrong:** For `Forwarded: host="[2001:db8::1]:443"`, as well as a normal `Host: [2001:db8::1]:443` fallback, the extractor records the address as `[2001` and does not record port 443. It treats the first colon inside the bracketed IPv6 literal as the host/port delimiter.
- **Why this is wrong:** Bracketed IPv6 is an authority form that the project already handles in its ordinary client Host parser: `HostAddressAndPortExtractor.java:35-43` locates `]`, removes the brackets, then parses a following port. The server-side forwarded-host extractor is also responsible for `:authority` and `Host` (lines 39-50), so it should support the same authority form.
- **Suggested fix:** Before looking for a colon, detect a leading `[`, find the matching `]`, set the address to the text inside it, and parse a port only when a colon follows the closing bracket. Preserve the existing quoted-value handling. Add cases for both quoted `Forwarded` and unquoted `Host`/`:authority` IPv6 authorities.

## 4. URL parsers cannot parse RFC 3986 bracketed IPv6 authorities

- **Files and lines:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-111`; `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`
- **Severity:** medium
- **What goes wrong:** For a valid absolute URL such as `http://[::1]:8080/path`, both parsers stop the host at the first colon and return `[` as the host. They then cannot parse the port. In the Reactor Netty getter, this additionally causes `getServerPort` to fall back to 80 because the malformed parse returns `null` (`ReactorNettyHttpClientAttributesGetter.java:104-113`), so a request to IPv6 port 8080 is attributed as server address `[` and port 80.
- **Why this is wrong:** `HttpClientAttributesGetter.getUrlFull` documents that the URL is an RFC 3986 absolute URL (`HttpClientAttributesGetter.java:26-32`), for which an IPv6 literal in an authority is bracketed. The loop in each parser assumes every colon begins a port, which contradicts that URL format and produces demonstrably invalid server attributes.
- **Suggested fix:** Make host-end detection recognize a leading `[` and find its matching `]`; return the enclosed address and parse a port only from a colon after that bracket. Add host, port, and path tests for URLs with bracketed IPv6 and a nondefault port.

## 5. Failed Reactor Netty requests construct an invalid URL for configured IPv6 remotes

- **File and line:** `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/FailedRequestWithUrlMaker.java:67-73`
- **Severity:** medium
- **What goes wrong:** When a request with a relative URI fails before a response and `remoteAddress` is an IPv6 `InetSocketAddress`, `computeUrlFromConfig` concatenates the unbracketed `getHostString()` and port. It yields strings like `http://0:0:0:0:0:0:0:1:8080/path`, which are not a valid IPv6 URI authority. The proxy is then used to create the connection-error telemetry span, so its URL/server attributes are wrong exactly on this failure path.
- **Why this is wrong:** The method’s purpose is to reconstruct a full resource URL for `FailedHttpClientRequest` (see `HttpResponseReceiverInstrumenter.java:121-125`). A URI authority must bracket an IPv6 literal to distinguish it from the port. The local `UrlParser` then misreads the malformed string as well, compounding the incorrect attributes.
- **Suggested fix:** Build the URL with a URI/authority builder, or wrap an IPv6 literal in `[` and `]` before concatenating the port. Add a failed-relative-request test using an IPv6 `InetSocketAddress` and assert the resulting URL and server attributes.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpMetricsAdvice.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/network/internal/ServerAddressAndPortExtractor.java`
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
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProviderTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorTest.java`
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java`
