# assertj triage, 2026-09-27

Source: `docs/research/triage-2026-09-27/scout-candidates-wave2.md` (assertj rows). Historical findings: `repos/secbench2/sb2-15-assertj/quality/BUGS.md` + `quality/patches/BUG-00{1..6}-*.patch` (QPB v1.5.10, 2026-06-21).
Pinned upstream: assertj/assertj `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada` (2026-09-27 00:20:11 +0200), `main`, 4.0.0-SNAPSHOT. Fresh shallow clone. Built with the project's `./mvnw` (Maven 3.9.16) on OpenJDK 25.0.4.1, `-pl assertj-core[,assertj-tests/assertj-integration-tests/assertj-core-tests] -am`. Baseline full suites on unpatched main: assertj-core 14441 run / 0 failures, assertj-core-tests 6338 run / 0 failures.
None of the candidates has security impact.

Runtime probe of every candidate on the pinned SHA: `assertj-triage-2026-09-27-probe.log` (verbatim output; probe sources are summarized at the end of this file).

| # | candidate (historical ID) | verdict | where | evidence |
|---|---|---|---|---|
| 1 | `DoubleComparator`/`FloatComparator` NaN vs Comparator contract (BUG-001/002) | **ALREADY REPORTED + maintainer-declined** (NaN==NaN, #1390). The residual antisymmetry part is **NEEDS-MAINTAINER-INPUT** | `util/DoubleComparator.java:35-38`, `util/FloatComparator.java:41-45` | probe log only |
| 2 | `ComparatorBasedComparisonStrategy` remove methods NPE on null (BUG-003) | **NEEDS-MAINTAINER-INPUT** (reproduces, but the class documents null handling as the comparator's job) | `api/comparisonstrategy/ComparatorBasedComparisonStrategy.java:112-138` | probe log only |
| 3 | `Percentage.toString()` int overflow (BUG-005) | **CONFIRMED** (low severity; message text only) | `data/Percentage.java:62` | `evidence/assertj-percentage-tostring-overflow/` |
| 4 | `NumberGrouping` hex regex literal pipe (BUG-006) | **LATENT ONLY**, no observable effect through the public API. No PR prepared | `presentation/NumberGrouping.java:27` | probe log only |
| 5 | `Float.NaN` rendered `"NaNf"` (BUG-004) | **NOT A DEFECT** (intended, pinned by 6 existing tests) | `presentation/StandardRepresentation.java:690-692` | probe log only |

(all paths relative to `assertj-core/src/main/java/org/assertj/core/`)

## 1. DoubleComparator / FloatComparator and NaN: ALREADY REPORTED (declined) / NEEDS-MAINTAINER-INPUT
Reproduces as described. `new DoubleComparator(0.01)`: `compare(NaN,1.0)=1`, `compare(1.0,NaN)=1`, `compare(NaN,NaN)=1`, and the same for `FloatComparator` (probe log). Observable effects:
- `assertThat(1.0).usingComparator(dc).isGreaterThan(NaN)` **and** `assertThat(NaN).usingComparator(dc).isGreaterThan(1.0)` both pass.
- `List.sort(dc)` threw `IllegalArgumentException: Comparison method violates its general contract!` in 197 of 200 random trials (200 elements, about 20% NaN). A 6-element list does **not** throw, because TimSort's small-array path never checks; the historical regression test sorts only 6 elements, so its sort assertion alone would pass on main (its antisymmetry assertions do fail).
- The default recursive comparison registers `DoubleComparator(1e-15)` for `Double`, so two objects whose `Double` field is `NaN` are reported as different (probe log). Meanwhile `assertThat(Double.NaN).isEqualTo(Double.NaN)` passes (fixed in #1783) and `OptionalDouble.hasValue(NaN)` passes (fixed in #3401).

Why not a PR:
- The historical fix (`Double.compare` in the non-close branch) makes `compare(NaN,NaN)==0`. That reverses a deliberate decision. In **#1390** (2019, "isEqualToComparingFieldByField does not deal with Infinity"), the reporter proposed treating NaN as equal, and project lead joel-costigliola replied: "I indeed think it should not compare NaN, users can always register their own double comparator". The Infinity half was fixed (milestone 3.12; the `x.doubleValue() == y.doubleValue()` short-circuit). The NaN half is pinned at HEAD by `DoubleComparatorTest.should_not_be_equal_if_not_a_number` (`nearlyEqual(NaN, NaN)` must be false). So the reflexivity part is **already reported and declined**.
- The contract cannot be met while keeping that policy. The `java.util.Comparator` javadoc requires `signum(compare(x, y)) == -signum(compare(y, x))` "for all x and y". With x = y = NaN this forces `compare(NaN,NaN) == 0`. Any contract-compliant fix therefore reverses the #1390 decision and breaks the pinned test. A partial fix (NaN consistently greater than numbers, but NaN != NaN) would stop the `isGreaterThan` contradiction but still violates the contract. Epsilon comparators are also inherently non-transitive (a~b, b~c, a!~c), so sorting with them breaks the contract even without NaN.
- The recursive-comparison inconsistency (NaN field != NaN field, while `isEqualTo(NaN)` passes) is the strongest user-facing argument. It is a policy question for the maintainers, not a patch.
- **Decision for Andrew:** file nothing, or open an *issue* (not a PR) asking whether the default recursive-comparison `Double`/`Float` comparators should treat NaN like `Double.equals` does, now that #1783/#3401 moved `isEqualTo`/`hasValue` that way. Cite #1390.

Searches: `repo:assertj/assertj NaN DoubleComparator` found 1 hit (#1390). `repo:assertj/assertj NaN recursive` found 0. `repo:assertj/assertj NaN in:title` found 3 (#984 isCloseTo NaN, fixed 2017; #1783 isEqualTo NaN, fixed 3.16.0; #3401 OptionalDouble.hasValue NaN, fixed 3.26.0). None is about the comparator contract.

## 2. ComparatorBasedComparisonStrategy null asymmetry: NEEDS-MAINTAINER-INPUT
Reproduces. With `Comparator.<Integer>naturalOrder()`, `iterableContains([1,null,2], 1)` returns true, while `iterableRemoves` and `iterablesRemoveFirst` throw an NPE from the comparator. Publicly, `assertThat(List.of-with-null).usingElementComparator(naturalOrder()).containsExactlyInAnyOrder(2, 1, null)` and the array `containsOnly(2, 1, null)` throw NPE, while `contains(2, 1, null)` passes.

Why not a PR: the same class documents the opposite policy. `areEqual` (lines 150-153) says:
> "we don't check actual or expected for null, this should be done by the comparator, the rationale being that a comparator might consider null to be equals to some special value (like blank String and null)"

Consistent with that, `containsExactly(1, null, 2)` with the same comparator also NPEs, through `areEqual` (stack: `ComparatorBasedComparisonStrategy.areEqual:153 <- IterableDiff.isActualElementInExpected:86`). The historical fix (a null guard in the remove methods) would therefore make `containsExactlyInAnyOrder` null-tolerant while `containsExactly` still NPEs. It would also bake `contains`' guard semantics (null matches only null) into the remove paths, which contradicts the "null may equal a special value" rationale. Precedent **#547** (2015, NPE from `usingElementComparator(new BigDecimalComparator())` with nulls) was resolved by making the *comparator* null-safe, not the strategy. The real inconsistency is that `iterableContains` pre-filters nulls while the rest of the class leaves nulls to the comparator. Which side is "right" is the maintainers' call.
- **Decision for Andrew:** drop it, or raise it as an issue/question. It is not a clear bug fix.

Searches: `repo:assertj/assertj usingElementComparator NullPointerException` found 2 (#547 above; #1794 unrelated). `repo:assertj/assertj ComparatorBasedComparisonStrategy null` found 4 (#3725 recursive map nulls, closed duplicate; #2901 `returns(null, ...)`; #1452; #2086). None covers this.

## 3. Percentage.toString() overflow: CONFIRMED
`withPercentage(3_000_000_000d).toString()` gives `2147483647%`, and the wrong value shows in `isNotCloseTo` failure messages. The fix uses `new BigDecimal(value).toPlainString()` for the integral branch. Red: 2 failing rows. Green: pass. `*Percentage*` classes: 334+71 before, 334+73 after, 0 failures. Full assertj-core + assertj-core-tests: 14441+6338 before, 14441+6340 after, 0 failures. Spotless/license checks are clean. No prior report was found (`Percentage toString`: 1 unrelated hit, #422; `Percentage overflow`: 0; open PRs mentioning percentage: 0). Details, alternatives, and Andrew's decisions are in the evidence README.

## 4. NumberGrouping `[0-9|A-Z]`: LATENT ONLY
The `|` inside the character class is literal, as described. The only callers are `HexadecimalRepresentation:132` (`NumberGrouping.toHexLiteral(toHex(value, size))`, where `toHex` is `String.format("%0<n>X", value)`, so only `[0-9A-F]`) and `BinaryRepresentation:133` (binary pattern, no pipe). `NumberGrouping` is a package-private final class. No input through the public API can put a `|` into a grouped string, so there is no observable effect. For example, `HexadecimalRepresentation.toStringOf("ab|c")` renders chars individually as `'0x007C'` and never groups a pipe (probe). A one-character cleanup PR is possible, but the task rules say not to prepare one for a latent-only issue. **Decision for Andrew:** skip, or bundle it as a drive-by in another PR if one ever touches this file.
Search: `repo:assertj/assertj NumberGrouping` found 0.

## 5. Float NaN rendered `"NaNf"`: NOT A DEFECT
The `f` suffix is how `StandardRepresentation` tells `Float` from `Double` in messages, and the NaN/Infinity forms are pinned by existing tests: `Floats_assertIsNaN_Test:43,55` (`"NaNf"`), `Floats_assertIsNotNaN_Test:42,54` (`NaNf`), `ShouldBeFinite_create_Test:46` (`"Infinityf"`), and `ShouldNotBeInfinite_create_Test:46` (`"Infinityf"`). It is useful: `assertThat((Object) Float.NaN).isEqualTo(Double.NaN)` fails with `expected: NaN / but was: NaNf`, which shows the type mismatch. Without the suffix, both sides would print `NaN`. The historical fix would break 6 tests and remove that disambiguation.
Search: `repo:assertj/assertj NaNf` found 0.

## PR packaging
Only one candidate is confirmed, so there is one PR (`evidence/assertj-percentage-tostring-overflow/`). CONTRIBUTING has no rule on bundling. It says maintainers squash-and-rebase PRs.

## Method notes
- All disclosure searches used the GitHub REST search API through `web_fetch` on 2026-09-27. `api.github.com/repos/assertj/assertj/issues/1390/comments` returned an empty body, so the #1390 maintainer comment was read from the issue HTML page. #1390 shows 5 comments and only the first reply was visible. Later comments were not read.
- The probe used `assertj-core/target/classes` from the pinned SHA (plus byte-buddy). The labelled line `C2 isEqualTo list ...` in the probe log actually runs `containsExactly(1, null, 2)`, which is a label typo in the probe.
- Nothing was pushed, opened, or commented on.
- Probe sources (in `/tmp`, deleted afterwards): `Probe.java` runs each candidate's call and prints the result or exception (as in the log). `Sort.java` runs 200 trials of sorting 200 random `Double`s (values 0..999, about 20% NaN) with `new DoubleComparator(0.01)` and counts `IllegalArgumentException`s.
