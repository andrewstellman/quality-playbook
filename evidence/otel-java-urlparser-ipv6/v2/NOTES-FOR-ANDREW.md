# otel-urlparser v2: what only you can do

## Not run here
Gradle was not run. Spotless, checkstyle, Error Prone, NullAway and the Gradle test tasks were **not run**. The tests ran under a standalone javac + JUnit harness (see `harness/`). Run the commands below on the Mac before opening the PR.

## 1. Apply the patch on a fresh branch
```zsh
cd ~/src/opentelemetry-java-instrumentation   # your clone/fork; adjust path
git fetch origin
git checkout -b urlparser-ipv6 78d71b585a77d7f2312c1b8751ff6c95a72722d7
git am "/Users/andrewstellman/Documents/QPB/evidence/otel-java-urlparser-ipv6/v2/0001-Handle-bracketed-IPv6-hosts-in-UrlParser.patch"
git rebase origin/main    # upstream has moved since the pinned commit
```
If the rebase conflicts, stop. Check whether upstream fixed `UrlParser` in the meantime.

## 2. Gradle checks (JDK 25, as CONTRIBUTING requires)
```zsh
java -version
./gradlew spotlessApply
git diff --stat    # should be empty; if spotless changed anything, amend it into the commit
./gradlew :instrumentation-api-incubator:check \
  :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests:check \
  :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:compileJava \
  :instrumentation:clickhouse:clickhouse-client-v2-0.8:javaagent:compileJava
```
- `check` runs spotlessCheck, checkstyle and tests. Error Prone runs inside `compileJava`, and NullAway does too in `instrumentation-api-incubator`, which applies `otel.nullaway-conventions`.
- Don't pass `-PdisableErrorProne=true`.
- Per the repo's AGENTS.md, don't pipe Gradle output through `tail`/`grep`; that hides the exit code.
- Optional and slow: `./gradlew :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:test` runs the reactor-netty integration tests.

## 3. EasyCLA
Sign the CNCF EasyCLA when the bot comments on the PR, or beforehand. The PR can't merge without it.

## 4. Before pasting
- `PR-DRAFT.md` is the exact body; the first line is the title. Paste everything after the title line into the body. It replaces the template, which is only a CHANGELOG reminder; no CHANGELOG entry is needed.
- The disclosure sentence says you reviewed the change and the tests. Make sure that's true before you post.
- Be ready for a reviewer to ask about the pulsar copy (the PR says it's a follow-up) and about a ClickHouse test (none was added).
- Upstream `main` was not re-checked for a duplicate fix during this revision. O1 checked on 2026-09-27; re-check before opening.
