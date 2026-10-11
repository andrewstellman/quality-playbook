# opentelemetry-java-instrumentation: UrlParser cuts off bracketed IPv6 hosts

Status: **open; Andrew reports marking it ready on 2026-10-05, [open-telemetry/opentelemetry-java-instrumentation#20320](https://github.com/open-telemetry/opentelemetry-java-instrumentation/pull/20320).** Opened from Andrew's account on 2026-09-29.

This file was written after the fact, on 2026-10-05. The PR was found by a git scan while preparing the sibling fix (`otel-java-forwarded-host-ipv6`). It was not presented under `SUBMISSION-PROTOCOL.md` in this session, and until today this folder's `STATUS.md` said "ready". The bug, the fix and the review history are in `README.md` and `v2/` in this folder.

## Submission record

- **PR:** #20320, "Handle bracketed IPv6 hosts in UrlParser", from `andrewstellman:urlparser-ipv6` into `open-telemetry:main`; 1 commit, `4e0cc52c6844792c58cc294ea47f142d5d1529b5`.
- **Verified by git (2026-10-05, `git fetch` of `refs/pull/20320/head`):**
  - Author `Andrew Stellman <andrew@stellman.com>`, authored 2026-09-28 01:14:20 -0400. Committer `andrewstellman <astellman@stellman-greene.com>`, 2026-09-29 14:48:23 -0400.
  - The diff has the same `git patch-id` as the reviewed patch `v2/0001-Handle-bracketed-IPv6-hosts-in-UrlParser.patch` (`1e016147b16adb516e6b4886ce2d5070b9dafdf5`). 5 files, 81 lines added, 1 removed.
  - Trailer: `Assisted-by: Claude Opus 5.5`, the form OpenTelemetry's generative-AI policy recommends. No `Signed-off-by` or `Co-Authored-By`.
  - Not merged: no commit for it on `main` at `57ea948e`. It merges cleanly onto that commit, and none of its 5 files has changed on `main` since its base.
- **As the fetch tool read the PR page on 2026-10-05** (a summary, and it has been wrong about draft state before):
  - State: Draft.
  - EasyCLA bot: the CLA is signed for commit `4e0cc52`.
  - A dashboard bot: "Waiting on the author", move out of draft to request review.
  - No human comments or reviews.
  - The exact check is `gh pr view 20320 --repo open-telemetry/opentelemetry-java-instrumentation --json isDraft,state`.

## Gradle checks, run on 2026-10-05

The reviews before submission could not run Gradle. I ran it today in the cloud sandbox on the PR's commit cherry-picked onto `main` at `57ea948e` (Gradle 9.8.0 from the wrapper, JDK 25.0.4.1 Corretto).

- `./gradlew :instrumentation-api-incubator:check :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests:check :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:compileJava :instrumentation:clickhouse:clickhouse-client-v2-0.8:javaagent:compileJava`: **`BUILD SUCCESSFUL`**.
  - `:instrumentation-api-incubator`: compile (Error Prone, NullAway), checkstyle, spotlessCheck, and five test tasks of 1249 tests each with 0 failures (3 or 32 skipped, depending on the task).
  - reactor-netty `javaagent-unit-tests`: 15 tests, 0 failures.
- `./gradlew :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:spotlessCheck ...:javaagent:checkstyleMain`: **`BUILD SUCCESSFUL`**. This covers the formatting of the second `UrlParser.java`, which the first command does not.
- Limits: dependencies came from Google's Maven Central mirror because Maven Central rate-limited the sandbox (HTTP 429). The reactor-netty integration tests (`...:javaagent:test`) were not run. Linux x64 only. I did not see the project's CI.

## Still to do on Andrew's side

- Decide when to move the PR out of draft. Draft PRs get less attention on this project (CONTRIBUTING, "Draft PRs").
- **2026-10-05 17:53 -04:00:** Andrew ran `gh pr view --json number,isDraft,state,url` for this PR. Output: `draft=true  OPEN`. It is still a draft.
- **2026-10-05 17:57 -04:00:** Andrew reports he set this PR to ready for review. Not re-checked from here; the exact check is `gh pr view 20320 --repo open-telemetry/opentelemetry-java-instrumentation --json isDraft`.
- **Maintainer responses:** none seen.
