# Code Review: opentelemetry-java-instrumentation

**Repo:** otel (open-telemetry/opentelemetry-java-instrumentation)
**Pinned commit:** 78d71b585a77d7f2312c1b8751ff6c95a72722d7
**Scope:**
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/`
- `instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv/net/`
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/`

## Defects found

### 1. Off-by-one in the "value must not be empty" check rejects legitimate single-character `Forwarded` header values

**Files / lines:**
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java:60`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java:50`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java:51`

**What goes wrong:** All three call sites use the same pattern to reject an empty value after a `Forwarded` header key (`host=`, `proto=`, `for=`):

```java
start += "host=".length(); // start is now the index after host=
if (start >= forwarded.length() - 1) { // the value after host= must not be empty
  return false;
}
```

`start >= forwarded.length()` is the correct test for "nothing follows the `=`" (i.e., the value is empty). The code instead tests `start >= forwarded.length() - 1`, which is off by one: it also rejects the case where **exactly one character** follows the key, even though a single character is a non-empty, well-formed value.

Verified with a standalone reproduction of the exact boundary check:
```
host=a   -> treated as empty? true   (should be false; "a" is a 1-char, non-empty host)
host=ab  -> treated as empty? false  (correct)
for=1    -> treated as empty? true   (should be false)
proto=h  -> treated as empty? true   (should be false)
```

So `Forwarded: host=a`, `Forwarded: proto=h`, or `Forwarded: for=1` (or any header where the `host=`/`proto=`/`for=` value is exactly one character) is silently discarded by these extractors and treated the same as a malformed/empty value, even though the comment directly above the check states the intent is only to reject an actually-empty value.

**Why it is wrong:** The code's own comment ("the value ... must not be empty") establishes the intended behavior — reject *empty* values only. A single character is not empty. The off-by-one causes the extractor to fall through to a lower-priority source (e.g. `X-Forwarded-Host`/`Host` header, or `network.peer.address`) instead of using the valid `Forwarded` value, silently producing wrong `server.address`, `url.scheme`, or `client.address` attributes for this edge case.

**Severity:** Low (the affected input — a single-character host/proto/for value — is rare in practice, but the defect is a clear, provable logic error, and it exists identically in three separate parsers, suggesting the bug was copy-pasted).

**Suggested fix:** Change the boundary check in all three locations from
```java
if (start >= forwarded.length() - 1) {
```
to
```java
if (start >= forwarded.length()) {
```

## Areas reviewed but found correct

- `UrlParser` (both the `instrumentation-api-incubator` internal copy and the private copy in `reactor-netty-1.0`): the two implementations are functionally identical (the incubator version additionally exposes `getPath`); host/port/path boundary scanning was traced by hand against representative inputs and matches the documented behavior.
- `HttpServerAddressAndPortExtractor`'s `X-Forwarded-For`/`Forwarded: for=` parsing: confirmed (via `HttpServerAddressAndPortExtractorTest`) that port is deliberately never populated from these headers (`sink.getPort()` is asserted `null` in every parameterized case) — this looked suspicious at first (the code computes an "IPv4 port separator" but never calls `sink.setPort`) but is intentional and test-covered, not a defect.
- `HttpServerRoute` / `HttpServerRouteSource` priority-and-longest-route logic (`SERVER_FILTER`/`NESTED_CONTROLLER` "use longest" vs `SERVER`/`CONTROLLER` "use first") is internally consistent with its documentation.
- `HttpStatusCodeConverter`, `HttpSpanStatusExtractor`, `HttpSpanNameExtractor`, `HttpCommonAttributesExtractor`/`HttpClientAttributesExtractor`/`HttpServerAttributesExtractor` (method/known-method fallback, `error.type`, status code capture, header capture, route re-stamping at `onEnd`) all match the semantic-conventions behavior described in their Javadoc.
- `CapturedHttpHeaders` selector/exact-name/enumeration logic.
- `HttpClientRequestResendCount` (atomic field updater usage is correct: initialized once via CAS, incremented via `AtomicIntegerFieldUpdater`).
- `InstrumentationContexts` in the reactor-netty package: the `Queue<RequestAndContext>` used to track overlapping resend attempts is drained (`poll()`) on every `endClientSpan` call regardless of which branch resolves the context, which looked initially like a mismatch risk, but the primary lookup path uses a `VirtualField` keyed by the actual `HttpClientRequest`/response object, and the queue is best-effort/comment-documented for the interleaved-resend edge case; no incorrect behavior could be demonstrated from reading the call sites.
- `DecoratorFunctions`, `HttpClientInstrumentation`, `HttpResponseReceiverInstrumenter`, `ResponseReceiverInstrumentation`, `FailedRequestWithUrlMaker`, `HttpClientRequestHeadersSetter`: instrumentation wiring reviewed; no logic errors found in the reviewed control flow (call-depth accounting, `try/finally` scope closing order, proxy-based `resourceUrl()` fallback for failed requests, IllegalStateException swallowing for header/status access on a not-yet-available response).

I did not find any other defects I was confident enough to report (no build was possible in this environment — no Gradle — so all analysis was via direct reading plus a small standalone Java reproduction of the boundary-check logic above).

## Files read

- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/CapturedHttpHeaders.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedUrlSchemeProvider.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HeaderParsingHelper.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpClientRequestResendCount.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpCommonAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpMetricsAdvice.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAttributesGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerMetrics.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRoute.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBiGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteGetter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerRouteSource.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanNameExtractorBuilder.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpSpanStatusExtractor.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/HttpStatusCodeConverter.java`
- `instrumentation-api/src/main/java/io/opentelemetry/instrumentation/api/semconv/http/internal/HostAddressAndPortExtractor.java`
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
- `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java`
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/HttpServerAddressAndPortExtractorTest.java` (for context/verification)
- `instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http/ForwardedHostAddressAndPortExtractorTest.java` (for context/verification)
