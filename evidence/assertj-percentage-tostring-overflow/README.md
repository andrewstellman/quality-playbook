# assertj: `Percentage.toString()` saturates integral values above `Integer.MAX_VALUE`

**Verdict: CONFIRMED (low severity; affects failure-message text, not assertion outcomes).**
QPB source: `repos/secbench2/sb2-15-assertj/quality/BUGS.md` BUG-005 (QPB v1.5.10 run, 2026-06-21). Scout ranking: candidate 3 of 5 in `docs/research/triage-2026-09-27/scout-candidates-wave2.md`.

## Pinned upstream
`7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada` (2026-09-27 00:20:11 +0200, "ignoring flaky perf test but keeping it to run it manually"), branch `main`, version 4.0.0-SNAPSHOT. Fresh `git clone --depth 1`.
Build: the project's own Maven wrapper (`./mvnw`, Maven 3.9.16) on OpenJDK 25.0.4.1 (CONTRIBUTING requires JDK 25+). Local repo `/tmp/m2`, reactor limited with `-pl ... -am`.

## Defect
`assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62` at the pinned SHA:

```java
    return noFractionalPart() ? "%s%%".formatted((int) value) : "%s%%".formatted(value);
```

`value` is a `double`. For an integral value above `Integer.MAX_VALUE`, the narrowing `(int)` cast saturates (JLS 5.1.3), so `withPercentage(3_000_000_000d).toString()` returns `2147483647%`.

User-visible effect: the percentage in `isCloseTo` / `isNotCloseTo` failure messages is wrong. Verbatim from `message-probe.log` (same assertion, only `Percentage` swapped):

```
== unpatched Percentage (main 7ca2715) ==
...
by more than 2147483647% but difference was 99.99999998999999%.
(a difference of exactly 2147483647% being considered incorrect)
== patched ==
...
by more than 3000000000% but difference was 99.99999998999999%.
(a difference of exactly 3000000000% being considered incorrect)
```

The assertion *outcome* is unaffected (the comparison uses `percentage.value`, not the string).

## Expected behaviour, with sources
- `Percentage` javadoc: "A positive percentage value." `withPercentage(double)` accepts any value `>= 0` (it only rejects negatives: `checkArgument(value >= 0, ...)`), so 3e9 is a valid, accepted input.
- The existing `Percentage_Test.toString_should_display_fractional_part_when_present` pins the intended format: integral values print without a fractional part (`"10.0" -> "10%"`), non-integral values print as-is. Nothing in the tests or javadoc suggests the integral branch was meant to clamp.
- JLS §5.1.3: for a narrowing conversion of a floating-point value too large for `int`, "the result of the first step is the largest representable value of type int".

Severity is low: nobody writes a 3-billion-percent tolerance on purpose. It is still a plain overflow in a public class's `toString()` that shows up in messages.

## Fix
Print the integral branch with `new BigDecimal(value).toPlainString()`. For an integral `double`, `new BigDecimal(double)` is exact with scale 0, so `10.0 -> "10"`, `0.0 -> "0"`, `3e9 -> "3000000000"`, `1e20 -> "100000000000000000000"`. It does not depend on the locale (a `%.0f` format would). The non-integral branch is unchanged.

**Alternative for Andrew:** the historical patch used `(long) value`. That is smaller but still saturates above `Long.MAX_VALUE` (`1e20` would print `9223372036854775807%`), so the second new test row would fail with it. If you prefer `(long)`, drop the `1e20` row.

## Tests (their style)
Two rows were added to the existing `@CsvSource` of `Percentage_Test.toString_should_display_fractional_part_when_present` in `assertj-tests/assertj-integration-tests/assertj-core-tests` (where `Percentage_Test` lives at HEAD). The test already uses GIVEN/WHEN/THEN and `BDDAssertions.then`.

## Results
| run | command | result |
|---|---|---|
| red (`red.log`) | new test rows, **unpatched** `Percentage.java`, `-Dtest=Percentage_Test` | 13 run, **2 failures**: `expected: "3000000000%" but was: "2147483647%"`, `expected: "100000000000000000000%" but was: "2147483647%"` |
| green (`green.log`) | same, patched | 13 run, 0 failures |
| tests-before (`tests-before.log`) | `-Dtest=*Percentage*` in assertj-core + assertj-core-tests, pristine main | 334 + 71 run, 0 failures |
| tests-after (`tests-after.log`) | same, patched | 334 + 73 run, 0 failures (+2 = the new rows) |
| full-suite-before/after (filtered summaries) | whole `assertj-core` + `assertj-core-tests` modules | before 14441 + 6338, after 14441 + 6340, 0 failures both |
| `spotless-license-check.log` | `./mvnw spotless:check license:check` on both modules, patched | BUILD SUCCESS |

Environment note: the first full `assertj-core-tests` run died with `OutOfMemoryError: Java heap space` in the surefire fork (sandbox has 3.9 GB RAM, default heap). Both full-suite runs recorded here used `JAVA_TOOL_OPTIONS=-Xmx2g`. This is an environment limit, not a project issue.

## Disclosure search (GitHub REST search via web_fetch, 2026-09-27)
- `repo:assertj/assertj Percentage toString`: 1 hit, #422 (2015 PR that added `isCloseTo` with percentage). Unrelated.
- `repo:assertj/assertj Percentage overflow`: 0 hits.
- `repo:assertj/assertj is:pr is:open percentage`: 0 hits.
No existing report or open PR was found. Lexical search can miss paraphrased duplicates.

## Contribution requirements
- No DCO or Signed-off-by is required (CONTRIBUTING.md and the PR template never mention it), so none was added. No CLA bot was observed.
- CONTRIBUTING "Legal Disclaimer": "You will only submit contributions where you have authored 100% of the content." The patch and test were written by Claude. **Decision for Andrew:** whether that clause permits submitting AI-authored content under your name, or whether to disclose/ask first. PR-DRAFT.md discloses it either way.
- `AGENTS.md` (repo root) sets rules for AI agents: `./mvnw`, JDK 25, snake_case test names, GIVEN/WHEN/THEN, Markdown `///` javadoc for *new* comments. The patch adds no comments and no new test methods.
- The patch was formatted per spotless (verified with `spotless:check`).

## Files
- `0001-Fix-Percentage.toString-for-integral-values-larger-t.patch` is a `git format-patch` against `7ca2715`, author `Andrew Stellman <andrew@stellman.com>`. `git apply --check` is clean on the pinned SHA.
- `red.log`, `green.log`, `tests-before.log`, `tests-after.log`: full Maven output.
- `full-suite-before.log`, `full-suite-after.log`: filtered summaries. The filter command is in each file header.
- `message-probe.log` shows the user-visible message before and after.
- `spotless-license-check.log`.
- `PR-DRAFT.md`.
