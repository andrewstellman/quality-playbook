# Round 2 executor B — red/green re-run: otel-urlparser, otel-forwarded

Execution kind for both fixes: **javac + JUnit Platform console, not Gradle.** No Gradle build,
no `./gradlew`, no dependency resolution via Gradle, no annotation-processor/error-prone Gradle
plugins, no checkstyle/spotless, no full-module compile (only the source files listed in
`run.sh` for each suite were compiled), no multi-module reactor build. Dependencies are 23 jars
pulled directly from Maven Central and verified by SHA1 against the harness's
`deps.SHA1SUMS` (all 23 `OK`) rather than resolved by Gradle/Maven. JDK: OpenJDK 25.0.4.1
(`/tmp/jdk25/...`).

Both repos were built fresh from `/tmp/review/src/otel/base` (pinned upstream SHA
`78d71b585a77d7f2312c1b8751ff6c95a72722d7`), copying in only the modules each fix's `run.sh`
suite needs (to fit the ~1.8GB shared disk), with `.git` removed and a new repo `git init`'d,
committed as `base`, then the v2 patch applied and committed/tagged `fix` — matching the
`fix~1`/`fix` convention `otel-verify.sh` expects. Both repos were deleted after their logs were
copied out; peak disk use per repo was under 4MB (only the modules needed, not the full 99MB
base tree).

## otel-urlparser

- Repo: `instrumentation-api/`, `instrumentation-api-incubator/`, `testing-common/`,
  `instrumentation/reactor/reactor-netty/reactor-netty-1.0/{javaagent,javaagent-unit-tests}/`
  copied from base; base commit `fbdb3d3c9b07b1d2b0485cfba343c1277b3bc53e`; patch applied cleanly
  (`git apply --check` passed with no fuzz); fix commit `f07755151ece941a9db109656a60c8349f18c268`,
  tagged `fix`.
- Suites run: `incubator` (compiles `UrlParser.java` + its in-module consumers, runs
  `UrlParserTest` + `ServicePeerResolverTest`) and `reactor` (compiles the reactor-netty copy of
  `UrlParser.java` alone, runs its own `UrlParserTest`). The `api` suite (semconv.http parser
  tests) is unaffected by this patch and was not run.
- **RED** (base main code + v2 test files only): `incubator` suite 32/34 pass, 2 fail; `reactor`
  suite 8/9 pass, 1 fail. Failures are exactly the claimed bug:
  `UrlParserTest.testGetHostAndPortWithIpv6()` fails `expected: "::1" but was: "["` in both
  modules, and `ServicePeerResolverTest.shouldResolve(...)[12] ::1, 8080, ...` fails
  `expected: "ipv6PortSvc" but was: null` (the `[::1]:8080` mapping key never matches because the
  parsed host is `"["`).
- **GREEN** (fix = v2 code + tests): `incubator` 34/34 pass; `reactor` 9/9 pass. Exit code 0 both.
- **REVERT** (fix's tests kept, `UrlParser.java` in both modules reverted to base): identical
  2 + 1 failures reappear, same assertions as RED.
- **SUITE**: `suite-before` (base, existing tests) 39+8 = clean, 0 failures. `suite-after` (fix,
  full module suite incl. the 4 `incubator` classes) 42+9 = clean, 0 failures. No regressions.
- **Malformed-URL rows, checked directly** (isolated probe, not just inferred from the combined
  assertion chain in `testGetHostAndPortWithIpv6`, which aborts at its first failing line before
  reaching the malformed-URL assertions): compiled `UrlParser.java` alone at `base` and at `fix`
  and called `getHost` on the exact strings from the v2 test:
  - `getHost("http://[::1/path]")`: base → `"["`, fix → `null`
  - `getHost("http://[x/p?token=abc]")`: base → `"[x"`, fix → `null`
  - `getHost("https://[::1]:8080/")`: base → `"["`, fix → `"::1"` (sanity check on the well-formed
    case)

  So the two malformed-URL rows are confirmed to fail on base (return a truncated/garbage host
  instead of `null`) and pass on v2. I did not build a separate "v1-style unbounded search"
  variant to test against (out of scope — no v1 source was read per the brief's instruction to
  ignore `fixed-*` dirs), so I can only confirm base-vs-v2, not v1-vs-v2, for these two rows.

## otel-forwarded

- Repo: `instrumentation-api/` only, copied from base; base commit
  `efbbde9d21444f6cc33fe87ed90e107e2dfa56a9`; patch applied cleanly; fix commit `c2b51ed`
  (abbreviated form from `git log --oneline`; repo was deleted after logs were copied out, so the
  full 40-char SHA was not retained), tagged `fix`.
- Suite run: `api` (compiles all of `instrumentation-api/src/main`, runs the semconv.http test
  package). Selection override for RED/GREEN/REVERT:
  `ForwardedHostAddressAndPortExtractorTest` + `HttpServerAttributesExtractorTest`.
- **RED** (base main code + v2 tests): 104/127 pass, **23 fail**. Every failure matches the
  claimed bug pattern, e.g.:
  - `shouldParsePseudoAuthority[12] [2001:db8::1]:42 → expected: "2001:db8::1" but was: "[2001"`
  - `shouldParseHost[15] [::1] → expected: null but was: "["`
  - `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader()` →
    `Expecting map: {server.address="[2001"} to contain only: [server.address="2001:db8::1",
    server.port=8080L]`
  All 23 are parametrized rows (or the one attribute-level test) added by the v2 patch for
  bracketed-IPv6 / malformed-`[` inputs across `shouldParsePseudoAuthority`, `shouldParseForwarded`,
  and `shouldParseHost` (the `X-Forwarded-Host`/`:authority`/`Host` header paths) plus the
  attribute-extractor test — none are pre-existing tests broken by the test-only checkout.
- **GREEN** (fix = v2 code + tests): 127/127 pass, exit 0.
- **REVERT** (fix's tests kept, `ForwardedHostAddressAndPortExtractor.java` reverted to base):
  same 23 failures reappear — `diff` of the two `MethodSource` failure lists (RED vs REVERT) is
  byte-identical.
- **SUITE**: `suite-before` 429/429 pass (full `api` suite, base). `suite-after` 452/452 pass
  (full `api` suite, fix — 23 more tests, all passing). No regressions.

## Gradle checks not run (both fixes)

- No `./gradlew compileJava`/`compileTestJava` for the full module or full repo (only the files
  each suite lists were javac'd).
- No Gradle test task (`test`, `spotlessCheck`, `checkstyleMain`, `errorprone`), no code-coverage
  (jacoco), no OSSRH/publish checks.
- No build across the reactor-netty module's full dependency graph — only the single
  `UrlParser.java` file was compiled standalone against the shared classpath jars, not against
  Netty/Reactor itself.
- No multi-module Gradle build verifying `instrumentation-api-incubator` and
  `instrumentation-api` compile together as Gradle would (they were compiled with `-sourcepath`/
  `-cp` tricks in `run.sh`, which is not the same dependency resolution Gradle performs).
- No CI-equivalent checks (license headers, muzzle, japicmp) were run.

## Summary table

| ID | red | green | revert | suite | execution kind | PASS/FAIL |
|---|---|---|---|---|---|---|
| otel-urlparser | FAIL as claimed (2+1 tests, `"["`/`"[x"` instead of parsed IPv6 host; malformed-URL rows independently confirmed base→garbage, fix→null) | PASS (34/34, 9/9) | FAIL again, same assertions | before 39+8 clean, after 42+9 clean | javac + JUnit console (not Gradle) | PASS |
| otel-forwarded | FAIL as claimed (23/127 tests, `"["`/`"[2001"` instead of parsed IPv6 host/port) | PASS (127/127) | FAIL again, identical 23 failures | before 429/429 clean, after 452/452 clean | javac + JUnit console (not Gradle) | PASS |

Both fixes' red/green/revert/suite cycles behaved exactly as the PR drafts claim, under the v2
harness. Nothing fabricated; the Gradle gaps above are real and unchecked by this run.
