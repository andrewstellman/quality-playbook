# otel-java BUG-002: incubator + reactor-netty `UrlParser` truncate bracketed IPv6 authorities

**Verdict: CONFIRMED** (reproduced red on unpatched upstream in both copies, green with the same 13-line change in each).

| | |
|---|---|
| Upstream | https://github.com/open-telemetry/opentelemetry-java-instrumentation |
| Pinned SHA | `78d71b585a77d7f2312c1b8751ff6c95a72722d7` (committed 2026-09-27 10:18:36 +0300) |
| Historical finding | `QPB/repos/secbench2_widenet/wn-jvm-02-opentelemetry-java-instrumentation/quality/BUGS.md` BUG-002 (QPB v1.5.8, 2026-06-23) |
| Patch | `0001-Handle-bracketed-IPv6-hosts-in-UrlParser.patch` (author Andrew Stellman, `Assisted-by: Claude Opus 5.5` trailer) |
| Files touched | `instrumentation-api-incubator/.../semconv/net/internal/UrlParser.java` (+13), `instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/.../v1_0/UrlParser.java` (+13), both `UrlParserTest.java` (+1 test each), `ServicePeerResolverTest.java` (+1 mapping, +2 rows) |

## What is wrong (probe-upstream.log, red.log)
Unmodified upstream, both parsers:
```
getHost("http://[::1]:8080/")              = "["      getPort = null
getHost("https://[2001:db8::1]:8443/path") = "[2001"  getPort = null
```
`getHostEndIndexExclusive` stops at the first `:` — inside the brackets.

Where the values go (source-read at the pinned SHA; only the first is attribute-level certain):
- reactor-netty 1.0 `ReactorNettyHttpClientAttributesGetter.getServerAddress` returns `UrlParser.getHost(resourceUrl)`
  → HTTP client `server.address = "["`; `getServerPort` gets `null` from `UrlParser.getPort` and falls back to
  443/80, so `server.port` is the scheme default instead of the URL's port (e.g. 80 for `http://[::1]:8080/`).
- clickhouse-client-v2-0.8 `CurrentServerInfo.of` passes `UrlParser.getHost/getPort(endpoint)` into `ClickHouseDbRequest` (not traced further).
- `ServicePeerResolver.addMapping` parses each `service_peer_mapping` `peer` with `UrlParser`; a peer `"[::1]:8080"`
  is keyed under host `"["` with no port, so it never matches `server.address="::1", server.port=8080`
  (red.log: `ServicePeerResolverTest` row `::1, 8080 → ipv6PortSvc` fails `expected: "ipv6PortSvc" but was: null`).

## Expected behaviour — grounding
- RFC 3986 §3.2 `authority = [ userinfo "@" ] host [ ":" port ]`; §3.2.2 `host = IP-literal / IPv4address / reg-name`,
  `IP-literal = "[" ( IPv6address / IPvFuture ) "]"`, and IP literals are "distinguished by enclosing the IP literal within square brackets ("[" and "]"). This is the only place where square bracket characters are allowed in the URI syntax."
  So the host ends at the closing `]` and the port delimiter is the `:` that follows it.
- OTel semconv registry `server.address`: "Server domain name if available without reverse DNS lookup; otherwise, IP address or UNIX domain socket name." `[` / `[2001` is not an IP address.
- In-repo consistency: `HostAddressAndPortExtractor` (#19540), `RedisServerTarget` (`redis://[::1]:6379` → `::1`), and the
  JDBC normalization work (#19366 "Normalize IPv6 server.address in JDBC URL parsing") all emit the address
  **without** brackets. The fix follows that: `getHost` returns `::1`.

## Fix (identical in both files)
- `getHostEndIndexExclusive`: if the authority starts with `[`, the host ends after the matching `]`
  (an unterminated `[` is treated as a missing host → `getHost`/`getPort` return `null`).
- `getHost`: strip the enclosing brackets (returns `null` for `[]`).
`getPort` and `getPath` need no change once the host end index is right.

Behaviour changes worth stating in the PR: (1) `getHost` returns `2001:db8::1`, not `[2001:db8::1]`
(java.net.URI.getHost style) — decision point below; (2) for the malformed `https://[::1/path`, `getHost`
goes from `"["` to `null` and incubator `getPath` from `"/path"` to `null`.

## Method
Same standalone harness as otel-java BUG-001 (see that README; `harness/run.sh`, `harness/logs.sh`, `harness/deps.SHA1SUMS`).
**Not Gradle** — a Gradle 9.7.1/JDK 25 run filled the sandbox disk during configuration.
- `incubator` suite: javac of all of `instrumentation-api/src/main`, then `UrlParser`, `ServicePeerResolver`,
  `ServicePeerAttributesExtractor`, `HttpClientServicePeerAttributesExtractor` from `instrumentation-api-incubator/src/main`
  (`-sourcepath` pulls in what they reference). Tests: `UrlParserTest`, `ServicePeerResolverTest`,
  `ServicePeerAttributesExtractorTest`, `HttpClientServicePeerAttributesExtractorTest` (plus the
  `:testing-common` helper `SemconvServiceStabilityUtil` compiled from source). This is a subset of
  `:instrumentation-api-incubator:test` — the UrlParser consumers only.
- `reactor` suite: javac of the reactor-netty `UrlParser.java` alone + its `UrlParserTest` (the other tests in
  `javaagent-unit-tests` need reactor-netty jars; not run).
- JDK 25.0.4.1 (Ubuntu package, extracted without root). Formatting of changed files checked with
  google-java-format 1.36.1 (clean). Spotless/checkstyle/errorprone/nullaway/muzzle not run.

## Logs (each file has part 1 = incubator, part 2 = reactor-netty)
| file | incubator | reactor-netty |
|---|---|---|
| module-tests-before.log | 39 passed, 0 failed | 8 passed, 0 failed |
| red.log | 20 passed, **2 failed** | 0 passed, **1 failed** |
| green.log | 22 passed, 0 failed | 1 passed, 0 failed |
| module-tests-after.log | 42 passed, 0 failed | 9 passed, 0 failed |
Note: `testGetHostAndPortWithIpv6` stops at its first failing assertion (`expected: "::1" but was: "["`);
`probe-upstream.log` shows the full set of wrong values.

## Disclosure search (GitHub REST search API via web_fetch, 2026-09-27)
| query | result |
|---|---|
| `repo:… UrlParser` | 12 hits: #19852, #16953, #16071, #18368, #17662, #13434, #14501, #7294 "Refactor UrlParser" (2022), #8007, #6417, #9061, #8804 — none about IPv6/brackets; none open |
| `repo:… ipv6` | 77 hits; IPv6 work is on Host header (#19540), JDBC (#19366), DB endpoint utilities (#20015/#20016), ClickHouse/R2DBC/Redis targets — none touch `UrlParser` |
| `repo:… ipv6 is:open` | 1 hit, #16161 (gRPC) — unrelated |
| `repo:… reactor-netty ipv6` | 3 hits (#9117, #3205, #5557) — unrelated |
**Not already reported.**
