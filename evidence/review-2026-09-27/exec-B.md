# Executor B — red/green re-run report

Three fixes: otel-urlparser, otel-forwarded, assertj-percentage. Independent clean-copy runs from `/tmp/review/src/<repo>/base` (read-only, never modified) plus `/tmp/review/packets/<ID>/0001-*.patch` (read-only, never modified). All work happened in `/tmp/review/exec/B/<ID>/` and scratch (copied repo, local Maven repo, harness output) was deleted after each fix, per the disk-sharing constraint with executor A.

Disk: `df -h /tmp` was checked before each fix. Started at 76% used / 2.4G free, peaked at 87% used / 1.3G free during the assertj Maven build (two live Maven-repo copies existed briefly for the base-vs-fixed comparison), ended at 84% / 1.6G free after cleanup. No fix ran out of disk.

---

## otel-urlparser

**Claim:** `UrlParser` (incubator and reactor-netty variants) returns `"["` as the host for bracketed IPv6 URLs such as `http://[::1]:8080/`.

**Pinned SHA:** source tree at `/tmp/review/src/otel/base` is at `78d71b585a77d7f2312c1b8751ff6c95a72722d7` (confirmed via `git -C /tmp/review/src/otel/base rev-parse HEAD`). My working copy was `cp -a`'d from that tree, its `.git` (a worktree pointer file, read-only) removed, and re-initialized as a fresh repo (`git init` + one commit) — so my local HEAD (`88472a149d7b45c83c2afd667a3fbd30bd1c572c` for the urlparser copy, `947ce8476354899903905575ba45dfcba277e570` for the forwarded copy) is a different SHA than the source pin but identical content at that pin.

**Execution kind:** javac + JUnit Platform Console Standalone, using the validator's own harness scripts (`/tmp/review/…/otel-java-urlparser-ipv6/harness/run.sh`, unmodified except copied to `/tmp/run_urlparser.sh`), against jars from `/tmp/deps` — I verified all 24 jars listed in `deps.SHA1SUMS` with `sha1sum -c` and all reported `OK`. This is **not** the project's own Gradle build. Gradle checks that were therefore **not run**: spotless, checkstyle, errorprone, nullaway, and the full Gradle test task (which would also run integration/muzzle checks). I did not attempt a Gradle build (the brief warned it fills the sandbox disk).

**Commands (abbreviated, full sequence in transcript):**
```
cp -a /tmp/review/src/otel/base ./repo && chmod -R u+w ./repo && rm -f ./repo/.git
cd ./repo && git init -q && git add -A && git commit -q -m base
git apply --include='*Test.java' 0001-Handle-bracketed-IPv6-hosts-in-UrlParser.patch   # RED
/tmp/run_urlparser.sh <repo> incubator
/tmp/run_urlparser.sh <repo> reactor
git apply --exclude='*Test.java' 0001-...patch                                        # GREEN (rest of patch)
/tmp/run_urlparser.sh <repo> incubator
/tmp/run_urlparser.sh <repo> reactor
git apply -R --exclude='*Test.java' 0001-...patch                                     # REVERT CHECK
/tmp/run_urlparser.sh <repo> incubator
/tmp/run_urlparser.sh <repo> reactor
git apply --exclude='*Test.java' 0001-...patch                                        # re-apply
/tmp/run_urlparser.sh <repo> api            # + base-tree api/incubator/reactor runs for comparison
```

**RED:** `incubator` suite: 42 tests found, 40 pass / 2 fail. `reactor` suite: 9 tests found, 8 pass / 1 fail. All three failures are the new `testGetHostAndPortWithIpv6` (or its consumer `ServicePeerResolverTest.shouldResolve[12]`) test cases, failing with:
```
expected: "::1"
 but was: "["
```
and
```
expected: "ipv6PortSvc"
 but was: null
```
— exactly the claimed defect (host resolves to `"["`, so the `ServicePeerResolver` mapping keyed on `::1` never matches). No compile errors, no environment errors.

**GREEN:** After applying the rest of the patch (`UrlParser.java` main-source changes in both the incubator and reactor-netty modules): `incubator` 42/42 pass, `reactor` 9/9 pass. Exit code 0 both times.

**REVERT CHECK:** Reversed only the two non-test files (`git apply -R --exclude='*Test.java'`), left the test changes in place. Both suites failed again with the identical failure set and identical assertion messages as RED (`incubator` 40/42, `reactor` 8/9). Re-applied the main-source changes afterward to restore the fixed state.

**SUITE (existing tests, no regressions):**
| Suite | Base (unpatched) | Fixed |
|---|---|---|
| incubator (`UrlParserTest` + `ServicePeerResolverTest` + 2 more) | 39/39 | 42/42 (+3 new) |
| reactor (`UrlParserTest`) | 8/8 | 9/9 (+1 new) |
| api (unrelated `semconv.http` package, included as a broader regression check) | 429/429 | 429/429 (unchanged) |

**Discrepancy from claim:** none found. Patch behaves exactly as described; test additions map 1:1 to the claimed bug.

Logs: `otel-urlparser-{red,green,revert,suite-base,suite-fixed}.log`

---

## otel-forwarded

**Claim:** `ForwardedHostAddressAndPortExtractor.extractHost` records `"[2001"` for a bracketed IPv6 host.

**Pinned SHA:** same source tree/commit as otel-urlparser (`78d71b585a77d7f2312c1b8751ff6c95a72722d7`), same fresh-`git init` caveat (local HEAD `947ce8476354899903905575ba45dfcba277e570`).

**Execution kind:** same javac + JUnit Platform Console Standalone harness (`otel-java-forwarded-host-ipv6/harness/run.sh`), same `/tmp/deps` jars (already verified above; both harnesses use an identical `deps.SHA1SUMS`). Same Gradle checks (spotless, checkstyle, errorprone, nullaway, full Gradle test task) **not run**.

**Test scope:** the patch's test changes are entirely inside `instrumentation-api/src/test/.../semconv/http/`, which is exactly the harness's `api` suite (`ForwardedHostAddressAndPortExtractorTest` + `HttpServerAttributesExtractorTest`, 452 tests total after the patch).

**RED:** `api` suite: 452 tests found, 429 pass / 23 fail. All 23 failures are the new IPv6 parameterized cases the patch adds (verified by listing every failing test name — see below) plus the one new direct test `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader`. Representative failures:
```
JUnit Jupiter:HttpServerAttributesExtractorTest:shouldExtractIpv6ServerAddressAndPortFromHostHeader()
=> Expecting map: {server.address="[2001"} to contain only: [server.address="2001:db8::1", server.port=8080L]
```
```
JUnit Jupiter:ForwardedHostAddressAndPortExtractorTest:shouldParseHost(...):[12] [[2001:db8::1]:42], 2001:db8::1, 42
=> expected: "2001:db8::1" but was: "["
```
Full list of 23 failing test IDs is in `otel-forwarded-red.log`; every one is a `[::1]`/`[2001:db8::1]`-bracketed case from `shouldParsePseudoAuthority`, `shouldParseForwarded`, `shouldParseForwardedHost`, `shouldParseHost`, or the new `HttpServerAttributesExtractorTest` case. No compile errors, no unrelated failures.

**GREEN:** After applying the rest of the patch (`ForwardedHostAddressAndPortExtractor.java`): 452/452 pass, exit code 0.

**REVERT CHECK:** Reversed only `ForwardedHostAddressAndPortExtractor.java`, kept the test changes. Diffed the failing-test-ID list against RED with `diff` — **identical set, byte-for-byte** (23 failures, same names). Re-applied afterward.

**SUITE (existing tests, no regressions):**
| Suite | Base (unpatched) | Fixed |
|---|---|---|
| api (`semconv.http` package) | 429/429 | 452/452 (+23 new) |

**Discrepancy from claim:** none found.

Logs: `otel-forwarded-{red,green,revert,suite-base,suite-fixed}.log`

---

## assertj-percentage

**Claim:** `Percentage.toString()` prints `2147483647%` for whole values above `int` range.

**Pinned SHA:** `/tmp/review/src/assertj/base` at `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada` (confirmed via `git -C /tmp/review/src/assertj/base rev-parse HEAD`). Same copy/re-init caveat as above (local HEAD `11fcf78455ddfd52a4bcb66b98b202c05554da36`).

**Execution kind:** the project's own Maven build (`./mvnw`) with JDK 25, `-Dmaven.repo.local` pointed at a scratch repo inside my work dir, `-pl assertj-tests/assertj-integration-tests/assertj-core-tests -am` (the changed test class lives in the `assertj-core-tests` integration-test module, not `assertj-core` itself — `-am` builds `assertj-core` as a dependency first), `-Dtest=<class names>` selection, `MAVEN_OPTS=-Xmx2g`. This is the real project build/test task, not a substitute harness.

**Test scope beyond `Percentage_Test`:** grepped `assertj-tests/**/*.java` for `withPercentage` and found 4 files total; ran all 4 as the "classes that exercise Percentage in messages": `Percentage_Test`, `OptionalDoubleAssert_hasValueCloseToPercentage_Test`, `Shorts_assertIsCloseToPercentage_Test`, `Shorts_assertIsNotCloseToPercentage_Test`.

**Commands:**
```
./mvnw -q -Dmaven.repo.local=<scratch> -pl assertj-tests/assertj-integration-tests/assertj-core-tests -am \
  -Dtest=Percentage_Test -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test
```
(patch applied incrementally per RED/GREEN/REVERT step; full 4-class selection used for the suite comparison)

**RED:** applied only the test-file hunk (`Percentage_Test.java`, adding the `3000000000` and `1e20` cases). `Tests run: 13, Failures: 2`:
```
Percentage_Test.toString_should_display_fractional_part_when_present(double, String)[6]
expected: "3000000000%" but was: "2147483647%"

Percentage_Test.toString_should_display_fractional_part_when_present(double, String)[7]
expected: "100000000000000000000%" but was: "2147483647%"
```
Exactly the claimed `int` overflow value (`2147483647` = `Integer.MAX_VALUE`) for both new cases. No compile errors.

**GREEN:** applied the rest of the patch (`Percentage.java`, switching the no-fractional-part branch to `new BigDecimal(value).toPlainString()`). Build exit 0; surefire report: `Tests run: 13, Failures: 0, Errors: 0`.

**REVERT CHECK:** reversed only `Percentage.java`, kept the test change. Build failed again, exit 1, identical two failures with identical assertion text as RED (`Tests run: 13, Failures: 2`, same expected/actual pairs). Re-applied afterward.

**SUITE (existing tests, no regressions):**
| Class | Base (unpatched) | Fixed |
|---|---|---|
| `Percentage_Test` | 11/11 | 13/13 (+2 new) |
| `Shorts_assertIsCloseToPercentage_Test` | 16/16 | 16/16 |
| `Shorts_assertIsNotCloseToPercentage_Test` | 16/16 | 16/16 |
| `OptionalDoubleAssert_hasValueCloseToPercentage_Test` | 25/25 | 25/25 |
| **Total** | 68/68 | 70/70 |

**Discrepancy from claim:** none found. One thing worth flagging for the panel (not a test-correctness issue, out of scope for a red/green re-run but visible in the diff): the fix routes the no-fractional-part branch through `new BigDecimal(value)` unconditionally, so every integral `Percentage` value now goes through `BigDecimal` construction and `toPlainString()` rather than an `int` cast — functionally correct per the tests run, but I did not check for behavior differences on negative-zero, `NaN`, or `Infinity` doubles since `Percentage` validates non-negative finite values elsewhere (not verified by me — I only ran the specified test classes, not the full `Percentage` validation-path tests).

Logs: `assertj-percentage-{red,green,revert,suite-base,suite-fixed}.log`

---

## Summary table

| ID | red | green | revert | suite | execution kind | PASS/FAIL |
|---|---|---|---|---|---|---|
| otel-urlparser | FAIL for claimed reason (2/42 incubator, 1/9 reactor) | PASS (42/42, 9/9) | FAILs again, identical | no regressions (base 39+8+429, fixed 42+9+429) | javac + JUnit Console Standalone (not Gradle; spotless/checkstyle/errorprone/nullaway not run) | **PASS** |
| otel-forwarded | FAIL for claimed reason (23/452) | PASS (452/452) | FAILs again, identical set (diff-verified) | no regressions (base 429, fixed 452) | javac + JUnit Console Standalone (not Gradle; spotless/checkstyle/errorprone/nullaway not run) | **PASS** |
| assertj-percentage | FAIL for claimed reason (2/13, both `2147483647%`) | PASS (13/13) | FAILs again, identical | no regressions (base 68, fixed 70 across 4 classes) | project's own Maven build (`./mvnw`, real test task) | **PASS** |

All three fixes pass the red/green/revert/suite protocol on an independent clean copy. Nothing fabricated; every log above reflects an actual command run in this session. Scratch (`m2repo`, copied source trees, harness output) was deleted after each fix per the shared-disk constraint.
