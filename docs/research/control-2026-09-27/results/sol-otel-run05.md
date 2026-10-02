model: gpt-6-sol
repo: otel
pinned commit: 78d71b585a77d7f2312c1b8751ff6c95a72722d7
date/time started and finished: started approximately 2026-09-28 22:21:55 UTC; finished 2026-09-28 22:23:37 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: OpenTelemetry Java instrumentation (`78d71b585a77d7f2312c1b8751ff6c95a72722d7`)

## Findings

1. **IPv6 authority is parsed as an empty or truncated host** — **medium**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:87-92`. For `Host: [::1]:8080` (and likewise `:authority` or `Forwarded: host="[::1]:8080"`), the first colon is *inside* the bracketed address. `extractHost` nevertheless treats it as the host/port separator, sets `server.address` to `[`, and rejects the rest as a nonnumeric port. This contradicts the extractor's purpose of deriving the forwarded server address and port; the adjacent client-address extractor explicitly recognizes bracketed IPv6 (`HttpServerAddressAndPortExtractor.java:91-100`). **Fix:** recognize a leading `[` and locate its matching `]` before looking for an optional following `:port`; store the IPv6 address without brackets. Add cases for all three header forms.

2. **A comma-separated `Forwarded` header corrupts the selected host** — **medium**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:63-68`. With `Forwarded: for=192.0.2.1;host=first.example, for=198.51.100.2;host=second.example`, the first `host=` is found, but the end search only looks for `;`. The extractor therefore stores `first.example, for=198.51.100.2` as `server.address`. The server client-address parser in the same package terminates at commas (`HttpServerAddressAndPortExtractor.java:115-122`), establishing that a comma divides header elements. **Fix:** terminate an unquoted host value at the first `;` or `,`, with quote-aware handling so punctuation inside a quoted value is not treated as a separator.

3. **A valid one-character forwarded host is skipped** — **low**. `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:59-61`. For `Forwarded: host=a`, `start` points to the final character and the `start >= forwarded.length() - 1` guard rejects it, despite the comment requiring only a nonempty value. If a later fallback header exists, it is used instead of the forwarded host. **Fix:** change the empty-value check to `start >= forwarded.length()` and let `extractHost` validate the value.

4. **Incubator URL parser misidentifies IPv6 hosts and ports** — **medium**. `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java:105-110`. In a valid URL such as `https://[::1]:8080/path`, the first `:` inside brackets ends the host, so `getHost` returns `[` and `getPort` returns null. `ServicePeerResolver.java:90-105` uses these outputs to index configured peers by host/port, and `HttpClientServicePeerAttributesExtractor` uses the same parser for URLs; IPv6 mappings and attributes are consequently wrong. **Fix:** when authority starts with `[`, scan through the closing `]` before recognizing the optional port delimiter; add IPv6 URL tests.

5. **Reactor Netty URL parser misidentifies IPv6 server addresses** — **medium**. `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java:74-86`. The same first-colon rule parses `http://[::1]:8080/` as host `[` and no port. `ReactorNettyHttpClientAttributesGetter.java:90-114` feeds these values into HTTP client `server.address` and `server.port`, causing incorrect span attributes for IPv6 requests (and defaulting the port to 80/443 even when an explicit port was supplied). **Fix:** handle bracketed IPv6 authority before scanning for `:port`, and test the getter with IPv6 resource URLs.

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java` (selected lines)
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/service/peer/internal/ServicePeerResolver.java` (selected lines)
- `instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParserTest.java` (matching lines)
- All `.java` files in `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/` (16 files).
