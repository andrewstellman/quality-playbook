# Code review: opentelemetry-java-instrumentation @ 78d71b585a77d7f2312c1b8751ff6c95a72722d7

Reviewer: claude-opus-5-5 (control run)
Scope:
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`

The URL parser findings (1 and 2) were confirmed by compiling and running the in-scope `UrlParser` with JDK 25 in `/tmp/control-work/opus-otel/`. The rest come from reading the code against the tests and the documentation cited in each finding.

---

## 1. Incubator `UrlParser.getPath` returns a "path" taken from the query string or fragment

- **File/line:** `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/internal/UrlParser.java`, lines 74-77 (`int pathStartIndex = url.indexOf('/', hostEndIndexExclusive);`)
- **What goes wrong:** After finding the end of the host, the method searches for the next `/` anywhere in the rest of the string. It does not stop at `?` or `#`. So when a URL has no path but its query or fragment contains a `/`, that part is returned as the path. Observed output:
  - `getPath("https://host?q=/foo")` returns `"/foo"` (expected `null`)
  - `getPath("https://host:8080?redirect=/admin")` returns `"/admin"`
  - `getPath("https://host#/frag")` returns `"/frag"`
- **Why it is wrong:** `getPathEndIndexExclusive` treats `?` and `#` as the end of the path, and `UrlParserTest` expects `getPath("https://localhost?query")` to be `null`. In both, the query and fragment are not part of the path; the same holds in RFC 3986. The only reason the existing test passes is that its query has no `/`.
- **Impact:** `HttpClientServicePeerAttributesExtractor.getUrlPath` passes this value to `ServicePeerResolver`. A request such as `https://api?next=/billing` can then match a service-peer mapping keyed on path `/billing` and get the wrong `peer.service` / service-name attributes. `ServicePeerResolver.addMapping` also uses `getPath` on configured peers, and `RestTemplateInstrumentation` uses it for `url.template`.
- **Severity:** medium
- **Fix:** Search for the path start between `hostEndIndexExclusive` and the first `?`/`#`, and only accept a `/`:
  ```java
  int authorityEnd = getPortEndIndexExclusive(url, hostEndIndexExclusive); // first '/', '?', '#'
  if (authorityEnd >= url.length() || url.charAt(authorityEnd) != '/') {
    return null;
  }
  int pathStartIndex = authorityEnd;
  ```

## 2. Both `UrlParser` copies break on IPv6 literals and userinfo; reactor-netty then reports the wrong `server.port`

- **File/line:**
  - `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/.../v1_0/UrlParser.java`, `getHostEndIndexExclusive` (lines 72-85) and `getPort`
  - `instrumentation-api-incubator/.../semconv/net/internal/UrlParser.java`, `getHostEndIndexExclusive` (lines 104-110)
  - Consumer: `ReactorNettyHttpClientAttributesGetter.getServerAddress` / `getServerPort` (lines 90-114)
- **What goes wrong:** The host ends at the first `:`, even inside a bracketed IPv6 literal. The parser also does not skip `userinfo@`. Observed output:
  - `http://[::1]:8080/x` gives host `"["` and port `null`
  - `http://[2001:db8::1]/` gives host `"[2001"`
  - `http://user:pw@host:9000/x` gives host `"user"` and port `null`

  In reactor-netty, `getServerPort` then falls back to the scheme default. A request to `http://[::1]:8080/` is therefore reported as `server.address="["` and `server.port=80`. That is a wrong value, not just a missing one. The same `server.address`/`server.port` go into the `http.client.request.duration` metric attributes (see `HttpMetricsAdvice`).
- **Why it is wrong:** `server.address` must be the host. The HTTP client path in this same package already handles bracketed IPv6: `HostAddressAndPortExtractor` (lines 36-45) strips `[`/`]` and reads the port after `]:`. `HttpClientAttributesGetter.getUrlFull` documents the URL as RFC 3986, and RFC 3986 allows both IP-literals and userinfo.
- **Severity:** medium
- **Fix:** In `getHostStartIndex`, skip past the last `@` that comes before the first `/`, `?` or `#`. In `getHostEndIndexExclusive`, when the host starts with `[`, end it at the matching `]` (host = contents without brackets), and start the port only if `]` is followed by `:`. In reactor-netty, only fall back to 80/443 when the authority really has no port, not when parsing failed.

## 3. `ForwardedHostAddressAndPortExtractor` mis-parses IPv6 hosts and comma-separated values

- **File/line:** `instrumentation-api/.../semconv/http/ForwardedHostAddressAndPortExtractor.java`, `extractHost` (lines 72-96), and `extractFromForwardedHeader` (lines 64-68)
- **What goes wrong:**
  - **IPv6:** `host.indexOf(':', start)` finds the first colon inside a bracketed IPv6 literal. For `Host: [::1]:8080`, `:authority: [::1]:8080`, or `Forwarded: host="[::1]:8080"`, `server.address` becomes `"["`. The port substring `"::1]:8080"` then fails to parse, so no port is recorded.
  - **Lists:** Only `;` ends the `host=` value in `Forwarded`. `,` does not. A multi-hop `Forwarded: host=a.example, host=b.example` gives `server.address = "a.example, host=b.example"`. Likewise `X-Forwarded-Host: a.example, b.example` (a comma-separated list, as proxies commonly send it) gives `"a.example, b.example"`.
- **Why it is wrong:** RFC 7239 §4 says an IPv6 address and any node with a port MUST be quoted and bracketed in `Forwarded`, and elements are comma-separated. RFC 9110 Host syntax allows `IP-literal`. The sibling `HttpServerAddressAndPortExtractor.extractClientInfo` already handles `[...]` and stops at `,`. The internal `HostAddressAndPortExtractor` handles `[...]:port`. This class does neither.
- **Severity:** medium (server spans and the `http.server.request.duration` metric get a garbage `server.address` whenever a server sits behind IPv6 or behind chained proxies)
- **Fix:** In `extractHost`, if `host.charAt(start) == '['`, take the address up to the matching `]` (checked with `notFound(..., end)`) and parse the port only if `]` is followed by `:`. Treat `,` as a terminator, both when computing `end` in `extractFromForwardedHeader` and in `extractHost`, so that only the first element or list entry is used.

## 4. Off-by-one in `Forwarded` parsing rejects one-character values

- **File/line:**
  - `ForwardedHostAddressAndPortExtractor.java`, line 60
  - `HttpServerAddressAndPortExtractor.java`, line 53
  - `ForwardedUrlSchemeProvider.java`, line 50
- **What goes wrong:** `if (start >= forwarded.length() - 1)` returns early whenever the value after `host=`/`for=`/`proto=` is 0 **or 1** characters long, and only when that parameter comes last in the header. For example, `Forwarded: host=a` or `Forwarded: for=x` is ignored, and extraction falls through to lower-priority headers.
- **Why it is wrong:** Each line's comment says the check exists because "the value after host= must not be empty". A one-character value is not empty. The downstream helpers (`extractHost`, `extractClientInfo`, `extractProto`) already reject empty values themselves.
- **Severity:** low
- **Fix:** Use `if (start >= forwarded.length())`, or drop the check and rely on the downstream empty checks.

## 5. `ResponseReceiverInstrumentation.AdviceScope.start` skips the original method even when instrumentation is not possible, so `response()` and related methods return `null`

- **File/line:** `instrumentation/reactor/.../v1_0/ResponseReceiverInstrumentation.java`, `AdviceScope.start` (lines ~118-125) together with `end` (lines ~127-137)
- **What goes wrong:** `HttpResponseReceiverInstrumenter.instrument(receiver)` is `@Nullable`. It returns `null` when the receiver is not an `HttpClient` or when the modified client is not a `ResponseReceiver`. `start` still returns a `SkipMethodBodyAdviceScope`, which implements `Runnable`, so `skipOn = Runnable.class` skips the original `response()`/`responseContent()`/`responseSingle()`/etc. body. In `end`, `modifiedReceiver == null`, so it returns `returnValue`. Because the body was skipped, that value is the default `null`. The user's `Mono`/`Flux` becomes `null`, which causes an NPE in application code.
- **Why it is wrong:** The comment says the method body "will be skipped due to return type and 'skipOn' value". That is only safe when a replacement receiver exists. For nested calls, the non-skipping `AdviceScope(callDepth, null)` path already shows the intended fallback.
- **Severity:** low. The in-code comments say the receiver "should always be" an `HttpClientFinalizer`, so this needs a non-standard `ResponseReceiver` implementation (for example, a wrapper or decorator). When it does happen, the result is a hard failure caused by the agent.
- **Fix:**
  ```java
  HttpClient.ResponseReceiver<?> modified = HttpResponseReceiverInstrumenter.instrument(receiver);
  if (modified == null) {
    return new AdviceScope(callDepth, null); // do not skip the original body
  }
  return new SkipMethodBodyAdviceScope(callDepth, modified);
  ```

## 6. `network.protocol.version` is reported as `"1"` for HTTP/1.0

- **File/line:** `instrumentation/reactor/.../v1_0/ReactorNettyHttpClientAttributesGetter.java`, lines 83-86
- **What goes wrong:** `if (version.minorVersion() == 0) return Integer.toString(version.majorVersion());` turns `HTTP/1.0` into `"1"`, not `"1.0"`.
- **Why it is wrong:** The semantic conventions define `network.protocol.version` values as `1.0`, `1.1`, `2`, `3`. The HTTP extractors link to v1.23.0 of those conventions. The intent of the special case is to shorten `2.0` to `2`, but it also collapses `1.0`. `"1"` is not a valid HTTP version, and it cannot be told apart from other versions in metrics.
- **Severity:** low. The same pattern appears in the netty-common getters outside this scope, so the fix should be made consistently.
- **Fix:** Only drop the minor version for major version ≥ 2: `if (version.majorVersion() >= 2 && version.minorVersion() == 0) return Integer.toString(version.majorVersion());`

---

## Areas checked with no confident defects found

`HttpCommonAttributesExtractor` (method normalisation, `error.type` fallback, protocol name/version), `HttpClientAttributesExtractor`, `HttpServerAttributesExtractor`, both extractor builders, `CapturedHttpHeaders` (selector/exact-name handling), `HttpStatusCodeConverter`, `HttpSpanStatusExtractor`, `HttpSpanNameExtractor(+Builder)`, `HttpServerRoute(+Builder)` priority logic, `HttpClientRequestResendCount`, `HttpClient/ServerMetrics`, `HttpMetricsAdvice`, `ForwardedUrlSchemeProvider` (apart from #4), `HttpServerAddressAndPortExtractor` (apart from #4), reactor-netty `InstrumentationContexts`, `HttpResponseReceiverInstrumenter`, `DecoratorFunctions`, `FailedRequestWithUrlMaker`, `ConnectionWrapper`, `TransportConnectorInstrumentation`, `HttpClientConnectInstrumentation`, `HttpClientInstrumentation`, `ReactorNettySingletons`.

## Files read

In scope:
- instrumentation-api/.../semconv/http/: HttpCommonAttributesExtractor, HttpClientAttributesExtractor, HttpClientAttributesExtractorBuilder, HttpServerAttributesExtractor, HttpServerAttributesExtractorBuilder, HttpCommonAttributesGetter, HttpClientAttributesGetter, HttpServerAttributesGetter, ForwardedHostAddressAndPortExtractor, ForwardedUrlSchemeProvider, HeaderParsingHelper, HttpServerAddressAndPortExtractor, internal/HostAddressAndPortExtractor, CapturedHttpHeaders, HttpClientMetrics, HttpServerMetrics, HttpMetricsAdvice, HttpClientRequestResendCount, HttpStatusCodeConverter, HttpServerRoute, HttpServerRouteBuilder, HttpSpanNameExtractor, HttpSpanNameExtractorBuilder, HttpSpanStatusExtractor
- instrumentation-api-incubator/.../semconv/net/internal/UrlParser.java
- reactor-netty-1.0 v1_0/: UrlParser, ReactorNettyHttpClientAttributesGetter, FailedRequestWithUrlMaker, DecoratorFunctions, InstrumentationContexts, HttpResponseReceiverInstrumenter, ConnectionWrapper, ReactorNettySingletons, ConnectionRequestAndContext, ReactorContextKeys, HttpClientRequestHeadersSetter, HttpClientInstrumentation, ResponseReceiverInstrumentation, TransportConnectorInstrumentation, HttpClientConnectInstrumentation, ReactorNettyInstrumentationModule

For context (outside scope):
- instrumentation-api/.../config/IncludeExclude.java
- instrumentation-api-incubator/.../service/peer/internal/ServicePeerResolver.java (excerpt)
- instrumentation-api-incubator/.../semconv/http/HttpClientServicePeerAttributesExtractor.java (excerpt)
- instrumentation-api-incubator/src/test/.../net/internal/UrlParserTest.java (grep)
- instrumentation-api/src/test/.../semconv/http/ForwardedHostAddressAndPortExtractorTest.java and HttpServerAddressAndPortExtractorTest.java (grep)

Not read: HttpServerRouteBiGetter, HttpServerRouteGetter, HttpServerRouteSource, package-info (all trivial).
