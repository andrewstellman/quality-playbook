# otel-forwarded v2: what only you can do

## Not run here
Gradle was not run. Spotless, checkstyle, Error Prone, NullAway and the Gradle test tasks were **not run**. The tests ran under a standalone javac + JUnit harness (see `harness/`). Run the commands below on the Mac before opening the PR.

## 1. Apply the patch on a fresh branch
```zsh
cd ~/src/opentelemetry-java-instrumentation   # your clone/fork; adjust path
git fetch origin
git checkout -b forwarded-host-ipv6 78d71b585a77d7f2312c1b8751ff6c95a72722d7
git am "/Users/andrewstellman/Documents/QPB/evidence/otel-java-forwarded-host-ipv6/v2/0001-Handle-bracketed-IPv6-hosts-in-ForwardedHostAddressA.patch"
git rebase origin/main    # upstream has moved since the pinned commit
```
This patch and the UrlParser patch touch different files and apply independently. Use separate branches and separate PRs.

## 2. Gradle checks (JDK 25)
```zsh
java -version
./gradlew spotlessApply
git diff --stat    # should be empty; if spotless changed anything, amend it into the commit
./gradlew :instrumentation-api:check
```
- `check` runs spotlessCheck, checkstyle and the full `instrumentation-api` test suite. Error Prone and NullAway run inside `compileJava`; `instrumentation-api` applies `otel.nullaway-conventions`.
- Don't pass `-PdisableErrorProne=true`. Don't pipe the output (repo AGENTS.md).

## 3. EasyCLA
Sign the CNCF EasyCLA when the bot comments on the PR, or beforehand.

## 4. Before pasting
- `PR-DRAFT.md` is the exact body; the first line is the title. Paste everything after the title line into the body. No CHANGELOG entry is needed.
- The disclosure sentence says you reviewed the change and the tests. Make sure that's true before you post.
- A reviewer may ask why bracket parsing now lives in three places (`HostAddressAndPortExtractor`, the `for=` parsing in `HttpServerAddressAndPortExtractor`, and here). O1's suggested answer: it's kept local to match the existing pattern, and you're happy to extract a helper.
- The new code comment is wordier than the existing `// ipv6 address enclosed in square brackets case` in `HttpServerAddressAndPortExtractor`. If a reviewer prefers the house wording, switching back is a one-line change.
- Upstream `main` was not re-checked for a duplicate fix during this revision.
