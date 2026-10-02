model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:24:31 UTC; finished 2026-09-28 23:27:43 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ `core/data` review

## Findings

### 1. Strict temporal offsets throw instead of producing an assertion failure when `TemporalUnit.between` overflows

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Severity:** medium
- **What goes wrong:** A strict temporal assertion such as `assertThat(Instant.parse("2017-03-12T07:10:00Z")).isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.MILLIS))` throws `ArithmeticException: long overflow`. `ChronoUnit.MILLIS.between` cannot represent that interval in a `long`.
- **Why this is wrong:** `TemporalUnitWithinOffset.isBeyondOffset` catches exactly this `ArithmeticException` and compares the `Duration` instead (lines 46-50), so its corresponding inclusive assertion reports the expected `AssertionError`. The strict variant performs the same difference calculation at line 45 but has no fallback. The public `isCloseTo` contract says that a temporal outside the supplied offset raises an `AssertionError`; it should not expose the unit-overflow implementation detail.
- **Suggested fix:** Mirror the inclusive implementation: catch `ArithmeticException` in `isBeyondOffset` and return `getAbsoluteDuration(temporal1, temporal2).compareTo(Duration.of(value, unit)) >= 0` for the strict boundary.

### 2. Offset validation accepts negative `BigDecimal` values that underflow during conversion

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60`
- **Severity:** low
- **What goes wrong:** `Offset.offset(new BigDecimal("-1e-1000"))` succeeds. That negative decimal's `doubleValue()` is `-0.0`, and Java considers `-0.0 >= 0d` true.
- **Why this is wrong:** The factory's documentation explicitly promises `IllegalArgumentException` for a negative offset (lines 55-56). The stored value remains negative, so validation has accepted a value outside the type's stated invariant and subsequent comparisons use a negative tolerance.
- **Suggested fix:** Validate without lossy `doubleValue()` conversion for supported numeric types, for example branch for `BigDecimal` and use `signum()`/`compareTo(BigDecimal.ZERO)`. Any generic fallback should avoid treating a negative underflow result as zero.

### 3. Temporal offsets with different units compare equal

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** low
- **What goes wrong:** `new TemporalUnitWithinOffset(1, ChronoUnit.HOURS).equals(new TemporalUnitWithinOffset(1, ChronoUnit.DAYS))` returns `true`, with the same hash code. The two offsets produce different results for the same temporal pair.
- **Why this is wrong:** `unit` is a final part of the offset's state (lines 34 and 49) and is used by `getDifference` to define the assertion's behavior (line 76). Ignoring it makes semantically distinct values collapse in sets, maps, and equality-based checks.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode` (while retaining the existing exact-class check so inclusive and strict offsets remain distinct).

### 4. Large integral percentages are rendered as `Integer.MAX_VALUE`

- **File/line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62`
- **Severity:** low
- **What goes wrong:** `Percentage.withPercentage(3_000_000_000d).toString()` returns `"2147483647%"` instead of representing the supplied percentage. Every finite integral `double` above `Integer.MAX_VALUE` follows the same path.
- **Why this is wrong:** `noFractionalPart()` is true and the code narrows the `double` to `int`; Java's narrowing conversion saturates this input at `Integer.MAX_VALUE`. `Percentage` is passed directly into failure-message factories (for example `ShouldBeEqualWithinPercentage`), so failed assertions report a tolerance different from the one the caller supplied.
- **Suggested fix:** Only use the integer formatting path when the value is in the `int` range, or format integral doubles without narrowing them to `int`.

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
- `assertj-core/src/main/java/org/assertj/core/error/ShouldBeEqualWithinPercentage.java`
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
