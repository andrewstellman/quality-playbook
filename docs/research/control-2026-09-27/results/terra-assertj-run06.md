model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:21:43 UTC; finished 2026-09-28 23:24:12 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ `org.assertj.core.data` review

## Findings

### 1. Strict temporal offsets accept zero, making every assertion fail

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:52-54` (used by `TemporalUnitLessThanOffset`)
- **Severity:** medium
- **What goes wrong:** `Assertions.byLessThan(0, ChronoUnit.SECONDS)` and `Assertions.byLessThan(Duration.ZERO)` construct a `TemporalUnitLessThanOffset` successfully. Its `isBeyondOffset` method then evaluates `difference >= 0`, which is true even when the two temporals are identical. Thus an assertion such as `assertThat(Instant.now()).isCloseTo(theSameInstant, byLessThan(0, SECONDS))` always fails.
- **Why this is wrong:** A strict offset represents the predicate `|actual - expected| < offset` (the class is documented as a “strict less than condition”). No non-negative temporal difference satisfies that predicate when the offset is zero. The corresponding numeric factory, `Offset.strictOffset`, explicitly rejects zero at `Offset.java:81-84`, so the temporal `byLessThan` factories behave inconsistently with the same strict-offset API.
- **Suggested fix:** Require `value > 0` for `TemporalUnitLessThanOffset` (for example, add a protected validation hook in `TemporalUnitOffset`, or validate in the strict subclass before construction). Keep zero valid for `TemporalUnitWithinOffset`.

### 2. Strict temporal comparisons overflow instead of reporting a failed assertion

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:44-46`
- **Severity:** medium
- **What goes wrong:** For temporal values whose difference cannot be represented in the requested unit, `getDifference` calls `TemporalUnit.between`, which can throw `ArithmeticException`. For example, comparing an ordinary `Instant` with `Instant.MIN` using `byLessThan(2, ChronoUnit.MILLIS)` overflows the millisecond count. `TemporalUnitLessThanOffset.isBeyondOffset` lets that exception escape, so `isCloseTo` throws `ArithmeticException` instead of its documented `AssertionError` for a temporal outside the offset.
- **Why this is wrong:** `TemporalUnitWithinOffset.isBeyondOffset` handles precisely this situation at `TemporalUnitWithinOffset.java:46-50`: it catches the overflow and compares `Duration` values, allowing the assertion machinery in `AbstractTemporalAssert.isCloseTo` to produce the expected failure. The strict variant has the same distance-calculation problem but omits the fallback.
- **Suggested fix:** Give `TemporalUnitLessThanOffset.isBeyondOffset` the same `ArithmeticException` fallback, using `getAbsoluteDuration(...).compareTo(Duration.of(value, unit)) >= 0` to preserve strict (`<`) semantics.

### 3. Temporal offsets with different units compare equal

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-111`
- **Severity:** low
- **What goes wrong:** `new TemporalUnitWithinOffset(1, ChronoUnit.DAYS)` equals `new TemporalUnitWithinOffset(1, ChronoUnit.HOURS)`, and both have the same hash code. These offsets represent different tolerances and produce different assertion results, so they collapse into one element in a `HashSet` or one key in a `HashMap`.
- **Why this is wrong:** The class stores both `value` and `unit` as the offset state (`TemporalUnitOffset.java:33-36`), and `getDifference` applies the stored unit (`line 76`). Equality currently compares and hashes only `value`, despite the unit changing the object's meaning.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode`, e.g. `Objects.hash(value, unit)` and `value == other.value && Objects.equals(unit, other.unit)`.

### 4. Large integral percentages are rendered as the wrong value

- **File / line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:60-67`
- **Severity:** low
- **What goes wrong:** `Percentage.withPercentage(2147483648d).toString()` returns `"2147483647%"`. Any accepted integral double greater than `Integer.MAX_VALUE` is narrowed at line 62; Java clamps an out-of-range double-to-`int` conversion to `Integer.MAX_VALUE`. Assertion messages therefore display a percentage that differs from the value used by the assertion.
- **Why this is wrong:** `withPercentage` accepts every non-negative `double` (`Percentage.java:38-40`) and the public `value` retains the supplied number, but `toString` is expected to represent that percentage. The cast only exists to remove the unnecessary `.0` for ordinary integral values and is not range-safe.
- **Suggested fix:** Format integral doubles without narrowing to `int`, such as `"%.0f%%".formatted(value)` for finite integral values, and retain the existing general-double formatting for fractional values.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/api/WithAssertions.java`
- `assertj-core/src/main/java/org/assertj/core/util/Preconditions.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
