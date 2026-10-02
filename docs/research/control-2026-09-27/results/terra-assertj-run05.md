model: gpt-5.6-terra
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 23:21:22 UTC; finished 2026-09-28 23:23:49 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

Reviewed commit `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`, limited to
`assertj-core/src/main/java/org/assertj/core/data/`.

## Findings

### 1. Strict temporal offsets leak `ArithmeticException` for a representable, far-apart temporal pair

- **Severity:** medium
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45`
- **Failure:** `assertThat(Instant.parse("2017-03-12T07:10:00Z"))`
  `.isCloseTo(Instant.MIN, byLessThan(2, ChronoUnit.MILLIS))` throws an
  `ArithmeticException` while computing `ChronoUnit.MILLIS.between`, rather
  than failing the assertion as outside the strict two-millisecond offset.
- **Why this is wrong:** `AbstractTemporalAssert.isCloseTo` documents an
  `AssertionError` when the actual temporal is not close enough. The inclusive
  implementation explicitly handles this same overflow: its
  `TemporalUnitWithinOffset.isBeyondOffset` catches `ArithmeticException` and
  compares the absolute `Duration` instead. The strict implementation calls
  `getDifference` directly, so its public `byLessThan` form has a different,
  accidental failure mode for the same type of input.
- **Suggested fix:** mirror the inclusive implementation's `try/catch` in
  `TemporalUnitLessThanOffset.isBeyondOffset`, and in the catch compare
  `getAbsoluteDuration(temporal1, temporal2)` to `Duration.of(value, unit)`
  using `>= 0` for the strict boundary.

### 2. `Offset.offset` accepts negative `BigDecimal` values that underflow when converted to `double`

- **Severity:** medium
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60`
- **Failure:** `Offset.offset(new BigDecimal("-1e-1000"))` succeeds. Its
  `doubleValue()` is `-0.0`, and Java evaluates `-0.0 >= 0d` as true. The
  resulting negative offset can be passed through the public
  `Assertions.within(BigDecimal)` entry point and changes close-to behavior
  (every non-equal value is outside that negative tolerance).
- **Why this is wrong:** the factory's contract at lines 55--56 says a
  negative value must throw `IllegalArgumentException`; the public
  `Assertions.within(BigDecimal)` method carries the same contract. Checking
  only `Number.doubleValue()` loses the sign of nonzero values below the
  smallest double magnitude.
- **Suggested fix:** validate using the supplied number's exact comparison for
  supported number types (in particular, use `BigDecimal.signum()` and
  `BigInteger.signum()`), or replace the generic factory validation with
  type-specific factories so the comparison cannot narrow to `double`.

### 3. `TemporalUnitOffset.equals` treats offsets in different units as equal

- **Severity:** low
- **Location:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:100-110`
- **Failure:** `new TemporalUnitWithinOffset(1, ChronoUnit.SECONDS).equals(new
  TemporalUnitWithinOffset(1, ChronoUnit.MINUTES))` returns true and the two
  values have the same hash code, although one permits one second and the
  other permits one minute.
- **Why this is wrong:** `unit` is a final field that defines the offset's
  meaning and is used by `getDifference`; it is omitted from both `equals` and
  `hashCode`. Consequently, sets and maps collapse distinct offsets, and an
  equality assertion can claim that semantically different offset
  configurations are the same.
- **Suggested fix:** include `unit` in both `equals` and `hashCode` (for
  example, compare `unit` with `Objects.equals` and hash `value, unit`), while
  retaining the existing concrete-class check that distinguishes strict from
  inclusive offsets.

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
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_within_Test.java`
