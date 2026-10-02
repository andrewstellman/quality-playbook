# Findings: assertj

Checkout: /tmp/control/assertj at 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada. Paths are relative to it.

| ID | Location | Observed behaviour |
|---|---|---|
| assertj-01 | assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:99-111 (hashCode / equals) | `new TemporalUnitWithinOffset(1, SECONDS).equals(new TemporalUnitWithinOffset(1, HOURS))` returns `true`, and the two have the same `hashCode`. |
| assertj-02 | assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:33-45 (constructor / isBeyondOffset) | `new TemporalUnitLessThanOffset(0, unit)` constructs successfully, and its `isBeyondOffset(now, now)` returns `true`, so `isCloseTo(x, x, byLessThan(0, unit))` fails for identical values. |
| assertj-03 | assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java:53 (checkThatValueIsPositive) | A value of `0` is accepted, and a negative value is rejected with the message "The value of the offset should be greater than zero". |
| assertj-04 | assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java:45 (isBeyondOffset) | When the difference between the two temporals in the offset's unit overflows a `long` (e.g. NANOS between `Instant.MIN` and `Instant.MAX`, or MILLIS between now and `Instant.MIN`), `isBeyondOffset` throws `ArithmeticException: long overflow`, so `isCloseTo(..., byLessThan(n, unit))` throws that exception. |
| assertj-05 | assertj-core/src/main/java/org/assertj/core/data/Percentage.java:62 (toString) | `withPercentage(1e10).toString()` and `withPercentage(3e9).toString()` both return `"2147483647%"`. |
