# otel, classifier S3 (Claude Sonnet), blind

### otel-01
Oracle: The method's own comment at line 50 ("the value after for= must not be empty") states the intent, but the check `start >= forwarded.length() - 1` (line 51) is an off-by-one: for `for=1`, `start` equals `forwarded.length() - 1`, tripping the guard even though the character at `start` is a valid non-empty value. `HttpServerAddressAndPortExtractorTest` tests the true-empty case (`"for="`) but has no single-character case, so the gap is untested.
Type: in-repo
Confidence: high

### otel-02
Oracle: `extractHost` (lines 87–93) finds the port separator with a plain `host.indexOf(':', start)`, with no special-casing for a bracketed IPv6 literal, so the first `:` inside `[::1]` is mistaken for the host/port separator. RFC 3986 §3.2.2 requires an IP-literal host to be bracketed and the authority parser to treat the whole bracketed token as the host before looking for a port colon.
Type: known-external
Confidence: high

### otel-03
Oracle: The method's own design, documented in the `getHostEndIndexExclusive` comment (lines 106–108: "look for the end of the host: ':' ==> start of port, or '/', '?', '#' ==> start of path"), establishes that `?`/`#` mark the end of the authority. But `getPath` (line 73) then calls `url.indexOf('/', hostEndIndexExclusive)`, which searches past that same boundary into the query/fragment text rather than stopping there — contradicting the method's own stated contract.
Type: in-repo
Confidence: high

### otel-04
Oracle: Identical off-by-one to otel-01, in the sibling class: the line-59 comment "the value after host= must not be empty" states intent, but line 60's `start >= forwarded.length() - 1` incorrectly rejects a genuine single-character value. `ForwardedHostAddressAndPortExtractorTest` tests `"host="` (empty) but not a length-1 value.
Type: in-repo
Confidence: high

### otel-05
Oracle: Same root cause as otel-02 but in `getHostStartIndex`/`getHostEndIndexExclusive`: no bracket-aware parsing exists anywhere in the file (confirmed by reading the whole class), so `[::1]` and `[2001:db8::1]` are split at the first internal `:`. RFC 3986 §3.2.2 defines the bracketed `IP-literal` host form this class doesn't special-case.
Type: known-external
Confidence: high

### otel-06
Oracle: This file is a byte-for-byte duplicate of the incubator `UrlParser`'s `getHostEndIndexExclusive`/`getHostStartIndex` logic, with the same missing IPv6-bracket handling, and it's used directly by `ReactorNettyHttpClientAttributesGetter.getServerAddress/getServerPort` (lines 92–115), so the malformed `"["` address and wrong port propagate straight into recorded span attributes. Root correctness contract is RFC 3986 §3.2.2 (bracketed IP-literal host).
Type: known-external
Confidence: high

### otel-07
Oracle: `extractHost`/`extractFromForwardedHeader` never split on `,` to select the first (client-facing) hop, so a second `host=`/comma-separated value gets appended verbatim into `server.address`, including the literal `host=` token — that's not a "which hop wins" judgment call, it's raw un-parsed text leaking into an address field. RFC 7239 §4 defines the Forwarded header as a comma-separated list of per-hop elements, from which one hop's `host` parameter should be extracted, not the raw remainder of the string.
Type: known-external
Confidence: high

### otel-08
Oracle: Same off-by-one family as otel-01/otel-04. Line 50's guard `start >= forwarded.length() - 1` incorrectly rejects a genuine single-char `proto=` value; the accompanying comment even says "the value after for= must not be empty" — a copy-pasted comment referencing the wrong field name, corroborating that this logic was copied from `HttpServerAddressAndPortExtractor` and carries its bug.
Type: in-repo
Confidence: high

### otel-09
Oracle: `HttpResponseReceiverInstrumenter.instrument`'s comment (lines 25–31, "receiver should always be an HttpClientFinalizer... modified should always be an HttpClientFinalizer too") frames the `null`-return path as an unexpected/defensive case. But `AdviceScope.start` (lines 102–110) unconditionally returns a `SkipMethodBodyAdviceScope` at call-depth 0 regardless of whether `instrument()` returned non-null, so ByteBuddy skips the real method body before it's known whether a substitute receiver exists; when `instrument()` returns null, `end()` has nothing to delegate to and returns the skipped (null) value instead of the real call result.
Type: in-repo
Confidence: medium

### otel-10
Oracle: `getHostStartIndex` (lines 86–103) returns the index right after `://` with no check for an `@` userinfo delimiter, so `user:pw@host:9000` is parsed as if `user` were the host and `pw@host:9000` the "port" (which then fails to parse as an integer, yielding null). RFC 3986 §3.2 defines `authority = [ userinfo "@" ] host [ ":" port ]`, which requires skipping past `userinfo@` before the host begins.
Type: known-external
Confidence: high

### otel-11
Oracle: Same missing-userinfo-handling defect as otel-10, duplicated verbatim in this package's own `UrlParser.getHostStartIndex` (lines 55–72), and consumed directly by `ReactorNettyHttpClientAttributesGetter.getServerAddress/getServerPort`. Correctness contract is RFC 3986 §3.2 (authority = `[userinfo "@"] host [":" port]`).
Type: known-external
Confidence: high

### otel-12
Oracle: Sibling implementations of the identical `getNetworkProtocolVersion` contract in this same repo return `"1.0"` explicitly for HTTP/1.0 (`Vertx4HttpAttributesGetter`/`Vertx5HttpAttributesGetter`, `case HTTP_1_0: return "1.0";`), and the shared cross-instrumentation test harness (`testing-common/.../HttpClientTestOptions.java`, `AbstractHttpClientTest.java`, `AbstractHttpServerTest.java` line 1205) expects dotted values like `"1.1"`/`"2"`. `ReactorNettyHttpClientAttributesGetter`'s `minorVersion() == 0 → Integer.toString(majorVersion())` shortcut (meant for HTTP/2 and HTTP/3, which carry no minor version) incorrectly also catches HTTP/1.0, collapsing it to `"1"`.
Type: in-repo
Confidence: high

The hardest to classify were otel-07 and otel-09. otel-07 sits between "wrong per an RFC's list-parsing rule" and "obviously wrong regardless of any spec" — I settled on known-external because RFC 7239's per-hop element structure is what tells you *what* the correct extracted value should be, even though the literal `host=` leaking into the output is self-evidently broken on its face. otel-09 was hardest because the surrounding comment explicitly frames the triggering condition ("modified should always be an HttpClientFinalizer") as effectively unreachable in real Reactor Netty usage, so the code path is a genuine logic defect by inspection but its practical exploitability is unclear from the checkout alone, which is why I gave it medium rather than high confidence.
