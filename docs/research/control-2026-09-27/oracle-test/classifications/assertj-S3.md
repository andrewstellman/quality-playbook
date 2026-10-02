# assertj, classifier S3 (Claude Sonnet), blind

### assertj-01
Oracle: The sibling class `Offset.java` (numeric offsets) implements `equals`/`hashCode` over all semantically relevant fields (`value` AND `strict`), but `TemporalUnitOffset.equals`/`hashCode` (lines 99-111) only compare `value` and ignore `unit`, so offsets in different units with the same numeric value collide. That in-repo parallel implementation is the oracle for what fields an offset's equality should be based on.
Type: in-repo
Confidence: high

### assertj-02
Oracle: `TemporalUnitOffset.isBeyondOffset`'s Javadoc and the documented "strict" semantics for `byLessThan` (e.g. `AbstractTemporalAssert.isCloseTo` Javadoc: `assertThat(8.1).isCloseTo(8.0, byLessThan(0.1)); // strict comparison!` — a diff equal to the bound fails) both establish that a strict less-than comparison rejects a diff equal to the offset value; with `value == 0` and identical temporals the diff is `0`, so `0 >= 0` correctly reports "beyond." This is the offset being unusable at its boundary (0 admits nothing), which is arguably by design of "strict," not a contradiction of any documented contract.
Type: in-repo
Confidence: low

### assertj-03
Oracle: `checkThatValueIsPositive` (TemporalUnitOffset.java:53) itself: `checkArgument(value >= 0, "The value of the offset should be greater than zero")` — the check permits `value == 0` while the message it throws on rejection claims values should be "greater than zero." The message and the guarded condition it belongs to directly contradict each other; that's a self-contained, in-repo inconsistency (no external doc needed).
Type: in-repo
Confidence: high

### assertj-04
Oracle: The sibling class `TemporalUnitWithinOffset.isBeyondOffset` (assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java:44-49) wraps the same `getDifference(...)` call in a `try/catch (ArithmeticException)` and falls back to a `Duration`-based comparison specifically to handle unit-overflow between far-apart temporals. `TemporalUnitLessThanOffset.isBeyondOffset` (line 45) calls the same `getDifference` without that fallback, so it throws where the parallel implementation was written to tolerate the same overflow. This is a directly comparable in-repo implementation gap.
Type: in-repo
Confidence: high

### assertj-05
Oracle: `Percentage.toString` (Percentage.java:62) does `noFractionalPart() ? "%s%%".formatted((int) value) : ...`; per the Java Language Specification, a narrowing `double`→`int` cast of any value ≥ `Integer.MAX_VALUE` clamps to `Integer.MAX_VALUE` (2147483647). Both `1e10` and `3e9` exceed that bound and clamp identically, so the collision is a direct, predictable consequence of a known language-level cast rule applied to an unbounded `double` field without a range check.
Type: known-external
Confidence: medium

The hardest to classify was assertj-02: the code path is internally consistent with the documented "strict" `byLessThan` semantics shown elsewhere in the Javadoc, so it reads more like an edge case of an intentional design (a strict bound of zero admits nothing) than a defect — but I couldn't find anywhere that explicitly discusses or tests the zero-offset boundary case, so I couldn't rule out that it's simply an overlooked edge case either. assertj-05 was the next hardest, since the "bug" is really the interaction of a very ordinary Java cast rule with an API that never validates an upper bound on `Percentage` — the oracle is solid (I know the JLS cast-clamping rule well) but whether it counts as a genuine defect versus an accepted (if surprising) consequence of allowing arbitrarily large percentages is a judgment call.
