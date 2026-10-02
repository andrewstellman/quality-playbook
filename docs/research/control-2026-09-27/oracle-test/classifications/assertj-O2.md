# assertj, classifier O2 (Claude Opus), blind

### assertj-01
Oracle: The sibling class `Offset.equals` (assertj-core/src/main/java/org/assertj/core/data/Offset.java:93-103) compares every field that changes behaviour (`strict == other.strict && Objects.equals(value, other.value)`, with `hash(value, strict)`). `TemporalUnitOffset` leaves out `unit`, even though `unit` decides what the offset means. `getUnit()` exposes it, and `isBeyondOffset` depends on it. As a result, `within(1, SECONDS)` and `within(1, HOURS)` are treated as equal. equals and hashCode still agree with each other, so the Object contract itself is not broken. The problem is equality that ignores a field that matters.
Type: in-repo
Confidence: high

### assertj-02
Oracle: The strict numeric sibling `Offset.strictOffset` (Offset.java:83) rejects zero with `checkArgument(value.doubleValue() > 0d, "A strict offset value should be greater than zero")`. The strict temporal offset `TemporalUnitLessThanOffset` has no such guard, so `byLessThan(0, unit)` builds an offset that no pair of values can ever satisfy, including identical ones. The class javadoc ("strict less than condition") and `isBeyondOffset` (`>= value`) show that a difference of 0 is never less than 0.
Type: in-repo
Confidence: high

### assertj-03
Oracle: The code does what its javadoc says (TemporalUnitOffset.java:43, "@throws IllegalArgumentException if the given value is negative"), so accepting 0 is intended. What's wrong is the message: "should be greater than zero" contradicts the `value >= 0` check. The parallel `Offset.offset` (Offset.java:60) gets it right: "An offset value should be greater than or equal to zero". So this is a wrong error message, not wrong logic.
Type: in-repo
Confidence: medium

### assertj-04
Oracle: The sibling `TemporalUnitWithinOffset.isBeyondOffset` (TemporalUnitWithinOffset.java:46-50) catches `ArithmeticException` and falls back to comparing `Duration`s. The shared base method `getBeyondOffsetDifferenceDescription` (TemporalUnitOffset.java:61-65) also handles overflow. The existing test AbstractTemporalAssert_isCloseTo_Test.java:122/135 checks `within(2, MILLIS)` against `Instant.MIN` and expects a normal failure message. `TemporalUnitLessThanOffset` has no such fallback, so the same input throws an uncaught exception. This is also an implicit oracle (uncaught exception). `byLessThan(Duration)` always converts to NANOS (Assertions.java:2498), which makes the overflow easier to hit.
Type: in-repo
Confidence: high

### assertj-05
Oracle: `toString` casts to `(int) value` whenever the value has no fractional part (Percentage.java:62). Java's narrowing conversion from double to int clamps to `Integer.MAX_VALUE` (JLS §5.1.3), so a value like `1e10` is shown as 2147483647. `withPercentage` sets no upper bound (only `value >= 0`, line 39), and the non-integral branch prints the real `value`. So the integral branch misreports values it accepts. The existing `toString` test (Percentage_Test.java:65-71) only covers small values. The impact is limited to how `toString` and failure messages display the value.
Type: known-external
Confidence: medium

Hardest to classify: assertj-03 and assertj-05. For 03, the finding describes two things. Accepting 0 matches the javadoc, so that part is not a defect. Only the message wording is wrong, which I can show from the `Offset` sibling but which matters little. For 05, the oracle is the JLS rule for casting double to int plus the fact that the class allows large values. Nothing in the repo says what the string should look like for huge integral values, and it only affects display. I chose `known-external` rather than `in-repo`, but either could be argued. 01, 02 and 04 were easy because the same package has a parallel class (`Offset`, `TemporalUnitWithinOffset`) that handles the exact case correctly.
