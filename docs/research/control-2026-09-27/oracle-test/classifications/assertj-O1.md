# assertj, classifier O1 (Claude Opus), blind

### assertj-01
Oracle: The sibling `Offset.equals`/`hashCode` (assertj-core/src/main/java/org/assertj/core/data/Offset.java:93-103) compares every field that changes behaviour (`strict` and `value`). `TemporalUnitOffset` compares only `value` and leaves out `unit` (TemporalUnitOffset.java:99-111), yet `unit` is protected state that `getDifference` uses (line 76). So two offsets that are "equal" give different `isBeyondOffset` results. The general `Object.equals` contract (known-external) points the same way.
Type: in-repo
Confidence: high

### assertj-02
Oracle: The numeric strict-offset sibling `Offset.strictOffset` (Offset.java:81-84) rejects 0 with `checkArgument(value.doubleValue() > 0d, "A strict offset value should be greater than zero")`. The temporal strict offset accepts 0 through the shared `>= 0` check (TemporalUnitOffset.java:53) and then produces an offset that can never pass (`>= 0` at TemporalUnitLessThanOffset.java:45). It should be rejected the same way.
Type: in-repo
Confidence: high

### assertj-03
Oracle: The check is `value >= 0` and the constructor Javadoc says "@throws IllegalArgumentException if the given value is negative" (TemporalUnitOffset.java:43), so accepting 0 is intended. The error message "should be greater than zero" is what's wrong. The sibling `Offset.offset` uses the accurate wording "An offset value should be greater than or equal to zero" (Offset.java:60), and `Percentage.withPercentage` does the same (Percentage.java:39).
Type: in-repo
Confidence: high (that the message is wrong; it's a small defect)

### assertj-04
Oracle: The parallel class `TemporalUnitWithinOffset.isBeyondOffset` (TemporalUnitWithinOffset.java:46-50) catches `ArithmeticException` and falls back to comparing `Duration`s. The shared `getBeyondOffsetDifferenceDescription` (TemporalUnitOffset.java:61-65) handles the same overflow, and `AbstractTemporalAssert_isCloseTo_Test` tests `Instant.MIN` with `within`. `TemporalUnitLessThanOffset` has no such guard. The `isCloseTo` Javadoc (AbstractTemporalAssert.java:75-77) documents only NPE and AssertionError. The bug also counts as `implicit`, since it's an uncaught exception.
Type: in-repo
Confidence: high

### assertj-05
Oracle: `toString` narrows with `(int) value` (Percentage.java:62). Under Java's double-to-int narrowing rule (JLS §5.1.3, known-external), any value above `Integer.MAX_VALUE` is clamped to 2147483647. So the string no longer shows the stored `value`, and failure messages would report the wrong percentage. In the repo, `Percentage_Test.toString_should_display_fractional_part_when_present` (assertj-tests/.../data/Percentage_Test.java) shows `toString` is meant to print the value, minus a fractional part of zero. Its test cases only go up to 10, though.
Type: in-repo
Confidence: medium

The hardest to classify was assertj-05. What makes the output wrong is Java's narrowing rule, but my evidence that `toString` should print the true value is only the test pattern and the fact that the string goes into failure messages. Percentages of 3e9 are also an unrealistic input, so I rated confidence medium. assertj-04 fit two types: it is an uncaught exception (`implicit`), but I chose `in-repo` because the sibling class shows the exact intended fallback. For assertj-03, I had to decide which part is the defect. The docstring and the check agree that 0 is allowed, so the only fault is the message text. The finding's wording could be read as saying that rejecting 0 was expected, and I don't think that reading holds.
