model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:15:36 UTC; finished 2026-09-28 23:18:58 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ `org.assertj.core.data` review

Reviewed commit `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada` in the requested package.

## Findings

### 1. Strict temporal offsets leak `ArithmeticException` for wide instant ranges

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Severity:** medium
- **What goes wrong:** A strict duration offset created with `byLessThan(Duration)` uses nanoseconds. For an assertion such as `assertThat(Instant.now()).isCloseTo(Instant.MIN, byLessThan(Duration.ofMillis(1)))`, `ChronoUnit.NANOS.between` cannot represent the span in a `long` and throws `ArithmeticException`. That exception escapes from `isBeyondOffset` instead of producing the documented failed close-to assertion.
- **Why this is wrong:** `AbstractTemporalAssert.isCloseTo` promises an `AssertionError` when values are not close (lines 75-77). The inclusive counterpart explicitly handles this exact overflow at `TemporalUnitWithinOffset.java:46-50` by comparing `Duration`s; `TemporalUnitOffset.getBeyondOffsetDifferenceDescription` also has an overflow fallback (lines 60-65), and its existing temporal assertion test covers the analogous `Instant.MIN` case. The strict counterpart at line 45 lacks the fallback.
- **Suggested fix:** Mirror `TemporalUnitWithinOffset.isBeyondOffset`: catch `ArithmeticException` around `getDifference` and compare `getAbsoluteDuration(temporal1, temporal2)` against `Duration.of(value, unit)`, using `>= 0` to preserve strict-offset semantics.

### 2. Temporal-offset equality discards the unit that defines the offset

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** medium
- **What goes wrong:** `within(1, ChronoUnit.DAYS)` compares equal to `within(1, ChronoUnit.HOURS)` (and has the same hash code), although the two offsets accept different temporal differences.
- **Why this is wrong:** The constructor stores both `value` and `unit` (lines 45-49), and `unit` is directly used for the comparison in `getDifference` (line 76) and in the diagnostic message (line 62). It is therefore part of the object’s observable value. Equality currently compares only `value`, violating the expected value-object meaning and making sets/maps collapse distinct offsets.
- **Suggested fix:** Include `unit` in both methods, for example `Objects.hash(value, unit)` and `value == other.value && Objects.equals(unit, other.unit)`.

### 3. Integral percentages above the `int` range are rendered as a different percentage

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`
- **Severity:** low
- **What goes wrong:** `Percentage.withPercentage(3_000_000_000d).toString()` returns `"2147483647%"`, even though its stored value is `3000000000d`. Any integral positive `double` outside the `int` range is similarly saturated or truncated in assertion failures.
- **Why this is wrong:** `withPercentage` accepts every non-negative `double` (lines 38-40), and `noFractionalPart()` deliberately takes this branch for integral values (lines 62 and 65-66). The `(int) value` conversion then loses the supplied value. `toString()` is the public rendering used in assertion diagnostics, so it must describe the actual percentage.
- **Suggested fix:** Avoid narrowing to `int`; render the original `double` after suppressing only the cosmetic `.0` (for example with `BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()` for finite values, with a separate non-finite path if desired).

## Validation performed

- Checked JDK behavior: `ChronoUnit.NANOS.between(Instant.now(), Instant.MIN)` throws `ArithmeticException: long overflow`, while `Duration.between(...).abs()` represents the span.
- Checked JDK narrowing behavior: `(int) 3_000_000_000d` is `2147483647`, and the value has no fractional component, so `Percentage.toString()` selects the narrowing branch.

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
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractDurationAssert.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
