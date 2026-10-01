# opentelemetry-java-instrumentation — triage of historical QPB findings (2026-09-27)

Source list: `docs/research/triage-2026-09-27/scout-candidates.md` ranks 7, 8, 10.
Historical findings: `repos/secbench2_widenet/wn-jvm-02-opentelemetry-java-instrumentation/quality/BUGS.md` (QPB v1.5.8 run, 2026-06-23, code-only).
Fresh shallow clone: `78d71b585a77d7f2312c1b8751ff6c95a72722d7`, committed 2026-09-27 10:18:36 +0300
("Mark bundled sampler dependency for removal in 3.0 (#20284)") — same HEAD the scout read.

| Candidate | Verdict | Evidence |
|---|---|---|
| BUG-002 — incubator + reactor-netty `UrlParser` truncate `[IPv6]` authorities | **CONFIRMED** | `evidence/otel-java-urlparser-ipv6/` |
| BUG-001 (rescoped) — `ForwardedHostAddressAndPortExtractor.extractHost` truncates `[IPv6]` hosts | **CONFIRMED** (the `HostAddressAndPortExtractor` half is already fixed upstream by #19540 / closed #15158) | `evidence/otel-java-forwarded-host-ipv6/` |
| BUG-003 — unanchored `indexOf("for=" / "host=" / "proto=")` in the Forwarded header | **STOPPED** (security-relevant angle found; no test, fix, patch or PR drafted) | this file only |

## Method (applies to both confirmed items)
- Gradle was attempted first (`./gradlew :instrumentation-api:test --tests '*ForwardedHostAddressAndPortExtractorTest'`, Gradle 9.7.1, JDK 25).
  It filled the sandbox root filesystem during configuration (verbatim tail of the attempt):
  ```
  * What went wrong:
  Failed to notify root build lifecycle listener.
  > Could not update /tmp/gradle-home/caches/9.7.1/file-changes/last-build.bin
  > Could not update /tmp/otel-java/.gradle/9.7.1/fileChanges/last-build.bin
  ...
  BUILD FAILED in 2m 49s
  ```
  (`df` afterwards: `/dev/nvme0n1p1 9.6G 9.6G 684K 100% /`; gradle home was 2.7 GB.)
- Fallback used for all logs: javac-compiled upstream sources + JUnit Platform Console 1.14.4, running the project's
  own test classes (existing + new) — details, exact test selection and the dependency list with Maven Central SHA-1
  checks are in each evidence README and `harness/`. JDK: OpenJDK 25.0.4.1 (Ubuntu `openjdk-25-jdk-headless`
  25.0.4.1+1-1~22.04.4 extracted without root; CONTRIBUTING.md says the build requires Java 25).
- Not run: spotless, checkstyle, errorprone, nullaway, muzzle, full module test tasks. google-java-format 1.36.1 was run on the changed files (clean).

## Contribution rules noted (CONTRIBUTING.md + org policy)
- Changelog: "Do not add a changelog entry for normal changes" — only deprecations/breaking changes. Neither patch adds one.
- CLA: CONTRIBUTING.md doesn't mention one, but the repo's `.github/scripts/generate-release-contributors.sh` filters out the `linux-foundation-easycla` bot, i.e. PRs are gated by the CNCF/LF EasyCLA check. Andrew needs a signed EasyCLA for the committing identity (andrew@stellman.com).
- GenAI: OpenTelemetry's Generative AI Contribution Policy (open-telemetry/community `policies/genai.md`) asks contributors who used generative AI to disclose it and recommends an `Assisted-by:` commit trailer. Both patches carry `Assisted-by: Claude Opus 5.5`, and both PR drafts say so.
- Repo `AGENTS.md` / `.github/agents/knowledge/testing-general-patterns.md` prefer `Arguments.argumentSet(name, ...)` for new parameterized rows; the patches follow the surrounding file's existing unnamed `arguments(...)` style instead.

## BUG-003 — STOPPED (why)
Source still has all three unanchored lookups at the pinned SHA (`HttpServerAddressAndPortExtractor.java:46` `for=`,
`ForwardedHostAddressAndPortExtractor.java:55` `host=`, `ForwardedUrlSchemeProvider.java:45` `proto=`; source read only, not executed).
As a telemetry-correctness bug it is real (e.g. an RFC 7239 §5.5 extension parameter named `xfor=` is read as `for=`).
But it has a security-relevant angle, so I stopped as instructed:
- `client.address` (semconv: "The IP address of the original client behind all proxies, if known (e.g. from Forwarded#for …)") is an attribute people use for abuse and forensic analytics.
- Normally a client can already put any `for=` value in `Forwarded` (RFC 7239 §8.1: the header "cannot be relied upon to be correct … including the client making the request"), so in the plain case the bug gives an attacker nothing new.
- In a deployment where a trusted proxy removes client-supplied `for=` pairs but passes other/unknown parameters through, a client-sent `xfor=<spoofed>` placed before the proxy's `for=<real>` gets recorded as `client.address`. That lets the client spoof `client.address` past a sanitizing proxy. Whether real proxies behave that way was **not** checked.
- The historical report already framed it this way ("`client.address` feeds downstream security analytics, so the attribute is attacker-spoofable").
- The repo has no `SECURITY.md`. The OpenTelemetry org routes vulnerabilities through private reporting, so a public PR shouldn't be opened before Andrew decides which channel to use.
- Disclosure search done before stopping: `repo:… forwarded in:title` (7 hits, none on token boundaries), `repo:… "client.address" forwarded spoof` (0), `repo:… "Forwarded" header parsing` (1 unrelated renovate PR), `repo:… "x-forwarded-host"` (3, unrelated). Nothing found.

## Other notes for Andrew
- The two confirmed patches touch different files and apply independently to the pinned SHA (`git am` checked for each; the result matches the branch tree).
- BUG-002 decision point: `getHost` now returns the address **without** brackets (`::1`), which matches #19540 / RedisServerTarget / JDBC.
  The alternative is URI-style `[::1]`. Either choice fixes the truncation; maintainers may have a preference.
- The scout's doubt about BUG-001's "becomes `[`" output is resolved: `[::1]`-style inputs give `"["`, while `[2001:db8::1]` inputs give `"[2001"` (both appear in red.log).
