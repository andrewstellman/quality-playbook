model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:15:21 UTC; finished 2026-09-28 23:17:44 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data-package review

Reviewed commit `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada` in `assertj-core/src/main/java/org/assertj/core/data/`.

## Findings

### 1. Strict temporal offsets leak `ArithmeticException` for valid, far-apart instants

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Severity:** medium
- **Failure:** `assertThat(Instant.now()).isCloseTo(Instant.MIN, byLessThan(1, ChronoUnit.MILLIS))` throws `ArithmeticException: long overflow` instead of failing the assertion. `ChronoUnit.MILLIS.between` cannot represent this distance in a `long`.
- **Why this is wrong:** `TemporalUnitOffset` already handles that exact overflow case when rendering a difference (lines 60–65), and the inclusive counterpart catches it in `isBeyondOffset` and compares absolute `Duration`s instead (lines 45–50 of `TemporalUnitWithinOffset`). The public `AbstractTemporalAssert.isCloseTo` contract says an out-of-range temporal should cause `AssertionError`; its call to this method therefore exposes an implementation overflow as an unrelated exception.
- **Suggested fix:** mirror the `try`/`catch` in `TemporalUnitWithinOffset.isBeyondOffset`. On `ArithmeticException`, compare `getAbsoluteDuration(temporal1, temporal2)` to `Duration.of(value, unit)` and use `>= 0` for the exclusive/less-than boundary.

### 2. Temporal offsets with different units compare equal

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** low
- **Failure:** `within(1, ChronoUnit.HOURS).equals(within(1, ChronoUnit.DAYS))` returns `true`, and their hash codes match. A `HashSet` or map keyed by offsets consequently conflates a one-hour tolerance with a one-day tolerance.
- **Why this is wrong:** `unit` is a final state field (line 34) and controls comparison semantics through `unit.between(...)` (line 76). The two objects therefore represent materially different offsets, but `equals` and `hashCode` use only `value`.
- **Suggested fix:** include `unit` in both methods, e.g. `Objects.hash(value, unit)` and `value == other.value && Objects.equals(unit, other.unit)` (while retaining the existing concrete-class check).

### 3. Whole-number percentages above the `int` range are rendered as the wrong value

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`
- **Severity:** low
- **Failure:** `Percentage.withPercentage(3_000_000_000d).toString()` returns `"2147483647%"`, although the stored percentage is `3000000000d`. Java’s narrowing conversion clamps the value to `Integer.MAX_VALUE`.
- **Why this is wrong:** the factory accepts every non-negative `double` (lines 38–40), and `toString` is used to communicate the percentage value. For a whole-valued input above the `int` range, `noFractionalPart()` selects the lossy `(int) value` branch.
- **Suggested fix:** avoid the narrowing cast. Render whole doubles with a representation that preserves the magnitude, such as `BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()`, then append `%`.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/main/java/org/assertj/core/presentation/StandardRepresentation.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
