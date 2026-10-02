# assertj, classifier S1 (Claude Sonnet), blind

### assertj-01
Oracle: `TemporalUnitOffset` stores `unit` as a field (`protected final TemporalUnit unit`, line 34) and exposes it via `getUnit()`, but `equals`/`hashCode` (lines 99-111) only consider `value`, so two offsets with the same numeric value but different units compare equal despite representing different constraints.
Type: in-repo
Confidence: high

### assertj-02
Oracle: This is a downstream symptom of assertj-03: `checkThatValueIsPositive` (TemporalUnitOffset.java:53) should reject `0` per its own name and message but doesn't, so `TemporalUnitLessThanOffset`'s documented "less than" semantics (isBeyondOffset returns true when difference `>= value`) get applied to a value that should never have been constructible.
Type: in-repo
Confidence: medium

### assertj-03
Oracle: The guard is named `checkThatValueIsPositive` and its message says "The value of the offset should be greater than zero," but the check is `checkArgument(value >= 0, ...)`, which admits zero. Contrast with the sibling `Offset.offset()` (Offset.java, non-strict factory), which pairs the correct message ("should be greater than or equal to zero") with the same `>= 0` check — showing the repo's own convention for how message and comparison should match.
Type: in-repo
Confidence: high

### assertj-04
Oracle: The sibling class `TemporalUnitWithinOffset.isBeyondOffset` handles exactly this overflow case with a `try { getDifference(...) > value } catch (ArithmeticException e) { Duration-based fallback }`, and `TemporalUnitOffset.getBeyondOffsetDifferenceDescription` also already anticipates `ArithmeticException` from `getDifference`. `TemporalUnitLessThanOffset.isBeyondOffset` (line 45) has no such try/catch, so it throws instead of falling back like its sibling.
Type: in-repo
Confidence: high

### assertj-05
Oracle: `Percentage_Test.java`'s `toString_should_display_fractional_part_when_present` establishes that `toString()` must faithfully render the stored `double value`. The implementation's `(int) value` cast (Percentage.java:62) saturates at `Integer.MAX_VALUE` for any value beyond the int range, so distinct large values (`1e10`, `3e9`) both silently collapse to `"2147483647%"`, contradicting the field's actual stored value.
Type: in-repo
Confidence: high

Hardest to classify: assertj-02, because its "wrongness" is not really its own — `isBeyondOffset`'s `>=` comparison is doing exactly what its javadoc says for whatever value it's given. The real defect is assertj-03 (the constructor should never have accepted `0`), and assertj-02 is just the visible consequence, so pinning an independent oracle on assertj-02 as though it were a distinct bug felt like double-counting the same root cause.
