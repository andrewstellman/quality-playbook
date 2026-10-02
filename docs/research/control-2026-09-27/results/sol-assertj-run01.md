model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:37:22 UTC; finished 2026-09-28 22:39:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`

## Findings

1. **Medium — Inclusive temporal offsets accept differences beyond the limit.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:47` compares `getDifference(...)` to `value`; `getDifference` calls `unit.between(...)` at `TemporalUnitOffset.java:76`, which truncates incomplete units. Thus `assertThat(LocalTime.NOON).isCloseTo(LocalTime.NOON.plusSeconds(119), within(1, MINUTES))` passes: `MINUTES.between` is 1, though the difference is nearly two minutes. Even `within(0, MINUTES)` accepts a 59-second difference. This contradicts the `TemporalUnitWithinOffset` contract at lines 22-23 and 38-42, and the `AbstractTemporalAssert.isCloseTo` contract that rejects values outside the provided offset. Compare at full precision, for example against a temporal boundary made by adding/subtracting the specified offset, rather than comparing truncated whole-unit counts.

2. **Medium — Different temporal units compare equal.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-111` includes only `value` in `hashCode` and `equals`, ignoring `unit`. Consequently `within(1, DAYS).equals(within(1, NANOS))` is true (as is equality between any two instances of the same subclass and value with different units), although they produce radically different `isBeyondOffset` results. The class documents both `unit` and `value` as the offset's state at lines 33-36 and returns `unit` via `getUnit` at lines 90-96. Include `unit` in both equality and hash code.

3. **Medium — Strict temporal offsets throw for distant Instants instead of evaluating closeness.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45` calls `getDifference` without the `ArithmeticException` fallback used by `TemporalUnitWithinOffset.java:46-50`. For example, comparing `Instant.MIN` with `Instant.MAX` using `byLessThan(1, NANOS)` causes `ChronoUnit.NANOS.between` to overflow and throw `ArithmeticException`, so `isCloseTo` never produces its specified assertion failure. `TemporalUnitWithinOffset` explicitly handles this same case with `Duration`. Add equivalent overflow handling to the strict variant, using `>=` for the strict boundary.

4. **Medium — Negative offsets can pass validation after conversion to double.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:58-61` validates a generic `Number` via `doubleValue()`. `new BigDecimal("-1E-400").doubleValue()` is negative zero, which compares `>= 0d`, so `offset(new BigDecimal("-1E-400"))` accepts a negative offset despite its documented `IllegalArgumentException` contract at line 56. Conversely, `strictOffset(new BigDecimal("1E-400"))` rejects a positive offset because it converts to zero (lines 81-84). Validate `BigDecimal` and `BigInteger` with their exact sign comparison, and handle other supported numeric types without lossy conversion.

5. **Low — Large integer percentages are printed as a different value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:60-66` casts every whole-valued percentage to `int` for `toString`. `withPercentage(2147483648d).toString()` therefore prints `"2147483647%"`; any larger finite whole value is also saturated at `Integer.MAX_VALUE`. The class exposes `value` as the percentage value at lines 25-28, so the representation reports the wrong offset in diagnostics. Format the integral `double` without narrowing it to `int`.

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
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_withinPercentage_Test.java`
