model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:42:27 UTC; finished 2026-09-28 22:44:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; reproduction performed, details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`

## Findings

1. **Medium — Inclusive temporal offsets admit differences almost one unit too large.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:47` compares the truncated `unit.between` result with `value`. For example, `within(1, MINUTES).isBeyondOffset(LocalTime.NOON, LocalTime.NOON.plusSeconds(119))` returns `false`: `MINUTES.between` returns 1 even though the times are 1 minute 59 seconds apart. Consequently, `assertThat(actual).isCloseTo(other, within(1, MINUTES))` passes outside its documented “less than or equal” offset (the class comment at line 23 and `Assertions.within(long, TemporalUnit)` documentation). Compare the actual temporal distance to the full boundary, preserving fractional units; for fixed-duration units, a precise duration comparison works, while calendar units need a boundary based on temporal addition.

2. **Medium — Strict temporal offsets throw for large valid temporal gaps.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45` calls `getDifference`, which uses `unit.between` and can throw `ArithmeticException` on overflow. For example, `byLessThan(1, NANOS).isBeyondOffset(Instant.MIN, Instant.MAX)` throws rather than returning `true`, so `isCloseTo` cannot produce its documented assertion failure. The inclusive implementation at `TemporalUnitWithinOffset.java:46-50` already catches this overflow and compares `Duration`s. Give the strict implementation the corresponding overflow fallback, with a `>=` comparison.

3. **Medium — Tiny negative BigDecimal offsets bypass validation.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60` decides negativity using `value.doubleValue()`. `new BigDecimal("-1e-1000").doubleValue()` is `-0.0`, which satisfies `>= 0d`, so `Offset.offset` accepts a negative offset despite its `IllegalArgumentException` contract at line 56. Conversely, line 83 rejects a positive `BigDecimal("1e-1000")` in `strictOffset` because it converts to `0.0`, contradicting its line 79 contract. Compare `BigDecimal` and `BigInteger` values in their native precision before constructing an offset; use the floating-point checks only for floating-point types.

4. **Low — Temporal offsets with different units compare equal.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-110` includes only `value` in `equals` and `hashCode`. Thus `within(1, MINUTES).equals(within(1, HOURS))` is true, even though those offsets lead to different assertion results. Include `unit` in both methods, retaining the existing class check so inclusive and strict offsets remain distinct.

5. **Low — Large whole-number percentages render as the wrong number.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62` casts an integral `double` to `int` for display. `withPercentage(3_000_000_000d).toString()` becomes `"2147483647%"` because Java saturates the narrowing conversion. This misreports the percentage in assertion messages, conflicting with the method's representation of the stored percentage value. Format integral values without narrowing to `int` (for example, with a decimal formatter able to represent the full `double` range).

## Verification

A standalone Java probe in `/private/tmp/qpb-control/sol-assertj-run03/Probe.java` confirmed `MINUTES.between` returns 1 for 119 seconds, tiny signed `BigDecimal`s convert to signed zero, `NANOS.between(Instant.MIN, Instant.MAX)` throws `ArithmeticException`, and `(int) 3_000_000_000d` yields `2147483647`. No checkout files were changed.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
