model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:58:44 UTC; finished 2026-09-28 23:01:06 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local JDK checks
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data review — `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`

## Findings

1. **Medium — Inclusive temporal offset accepts differences beyond its limit.** [`TemporalUnitWithinOffset.java:47`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java#L47) compares `getDifference()` with `value`, but [`TemporalUnitOffset.java:76`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java#L76) obtains that difference with `unit.between`, which truncates a partial unit. For example, `LocalTime.NOON` and `LocalTime.NOON.plusSeconds(90)` are 90 seconds apart, but `MINUTES.between` returns 1, so `isCloseTo(..., within(1, MINUTES))` passes. The `within(long, TemporalUnit)` documentation promises a *less than or equal* condition; 90 seconds exceeds one minute. Compare the actual temporals against the full boundary (or account for the remainder after whole units), without truncating the difference before the inclusive test.

2. **Medium — Strict temporal offset propagates overflow instead of reporting a failed assertion.** [`TemporalUnitLessThanOffset.java:45`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java#L45) calls `getDifference()` without handling `ArithmeticException`. `ChronoUnit.MILLIS.between(Instant.parse("2020-01-01T00:00:00Z"), Instant.MIN)` overflows, so `isCloseTo(Instant.MIN, byLessThan(2, MILLIS))` throws `ArithmeticException` rather than an assertion failure. The `AbstractTemporalAssert.isCloseTo` contract says an actual value outside the offset fails with `AssertionError`, and the inclusive implementation at `TemporalUnitWithinOffset.java:46-50` already handles this overflow using `Duration`. Give the strict implementation a corresponding overflow path that compares the absolute duration with the allowed offset.

3. **Medium — Temporal offsets with different units compare equal.** [`TemporalUnitOffset.java:99-110`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java#L99) implements `equals` and `hashCode` using only the numeric value and subclass. Thus `new TemporalUnitWithinOffset(1, MINUTES).equals(new TemporalUnitWithinOffset(1, HOURS))` is true, despite the offsets permitting different time gaps. The class exposes the unit at `getUnit()` and documents both value and unit as constructor inputs. Include `unit` in both equality and hash calculation.

4. **Medium — Generic numeric offsets misclassify tiny `BigDecimal` values.** [`Offset.java:60`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/Offset.java#L60) and [`Offset.java:83`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/Offset.java#L83) validate using `doubleValue()`. `new BigDecimal("-1e-1000").doubleValue()` is negative zero, which satisfies `>= 0`, so `offset(new BigDecimal("-1e-1000"))` accepts a negative offset contrary to its `IllegalArgumentException` contract. Conversely, `strictOffset(new BigDecimal("1e-1000"))` rejects a positive value because it rounds to positive zero. Validate `BigDecimal` and `BigInteger` with their native sign comparisons, then handle the remaining `Number` types appropriately.

5. **Low — Large whole percentages stringify as the wrong value.** [`Percentage.java:62`](../../../../repos/control-2026-09-27/assertj/assertj-core/src/main/java/org/assertj/core/data/Percentage.java#L62) casts any whole valued `double` to `int`. `withPercentage(10_000_000_000d).toString()` therefore produces `2147483647%`, although the stored percentage is ten billion. The factory accepts every nonnegative `double`, and `toString()` is intended to represent that percentage. Avoid the `int` cast for values outside the `int` range; use a whole-number formatting path that retains the full magnitude.

## Verification

Read the relevant assertion API contract and tests. A local Java 21 `jshell --execution local` check confirmed `MINUTES.between` returns `1` for 90 seconds, the `Instant.MIN` millisecond calculation throws `ArithmeticException`, tiny positive/negative `BigDecimal` values convert to `0.0`/`-0.0`, and `(int) 1e10` yields `2147483647`. No checkout files were modified.

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
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
