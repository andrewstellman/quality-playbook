model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:46:36 UTC; finished 2026-09-28 22:49:11 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`. Scope: `assertj-core/src/main/java/org/assertj/core/data/`.

## Findings

1. **Medium — Temporal offsets compare equal despite different units.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-110`. `new TemporalUnitWithinOffset(1, HOURS).equals(new TemporalUnitWithinOffset(1, DAYS))` returns `true` and their hash codes are identical, although one allows one hour and the other one day. The class stores `unit` at line 49 and uses it in `getDifference` at line 76; the factory documentation in `Assertions.within(long, TemporalUnit)` calls it “the unit of the offset.” Include `unit` in both `equals` and `hashCode`.

2. **Medium — Whole-unit truncation accepts temporal differences outside an inclusive offset.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:75-76` and `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:45-49`. `ChronoUnit.HOURS.between(12:00, 13:59)` returns `1`, so `isCloseTo(13:59, within(1, HOURS))` passes even though the difference is 1 hour 59 minutes. The API documents `within` as a “less than or equal condition,” and `TemporalUnitWithinOffset` says the difference must be less than or equal to the offset. Compare the full temporal difference with the offset instead of comparing the truncated count returned by `unit.between`.

3. **Medium — Strict temporal offsets leak overflow instead of an assertion failure.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:43-46`. `isCloseTo(Instant.MAX, byLessThan(1, NANOS))` on `Instant.MIN` throws `ArithmeticException` from `ChronoUnit.NANOS.between`, rather than reporting that the two instants are too far apart. `TemporalUnitWithinOffset.java:46-49` already catches this overflow and compares `Duration` values, while `AbstractTemporalAssert.isCloseTo` promises `AssertionError` when a value is not close. Apply the same overflow fallback to the strict variant, with a strict comparison.

4. **Medium — A negative `BigDecimal` can be accepted as a nonnegative numeric offset.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:58-61`. `Offset.offset(new BigDecimal("-1e-400"))` succeeds because `doubleValue()` rounds the negative value to `-0.0`, and `-0.0 >= 0` is true. The method promises to reject negative values, and downstream numeric assertions receive the invalid offset. Compare the `Number` without narrowing it to `double` (with appropriate handling for the supported numeric types).

5. **Low — Large integral percentages print the wrong value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:60-66`. `Percentage.withPercentage(10000000000d).toString()` returns `2147483647%`: `noFractionalPart()` is true, then the `int` cast saturates at `Integer.MAX_VALUE`. The returned string purports to represent the stored percentage value but does not. Format the integral `double` without casting to `int`, or use a wider/decimal representation.

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
- `assertj-core/src/main/java/org/assertj/core/util/Preconditions.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
