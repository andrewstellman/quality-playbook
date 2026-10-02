model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:55:57 UTC; finished 2026-09-28 22:58:37 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local Java checks
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`

1. **Medium — Negative BigDecimal offsets can be accepted** — `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60` (also line 83). `offset(new BigDecimal("-1E-1000"))` succeeds because `doubleValue()` underflows to negative zero, and `-0.0 >= 0.0` is true. Conversely, `strictOffset(new BigDecimal("1E-1000"))` rejects a positive value because conversion yields zero. The factories document nonnegative and positive offset bounds respectively; these inputs violate both bounds. Compare `BigDecimal` and `BigInteger` values in their native type (or compare the sign without lossy conversion), with suitable handling for other `Number` implementations.

2. **Medium — Temporal offsets with different units compare equal** — `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:110` (and line 101). `new TemporalUnitWithinOffset(1, ChronoUnit.SECONDS).equals(new TemporalUnitWithinOffset(1, ChronoUnit.DAYS))` returns true, although the two objects give different results for the same temporal values because `getDifference` uses `unit` at line 76. Equality and hash code consider only `value`. Include `unit` in both methods.

3. **Medium — Strict temporal comparison leaks arithmetic overflow** — `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`. For example, `assertThat(Instant.EPOCH).isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.MILLIS))` calls `ChronoUnit.MILLIS.between` through `getDifference`, which throws `ArithmeticException` for this range. The inclusive counterpart at `TemporalUnitWithinOffset.java:46-50` handles that overflow using `Duration`, and `AbstractTemporalAssert.isCloseTo` documents an `AssertionError` when values are outside the offset. Give the strict comparison the same overflow fallback, using `>=` for the duration comparison.

4. **Low — Large whole percentages display a different number** — `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`. `withPercentage(2147483648d).toString()` becomes `2147483647%`: `noFractionalPart()` is true, but casting the double to `int` saturates at `Integer.MAX_VALUE`. This misstates the percentage in diagnostics. Format the whole value without narrowing to `int` (for example, use a floating-point integral format or `BigDecimal` representation).

Validation: local Java 21 snippets confirmed the BigDecimal conversion and double-to-int cast behavior, and that `ChronoUnit.MILLIS.between(Instant.EPOCH, Instant.MIN)` throws `ArithmeticException`. No checkout files were modified.

Files read: `assertj-core/src/main/java/org/assertj/core/data/Index.java`, `MapEntry.java`, `Offset.java`, `Percentage.java`, `TemporalOffset.java`, `TemporalUnitLessThanOffset.java`, `TemporalUnitOffset.java`, `TemporalUnitWithinOffset.java`; `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`, `Assertions.java`; `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`.
