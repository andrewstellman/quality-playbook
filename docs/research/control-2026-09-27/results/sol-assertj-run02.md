model: gpt-6-sol
repo: assertj
pinned commit: 7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada
date/time started and finished: started approximately 2026-09-28 22:39:35 UTC; finished 2026-09-28 22:42:15 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran offline compiled probe
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: `assertj-core/src/main/java/org/assertj/core/data/`

Checkout: `7ca27151d9bc4ba86b7e789a327e2e6e96ae5ada`. I compiled the scoped classes with a small local stub of `Preconditions` and ran an offline probe in `/private/tmp/qpb-control/sol-assertj-run02`; the checkout was unchanged.

1. **Medium — inclusive temporal offsets accept differences larger than their limit.** `TemporalUnitOffset.java:75-76`, used by `TemporalUnitWithinOffset.java:47`, compares the *truncated count of whole units*. For example, `new TemporalUnitWithinOffset(1, HOURS).isBeyondOffset(00:00, 01:59)` returns `false`, so `isCloseTo(..., within(1, HOURS))` passes for a 1-hour-59-minute difference. The public `Assertions.within(long, TemporalUnit)` documentation calls the value the “allowed offset,” and `AbstractTemporalAssert.isCloseTo` documents failing when the values are not close for that offset; 1h59m exceeds 1h. Compare full differences to the offset boundary, retaining fractional units, rather than comparing `unit.between`'s truncated result.

2. **Medium — negative `BigDecimal` offset can pass validation.** `Offset.java:60` validates by converting the supplied `Number` to `double`. `Offset.offset(new BigDecimal("-1E-1000"))` is accepted because `doubleValue()` becomes `-0.0`, which compares greater than or equal to zero. The method documents `IllegalArgumentException` for a negative value, and `Numbers.java:201` describes the offset as positive. Validate `BigDecimal` and `BigInteger` in their native precision (and handle other supported numeric types explicitly). This also prevents the negative offset from reaching the assertion comparison.

3. **Low — temporal offsets with different units compare equal.** `TemporalUnitOffset.java:105-110` checks class and value but omits `unit`; `new TemporalUnitWithinOffset(1, HOURS).equals(new TemporalUnitWithinOffset(1, MINUTES))` returns `true`. The class represents an offset “on basis of `TemporalUnit`” (`TemporalUnitOffset.java:27-29`), its constructor stores the unit (`:45-49`), and the two objects give different assertion results. Include `unit` in `equals` and `hashCode`.

4. **Medium — strict temporal offsets throw on a large representable distance.** `TemporalUnitLessThanOffset.java:45` calls `getDifference` without the `ArithmeticException` fallback present in `TemporalUnitWithinOffset.java:46-50`. `new TemporalUnitLessThanOffset(1, NANOS).isBeyondOffset(Instant.MIN, Instant.MAX)` throws `ArithmeticException: long overflow` from `ChronoUnit.NANOS.between`, instead of returning `true` for a difference well beyond 1 ns. `TemporalOffset.isBeyondOffset` promises a boolean answer, and the inclusive implementation explicitly handles this overflow. Add a fallback comparison that can represent the distance, preserving strict boundary semantics.

5. **Low — large whole percentages render as the wrong number.** `Percentage.java:62` casts any integral `double` to `int`. `Percentage.withPercentage(3000000000.0).toString()` returns `2147483647%`. Since this value is accepted by `withPercentage` and `toString` appears in assertion diagnostics, errors can misstate the requested tolerance. Render the whole-valued `double` without narrowing to `int` (for example, with a decimal formatter or `BigDecimal.valueOf(value).toPlainString()`).

Files read:

- `assertj-core/src/main/java/org/assertj/core/data/Index.java`
- `assertj-core/src/main/java/org/assertj/core/data/MapEntry.java`
- `assertj-core/src/main/java/org/assertj/core/data/Offset.java`
- `assertj-core/src/main/java/org/assertj/core/data/Percentage.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitLessThanOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitOffset.java`
- `assertj-core/src/main/java/org/assertj/core/data/TemporalUnitWithinOffset.java`
- `assertj-core/src/main/java/org/assertj/core/api/Assertions.java` (relevant excerpts)
- `assertj-core/src/main/java/org/assertj/core/api/AbstractTemporalAssert.java` (relevant excerpt)
- `assertj-core/src/main/java/org/assertj/core/internal/BigDecimals.java` (relevant excerpt)
- `assertj-core/src/main/java/org/assertj/core/internal/Numbers.java` (relevant excerpt)
- `assertj-core/src/main/java/org/assertj/core/util/Preconditions.java` (relevant excerpt)
- `assertj-core/src/test/java/org/assertj/core/api/AbstractTemporalAssert_isCloseTo_Test.java` (relevant excerpt)
