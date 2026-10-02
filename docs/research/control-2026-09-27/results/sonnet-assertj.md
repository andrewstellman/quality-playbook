# Code review: assertj-core `org.assertj.core.data`

Repo: assertj (https://github.com/assertj/assertj), pinned commit `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`
Scope: `assertj-core/src/main/java/org/assertj/core/data/`

## Defect 1 — `TemporalUnitLessThanOffset.isBeyondOffset` does not guard against the `ArithmeticException` its sibling class handles

**File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`, lines 43–46

```java
@Override
public boolean isBeyondOffset(Temporal temporal1, Temporal temporal2) {
  return getDifference(temporal1, temporal2) >= value;
}
```

`getDifference` (defined in the parent `TemporalUnitOffset`, lines 75–77) is:

```java
protected long getDifference(Temporal temporal1, Temporal temporal2) {
  return abs(unit.between(temporal1, temporal2));
}
```

`TemporalUnit.between(...)` can throw `ArithmeticException` on numeric overflow (e.g. computing `ChronoUnit.NANOS.between(Instant.MIN, Instant.MAX)`, or any sufficiently wide temporal range in a fine-grained unit). The sibling class `TemporalUnitWithinOffset.isBeyondOffset` (lines 44–51) explicitly anticipates and handles this:

```java
@Override
public boolean isBeyondOffset(Temporal temporal1, Temporal temporal2) {
  try {
    return getDifference(temporal1, temporal2) > value;
  } catch (@SuppressWarnings("unused") ArithmeticException e) {
    return getAbsoluteDuration(temporal1, temporal2).compareTo(Duration.of(value, unit)) > 0;
  }
}
```

`TemporalUnitOffset.getBeyondOffsetDifferenceDescription` (the shared base, lines 60–66) also has the identical fallback for building the failure message. So the codebase clearly establishes the intended behavior: overflow from `unit.between()` should be caught and the comparison redone via `Duration`. `TemporalUnitLessThanOffset.isBeyondOffset` is the only one of the three overflow-sensitive methods that omits this handling.

**What goes wrong:** when a user asserts `isCloseTo(actual, expected, byLessThan(n, unit))` (which constructs a `TemporalUnitLessThanOffset`) and the two temporal values are far enough apart that `unit.between(...)` overflows a `long` (verified below with `ChronoUnit.NANOS` between `Instant.MIN` and `Instant.MAX`), the assertion throws an uncaught `ArithmeticException: long overflow` instead of returning a normal (true) "beyond offset"/assertion-failure result the way the equivalent `isCloseTo(..., within(n, unit))` assertion does for the same inputs.

**Verified with a standalone repro** (compiled the three classes directly with `javac`/`java`, JDK 25):

```
within.isBeyondOffset(Instant.MIN, Instant.MAX)   -> succeeded, result=true
lessThan.isBeyondOffset(Instant.MIN, Instant.MAX) -> threw ArithmeticException: long overflow
```

**Severity:** medium. It's an inconsistency between two assertion variants that are documented and expected to behave analogously (`isCloseTo(..., within(...))` vs. `isCloseTo(..., byLessThan(...))`), and it surfaces as an uncaught runtime exception rather than a clean assertion pass/fail for legitimate (if extreme) temporal inputs.

**Suggested fix:** wrap `TemporalUnitLessThanOffset.isBeyondOffset` the same way as `TemporalUnitWithinOffset.isBeyondOffset`:

```java
@Override
public boolean isBeyondOffset(Temporal temporal1, Temporal temporal2) {
  try {
    return getDifference(temporal1, temporal2) >= value;
  } catch (@SuppressWarnings("unused") ArithmeticException e) {
    return getAbsoluteDuration(temporal1, temporal2).compareTo(Duration.of(value, unit)) >= 0;
  }
}
```

---

## Defect 2 — `TemporalUnitOffset`'s positivity check contradicts its own error message and lets `TemporalUnitLessThanOffset` be constructed with a useless zero offset

**File / line:** `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`, lines 52–54

```java
private static void checkThatValueIsPositive(long value) {
  checkArgument(value >= 0, "The value of the offset should be greater than zero");
}
```

The message says the value must be "greater than zero," but the check accepts `value == 0`. This constructor is shared by both `TemporalUnitWithinOffset` (inclusive, `<=`) and `TemporalUnitLessThanOffset` (exclusive, `<`). Compare with the analogous pair in `Offset.java` in the same package, which correctly differentiates the two variants: `offset(value)` requires `value >= 0` ("should be greater than or equal to zero") while `strictOffset(value)` requires `value > 0d` ("should be greater than zero") — i.e. the strict/exclusive variant has its own, stricter check matching its own message.

`TemporalUnitLessThanOffset` never adds an analogous stricter check, so it silently accepts `value = 0`, contradicting the "greater than zero" message inherited from the base class and producing a degenerate, always-failing assertion: with `value = 0`, `isBeyondOffset` becomes `getDifference(...) >= 0`, which is always true (a time difference is never negative), so `isCloseTo(actual, expected, byLessThan(0, unit))` can never pass for any two temporals, not even two identical ones.

**Verified with a standalone repro:**

```
Constructed with value=0 (message says 'greater than zero' but this succeeded)
isBeyondOffset(now, now) = true   // "now" compared to itself is reported as beyond the offset
```

**Severity:** low/medium. It's an argument-validation gap: the class's own documented/implied invariant ("greater than zero" for the strict variant) is not enforced, unlike the equivalent `Offset`/`strictOffset` pair in the same package, and the result is a constructible-but-unusable offset object rather than an immediate, clear `IllegalArgumentException` at construction time.

**Suggested fix:** give `TemporalUnitLessThanOffset` its own constructor-time check requiring `value > 0`, matching the pattern used by `Offset.strictOffset`, e.g.:

```java
public TemporalUnitLessThanOffset(long value, TemporalUnit unit) {
  super(value, unit);
  checkArgument(value > 0, "The value of the offset should be greater than zero");
}
```

(or tighten `TemporalUnitOffset.checkThatValueIsPositive` and give `TemporalUnitWithinOffset` an explicit `>= 0` override if the shared method is meant to be strict by default).

---

## Files reviewed (no defects found beyond those listed above)

- `Index.java` — no defects found.
- `MapEntry.java` — `equals`/`hashCode` correctly follow the general `Map.Entry` contract; no defects found.
- `Offset.java` — `offset()`/`strictOffset()` validation is internally consistent (message matches check in both cases); no defects found.
- `Percentage.java` — no logic defects found (the javadoc's `@throws NullPointerException` note is a documentation-only issue for a primitive `double` parameter, not reported per review scope).
- `TemporalOffset.java` — interface only, no defects.
- `TemporalUnitOffset.java` — see Defect 2 above for the shared validation helper; otherwise no defects found.
- `TemporalUnitLessThanOffset.java` — see Defects 1 and 2 above.
- `TemporalUnitWithinOffset.java` — no defects found (this class is the one that gets the overflow handling and inclusive-zero semantics right; it's the baseline the other two should match).

Supporting file read for context (not part of the review scope, read only to understand `checkArgument`'s semantics): `assertj-core/src/main/java/org/assertj/core/util/Preconditions.java`.

All findings above were confirmed by compiling and executing small standalone Java snippets against copies of the actual source files (JDK 25, `javac`/`java`), not just read by inspection.
