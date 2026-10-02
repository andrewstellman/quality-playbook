# assertj, classifier S2 (Claude Sonnet), blind

### assertj-01
Oracle: `TemporalUnitOffset.equals`/`hashCode` (TemporalUnitOffset.java:99-111) only consider the `value` field and ignore `unit`, even though `unit` is treated as significant state everywhere else in the class (`getUnit()`, `getDifference()`, `getBeyondOffsetDifferenceDescription()`, and the very different `isBeyondOffset` semantics per subclass). Compare with the sibling class `Percentage` (data/Percentage.java:47-58), whose `equals`/`hashCode` cover its full state and which has a dedicated `EqualsVerifier` contract test (`Percentage_Test.java:37-43`) — no analogous equals-contract test exists for `TemporalUnitOffset`, so there's nothing in-repo asserting the current (incomplete) behavior is intentional.
Type: in-repo
Confidence: medium

### assertj-02
Oracle: `isBeyondOffset` for `TemporalUnitLessThanOffset` (line 45, `getDifference(...) >= value`) with `value == 0` is always true because a difference can never be negative, so `byLessThan(0, unit)` can never pass even for identical instants. This is a direct consequence of the `value >= 0` check at `TemporalUnitOffset.java:53` (see assertj-03) admitting 0. Whether "always-false/never-satisfiable" counts as a defect versus a logically-consistent (if useless) edge case isn't stated anywhere in the code or docs.
Type: in-repo
Confidence: low

### assertj-03
Oracle: `TemporalUnitOffset.java:53` — `checkArgument(value >= 0, "The value of the offset should be greater than zero")`. The message text ("greater than zero") directly contradicts the condition it guards (`>= 0`, which accepts zero). This is a self-contained inconsistency inside a single line, not an inference from usage elsewhere.
Type: in-repo
Confidence: high

### assertj-04
Oracle: `TemporalUnitWithinOffset.isBeyondOffset` (TemporalUnitWithinOffset.java:45-51) explicitly catches `ArithmeticException` from `getDifference` and falls back to a `Duration`-based comparison — and `AbstractTemporalAssert_isCloseTo_Test.java` (parameters index 1: MILLIS offset between now and `Instant.MIN`, expected message `"...difference was PT8765837682367H10M"`) is an existing project test that specifically exercises this overflow path for `within()`. `TemporalUnitLessThanOffset.isBeyondOffset` (line 45) is the parallel implementation for `byLessThan()` and has no such catch, so the same overflow scenario throws instead of degrading gracefully.
Type: in-repo
Confidence: high

### assertj-05
Oracle: `Percentage.toString()` (Percentage.java:62) casts to `(int) value` whenever `noFractionalPart()` is true, so any integral double beyond `Integer.MAX_VALUE` overflows to `2147483647`, making distinct values print identically. This contradicts the class's own `equals`/`hashCode` (lines 47-58), which compare the full `double` and are verified by `EqualsVerifier` in `Percentage_Test.java:37-43` to treat such values as distinct — an internal inconsistency between identity and display within the same class. The existing test `toString_should_display_fractional_part_when_present` (`Percentage_Test.java:64-79`) further establishes that `toString()` is meant to reflect the actual stored value (minus the decimal point when integral), not a truncated one.
Type: in-repo
Confidence: high

Hardest to classify: assertj-02. It follows mechanically from the same `value >= 0` check as assertj-03, but on its own the "always-false assertion" outcome is mathematically self-consistent (a difference, which is always ≥ 0, can never be strictly less than 0), so nothing in the repo states that construction with `value == 0` was meant to be rejected or that a permanently-failing assertion is wrong — it's arguably a usability wart riding on assertj-03's contradiction rather than an independent defect. assertj-01 was also non-trivial: the omission of `unit` from `equals`/`hashCode` is visibly inconsistent with how the field is used elsewhere in the class, but without an equals-contract test (unlike `Percentage`) there's no in-repo statement of intended behavior to weigh it against, only inference from the class's own design pattern.
