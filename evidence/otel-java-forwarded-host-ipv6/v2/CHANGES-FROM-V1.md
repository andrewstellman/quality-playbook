# otel-forwarded: changes from v1

Source: `review-2026-09-27/SYNTHESIS.md`, section "otel-forwarded", plus O1, O2, O3, S2, S5.

| Synthesis item | What v2 does |
|---|---|
| Run Gradle `:instrumentation-api:check`, including spotless | Not run here. See NOTES-FOR-ANDREW.md. google-java-format 1.36.1 `--dry-run` reports no changes to the main file or the extractor test. It flags `HttpServerAttributesExtractorTest.java`, but only for three long string literals around line 582 that the patch doesn't touch. Base gets the same flag, so this comes from this gjf invocation and not from the patch. That is not a substitute for `spotlessCheck`. |
| Remove the HTML provenance comment | Removed. The PR body has no HTML comments and nothing addressed to Andrew. `Assisted-by: Claude Opus 5.5` stays as the commit trailer; the PR ends with one disclosure sentence. The Quality Playbook link was dropped to keep that to one sentence. |
| EasyCLA | Andrew's action; see NOTES-FOR-ANDREW.md. |
| Mention the unterminated `[` fall-through (S5, O2) | The PR has a paragraph saying an unterminated `[` is now treated as malformed, so the extractor falls through to the next header source instead of recording `"["`. The red log shows the base behavior (`[::1` rows: `expected: null but was: "["`). |
| Clearer comment (S2) | `// ipv6 address enclosed in square brackets case` is now `// an IPv6 address is enclosed in square brackets and contains ':' characters, so the address ends at the closing ']' and the port, if any, follows it`, matching the UrlParser patch's wording. Note: the old terse wording copies the existing comment in `HttpServerAddressAndPortExtractor.java:91` at the pinned commit. The new wording follows the synthesis, but a maintainer could prefer the house wording. |
| PR template / CONTRIBUTING | The template is only a comment saying not to add a CHANGELOG entry except for deprecations or breaking changes. None is added. No issue is needed for a bug fix. |
| Commit message short and proportional | Subject unchanged; a three-line body, then the trailer. |

Code logic and tests are unchanged from v1; only the comment changed. `[]` still yields an empty `server.address`, as `HostAddressAndPortExtractor` does (O2, O3 noted this as optional).

## Evidence in this folder
- `red.log`: base main code + v2 tests. 48 passed / 23 failed (`but was: "["` / `"[2001"`, and `server.address="[2001"` with no port in the attribute-level test). Exit 1.
- `green.log`: v2. 71/0. Exit 0.
- `revert.log`: v2 with `ForwardedHostAddressAndPortExtractor.java` checked out from base, tests kept. The same 23 failures as red. Exit 1.
- `suite-before.log`: base, all of package `semconv.http` except three tests that need other Gradle projects. 429/0.
- `suite-after.log`: v2, 452/0 (+23 new cases).
- `harness/`: `run.sh` (unchanged from v1), `otel-verify.sh` (driver), `deps.SHA1SUMS` (all 24 jars matched).

All runs used javac + JUnit Platform console on JDK 25.0.4.1 (Linux arm64). Gradle was not used.
