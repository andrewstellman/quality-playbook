model: gpt-5.6-terra
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 23:04:22 UTC; finished 2026-09-28 23:08:26 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Code review: OpenTelemetry Java instrumentation

Reviewed commit `78d71b585a77d7f2312c1b8751ff6c95a72722d7` in the requested HTTP, network URL-parser, and Reactor Netty scopes.

## Findings

### 1. Port parsing throws for ordinary absolute URLs with no explicit port

**Severity:** high

**Locations:**

- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:46-57`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:41-52`

For an ordinary URL such as `https://localhost`, `getHostEndIndexExclusive()` returns `url.length()`. The condition at line 46/41 only rejects a non-colon delimiter when that index is *less* than the length, so execution instead sets `portStartIndex` to `url.length() + 1` and evaluates `substring(url.length() + 1, url.length())`. That throws `StringIndexOutOfBoundsException` instead of returning `null`.

This contradicts both modules' unit tests, which explicitly require `getPort("https://localhost")` to return `null` (`instrumentation-api-incubator/.../UrlParserTest.java:88` and `reactor-netty-1.0/javaagent-unit-tests/.../UrlParserTest.java:88`). The Reactor Netty getter directly calls this method before its default-port fallback (`ReactorNettyHttpClientAttributesGetter.java:100-114`), so requests to normal URLs without an explicit port trigger the exception during attribute extraction.

**Suggested fix:** Require the host terminator to exist and be `':'` before calculating the port start, for example:

```java
if (hostEndIndexExclusive >= url.length() || url.charAt(hostEndIndexExclusive) != ':') {
  return null;
}
```

Apply the same correction to both copies and run the existing no-port cases.

### 2. The URL parsers do not parse bracketed IPv6 authorities

**Severity:** medium

**Locations:**

- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-116`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-100`

The host scan treats every `:` as the port delimiter. A valid URL such as `https://[2001:db8::1]:8443/path` therefore produces `"[2001"` as the host; `getPort()` starts at the first IPv6 colon and cannot parse `"db8::1]:8443"` as an integer. In Reactor Netty, `ReactorNettyHttpClientAttributesGetter` uses these methods for `server.address` and `server.port` (lines 92-114), so it records an invalid address and falls back to port 443 instead of the explicit 8443. The incubator parser is also used by HTTP service-peer resolution (`HttpClientServicePeerAttributesExtractor.java:90-96` and `ServicePeerResolver.java:90-106`).

The parser's own comment says it is locating the host and port in an authority, and `HttpClientAttributesGetter#getUrlFull` documents RFC 3986 absolute URLs, where bracketed IPv6 is a valid authority form.

**Suggested fix:** Detect an authority beginning with `[`; find its matching `]`, return the contents as the host, and only treat the following colon as a port separator. Add host/port tests for `https://[::1]` and `https://[2001:db8::1]:8443` to both parser test suites.

### 3. Forwarded server-address parsing mishandles IPv6 Host, :authority, and Forwarded values

**Severity:** medium

**Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:71-93`

`extractHost()` also treats the first colon as a port separator without recognizing brackets. Consequently, all of `Host: [::1]:8443`, `:authority: [::1]:8443`, and `Forwarded: host="[::1]:8443"` set the address to `"["` and fail to parse the port. This extractor is the default server-address extractor installed by `HttpServerAttributesExtractorBuilder` (lines 49-57 and 282-284), so server spans for IPv6 virtual hosts receive incorrect `server.address` and omit `server.port`.

The nearby `HttpServerAddressAndPortExtractor` explicitly handles a bracketed IPv6 address (lines 91-100), and its comment cites the Forwarded-header bracket rule. That establishes the expected handling which this related extractor lacks.

**Suggested fix:** Reuse the bracket-aware logic from `HostAddressAndPortExtractor`/`HttpServerAddressAndPortExtractor`: on `[`, find `]`, emit the text between brackets as the address, and parse a port only from a colon immediately following that bracket. Add this case to the existing `ForwardedHostAddressAndPortExtractorTest` for each supported header source.

### 4. A comma-separated Forwarded header is captured past the current element

**Severity:** medium

**Location:** `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68`

The parser chooses the end of `host=` by looking only for `';'`. Comma separates forwarded elements, however, and the adjacent `ForwardedUrlSchemeProvider` explicitly recognizes commas as a terminator (lines 70-76). Thus `Forwarded: for=192.0.2.1;host=example.test,for=198.51.100.1` causes this class to set `server.address` to `"example.test,for=198.51.100.1"`; with `host=example.test:8443,for=...`, it loses the port because the candidate port includes the following element.

The comment at line 63 says the code is finding the end of the `host=<address>` section, so including the next forwarded element is contrary to its stated parsing intent.

**Suggested fix:** Stop the unquoted host value at the first of either `';'` or `','` (and retain the existing quoted-value behavior). Add comma-terminated examples to `ForwardedHostAddressAndPortExtractorTest`.

### 5. `getPath` can take a slash from the query string as the URL path

**Severity:** low

**Location:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:73-83`

`getPath()` searches for `'/'` from the end of the host through the remainder of the URL, without first checking whether `?` or `#` ended the authority. For `https://example.test?next=/internal`, it returns `/internal` even though the URL has no path; the slash belongs to the query. The test suite establishes that a URL with a query and no path must return `null` (`UrlParserTest.java:168`), and this input is the same case with a legal slash-containing query value.

This value feeds HTTP service-peer matching through `HttpClientServicePeerAttributesExtractor` (lines 82-96), so a configured path-specific mapping can match based on a query parameter instead of the actual request path.

**Suggested fix:** Find the first authority terminator among `/`, `?`, and `#`. Return `null` unless that first terminator is `/`; then scan the path only until `?` or `#`. Add a regression case such as `https://localhost?next=/api/v1`.

## Files read

- `AGENTS.md`, `CONTRIBUTING.md`, and `.github/agents/knowledge/README.md`, plus the applicable Javaagent, virtual-field, nullability, library-pattern, and semantic-convention guidance.
- `CapturedHttpHeaders.java`, `ForwardedHostAddressAndPortExtractor.java`, `ForwardedUrlSchemeProvider.java`, `HeaderParsingHelper.java`, `HttpClientAttributesExtractor.java`, `HttpClientAttributesExtractorBuilder.java`, `HttpClientAttributesGetter.java`, `HttpCommonAttributesExtractor.java`, `HttpCommonAttributesGetter.java`, `HttpServerAddressAndPortExtractor.java`, `HttpServerAttributesExtractor.java`, `HttpServerAttributesExtractorBuilder.java`, `HttpServerAttributesGetter.java`, `HttpServerRoute.java`, `HttpServerRouteBuilder.java`, `HttpSpanNameExtractor.java`, `HttpSpanNameExtractorBuilder.java`, `HttpStatusCodeConverter.java`, `HttpSpanStatusExtractor.java`, `HttpClientMetrics.java`, `HttpServerMetrics.java`, `HttpMetricsAdvice.java`, `HttpClientRequestResendCount.java`, and `internal/HostAddressAndPortExtractor.java`.
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`.
- `ConnectionRequestAndContext.java`, `ConnectionWrapper.java`, `DecoratorFunctions.java`, `FailedRequestWithUrlMaker.java`, `HttpClientConnectInstrumentation.java`, `HttpClientInstrumentation.java`, `HttpResponseReceiverInstrumenter.java`, `InstrumentationContexts.java`, `ReactorContextKeys.java`, `ReactorNettyHttpClientAttributesGetter.java`, `ReactorNettySingletons.java`, `ResponseReceiverInstrumentation.java`, `TransportConnectorInstrumentation.java`, and `UrlParser.java` from the requested Reactor Netty package.
- `ForwardedHostAddressAndPortExtractorTest.java`, `ForwardedUrlSchemeProviderTest.java`, `HttpServerAddressAndPortExtractorTest.java`, both `UrlParserTest.java` files, `HttpClientServicePeerAttributesExtractor.java`, and `ServicePeerResolver.java`.
