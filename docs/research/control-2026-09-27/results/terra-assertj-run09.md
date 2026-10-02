model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:25:58 UTC; finished 2026-09-28 23:27:41 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ `core/data` review

## Findings

### 1. Strict temporal offsets throw on large, otherwise valid temporal ranges

- **Severity:** medium
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Failure:** `assertThat(Instant.now()).isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.MILLIS))` throws `ArithmeticException` from `ChronoUnit.MILLIS.between` rather than failing the assertion. `Instant.MIN` is already used by the corresponding temporal assertion test for the inclusive-offset overflow case.
- **Why this is wrong:** `AbstractTemporalAssert.isCloseTo` documents that a temporal outside its provided offset produces an `AssertionError` (lines 75-77). `TemporalUnitWithinOffset.isBeyondOffset` deliberately catches this `ArithmeticException` and compares absolute `Duration`s instead (lines 46-50), so the inclusive form correctly reports the assertion failure for the same range. The strict variant calls `getDifference` without that fallback, even though its difference predicate only changes from `>` to `>=`.
- **Suggested fix:** Mirror the inclusive implementation: catch `ArithmeticException` in `TemporalUnitLessThanOffset.isBeyondOffset` and return `getAbsoluteDuration(temporal1, temporal2).compareTo(Duration.of(value, unit)) >= 0` in the fallback.

### 2. Temporal-offset equality ignores the temporal unit

- **Severity:** low
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Failure:** `new TemporalUnitWithinOffset(1, ChronoUnit.DAYS).equals(new TemporalUnitWithinOffset(1, ChronoUnit.HOURS))` returns `true`, and the two instances have the same hash code, although they permit materially different time ranges.
- **Why this is wrong:** The constructor stores both `value` and `unit` as the offset's state (lines 33-49), and the public factories document `value` as the allowed offset and `unit` as its temporal unit (`Assertions.within`, lines 2275-2291). Equality compares only `value`; hash code likewise hashes only `value`. Consequently callers using these public data objects as map keys or comparing factory results cannot distinguish one hour from one day.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode` (for example, `Objects.hash(value, unit)`) while retaining the concrete-class check that distinguishes strict from inclusive offsets.

### 3. Large integral percentages are rendered as an unrelated integer

- **Severity:** low
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:61-66`
- **Failure:** `Percentage.withPercentage(2147483648d).toString()` returns `"2147483647%"`; `withPercentage(1.0e20).toString()` has the same result. Both values are accepted by the factory.
- **Why this is wrong:** The factory preserves a `double` percentage value (lines 38-44), but `toString` casts every fractional-free value to `int`. Java saturates a narrowing floating-point conversion above `Integer.MAX_VALUE`, so assertion diagnostics report a percentage that the caller did not supply.
- **Suggested fix:** Avoid the narrowing `int` cast. Format the original `double` (or use a representation that removes a trailing `.0` without changing magnitude).

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
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java` (relevant temporal factory sections)
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java` (relevant temporal factory tests)
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java` (relevant temporal factory tests)
