model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:28:04 UTC; finished 2026-09-28 23:30:54 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ `core/data` review

## Findings

### 1. Strict temporal offsets leak `ArithmeticException` for distant instants

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Severity:** medium
- **What goes wrong:** A strict temporal assertion such as
  `assertThat(Instant.now()).isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.MILLIS))`
  throws `ArithmeticException: long overflow`, instead of failing the assertion as not close.
  `ChronoUnit.MILLIS.between` over that pair overflows; `getDifference` delegates directly to it.
- **Why this is wrong:** `AbstractTemporalAssert.isCloseTo` documents an `AssertionError` when the actual temporal is not close (lines 75-77), and the inclusive implementation explicitly catches this same `ArithmeticException` and compares absolute `Duration`s instead (`TemporalUnitWithinOffset:46-50`).  The strict implementation has the same overflowing call but no fallback.
- **Suggested fix:** Mirror `TemporalUnitWithinOffset.isBeyondOffset`: catch `ArithmeticException` and compare `getAbsoluteDuration(temporal1, temporal2)` with `Duration.of(value, unit)`, using `>= 0` for the exclusive boundary.

### 2. Temporal-offset equality omits the temporal unit

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** low
- **What goes wrong:** `new TemporalUnitWithinOffset(1, ChronoUnit.HOURS)` compares equal to
  `new TemporalUnitWithinOffset(1, ChronoUnit.DAYS)`, and the two objects have the same hash code.
  They represent different offsets and produce different `isBeyondOffset` results for the same temporals.
- **Why this is wrong:** The constructor stores both the offset `value` and its `unit` (lines 45-49), and the API describes `unit` as “the TemporalUnit of the offset” (`Assertions.within(long, TemporalUnit)`, lines 2284-2285).  Yet `equals` compares only `value`, and `hashCode` hashes only `value`.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode` (for example, `value == other.value && unit.equals(other.unit)` and `Objects.hash(value, unit)`).

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
- `assertj-core/src/main/java/org/assertj/core/api/WithAssertions.java`
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
