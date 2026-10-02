model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:51:20 UTC; finished 2026-09-28 22:53:26 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran standalone Java probe
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# AssertJ data package review

## Findings

1. **Medium — Negative `BigDecimal` offsets can pass validation.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:60` validates a generic `Number` by converting it to `double`. For `Offset.offset(new BigDecimal("-1e-400"))`, that conversion is `-0.0`, and `-0.0 >= 0d` is true, so a negative offset is accepted. The method contract at lines 55–56 says negative values throw `IllegalArgumentException`; the class also describes offsets as positive. Compare `BigDecimal` and `BigInteger` using their own exact sign operations (and handle the other supported `Number` types without a lossy conversion).

2. **Medium — Valid tiny strict offsets are rejected.** `assertj-core/src/main/java/org/assertj/core/data/Offset.java:83` has the same lossy conversion: `Offset.strictOffset(new BigDecimal("1e-400"))` converts the positive value to `0.0`, so the `> 0d` check rejects it. The method contract at lines 65 and 79 excludes zero and negative values, but this value is positive. Use exact sign checks for arbitrary-precision number types.

3. **Medium — Strict temporal closeness can throw an arithmetic exception for distant instants.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45` calls `getDifference`, whose `unit.between` can overflow for nanoseconds. For example, comparing `Instant.EPOCH` and `Instant.parse("2300-01-01T00:00:00Z")` with `byLessThan(1, ChronoUnit.NANOS)` throws `ArithmeticException` instead of making `isCloseTo` fail with `AssertionError`. `TemporalUnitWithinOffset.isBeyondOffset` at lines 46–50 explicitly catches this case and compares absolute `Duration`s, while `AbstractTemporalAssert.isCloseTo` relies on `isBeyondOffset` to decide whether to raise the assertion failure. Give the strict class the same overflow fallback, using `>=` for the exclusive boundary.

4. **Low — Temporal offsets with different units compare equal.** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-110` includes only `value` in `hashCode` and `equals`. Thus `new TemporalUnitWithinOffset(1, ChronoUnit.SECONDS).equals(new TemporalUnitWithinOffset(1, ChronoUnit.DAYS))` returns true, although they produce different `isBeyondOffset` results for the same temporals. The constructor and class documentation define an offset using both a value and a temporal unit, and `getUnit()` exposes that unit. Include `unit` in both methods.

5. **Low — Large whole percentages render as the wrong value.** `assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62` casts every whole `double` percentage to `int` for formatting. `Percentage.withPercentage(2147483648.0).toString()` returns `"2147483647%"` because the narrowing cast saturates at `Integer.MAX_VALUE`. The field and factory accept any nonnegative `double`; `toString` should represent the stored percentage. Format the whole `double` without narrowing to `int` (or only cast when it is in range).

## Verification

A standalone Java probe in the scratch directory confirmed the two `BigDecimal.doubleValue()` results, the narrowing conversion for the percentage, and `ChronoUnit.NANOS.between` throwing `ArithmeticException` for the specified instants. The checkout was not modified.

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
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java`
- `assertj-core/src/test/java/org/assertj/core/api/EntryPointAssertions_byLessThan_Test.java`
