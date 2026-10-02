model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:53:45 UTC; finished 2026-09-28 22:55:49 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`  
Scope: `assertj-core/src/main/java/org/assertj/core/data/`

## Findings

1. **Medium — An inclusive temporal offset accepts differences beyond its limit.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:47` compares the whole-unit result of `getDifference` with `value`. `TemporalUnitOffset.java:76` obtains that result with `unit.between`, which truncates fractional units. For example, `within(1, SECONDS).isBeyondOffset(Instant.EPOCH, Instant.EPOCH.plusMillis(1500))` returns `false`: `SECONDS.between` returns `1`, although the actual difference is 1.5 seconds. Likewise, `within(0, SECONDS)` accepts any positive difference shorter than a second. The class documentation at lines 23 and 39–42 specifies a less-than-or-equal offset, and `AbstractTemporalAssert.isCloseTo` uses this result to decide whether to fail. Compare the precise duration with the allowed amount for time-based units, or otherwise check whether a whole-unit equality has a nonzero remainder.

2. **Medium — Strict temporal comparison throws on large differences instead of producing an assertion failure.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45` calls `getDifference` without handling `ArithmeticException`. For `byLessThan(1, NANOS)` comparing `Instant.EPOCH` with `Instant.EPOCH.plusSeconds(10_000_000_000L)`, `ChronoUnit.NANOS.between` overflows a `long`, so `isCloseTo` propagates `ArithmeticException`. `TemporalUnitWithinOffset.java:46–49` explicitly handles this same overflow with a `Duration` fallback; the `TemporalOffset` contract says this method reports whether the difference is beyond the offset. Apply an analogous overflow fallback to the strict comparison, using `>=` rather than `>`.

3. **Medium — Equality ignores a temporal offset's unit.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99–110` hashes and compares only `value`. Thus `new TemporalUnitWithinOffset(1, SECONDS).equals(new TemporalUnitWithinOffset(1, HOURS))` is `true`, although the two objects give different answers for the same temporal pair. The class stores the unit as part of its offset at lines 33–49, and `getDifference` uses it at line 76. Include `unit` in both `equals` and `hashCode`.

4. **Medium — Numeric offset validation loses the sign of very small `BigDecimal` values.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60` validates a `Number` through `doubleValue()`. `new BigDecimal("-1e-400").doubleValue()` is negative zero, for which `>= 0d` is true, so `offset(new BigDecimal("-1e-400"))` accepts a negative value despite the factory's documented `IllegalArgumentException` for negative offsets (lines 41–56). Conversely, line 83 rejects a positive `BigDecimal("1e-400")` as a strict offset because it underflows to positive zero. Validate `BigDecimal` and `BigInteger` with their native sign or comparison methods, and use the primitive checks for the fixed-width numeric types.

5. **Low — Large integral percentages are printed as a different value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62` casts every percentage without a fractional part to `int`. For example, `withPercentage(3_000_000_000d).toString()` yields `2147483647%` rather than `3000000000%` because the Java narrowing conversion saturates. The `value` field and the factory's documentation establish that the object represents the supplied percentage. Format the `double` without a fractional part using a representation that does not narrow to `int`.

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
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java` (matching lines)
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java` (matching lines)
