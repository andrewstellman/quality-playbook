model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:44:29 UTC; finished 2026-09-28 22:46:23 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; verification performed, details in review
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`  
Scope: `assertj-core/src/main/java/org/assertj/core/data/`

## Findings

1. **Medium — Inclusive temporal offsets can accept a difference larger than the offset.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:47` compares `getDifference(...) > value`, while `TemporalUnitOffset.java:76` computes that difference with `unit.between`, which truncates fractional units. For example, `LocalDateTime` values 1 hour 59 minutes apart with `within(1, HOURS)` produce a difference of `1`, so `isCloseTo` passes. The class documents a “less than or equal” condition (line 23), and `Assertions.within(long, TemporalUnit)` calls the value the allowed offset. Compare the full elapsed duration with the duration represented by the offset for time-based units; for date-based units, use an exact boundary comparison that preserves the subunit remainder.

2. **Medium — Numeric offset validation loses sign and magnitude for tiny `BigDecimal` values.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60` and `:83` validate via `value.doubleValue()`. `new BigDecimal("-1e-400").doubleValue()` is negative zero, so `offset(...)` accepts a negative value despite its documented `IllegalArgumentException` contract (lines 55–56). Conversely, `strictOffset(new BigDecimal("1e-400"))` rejects a positive value as zero, contrary to the strict offset contract (lines 65 and 79). Validate `BigDecimal` and `BigInteger` with their exact `signum()`, and use type-aware comparisons for other `Number` implementations.

3. **Medium — Strict temporal offsets throw on large valid instant differences.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45` calls `getDifference` without handling arithmetic overflow. With `byLessThan(1, NANOS)` and two `Instant`s roughly 300 years apart, `ChronoUnit.NANOS.between` throws `ArithmeticException` instead of allowing `isCloseTo` to fail with the documented `AssertionError` (`AbstractTemporalAssert.java`, `isCloseTo` Javadoc). The inclusive implementation at `TemporalUnitWithinOffset.java:46–50` already catches this case and compares `Duration`s. Add the corresponding duration fallback to the strict implementation, using `>=`.

4. **Low — Temporal offsets with different units compare equal.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99–110` hashes and compares only `value`. Thus `within(1, DAYS).equals(within(1, HOURS))` is true even though the offsets give different `isBeyondOffset` results for the same temporals. The class stores the unit as part of the offset (lines 33–36), and its comparison uses that unit (line 76). Include `unit` in both `equals` and `hashCode`.

5. **Low — Large whole percentages render as a different value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62` casts every whole-valued `double` to `int` for `toString()`. `withPercentage(3_000_000_000d).toString()` becomes `"2147483647%"`, so assertion diagnostics misstate the supplied percentage. The factory permits every nonnegative finite value (lines 38–40). Format whole values without narrowing to `int`; for example, use a decimal formatter or the original `double` representation when outside the `int` range.

## Verification

A local Java probe confirmed that `ChronoUnit.HOURS.between` returns `1` for a 1 hour 59 minute gap; the tiny negative and positive `BigDecimal` values convert to signed zero; and `ChronoUnit.NANOS.between` throws `ArithmeticException` for a roughly 300 year `Instant` gap while `Duration.between` succeeds. No checkout files were modified.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java` (relevant methods and Javadoc)
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java` (relevant method and Javadoc)
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java` (relevant test data)
