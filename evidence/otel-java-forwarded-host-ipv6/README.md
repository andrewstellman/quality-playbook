# otel-java BUG-001 (rescoped): `ForwardedHostAddressAndPortExtractor` truncates bracketed IPv6 hosts

**Verdict: CONFIRMED** (reproduced red on unpatched upstream, green with a 14-line fix).

| | |
|---|---|
| Upstream | https://github.com/open-telemetry/opentelemetry-java-instrumentation |
| Pinned SHA | `78d71b585a77d7f2312c1b8751ff6c95a72722d7` (committed 2026-09-27 10:18:36 +0300, "Mark bundled sampler dependency for removal in 3.0 (#20284)") |
| Historical finding | `QPB/repos/secbench2_widenet/wn-jvm-02-opentelemetry-java-instrumentation/quality/BUGS.md` BUG-001 (QPB v1.5.8 run, 2026-06-23, code-only review) |
| Patch | `0001-Handle-bracketed-IPv6-hosts-in-ForwardedHostAddressA.patch` (author Andrew Stellman, `Assisted-by: Claude Opus 5.5` trailer) |
| Files touched | `instrumentation-api/.../semconv/http/ForwardedHostAddressAndPortExtractor.java` (+14), `ForwardedHostAddressAndPortExtractorTest.java` (+10 cases), `HttpServerAttributesExtractorTest.java` (+1 test) |

## Rescope vs. the historical finding
The historical BUG-001 bundled two sites. `internal/HostAddressAndPortExtractor` was fixed upstream by
PR #19540 (merged; closed issue #15158 "Consider ipv6 when extracting server name from host header",
closed 2026-08-19). That PR changed only `HostAddressAndPortExtractor`. The sibling
`ForwardedHostAddressAndPortExtractor.extractHost` — the extractor `HttpServerAttributesExtractor` uses for
`server.address`/`server.port` from `Forwarded: host=`, `X-Forwarded-Host`, `:authority` and `Host` — still
splits on the first `:`. This patch is scoped to that one method only.

The historical writeup's "becomes `[`" output is reproduced for `[::1]`-style inputs; for
`[2001:db8::1]:42` the value is `[2001` (both in red.log).

## What is wrong (observed on unpatched upstream, red.log)
`HttpServerAttributesExtractor` with request header `Host: [2001:db8::1]:8080` emits
`{server.address="[2001"}` and no `server.port` (test `shouldExtractIpv6ServerAddressAndPortFromHostHeader`).
The extractor-level cases fail the same way for `X-Forwarded-Host`, `:authority`, `Host` and quoted
`Forwarded: host="[...]"`: `expected: "::1" but was: "["`, `expected: "2001:db8::1" but was: "[2001"`.

## Expected behaviour — grounding
- RFC 3986 §3.2.2: `host = IP-literal / IPv4address / reg-name`, `IP-literal = "[" ( IPv6address / IPvFuture ) "]"`;
  "A host identified by an IPv6 literal address is represented inside the square brackets". §3.2 `authority = [ userinfo "@" ] host [ ":" port ]`
  — so the port separator is the `:` after `]`, not the first `:`.
- RFC 7239 §5.3: the `host` value "MUST conform to the Host ABNF described in Section 5.4 of [RFC7230]"
  (i.e. `uri-host [ ":" port ]`, uri-host from RFC 3986). §6: "an IPv6 address and any nodename with
  node-port specified MUST be quoted" — hence the quoted `host="[::1]:42"` test rows.
- OTel semconv, HTTP spans ("Setting server.address and server.port attributes"): "`Host` and `:authority` headers contain host and port number of the server. The same applies to the `host` identifier of `Forwarded` header or the `X-Forwarded-Host` header. Instrumentations SHOULD populate both `server.address` and `server.port` attributes by parsing the value of corresponding header."
  Registry `server.address`: "Server domain name if available without reverse DNS lookup; otherwise, IP address or UNIX domain socket name." `[` / `[2001` is none of these.
- In-repo precedent for the exact expected value (brackets stripped): `internal/HostAddressAndPortExtractor`
  after #19540 (`setAddress("2001:db8::1")` in `HostAddressAndPortExtractorTest`), and the `for=` branch of
  `HttpServerAddressAndPortExtractor.extractClientInfo`. The fix mirrors those two branches.

## Fix
Add a `[`-branch in `extractHost` (after the existing quote-stripping branch): find `]` within the
value; if missing → return `false` (malformed, same as the existing unterminated-quote handling, so the
next header source is tried); otherwise address = text between the brackets, and if `]` is followed by
`:`, parse the port after it with the existing `HeaderParsingHelper.setPort`.

## Method (read this before trusting the logs)
**Not Gradle.** A Gradle run was attempted with JDK 25 (the version CONTRIBUTING.md requires) and
exhausted the sandbox disk during configuration (`/tmp/gradle-home` reached 2.7 GB; root fs 100% full,
"Could not update .../last-build.bin"). Instead, `harness/run.sh`:
- JDK: OpenJDK 25.0.4.1 (Ubuntu `openjdk-25-jdk-headless` 25.0.4.1+1-1~22.04.4, extracted with `apt-get download` + `dpkg -x` into /tmp — no root).
- javac compiles **all** of `instrumentation-api/src/main/java` from the checkout (auto-value processor on), then the test sources.
- Test selection ("module tests"): every test class in `io.opentelemetry.instrumentation.api.semconv.http` (+ `.internal`) **except**
  `HttpClientMetricsTest`, `HttpServerMetricsTest`, `HttpSpanNameExtractorTest` (they need the `:testing-common` /
  `:instrumentation-api-incubator` project deps). 429 tests before, 452 after. This is not the whole
  `:instrumentation-api:test` task.
- Runner: JUnit Platform Console Standalone 1.14.4, JVM flags from `instrumentation-api/build.gradle.kts` (`--add-opens` java.lang/java.util).
- Jars from Maven Central at the versions in `dependencyManagement/build.gradle.kts` (otel 1.66.0, semconv 1.44.0, junit 5.14.4, assertj 3.27.7, mockito 4.11.0, byte-buddy 1.18.14, auto-value 1.11.1), each verified against Central's `.sha1` (`harness/deps.SHA1SUMS`).
  Substitution: `error_prone_annotations` 2.42.0 instead of the project's 2.50.0 (compile-only annotations; no runtime effect).
- `logs.sh`: red = pinned SHA + only the branch's test-file diff applied; green/after = the branch.
- Formatting: changed files checked with google-java-format 1.36.1 (spotless uses `googleJavaFormat()`); no diffs in the added code. Spotless/checkstyle/errorprone/nullaway were **not** run — Andrew should run `./gradlew :instrumentation-api:check` locally before submitting.

## Logs
| file | result |
|---|---|
| module-tests-before.log | unmodified upstream: 429 passed, 0 failed |
| red.log | upstream main + new tests: 48 passed, **23 failed** |
| green.log | patched: 71 passed, 0 failed |
| module-tests-after.log | patched: 452 passed, 0 failed |

## Disclosure search (GitHub REST search API via web_fetch, 2026-09-27)
| query | result |
|---|---|
| `repo:… ipv6` | 77 hits; relevant: #15158 (closed, Host header only), PR #19540 (merged, `HostAddressAndPortExtractor` only), DB IPv6 normalization PRs (#19366, #20015, #20016). None touch `ForwardedHostAddressAndPortExtractor`. |
| `repo:… ipv6 is:open` | 1 hit, #16161 (gRPC targets) — unrelated |
| `repo:… ForwardedHostAddressAndPortExtractor` | 0 |
| `repo:… "x-forwarded-host"` | 3 hits (#19419 url.full redaction, #9721, #8865) — unrelated |
| `repo:… forwarded in:title` | 7 hits (#5357, #9721, #10370, #3651 "Handle port and IPv6 in forwarded headers" merged 2021-07, i.e. before `host=`/X-Forwarded-Host support for `server.address` was added by #9721 in 2023-10, #2958, 2 unrelated) — none cover `host=` IPv6 |
**Not already reported** as a distinct item; closest is closed #15158 (whose fix missed this sibling).
Suggest the PR reference #15158/#19540 as a follow-up.
