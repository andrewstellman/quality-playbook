model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:17:59 UTC; finished 2026-09-28 23:21:29 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data-package review

## Defects

### 1. Negative `BigDecimal` offsets can pass the non-strict factory validation

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60`
- **Severity:** low
- **What goes wrong:** `Offset.offset(new BigDecimal("-1E-1000"))` returns an offset even though the supplied `BigDecimal` is negative.  Its conversion to `double` underflows to `-0.0`, and Java considers `-0.0 >= 0d` true.
- **Why it is wrong:** The factory's Javadoc at lines 55-56 promises `IllegalArgumentException` for a negative value.  The returned negative offset is then used directly by numeric assertions (`Numbers.assertIsCloseTo`, lines 210-211), rather than being rejected at the public API boundary.
- **Suggested fix:** Validate with a type-preserving sign test for the supported numeric types (in particular, use `BigDecimal.signum()` and `BigInteger.signum()`), or constrain the factory to numeric types that can be validated correctly.  Do not use a lossy `doubleValue()` conversion as the sole sign check.

### 2. Temporal offsets with different units compare equal

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Severity:** medium
- **What goes wrong:** `within(1, ChronoUnit.HOURS).equals(within(1, ChronoUnit.DAYS))` returns true, and the two values have the same hash code.  The offsets represent different tolerance windows, so a `HashSet`, `HashMap`, cache, or equality-based test collapses them incorrectly.
- **Why it is wrong:** `TemporalUnitOffset` stores both `value` and `unit` (lines 35-36), and the class describes itself as an offset "for a given temporal unit" (lines 39-41).  However, `equals` and `hashCode` use only `value`.
- **Suggested fix:** Include `unit` in both `equals` and `hashCode`, while retaining the existing exact-class check so inclusive and exclusive offsets remain distinct.

### 3. Strict temporal offsets leak `ArithmeticException` for valid large `Instant` comparisons

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:44-45`
- **Severity:** medium
- **What goes wrong:** A strict assertion such as `assertThat(Instant.parse("2017-03-12T07:10:00Z")).isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.NANOS))` throws `ArithmeticException: long overflow`.  `ChronoUnit.NANOS.between` cannot represent that gap as a `long`.
- **Why it is wrong:** `AbstractTemporalAssert.isCloseTo` documents an `AssertionError` when the temporal values are not close, but the strict implementation lets `getDifference` escape.  The inclusive counterpart explicitly catches that overflow and compares `Duration` values instead (`TemporalUnitWithinOffset.java:46-50`); the existing temporal assertion test also exercises the corresponding overflow path for `within(2, MILLIS)` with `Instant.MIN`.
- **Suggested fix:** Give `TemporalUnitLessThanOffset.isBeyondOffset` the same `ArithmeticException` fallback as `TemporalUnitWithinOffset`, using `getAbsoluteDuration(...).compareTo(Duration.of(value, unit)) >= 0` for its exclusive boundary.

### 4. Large whole-number percentages are rendered as `Integer.MAX_VALUE%`

- **File and line:** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:61-66`
- **Severity:** low
- **What goes wrong:** `withPercentage(3_000_000_000d).toString()` returns `2147483647%`.  The value has no fractional part, so the method narrows it to `int`; Java's narrowing conversion saturates out-of-range floating-point values at `Integer.MAX_VALUE`.
- **Why it is wrong:** The factory accepts every nonnegative `double` (lines 38-40), and percentage instances are interpolated into assertion failure messages (for example, `ShouldBeEqualWithinPercentage`).  Those messages therefore report a tolerance different from the one the assertion received.
- **Suggested fix:** Only use the integer formatting branch when the value fits in `int`, or format the `double` without narrowing (removing a trailing `.0` if desired).

### 5. `Duration` overloads reject valid durations above the nanosecond `long` range

- **File and line:** `assertj-core/src/main/java/org/assertj/core/api/Assertions.java:2272,2498`
- **Severity:** medium
- **What goes wrong:** `within(Duration.ofDays(107_000))` and `byLessThan(Duration.ofDays(107_000))` throw `ArithmeticException: long overflow` from `Duration.toNanos()`.  Such durations are valid `Duration` instances; the overflow threshold is only about 292 years.
- **Why it is wrong:** Both overloads document that they accept a `Duration` as the temporal offset and declare no range restriction or arithmetic exception.  Converting the entire duration to a `long` nanosecond count needlessly narrows the input domain.
- **Suggested fix:** Represent the `Duration` directly in a dedicated `TemporalOffset` implementation and compare it with `Duration.between`, or preserve seconds and nanos without requiring a single nanosecond `long` value.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java`
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java`
- `assertj-core/src/main/java/org/assertj/core/internal/BigDecimals.java`
- `assertj-core/src/main/java/org/assertj/core/util/Preconditions.java`
- `assertj-core/src/main/java/org/assertj/core/error/ShouldBeEqualWithinPercentage.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
