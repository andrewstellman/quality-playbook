model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:23:59 UTC; finished 2026-09-28 23:25:51 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data-package review

## Findings

1. **Medium — negative `BigDecimal` offsets can be constructed and used**

   - **Location:** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60`
   - `Offset.offset(new BigDecimal("-1E-10000"))` succeeds because converting that negative value to `double` produces `-0.0`, and `-0.0 >= 0d` is true. The returned offset retains the negative `BigDecimal`; for example, `assertThat(BigDecimal.ONE).isCloseTo(BigDecimal.ONE.add(new BigDecimal("1E-10000")), offset(new BigDecimal("-1E-10000")))` uses a negative tolerance instead of rejecting it.
   - This contradicts the factory's documented contract at lines 52–60, which says negative values cause `IllegalArgumentException`. The value is subsequently compared in its original numeric type by `Numbers.assertIsCloseTo` (lines 210–213), so the negative value is not normalized away.
   - **Suggested fix:** validate according to the concrete number type without a lossy `doubleValue()` conversion. At minimum, special-case `BigDecimal` and `BigInteger` with `signum()`; preferably centralize an exact non-negative comparison for the supported `Number` types. Add a regression test for a negative `BigDecimal` whose `doubleValue()` is `-0.0`.

2. **Low — temporal offsets with different units compare equal**

   - **Location:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-111`
   - `new TemporalUnitWithinOffset(1, ChronoUnit.HOURS).equals(new TemporalUnitWithinOffset(1, ChronoUnit.DAYS))` returns `true` and the two objects have the same hash code. They have observably different behavior: a two-hour difference is beyond the former offset but within the latter.
   - `unit` is a stored part of the offset state (lines 33–50) and is used to calculate the difference (line 76), but both `equals` and `hashCode` use only `value`. This causes semantically distinct offsets to collapse in `HashSet`, `HashMap`, and equality-based tests.
   - **Suggested fix:** include `unit` in both methods, e.g. `Objects.hash(value, unit)` and `value == other.value && Objects.equals(unit, other.unit)`. Add coverage using identical values with `HOURS` and `DAYS`.

3. **Low — whole percentages above `Integer.MAX_VALUE` are rendered as a different percentage**

   - **Location:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`
   - `Percentage.withPercentage(2_147_483_648d).toString()` produces `"2147483647%"`, because the whole-valued `double` is narrowed to `int`. Any accepted whole percentage above the `int` range is displayed as `Integer.MAX_VALUE%` (or the corresponding narrowing result), rather than its stored value.
   - The factory accepts every non-negative `double` (lines 38–40), and `toString` is the object's public representation. The conversion therefore makes assertion diagnostics report a tolerance different from the one supplied.
   - **Suggested fix:** avoid narrowing to `int`. Format the whole-valued double directly (or use `BigDecimal.valueOf(value).toPlainString()` when the integer-style presentation is required) and add a test for a whole value greater than `Integer.MAX_VALUE`.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractBigDecimalAssert.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
- `assertj-core/src/test/java/org/assertj/core/internal/bigdecimals/BigDecimals_assertIsCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
