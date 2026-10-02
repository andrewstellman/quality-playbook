# otel, classifier S2 (Claude Sonnet), blind

### otel-01
Oracle: The method's own comment at line 51 ("the value after for= must not be empty") states the intent, but the bounds check `start >= forwarded.length() - 1` is off by one: for `Forwarded: for=1`, `start` equals `forwarded.length() - 1` and the branch fires even though a genuine one-character value is present, incorrectly treating it as empty.
Type: in-repo
Confidence: high

### otel-02
Oracle: The sibling extractor in the same package, `HttpServerAddressAndPortExtractor.extractClientInfo` (lines 92–101), explicitly special-cases a `[`-prefixed value as a bracketed IPv6 literal and strips the brackets; `ForwardedHostAddressAndPortExtractor.extractHost` has no such branch, so it finds the first `:` inside `[::1]:8080` (index 1) and truncates the address to `"["`.
Type: in-repo
Confidence: high

### otel-03
Oracle: `getHostEndIndexExclusive` (used to bound the host) deliberately stops at `?`/`#` as well as `/`, showing the code already treats those characters as terminating the authority/path region — but `getPath`'s `url.indexOf('/', hostEndIndexExclusive)` ignores that boundary and keeps scanning past a `?` or `#` it just found, picking up a `/` that lives inside the query or fragment.
Type: in-repo
Confidence: high

### otel-04
Oracle: Same off-by-one as otel-01, in the `host=` variant at line 60 (`start >= forwarded.length() - 1`), contradicting the adjacent comment "the value after host= must not be empty" for one-character values.
Type: in-repo
Confidence: high

### otel-05
Oracle: RFC 3986 §3.2.2 requires an IPv6 address in a URI authority to be written as an `IP-literal` in square brackets, with the brackets being part of host delimiters, not host content or a port separator. `getHostEndIndexExclusive` treats the first `:` it meets as a delimiter without ever recognizing `[...]`, so it stops one character into the literal.
Type: known-external
Confidence: high

### otel-06
Oracle: Same as otel-05 — `reactor-netty`'s `UrlParser.java` is a byte-for-byte copy of the incubator `UrlParser` lacking IPv6-bracket handling, and this file's own `getServerPort` fallback (lines 104–114, defaulting to 80/443 when `UrlParser.getPort` returns null) shows the authors anticipated `getPort` failing but not that `getHost` would silently return the garbage value `"["`.
Type: known-external
Confidence: high

### otel-07
Oracle: RFC 7239 §4 defines `Forwarded` (and by convention `X-Forwarded-Host`) as potentially containing a comma-separated list of hops, where only the first element is the relevant one for this extractor's purpose; the same file's own comment block (lines 66–73) already reasons directly from RFC 7239 for the sibling `for=` extractor, showing the author is working from that spec. Here, `extractFromForwardedHeader`'s `end` is only the next `;` (or end-of-string), so a second `host=` parameter is folded into the first value instead of being cut off at the comma.
Type: known-external
Confidence: medium

### otel-08
Oracle: Same off-by-one pattern as otel-01/otel-04, now for `proto=` at line 50 (`start >= forwarded.length() - 1`), with the copy-pasted comment "the value after for= must not be empty" (leftover from the `for=` version) confirming the intent that a one-character value should be accepted.
Type: in-repo
Confidence: high

### otel-09
Oracle: `HttpResponseReceiverInstrumenter.instrument`'s own comment ("receiver should always be an HttpClientFinalizer... modified should always be an HttpClientFinalizer too") documents an assumed invariant; if it's ever false, `instrument()` returns `null`, `AdviceScope.start` still constructs a `SkipMethodBodyAdviceScope` (so the real method body is skipped via `skipOn = Runnable.class`), and `end()`'s `if (modifiedReceiver != null)` branch is skipped too — so the real HTTP call is never issued and the method just returns the default (null) `returnValue` instead of falling back to calling the original, un-instrumented receiver.
Type: in-repo
Confidence: medium

### otel-10
Oracle: RFC 3986 §3.2 authority syntax is `[ userinfo "@" ] host [ ":" port ]`; `getHostStartIndex` only skips past `scheme://` and never looks for an `@`, so `getHostEndIndexExclusive`'s search for `:`/`/`/`?`/`#` starting right after `//` stops at the `:` inside `user:pw@host:9000`, treating `"user"` as the whole host.
Type: known-external
Confidence: high

### otel-11
Oracle: Same as otel-10 — the reactor-netty `UrlParser.getHostStartIndex`/`getHostEndIndexExclusive` have no userinfo handling, and `ReactorNettyHttpClientAttributesGetter.getServerPort` (lines 99–114) falls back to the scheme-default port (80 here) whenever `UrlParser.getPort` returns null, which is exactly what happens once `getHost` has already misparsed the address as `"user"`.
Type: known-external
Confidence: high

### otel-12
Oracle: `NetworkAttributesGetter.getNetworkProtocolVersion`'s own javadoc gives "Examples: 3.1.1" (a dotted version string), and a sibling implementation, `HttpUrlHttpAttributesGetter.getNetworkProtocolVersion`, hardcodes `"1.1"` rather than `"1"` for HTTP/1.x — but `ReactorNettyHttpClientAttributesGetter.getNetworkProtocolVersion` special-cases `minorVersion() == 0` to return only the bare major version `"1"` for HTTP/1.0, breaking the dotted-format convention every other getter in the repo follows.
Type: in-repo
Confidence: high

Hardest to classify were otel-07 and otel-09. otel-07 required judging whether RFC 7239's multi-hop comma-list semantics genuinely apply to the specific fields being read here (versus the extractor intentionally only caring about the first `;`-delimited segment for a different reason), so I could not push it above medium confidence. otel-09 was hard because the "defect" is gated entirely behind an assumption the author states as always holding ("receiver should always be... modified should always be...") — the code is demonstrably fragile if that invariant breaks, but I have no in-repo evidence that it ever does in practice, so I could not call it high confidence without knowing whether the guarded branch is reachable in real usage.
