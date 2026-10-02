# Code review: assertj `assertj-core/src/main/java/org/assertj/core/data/`

Reviewer: Opus (control run). Pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada (checkout at `/tmp/control/assertj`, which has no `.git` directory, so the commit could not be confirmed locally).

I confirmed all three defects below by compiling the in-scope classes (with a one-method stub for `Preconditions.checkArgument`) under JDK 25 in `/tmp/control-work/opus-assertj/` and running a small driver. Observed output:

```
within(1,SECONDS).equals(within(1,HOURS)) = true
within(2 MILLIS) beyond for MIN: true
byLessThan(2 MILLIS) throws: java.lang.ArithmeticException: long overflow
withPercentage(1e10) = 2147483647%
withPercentage(3e9) = 2147483647%
```

---

## 1. `TemporalUnitLessThanOffset.isBeyondOffset` throws `ArithmeticException` on overflow. The `within` variant handles this case.

- **File/line:** `TemporalUnitLessThanOffset.java`, `isBeyondOffset` (line ~45: `return getDifference(temporal1, temporal2) >= value;`)
- **What goes wrong:** `getDifference` calls `unit.between(...)`, which throws `ArithmeticException` when the difference in the requested unit overflows a `long`. One example is millis or nanos between a normal `Instant` and `Instant.MIN`. `TemporalUnitWithinOffset.isBeyondOffset` catches this and falls back to comparing `Duration`s (`getAbsoluteDuration(...).compareTo(Duration.of(value, unit)) > 0`). `TemporalUnitLessThanOffset` has no such fallback. So `assertThat(now).isCloseTo(Instant.MIN, byLessThan(2, MILLIS))` escapes with a raw `ArithmeticException: long overflow` instead of failing with a proper assertion error. The same assertion using `within(2, MILLIS)` fails cleanly.
- **Why it is wrong:** The two sibling implementations of the same contract behave inconsistently. The base class's `getBeyondOffsetDifferenceDescription` already catches `ArithmeticException` for this exact case, which shows the overflow case is intended to be supported. The existing test `AbstractTemporalAssert_isCloseTo_Test` expects `Instant.MIN` with a 2-millis `within` offset to produce a normal failure message (`...within 2 Millis but difference was PT8765837682367H10M`), so the design intends a normal failure for overflowing differences. The strict variant is simply missing the fallback.
- **Severity:** medium. The assertion outcome is still "failed", but the user gets an `ArithmeticException` with no assertion message instead of an `AssertionError`.
- **Suggested fix:**
  ```java
  @Override
  public boolean isBeyondOffset(Temporal temporal1, Temporal temporal2) {
    try {
      return getDifference(temporal1, temporal2) >= value;
    } catch (ArithmeticException e) {
      return getAbsoluteDuration(temporal1, temporal2).compareTo(Duration.of(value, unit)) >= 0;
    }
  }
  ```
  A cleaner alternative is to move the try/fallback into the base class, for example a `compareDifference` helper.

## 2. `TemporalUnitOffset.equals` and `hashCode` ignore `unit`

- **File/line:** `TemporalUnitOffset.java`, `hashCode()` (`return Objects.hash(value);`) and `equals()` (`return value == other.value;`), around lines 97–110
- **What goes wrong:** `new TemporalUnitWithinOffset(1, SECONDS).equals(new TemporalUnitWithinOffset(1, HOURS))` returns `true` (confirmed). Two offsets with very different meanings compare equal and hash to the same value. Anything that relies on equality treats them as interchangeable, including collections, caching, and assertions that compare offsets.
- **Why it is wrong:** An offset's meaning is the pair (value, unit). `unit` is a `final` state field with a public getter (`getUnit()`), and `isBeyondOffset` and the difference description both depend on it. The other value types in this package include every semantic field in `equals`/`hashCode`. For example, `Offset` compares both `value` and `strict`.
- **Severity:** low
- **Suggested fix:**
  ```java
  public int hashCode() { return Objects.hash(value, unit); }
  ... return value == other.value && unit.equals(other.unit);
  ```

## 3. `Percentage.toString` truncates large whole-number percentages to `Integer.MAX_VALUE`

- **File/line:** `Percentage.java`, `toString()` (`noFractionalPart() ? "%s%%".formatted((int) value) : ...`), line ~59
- **What goes wrong:** Any whole-number value above `Integer.MAX_VALUE` gets narrowed by the `(int)` cast. `withPercentage(1e10).toString()` and `withPercentage(3e9).toString()` both print `2147483647%` (confirmed). `withPercentage` accepts any non-negative double, so these values are valid. The wrong number then appears in `isCloseTo(..., withPercentage(...))` failure messages that render the percentage.
- **Why it is wrong:** `toString` should show the configured value. The `(int)` cast is only a formatting device to drop a trailing `.0`, but it silently changes the number for values outside the int range.
- **Severity:** low. Large percentages are unusual, but the message is actively wrong when they are used.
- **Suggested fix:** Format with `(long) value` guarded by a range check. Alternatively, use `BigDecimal.valueOf(value).stripTrailingZeros().toPlainString() + "%"`, or `String.format("%.0f%%", value)` for the whole-number branch.

---

## Checked and not reported

- `Offset.offset`/`strictOffset` reject NaN (`NaN >= 0` is false) and negatives correctly. `equals` and `hashCode` are consistent.
- `MapEntry.equals` and `hashCode` follow the `Map.Entry` contract (`key^value` hash, compared against any `Map.Entry`).
- `Index` validation and equality are fine.
- Some messages and javadoc are inaccurate but do not affect behaviour, so they are not reported as defects. `TemporalUnitOffset` says "should be greater than zero" while it accepts 0. `Percentage.withPercentage` documents an NPE for a primitive argument.

## Files read

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java` (lines 110–145, context)
- grep results only from `assertj-core/src/main/java/org/assertj/core/api/Assertions.java` and `AbstractTemporalAssert.java` (call sites of the offsets)
