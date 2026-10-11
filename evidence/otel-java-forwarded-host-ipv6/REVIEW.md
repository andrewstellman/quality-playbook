# opentelemetry-java-instrumentation: `server.address` is cut off for bracketed IPv6 hosts

Status: **open and ready for review (marked ready by Andrew on 2026-10-05), [open-telemetry/opentelemetry-java-instrumentation#20393](https://github.com/open-telemetry/opentelemetry-java-instrumentation/pull/20393).** Submitted by Andrew on 2026-10-05. See the submission record at the end.

**Read this first:** the other OpenTelemetry fix from this campaign, the UrlParser one, is already an open draft PR: [#20320](https://github.com/open-telemetry/opentelemetry-java-instrumentation/pull/20320), opened from your account on 2026-09-29. It was not in any of the records, so my earlier statement that this project had nothing pending was wrong. Details are under "Things to know".

## The project

[open-telemetry/opentelemetry-java-instrumentation](https://github.com/open-telemetry/opentelemetry-java-instrumentation) is the OpenTelemetry Java agent and its instrumentation libraries. It records telemetry (spans and metrics) for Java applications without code changes.

For every HTTP request a server handles, it records `server.address` and `server.port`: the host name and port the client asked for. It reads them from the request headers, in this order: `Forwarded` (the `host=` part), `X-Forwarded-Host`, `:authority`, `Host`.

## The bug

An IPv6 address in a host header is written in square brackets, because the address itself contains colons: `Host: [2001:db8::1]:8080`. The code that parses the header splits at the first colon, which is inside the brackets.

| Request header | Recorded today | Expected |
|---|---|---|
| `Host: [2001:db8::1]:8080` | `server.address = "[2001"`, no `server.port` | `"2001:db8::1"`, `8080` |
| `Host: [::1]:8080` | `server.address = "["`, no `server.port` | `"::1"`, `8080` |

The parser is `ForwardedHostAddressAndPortExtractor.extractHost`. It is the default source of `server.address` and `server.port` for every HTTP server instrumentation (`HttpServerAttributesExtractorBuilder.java:56`).

**Where the expectation comes from:**

- The project already fixed the same bug in the sibling class. PR #19540 ("Handle IPv6 addresses in HTTP Host headers", on `main` as `fdc5e98b`, 2026-08-20) taught `internal/HostAddressAndPortExtractor` to read `[...]`. This class was missed. A third place in the same package, the `for=` parsing in `HttpServerAddressAndPortExtractor.java:91-101`, also already handles brackets.
- RFC 3986 section 3.2.2: an IPv6 host is written inside square brackets, and the port separator is the colon after the closing bracket.
- The OpenTelemetry definition of `server.address`: "Server domain name if available without reverse DNS lookup; otherwise, IP address or UNIX domain socket name." `[2001` is none of those.
- The RFC and OpenTelemetry quotations were checked by the review panel on 2026-09-27 and 2026-09-28. I did not re-read them today.

## The fix

One new branch in `extractHost`, copied from the two places that already do this:

```diff
+    // an IPv6 address is enclosed in square brackets and contains ':' characters, so the address
+    // ends at the closing ']' and the port, if any, follows it
+    if (host.charAt(start) == '[') {
+      int ipv6End = host.indexOf(']', start + 1);
+      if (notFound(ipv6End, end)) {
+        // malformed header value
+        return false;
+      }
+      sink.setAddress(host.substring(start + 1, ipv6End));
+      if (ipv6End + 1 < end && host.charAt(ipv6End + 1) == ':') {
+        setPort(sink, host, ipv6End + 2, end);
+      }
+      return true;
+    }
```

Tests:

- 10 new rows in the existing parametrized tables of `ForwardedHostAddressAndPortExtractorTest` (4 for `Forwarded: host=`, 6 for the plain host headers).
- 1 new test in `HttpServerAttributesExtractorTest` that checks the recorded attributes for `Host: [2001:db8::1]:8080`.

Total: 3 files, 40 lines added, none removed. No changelog entry, because the project generates its changelog from merged PRs.

## Regression test

Run on 2026-10-05 in the cloud sandbox with **the project's own Gradle build** (Gradle 9.8.0 from the wrapper, JDK 25.0.4.1 Corretto, which is the Java version CONTRIBUTING requires). This is the Gradle run the earlier reviews could not do.

- **`./gradlew :instrumentation-api:check` on the fixed tree: `BUILD SUCCESSFUL`.** That task ran:
  - `compileJava` and `compileTestJava` (Error Prone and NullAway run inside them, with warnings treated as errors),
  - `checkstyleMain`, `checkstyleTest`,
  - `spotlessCheck` (formatting),
  - `animalsnifferMain` and `jApiCmp` (API compatibility),
  - three test tasks: 744 tests each, 0 failures.
- **`./gradlew :instrumentation-api:spotlessApply`: `BUILD SUCCESSFUL`, and it changed nothing** (`git status` empty afterwards).
- **Revert** (the source file put back, tests kept), the two test classes: `128 tests completed, 23 failed`. All 23 are the new cases, with the expected messages, for example `expected: "2001:db8::1" but was: "[2001"` and `{server.address="[2001"} to contain only: [server.address="2001:db8::1", server.port=8080L]`.
- **Unpatched** `:instrumentation-api:test`: 721 tests, 0 failures. 721 plus the 23 new cases is 744.

Substitutes and limits, stated plainly:

- **Maven Central rate-limited the sandbox** (HTTP 429), so the first three Gradle attempts failed while downloading dependencies. I added a Gradle init script that reads the same artifacts from Google's Maven Central mirror. The project has no dependency checksum file, so the mirror's content was not independently verified. Nothing in the repository was changed for this.
- I applied and tested the patch on `main` at `66666d44`. `main` moved one commit during the session, to `57ea948e`. That commit changes nothing under `instrumentation-api/`, and the patch merges cleanly onto it. I did not re-run Gradle on `57ea948e`.
- One module only (`:instrumentation-api`), on Linux x64. The project's CI runs much more.
- Earlier logs from the javac and JUnit harness runs are in `v2/` in this folder.

## Knock-on effects

- **Callers.** The class is created in one place, `HttpServerAttributesExtractorBuilder.java:56`. So the change reaches `server.address` and `server.port` on HTTP server telemetry, and nothing else.
- **Before and after, 26 header combinations.** Run on 2026-10-05 through `HttpServerAttributesExtractor` on the unpatched and the fixed code (`KnockOnProbeTest.java` in this folder; it is not part of the patch).

| Header | Before (address, port) | After |
|---|---|---|
| `Host: example.com` | `example.com`, none | same |
| `Host: example.com:8080` | `example.com`, 8080 | same |
| `Host: example.com:` | `example.com`, none | same |
| `Host: example.com:port` | `example.com`, none | same |
| `Host: 1.2.3.4:80` | `1.2.3.4`, 80 | same |
| `Host: :8080` | empty string, 8080 | same |
| `X-Forwarded-Host: example.com:8080` | `example.com`, 8080 | same |
| `Forwarded: for=1.2.3.4;host=example.com:42` | `example.com`, 42 | same |
| `Host: [::1]` | `[`, none | `::1`, none |
| `Host: [::1]:8080` | `[`, none | `::1`, 8080 |
| `Host: [2001:db8::1]:8080` | `[2001`, none | `2001:db8::1`, 8080 |
| `Host: [fe80::1%25eth0]:80` | `[fe80`, none | `fe80::1%25eth0`, 80 |
| `Host: [::1]:port` | `[`, none | `::1`, none |
| `Host: [::1]:` | `[`, none | `::1`, none |
| `Host: [::1]x` | `[`, none | `::1`, none |
| `Host: "[::1]:8080"` | `[`, none | `::1`, 8080 |
| `X-Forwarded-Host: [::1]:8080` | `[`, none | `::1`, 8080 |
| `:authority: [::1]:8443` | `[`, none | `::1`, 8443 |
| `Forwarded: host="[2001:db8::1]:42"` | `[2001`, none | `2001:db8::1`, 42 |
| `Forwarded: host=[::1]:42` | `[`, none | `::1`, 42 |
| `Host: []` | `[]`, none | empty string, none |
| `Host: []:80` | `[]`, 80 | empty string, 80 |
| `Host: [::1` (no closing bracket) | `[`, none | nothing recorded |
| `Forwarded: host="[::1"` | `[`, none | nothing recorded |
| `X-Forwarded-Host: [::1` with `Host: example.com:80` | `[`, none | `example.com`, 80 |
| `Forwarded: host="[::1"` with `Host: [2001:db8::2]:81` | `[`, none | `2001:db8::2`, 81 |

- **What changes for users.** Only header values that start with `[`. All 8 ordinary host values are identical.
- **Bracketed IPv6 hosts** now record the address and the port. Anyone with a dashboard or alert keyed on the broken values (`[` or `[2001`) would see the value change. The panel found that unlikely and judged the change strictly an improvement.
- **Malformed values, stated in the PR text:** a value with an opening bracket and no closing bracket is now treated as malformed. The extractor moves on to the next header, as it already does for an unterminated quote. Before, it recorded `[`.
- **Not stated in the PR text:**
  - `[]` now records an empty string, where it recorded `[]`. The sibling `for=` parser does the same. The panel called it harmless.
  - Because of the fall-through, a malformed bracketed value in one header can mean the address comes from a different header (last two rows). Reviewer S5 noted this and did not ask for a change.

## Review history

- **Round 1 panel** (2026-09-27, `evidence/review-2026-09-27/`): approved the logic; asked for the Gradle run, removal of an HTML comment in the PR text, a mention of the unterminated-bracket behaviour, and a clearer code comment. All done in `v2/` except the Gradle run.
- **Round 2 panel** (2026-09-28, `evidence/review-2026-09-28-v2/SYNTHESIS.md`): 13 of 13 SHIP, conditional on the Gradle run and the EasyCLA. No correctness or security finding. O2: "It's a telemetry-accuracy fix. Public PR."
- **The Gradle run** was done today (above).

## Upstream check (2026-10-05)

- 90 commits landed between the pinned commit (`78d71b58`, 2026-09-27) and `66666d44`. None touches the three files in the patch.
- The patch applies cleanly with `git am`. Base blobs match the patch (`f4c7b592`, `73326ce5`, `63c18574`), and so do the results (`c3011cf0`, `11ea221e`, `db4d3d80`). Resulting tree on `66666d44`: `a38f25ab66fda12ee6bcf291e5d68e70c675ad27`.
- No commit on `main` since the pinned commit mentions IPv6, brackets or forwarded headers.
- **Duplicate scan by git.** I fetched the 1519 pull-request heads numbered 18500 and higher (roughly the last four months; the repository has 14,410 in total). Exactly one touches this extractor, its siblings or the UrlParser files: #20320, which is yours. None touches `ForwardedHostAddressAndPortExtractor`. I did not scan older PRs or search the issue tracker (no `gh` here). The first review searched issues on 2026-09-27 and found nothing for this class.

## Things to know before submitting

- **#20320 is already open, as a draft, and unrecorded.**
  - Title "Handle bracketed IPv6 hosts in UrlParser", head `4e0cc52c`, author Andrew Stellman, committed 2026-09-29 14:48 -0400.
  - Its diff is identical to the reviewed v2 UrlParser patch (same `git patch-id`, `1e016147`).
  - It is not merged, and it still merges cleanly onto current `main`.
  - As the fetch tool read the page today: state Draft, the EasyCLA bot says the CLA is signed, and a dashboard bot says "Waiting on the author" and to move it out of draft to request review. No human comments. That tool has been wrong about draft state before; `gh pr view 20320 --repo open-telemetry/opentelemetry-java-instrumentation --json isDraft,state` is the exact check.
  - `evidence/otel-java-urlparser-ipv6/STATUS.md` said "ready". I changed it to "open" with the link on 2026-10-05.
- **So this would be a second open PR on this project**, while the first is still a draft. Whether to send this one now, or first move #20320 out of draft, is your call.
- **The commit has a trailer: `Assisted-by: Claude Opus 5.5`.** OpenTelemetry's generative-AI policy (open-telemetry/community, `policies/genai.md`, read today through the fetch tool) says: "For code contributions, the recommended method to disclose this is an 'Assisted-by:' commit message trailer that includes the model used". #20320 carries the same trailer. This is the project-policy exception to the no-trailers rule; there is no `Signed-off-by` or `Co-Authored-By`.
- **The disclosure sentence differs slightly from the usual one:** "Found by Quality Playbook, an AI code-review tool, and fixed with Claude (Opus 5.5); I reviewed the change and the tests." It says you reviewed the tests too. Make sure that is true before posting.
- **EasyCLA:** per the bot on #20320 you have already signed it.
- **Script changes, made on 2026-10-05:**
  - Added `SKIP_TESTS=1`, as the other scripts have, so you can skip the local Gradle run now that it has been run here.
  - Narrowed `./gradlew spotlessApply` (the whole repository) to `./gradlew :instrumentation-api:spotlessApply`. The patch only touches that module.
  - Checked with `bash -n` only; there is no zsh in the shell I can reach.
- **If you do run Gradle locally,** it needs JDK 25, and the first run downloads a lot and takes several minutes. The repository's `AGENTS.md` says not to pipe Gradle output.
- **Likely review comments** (from the panel):
  - The new code comment is longer than the house wording `// ipv6 address enclosed in square brackets case`. Switching back is a one-line change.
  - Bracket parsing now lives in three places. The suggested answer: it is kept local to match the existing pattern, and you are happy to extract a helper.
- **A dashboard bot will probably comment** on a draft, as it did on #20320. Draft PRs get less attention on this project (CONTRIBUTING, "Draft PRs").
- **Not verified today:** issue #15158, which the PR text cites as the origin (the panel fetched it on 2026-09-28).

## The PR as it will be submitted

**Title:** Handle bracketed IPv6 hosts in ForwardedHostAddressAndPortExtractor

> Follow-up to #15158 / #19540.
>
> #19540 taught `HostAddressAndPortExtractor` to parse a bracketed IPv6 authority, but the sibling
> `ForwardedHostAddressAndPortExtractor` still splits at the first `:`. That is the extractor
> `HttpServerAttributesExtractor` uses for `server.address` / `server.port` from the `Forwarded` `host=`
> parameter, `X-Forwarded-Host`, `:authority` and `Host`, so a server request with
> `Host: [2001:db8::1]:8080` currently gets `server.address = "[2001"` and no `server.port`
> (`Host: [::1]:8080` gives `"["`).
>
> This adds the same `[`…`]` branch used in `HostAddressAndPortExtractor` and in the `for=` parsing of
> `HttpServerAddressAndPortExtractor`: the address is the text inside the brackets and the port is parsed
> after `]:`.
>
> One behavior change for malformed values: an unterminated `[` (for example `Host: [::1`) is now
> treated as malformed, like an unterminated quote, so the extractor falls through to the next header
> source instead of recording `server.address = "["`.
>
> Tests:
> - new rows in `ForwardedHostAddressAndPortExtractorTest` for `Host` / `X-Forwarded-Host` / `:authority`
>   and quoted `Forwarded: host="[...]"` (RFC 7239 requires IPv6 values to be quoted)
> - `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` (attribute-level)
>
> Before the fix the new cases fail with e.g. `expected: "2001:db8::1" but was: "[2001"`.
>
> Found by Quality Playbook, an AI code-review tool, and fixed with Claude (Opus 5.5); I reviewed the change and the tests.

**Commit message** (author Andrew Stellman <andrew@stellman.com>):

```
Handle bracketed IPv6 hosts in ForwardedHostAddressAndPortExtractor

The host value was split at the first ':', so Host: [::1]:8080 gave
server.address "[" and no server.port. Parse [...] the same way
HostAddressAndPortExtractor does.

Assisted-by: Claude Opus 5.5
```

## To submit

To skip the local Gradle run (it passed here today):

```zsh
SKIP_TESTS=1 zsh ~/Documents/QPB/evidence/SUBMIT/submit-otel-forwarded.sh
```

To run Gradle on your Mac first (JDK 25):

```zsh
zsh ~/Documents/QPB/evidence/SUBMIT/submit-otel-forwarded.sh
```

The script uses your existing fork, creates branch `forwarded-host-ipv6` from upstream `main`, applies the patch, pushes, and opens a **draft** PR. It prints the PR number, URL, draft state and title at the end.

## Submission record

- **Submitted:** 2026-10-05 by Andrew, after reviewing this file, using `submit-otel-forwarded.sh`. His paste of the script output: `"isDraft": true`, `"number": 20393`, `"title": "Handle bracketed IPv6 hosts in ForwardedHostAddressAndPortExtractor"`.
- **PR:** [#20393](https://github.com/open-telemetry/opentelemetry-java-instrumentation/pull/20393), opened as a **draft** from `andrewstellman:forwarded-host-ipv6` into `open-telemetry:main`; 1 commit, `ed126c85f1309f965be4b7e52f83ff650d007904`.
- **Verified by git (2026-10-05 18:24 UTC, `git fetch` of `refs/pull/20393/head`):**
  - One commit on top of `57ea948e`, the tip of `main`. That is one commit newer than the `66666d44` I tested on; the commit in between changes nothing under `instrumentation-api/`.
  - Blobs: `f4c7b592..c3011cf0`, `73326ce5..11ea221e`, `63c18574..db4d3d80`, the same as the reviewed patch. The diff has the same `git patch-id` as the patch (`63b98c73d6cfad977e87891e1e0576ee1fb77376`).
  - The commit message matches the patch, including `Assisted-by: Claude Opus 5.5`. No `Signed-off-by` or `Co-Authored-By`.
  - Author: `Andrew Stellman <andrew@stellman.com>`. Committer: `andrewstellman <astellman@stellman-greene.com>`, 2026-10-05 14:23:35 -0400.
- **Gradle on the PR's exact commit (2026-10-05 18:27 UTC):** `./gradlew :instrumentation-api:check` on `ed126c85`: `BUILD SUCCESSFUL in 2m 26s`. Gradle reused the compile and test results from the earlier run because the module's inputs were identical (`compileJava FROM-CACHE`, `test FROM-CACHE`); the formatting check ran again. Test reports: 744 tests in each of the three test tasks, 0 failures.
- **Title and description:** the title in Andrew's paste matches. The fetch tool's reading of the PR page gave the description word for word as above, base `open-telemetry:main`, 1 commit. That tool is a summary, so treat the description check as likely, not proven.
- **Bot:** the fetch tool showed one comment, from `opentelemetry-pr-dashboard`: "Waiting on the author · refreshed 2026-10-05 18:23 UTC. Move out of draft to request review." No EasyCLA comment was visible yet.
- **Not checked:** CI results.
- **Still to do on Andrew's side:** nothing until a maintainer responds.
- **CI (2026-10-05):** Andrew received GitHub's email "Build pull request, Attempt #2: Some jobs were not successful" for run 37355605539. As the fetch tool read the run page at 21:47 UTC (a summary, not proof):
  - the run is for #20393, a re-run started 2026-10-05 19:30;
  - passed: spotless, license-check, build, gradle-plugins, examples, lint-check, and the test, smoke-test, muzzle and latest-deps jobs that ran;
  - failed: `build / common / test2 (11, hotspot, indy false)` with "The job was not acquired by Runner of type hosted even after multiple attempts", and `build / required-status-check` ("Process completed with exit code 1"), which fails when any required job does;
  - the page also showed "Internal server error. Correlation ID: d02215d9-1dd6-4adb-bad8-085adcd85027".
  - Reading: the one failed test job never got a runner, so it did not run the change at all. That is a GitHub infrastructure failure, not a test failure.
  - By git at 21:47 UTC: PR head unchanged (`ed126c85`); GitHub's merge ref exists, so there is no conflict with `main` (now `02a00ba2`, one commit newer).
- **2026-10-05 17:53 -04:00:** Andrew ran `gh pr view --json number,isDraft,state,url` for this PR. Output: `draft=false  OPEN`. He had marked it ready in the web UI. It is open and ready for review.
- **Maintainer responses:** none seen.
