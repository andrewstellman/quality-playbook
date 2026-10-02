model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:19:08 UTC; finished 2026-09-28 23:21:13 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data-package review — run 04

Reviewed commit `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`, limited to
`assertj-core/src/main/java/org/assertj/core/data/`.

## Findings

### 1. Strict temporal offsets leak an arithmetic overflow instead of producing an assertion result

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Severity:** medium
- **What goes wrong:** A strict temporal closeness assertion can throw `ArithmeticException` for valid `Temporal` inputs whose unit-level difference does not fit in a `long`. For example, comparing `Instant.MIN` and `Instant.MAX` with `byLessThan(1, ChronoUnit.NANOS)` calls `ChronoUnit.NANOS.between`, which throws `ArithmeticException: long overflow`. The assertion therefore escapes as an implementation exception rather than failing as an ordinary “not close” assertion.
- **Why this is wrong:** `TemporalUnitWithinOffset.isBeyondOffset` explicitly catches this exact exception and compares `Duration` values instead (lines 46–50). `AbstractTemporalAssert.isCloseTo` expects `isBeyondOffset` to return a boolean and creates its documented `AssertionError` when it returns true. The strict implementation uses the same overflow-prone `getDifference` but has no equivalent fallback.
- **Suggested fix:** Add the same `ArithmeticException` fallback to `TemporalUnitLessThanOffset.isBeyondOffset`, using `getAbsoluteDuration(...).compareTo(Duration.of(value, unit)) >= 0` so the strict boundary remains exclusive. Add coverage with the `Instant.MIN`/`Instant.MAX`, `ChronoUnit.NANOS` case.

### 2. Temporal offsets with different units compare equal

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** low
- **What goes wrong:** `new TemporalUnitWithinOffset(1, ChronoUnit.HOURS)` equals `new TemporalUnitWithinOffset(1, ChronoUnit.DAYS)` and they have the same hash code. A caller that stores offsets in a set or uses one as a map key loses the distinction between one hour and one day.
- **Why this is wrong:** The constructor stores both `value` and `unit` (lines 45–49), and `isBeyondOffset` calculates the difference through `unit.between` (line 76); the unit directly changes the offset’s behavior. Equality currently compares only `value` (line 110), despite the two objects representing different offsets.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode`, for example `return value == other.value && Objects.equals(unit, other.unit);` and `return Objects.hash(value, unit);`.

### 3. Integer percentage rendering corrupts values above the `int` range

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`
- **Severity:** low
- **What goes wrong:** An accepted whole-valued percentage greater than `Integer.MAX_VALUE` is rendered as `2147483647%`. For example, `withPercentage(2147483648d).toString()` takes the no-fraction branch, casts to `int`, and returns `2147483647%` instead of `2147483648%`.
- **Why this is wrong:** `withPercentage` accepts every non-negative `double` (lines 38–40), while `toString` is the value’s public representation. The cast in the integral-value branch silently saturates a valid stored value and produces a message that names a different percentage.
- **Suggested fix:** Format integral finite doubles without narrowing to `int` (for example, use `BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()` for the integral branch, with an explicit policy for non-finite values), then append `%`.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
