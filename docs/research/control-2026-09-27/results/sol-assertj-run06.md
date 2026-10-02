model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:49:30 UTC; finished 2026-09-28 22:51:09 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Commit: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`  
Scope: `assertj-core/src/main/java/org/assertj/core/data/`

## Findings

1. **Medium — An inclusive temporal offset accepts differences larger than the offset.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:47`. `getDifference` calls `unit.between`, which truncates fractional units. Thus `assertThat(LocalTime.NOON).isCloseTo(LocalTime.NOON.plusSeconds(90), within(1, ChronoUnit.MINUTES))` passes: `MINUTES.between` returns 1 and the `> 1` check is false, although 90 seconds exceeds one minute. The factory's documentation in `Assertions.java` describes `within(long, TemporalUnit)` as a “less than or equal condition,” and `TemporalUnitWithinOffset` says the same. Compare the full temporal difference with the allowed duration where the unit supports it; for calendar units, compare the temporal boundary directly without truncating the difference.

2. **Medium — Temporal offsets with different units compare equal.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`. Both `hashCode` and `equals` use only `value`, omitting `unit`. Therefore `within(1, ChronoUnit.SECONDS).equals(within(1, ChronoUnit.DAYS))` is true even though these offsets accept different time differences. The class stores the unit as part of the offset and `getUnit()` exposes it; the `Assertions.within(long, TemporalUnit)` factory defines both the value and unit as the allowed offset. Include `unit` in both equality and hash calculation.

3. **Medium — Numeric offset validation misclassifies tiny `BigDecimal` values.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60,83`. Validation converts any `Number` to `double` before checking its sign. `Offset.offset(new BigDecimal("-1E-1000"))` accepts a negative offset because `doubleValue()` underflows to `-0.0`, which compares greater than or equal to zero. Conversely, `Offset.strictOffset(new BigDecimal("1E-1000"))` rejects a positive value because it underflows to `0.0`. Both methods document rejection based on the supplied value's sign. Validate `BigDecimal` and `BigInteger` with exact `signum()`, and use type-appropriate comparisons for other number types.

4. **Low — Rendering a large whole percentage changes its value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`. `withPercentage(3000000000d).toString()` renders `2147483647%`: the whole-number branch casts the positive `double` to `int`, saturating at `Integer.MAX_VALUE`. The class represents the supplied percentage value, and the fractional branch renders that value directly. Format the whole `double` without narrowing it to `int`.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/main/java/org/assertj/core/internal/BigDecimals.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
