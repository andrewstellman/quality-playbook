# otel, classifier S1 (Claude Sonnet), blind

### otel-01
Oracle: The method's own comment says "start is now the index after for=" / "the value after for= must not be empty," but the guard `start >= forwarded.length() - 1` rejects any single-character value too (e.g. `for=1` has `start == forwarded.length() - 1`), contradicting the stated non-empty intent (HttpServerAddressAndPortExtractor.java:51-52). No existing test (HttpServerAddressAndPortExtractorTest) exercises a length-1 `for=` value, so this isn't test-caught, but the comment vs. code mismatch is unambiguous.
Type: in-repo
Confidence: high

### otel-02
Oracle: The sibling parser `HttpServerAddressAndPortExtractor.extractClientInfo` (same file family, same header format) explicitly special-cases `[` to find the matching `]` before treating `:` as a port separator (lines ~92-99), but `ForwardedHostAddressAndPortExtractor.extractHost` (line 87) has no such bracket handling and just does `host.indexOf(':', start)`, which matches the first colon inside `[::1]`. RFC 7239/RFC 3986 IP-literal syntax (`"[" IPv6address "]"`) is the known-external backing.
Type: in-repo
Confidence: high

### otel-03
Oracle: The class's own existing test `UrlParserTest.testGetPath` establishes the invariant that `getPath` returns `null` when there is no `/`-delimited path segment right after the host/port (e.g. `getPath("https://localhost?query")` → null). `getPath` (line 73) finds the path start via `url.indexOf('/', hostEndIndexExclusive)`, which searches inside the query/fragment text too, so a `/` embedded in the query or fragment is wrongly treated as the start of the path, violating that established invariant.
Type: in-repo
Confidence: high

### otel-04
Oracle: Same off-by-one as otel-01, in the parallel `host=` extractor: comment "the value after host= must not be empty" contradicts the `start >= forwarded.length() - 1` guard rejecting length-1 values (ForwardedHostAddressAndPortExtractor.java:60-61).
Type: in-repo
Confidence: high

### otel-05
Oracle: Same bracket-handling gap as otel-02 but in the shared `UrlParser` used by `getHost`/`getPort`: `getHostEndIndexExclusive` (line 105) treats the first `:` as the host terminator with no IPv6-bracket special case, unlike the sibling `extractClientInfo` bracket handling elsewhere in the repo. RFC 3986 §3.2.2 IP-literal syntax is the known-external backing for what "correct" looks like.
Type: in-repo
Confidence: high

### otel-06
Oracle: This `UrlParser` in the reactor-netty module is a near-verbatim copy of the incubator `UrlParser` (diff shows identical `getHostStartIndex`/`getHostEndIndexExclusive` logic), so it inherits the same IPv6-bracket bug as otel-05. Additionally, `ReactorNettyHttpClientAttributesGetter.getServerPort` (lines ~93-105) falls back to the scheme-default port (80/443) whenever `UrlParser.getPort` returns null, which is exactly what happens here — the getPort's null combines with the fallback to produce the observed `server.port=80` for an explicit `:8080`, compounding the bug.
Type: in-repo
Confidence: high

### otel-07
Oracle: `HttpServerAddressAndPortExtractor.extractClientInfo` (used for the analogous `for=`/X-Forwarded-For case) explicitly stops at a comma as an address terminator (`c == ',' || c == ';' ...`), but `ForwardedHostAddressAndPortExtractor.extractFromForwardedHeader`/`extractHost` never checks for `,` — it only splits on `;` (for `Forwarded`) and never splits at all for X-Forwarded-Host — so a comma-joined list is swallowed whole into the address. RFC 7239 §4 (comma-separated forwarded-element list) and the conventional multi-hop format of `X-Forwarded-Host` are the known-external backing for what should happen instead.
Type: in-repo
Confidence: high

### otel-08
Oracle: Identical off-by-one bug to otel-01/otel-04, and the comment is even a stale copy-paste: `ForwardedUrlSchemeProvider.extractProtoFromForwardedHeader` (line 50) has the guard `start >= forwarded.length() - 1` with the comment "the value after for= must not be empty" — literally referencing `for=` inside a `proto=` parser, confirming the logic (and comment) were copied from the `for=` extractor without adjustment, and the same non-empty-value guard incorrectly rejects single-character values.
Type: in-repo
Confidence: high

### otel-09
Oracle: `HttpResponseReceiverInstrumenter.instrument()`'s own comments assert the receiver "should always be an HttpClientFinalizer" and the modified client "should always be" one too, treating a null return as a defensive/theoretically-unreachable case — but `AdviceScope.start()` unconditionally builds a `SkipMethodBodyAdviceScope` (which skips the original method body via `skipOn = Runnable.class`) around whatever `instrument()` returns, including null, and `end()` only calls through when `modifiedReceiver != null`; otherwise it returns the advice's (unset) `returnValue`, i.e., null. So if the "should always be" assumption is ever false, the real `response()`/`responseContent()`/etc. call is dropped rather than falling back to un-instrumented execution. There's no unit test exercising this path (no test references `HttpResponseReceiverInstrumenter`), so this is inferred purely from control flow and the class's own comments, not demonstrated.
Type: in-repo
Confidence: medium

### otel-10
Oracle: The repo has multiple other URL/authority parsers that explicitly recognize and strip userinfo before `@` (e.g. `R2dbcServerTarget.java:29-37` splits on `@` for user info, `JdbcConnectionUrlParserTest.java` has dedicated userinfo-ambiguity tests, `ApacheHttpClientRequest.java:99` uses `uri.getUserInfo()`), but `UrlParser.getHostStartIndex`/`getHostEndIndexExclusive` has no `@` handling at all, so it stops at the first `:` inside `user:pw@host`. The formal backing is RFC 3986 §3.2 authority grammar (`[ userinfo "@" ] host [ ":" port ]`).
Type: known-external
Confidence: high

### otel-11
Oracle: Same as otel-10 — this `UrlParser` is a verbatim copy of the incubator one (confirmed via diff) and inherits the missing `@`/userinfo handling, and `ReactorNettyHttpClientAttributesGetter.getServerPort` (same fallback-to-scheme-default logic as otel-06) compounds it into `server.port=80`.
Type: known-external
Confidence: high

### otel-12
Oracle: `CHANGELOG.md` records a prior, deliberate semconv-compliance fix: "Update network.protocol.version `2.0` -> `2` and `3.0` -> `3`" (PR #9145) — establishing that only versions without a real minor component (HTTP/2, HTTP/3) get collapsed to the bare major number, while versions with a genuine minor (HTTP/1.0, HTTP/1.1) are expected to keep `major.minor`. This is corroborated by the sibling getter `Vertx5HttpAttributesGetter.getNetworkProtocolVersion` (and the 4.0 variant), which explicitly returns `"1.0"` for `HTTP_1_0` and `"1.1"` for `HTTP_1_1`. `ReactorNettyHttpClientAttributesGetter.getNetworkProtocolVersion` (line 84) instead does `if (version.minorVersion() == 0) return Integer.toString(version.majorVersion())`, collapsing HTTP/1.0 to `"1"` — contradicting both the changelog-documented convention and the vertx sibling implementation. (The same flawed pattern also appears in `AsyncHttpClientHttpAttributesGetter` and `AwsSdkHttpAttributesGetter`, suggesting it was copied around rather than independently invented.)
Type: in-repo
Confidence: high

Hardest to classify: otel-09 was the hardest — it hinges on interpreting the intent behind a defensive "should always be an HttpClientFinalizer" comment and byte-buddy `skipOn`/`CallDepth` control flow rather than any directly-stated contract or test, so I can describe exactly what the code does but I'm inferring rather than pointing to a stated spec for what it "should" do in the fallback case. otel-07 and otel-10/11 were next-hardest to pin to a single type: the X-Forwarded-Host comma-list convention isn't a hard RFC (it's de facto/MDN-documented), and the userinfo-in-authority case is well-specified externally (RFC 3986) even though the repo also has plenty of in-repo sibling code that treats userinfo as a real concept — I had to pick which oracle I'd actually rely on rather than citing both as equally load-bearing.
