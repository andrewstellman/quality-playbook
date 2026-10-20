# Gson Adversarial Code Review — Findings

**Scope:** Deep, maintainer-grade review of the `gson` core module (public API, serialization/deserialization
pipeline, adapter/factory resolution, streaming and tree APIs, type system, robustness).

**Method:** Read the core pipeline and adapter classes; cross-checked behavior against Javadocs, the
`UserGuide`/`Troubleshooting` docs, and existing tests; validated every reported finding with a small
compiled reproducer run against the freshly built `gson/target/classes`, and (for FINDING-1) with a
temporary JUnit test that was confirmed to fail and then removed.

**Headline:** The streaming layer (`JsonReader`/`JsonWriter`), container/tree adapters, exclusion/naming/
`@JsonAdapter` resolution, and constructor/type-resolution machinery were examined adversarially and found
to faithfully implement their documented contracts — no defects there I could reproduce. The reproducible
defects all live in **`JsonPrimitive` value equality** and in a **cross-API inconsistency for duplicate JSON
member names**. Findings 1 and 2 share a root cause (the design of `JsonPrimitive.equals`) but violate two
*different* `Object` contracts, are masked by two *different* zero-only tests, and have different impact, so
they are reported separately.

---

## FINDING-1: `JsonPrimitive.equals`/`hashCode` violate the `Object.hashCode` contract for numerically-equal integral vs. floating values

**Severity:** High
**Confidence:** High
**Area:** `com.google.gson.JsonPrimitive#equals` / `#hashCode` (and, by propagation, `JsonObject`/`JsonArray`)

**Claim:**
Two `JsonPrimitive` instances that hold numerically-equal numbers — one of an *integral* runtime type
(`Integer`/`Long`/`Short`/`Byte`/`BigInteger`) and one of a *floating* runtime type (`Double`/`Float`/
`BigDecimal`) — are reported as `equals() == true`, but produce **different `hashCode()` values** for every
non-zero magnitude. This breaks the `Object.equals`/`Object.hashCode` invariant ("equal objects must have
equal hash codes") and makes `JsonPrimitive` (and any `JsonObject`/`JsonArray` containing such a value)
unsafe as a `HashSet`/`HashMap` key.

**Evidence:**
`JsonPrimitive.java:281-311` (`equals`): when the two values are not *both* integral and not *both*
`BigDecimal`, equality falls through to a `double` comparison:
```java
double thisAsDouble = this.getAsDouble();
double otherAsDouble = other.getAsDouble();
return (thisAsDouble == otherAsDouble) || (Double.isNaN(thisAsDouble) && Double.isNaN(otherAsDouble));
```
So `new JsonPrimitive(1).equals(new JsonPrimitive(1.0))` is `true`.

`JsonPrimitive.java:259-275` (`hashCode`) uses two *different* algorithms depending on `isIntegral`:
```java
if (isIntegral(this)) {                       // Integer/Long/Short/Byte/BigInteger
  long value = getAsNumber().longValue();
  return (int) (value ^ (value >>> 32));      // hash of the long bits
}
if (value instanceof Number) {                // Double/Float/BigDecimal
  long value = Double.doubleToLongBits(getAsNumber().doubleValue());
  return (int) (value ^ (value >>> 32));      // hash of the IEEE-754 bit pattern
}
```
For magnitude `1`, the integral branch yields `1`, while the floating branch yields
`(int)(doubleToLongBits(1.0) ^ (… >>> 32)) = 1072693248`. The two branches only coincide at value `0`
(because `doubleToLongBits(0.0) == 0L`), which is exactly — and *only* — what the existing tests exercise
(see "test gap" below).

Propagation: `JsonObject`/`JsonArray` delegate `equals`/`hashCode` to their backing map/list, which call
`JsonPrimitive`'s. So two `JsonObject`s that are `equals()`-equal can have unequal hash codes too.

**Why this violates the intended contract:**
The `Object.hashCode` Javadoc requires that `a.equals(b)` implies `a.hashCode() == b.hashCode()`. The Gson
maintainers clearly intend cross-type numeric equality (the `equals` code deliberately equates
`BigDecimal("0.0")` with `BigDecimal("0.00")` and `0.0d`, and `JsonPrimitiveTest.testEqualsAcrossTypes`
asserts `assertEqualsAndHashCode(new JsonPrimitive(new BigDecimal("0")), new JsonPrimitive(0))`). Given that
intent, `hashCode` is simply inconsistent with `equals` for every non-zero value.

**Minimal reproducer** (verified by running the snippet against `gson/target/classes`):
```java
JsonPrimitive a = new JsonPrimitive(1);     // Integer
JsonPrimitive b = new JsonPrimitive(1.0);   // Double
a.equals(b);    // true
a.hashCode();   // 1
b.hashCode();   // 1072693248  -> contract violated

Set<JsonPrimitive> s = new HashSet<>(); s.add(a);
s.contains(b);  // false, even though a.equals(b)

JsonObject o1 = new JsonObject(); o1.addProperty("v", 1);
JsonObject o2 = new JsonObject(); o2.addProperty("v", 1.0);
o1.equals(o2);                       // true
o1.hashCode() == o2.hashCode();      // false
```
Temporary JUnit test `TempHashCodeReproTest` (since removed) was run with
`mvn -pl gson test -Dtest=TempHashCodeReproTest` and **failed** as expected:
```
integralVsFloatingHashCodeConsistency: expected 1072693248 but was 1
bigDecimalVsIntegerNonZeroHashCode:    expected 1 but was 1072693248
```

**Test gap that hides it:** `JsonPrimitiveTest.testEqualsAcrossTypes` (lines 290-299) only checks the
combination at value **0** — `new JsonPrimitive(new BigDecimal("0"))` vs `new JsonPrimitive(0)`,
`new JsonPrimitive(0)` vs `0L`, etc. Zero is the one magnitude where `longValue`-hash and
`doubleToLongBits`-hash coincide, so the suite passes while the contract is broken for all other values.

**Expected behavior:** If `a.equals(b)`, then `a.hashCode() == b.hashCode()`.

**Actual behavior:** `equals` true, hash codes differ for all non-zero integral-vs-floating numeric pairs.

**Suggested fix direction:** Make `hashCode` consistent with the equality relation. The cleanest option that
keeps current equality semantics: collapse all numeric primitives to a single canonical hashing path —
e.g. hash on `getAsBigDecimal().stripTrailingZeros()` for numbers Gson treats as comparable, or hash on
`Double.doubleToLongBits(getAsDouble())` uniformly (accepting collisions for huge `BigInteger`/`BigDecimal`
values that `equals` already distinguishes — collisions are legal, unequal hashes for equal objects are not).
Compatibility note: changing `hashCode` changes hash-bucket placement but no `equals` result; the only risk
is to code that persisted/serialized raw `hashCode` integers, which is not a supported contract. Note this
fix interacts with FINDING-2 — fixing equality semantics there may dictate the canonical hash.

**Suggested regression test:** Extend `testEqualsAcrossTypes` to assert `assertEqualsAndHashCode` for
**non-zero** cross-type pairs: `(1, 1.0)`, `(5L, 5.0d)`, `(new BigInteger("7"), 7.0d)`,
`(100, new BigDecimal("100.00"))`, plus a `HashSet.contains` round-trip and a `JsonObject` pair that differ
only in `int` vs `double` representation.

---

## FINDING-2: `JsonPrimitive.equals` is not transitive for high-precision `BigDecimal` vs `double`

**Severity:** Medium
**Confidence:** High
**Area:** `com.google.gson.JsonPrimitive#equals`

**Claim:**
`JsonPrimitive.equals` mixes two comparison strategies — exact `BigDecimal.compareTo` when *both* operands are
`BigDecimal`, but lossy `double` comparison when only one is. This makes equality **non-transitive**: there
exist `x`, `y`, `z` with `x.equals(y)` and `y.equals(z)` true but `x.equals(z)` false.

**Evidence:**
`JsonPrimitive.java:298-309`. When both operands are `BigDecimal`, it uses
`getAsBigDecimal().compareTo(...) == 0` (exact, scale-insensitive). Otherwise it compares
`getAsDouble() == getAsDouble()` (rounds each operand to IEEE-754 double first). Two `BigDecimal`s that differ
only beyond double precision are *unequal* to each other (exact compareTo) yet each is *equal* to the
`double` they both round to.

**Why this violates the intended contract:**
`Object.equals` requires transitivity. The maintainers explicitly care about this: the existing test
`JsonPrimitiveTest.testBigDecimalEqualsTransitive` is documented as *"Verifies that equals is transitive for
BigDecimal, as required by the Object.equals documentation"* — but it only checks the value **0**
(`BigDecimal("0")`, `0.0d`, `BigDecimal("0.00")`), where double rounding is exact, so it never exercises the
failing case.

**Minimal reproducer** (verified against `gson/target/classes`):
```java
JsonPrimitive x = new JsonPrimitive(new BigDecimal("1.0000000000000001")); // beyond double precision
JsonPrimitive y = new JsonPrimitive(1.0d);
JsonPrimitive z = new JsonPrimitive(new BigDecimal("1"));
x.equals(y); // true  (double compare: 1.0 == 1.0)
y.equals(z); // true  (double compare: 1.0 == 1.0)
x.equals(z); // false (BigDecimal.compareTo: 1.0000000000000001 != 1)  -> not transitive
```

**Expected behavior:** Transitive equality (per `Object.equals`).

**Actual behavior:** `x~y` and `y~z` but `x≁z`.

**Suggested fix direction:** Use a single, consistent comparison for all numeric primitives — e.g. always
compare via `BigDecimal` (`getAsBigDecimal().compareTo(...)`), treating a `double`/`float` operand as the
`BigDecimal` of its exact value (`new BigDecimal(doubleValue)`), with explicit handling for `NaN`/`±Infinity`
which have no `BigDecimal` representation. This makes equality exact and transitive. Compatibility risk:
some previously-"equal" double-vs-BigDecimal pairs (those that only matched after rounding) would become
unequal; that is the correct direction and removes the contract violation. This change must be co-designed
with the FINDING-1 `hashCode` fix.

**Suggested regression test:** Add a transitivity test using `x = BigDecimal("1.0000000000000001")`,
`y = 1.0d`, `z = BigDecimal("1")` asserting that the three pairwise results are mutually consistent (no
`a~b ∧ b~c ∧ ¬a~c`).

---

## FINDING-3: Duplicate JSON member names are handled inconsistently across deserialization APIs (`Map` throws; `Object`, tree, and reflective paths silently keep the last value)

**Severity:** Medium
**Confidence:** High
**Area:** `internal/bind/MapTypeAdapterFactory` vs `ObjectTypeAdapter` / `JsonParser`(tree) / `ReflectiveTypeAdapterFactory`

**Claim:**
For the identical input `{"x":1,"x":2}`, Gson's behavior depends entirely on the *target type*:
deserializing to a `Map` throws `JsonSyntaxException: duplicate key: x`, while deserializing to `Object`, to a
`JsonElement` tree, or to a reflective POJO **silently accepts** the input and keeps the **last** value. There
is no documented contract that distinguishes these, so the same malformed-ish document is rejected through one
public entry point and silently accepted through three others.

**Evidence:**
- `MapTypeAdapterFactory.Adapter.read` explicitly rejects duplicates:
  `if (map.containsKey(key)) throw new JsonSyntaxException("duplicate key: " + key);`
- `ObjectTypeAdapter.read` does `map.put(name, value)` with no duplicate check (last-wins).
- `JsonParser`/tree builds via `LinkedTreeMap.put` (last-wins; `JsonObject.add` overwrites).
- `ReflectiveTypeAdapterFactory.Adapter.read` (lines 511-519) loops `while (in.hasNext())` and calls
  `readField` for each occurrence, overwriting the field (last-wins).

Verified against `gson/target/classes`:
```
gson.fromJson("{\"x\":1,\"x\":2}", Object.class)        => {x=2.0}
gson.fromJson("{\"x\":1,\"x\":2}", Map<String,Object>)  => THREW JsonSyntaxException: duplicate key: x
JsonParser.parseString("{\"x\":1,\"x\":2}")             => {"x":2}
gson.fromJson("{\"x\":1,\"x\":2}", Pojo.class).x        => 2
```

**Why this violates the intended contract:**
There is no Javadoc, UserGuide, or Troubleshooting entry stating that duplicate JSON keys are rejected. (The
only "duplicate" guidance — `Troubleshooting.md#duplicate-fields` — is about conflicting *Java field names*,
not JSON keys.) JSON itself leaves duplicate-name semantics undefined, but a single library should be
*consistent* about its choice across `fromJson`/tree/reflective paths. The current state is a surprising
difference between similar public methods (review category "API-layer inconsistencies → duplicate object
member names"): a user who relies on the `Map` path to reject duplicates gets no protection on the `Object`,
tree, or POJO paths, and vice-versa.

**Minimal reproducer:** see the four-line transcript above (`Repro.java`, run and confirmed).

**Expected behavior:** One documented, uniform policy for duplicate member names across all deserialization
entry points (either reject everywhere, or last-wins everywhere, with the choice documented).

**Actual behavior:** `Map` rejects; `Object`/tree/reflective silently keep the last value.

**Suggested fix direction:** Decide the intended policy and align the paths. Least-disruptive: keep last-wins
as the universal default (it is the long-standing behavior for tree/reflective/`Object`) and document it,
demoting the `Map` exception to match — or, if rejection is desired, gate it behind a single opt-in on
`GsonBuilder` applied uniformly. Compatibility risk: removing the `Map` exception relaxes a check added
deliberately; introducing rejection on the other paths would be a breaking change. Because of that, the safest
concrete step is to **document** the per-target behavior explicitly and, longer term, unify it behind a
builder flag rather than silently diverging.

**Suggested regression test:** A parameterized test feeding `{"x":1,"x":2}` to `Object.class`,
`Map<String,Object>`, `JsonParser.parseString`, and a POJO, asserting the *same* policy (whichever is chosen)
for all four.

---

## Near misses / investigated but not findings

- **No nesting limit on `JsonWriter` (vs. the reader's `nestingLimit`).** `JsonWriter.beginArray/beginObject`
  grow the stack unboundedly and 200k levels succeed. Rejected: the writer is iterative and cannot
  self-`StackOverflow`; deep output only reflects the caller's own object-graph recursion. This matches
  upstream design and the `JsonReader.setNestingLimit` Javadoc (the limit exists to protect recursive
  *adapters during reading*).
- **`ObjectTypeAdapter.write` emits `{}` for a bare `Object`/cycle fallback (lossy).** Real but intended
  anti-infinite-recursion guard; not a contract violation.
- **`peekNumber` leading-zero handling (`fitsInLong && value == 0`).** This is the deliberate fix in commit
  `004e7a49` (#3034); verified correct for `2^64 + "0"`.
- **`ToNumberPolicy.LONG_OR_DOUBLE` returns `Double` for integers exceeding `long` / for `2e3`.** Lossy/
  surprising but exactly what the Javadoc states ("Long if parseable as Long, otherwise Double"). Not a bug.
- **`TypeToken.getParameterized` validates only the *raw* bound; `isAssignableFrom`/`typeEquals` index
  arg arrays without length checks.** Real robustness fragility on malformed user `Type` implementations, but
  confined to a `@Deprecated`, "basic validation"-documented surface; a maintainer would likely treat it as a
  low-priority hardening, not a defect. Worth a length-guard in `typeEquals`.
- **`TypeAdapterRuntimeTypeWrapper` only substitutes runtime type for `Class`/`TypeVariable` declared types,
  not `ParameterizedType`.** Verified to be the intended conservative behavior (preserving type arguments);
  not a defect.
- **`GsonTypes.resolve` on recursive generics (`T extends Comparable<T>`).** Guarded by `visitedTypeVariables`;
  no `StackOverflow`. Correct.
- **`FieldNamingPolicy` uses `Locale.ENGLISH` rather than `Locale.ROOT`.** Behaviorally identical for ASCII;
  cosmetic only.
- **`Map`/`LinkedTreeMap` null-key/null-value handling, AVL rebalancing, `removeInternal`.** Reviewed; matches
  documented behavior and the well-tested Android-derived implementation.

## Highest-risk areas for a second pass

1. **`JsonPrimitive` numeric equality/hashing as a whole** — Findings 1 & 2 indicate the equality model
   (mixing `double` and `BigDecimal` comparison, plus split hashing) is internally inconsistent; a focused
   redesign + property-based tests (reflexive/symmetric/transitive + equals⇒hashCode over random numeric
   types and magnitudes) would likely surface more edge cases (e.g. `Float` vs `Double` near-but-not-equal,
   subnormals, `-0.0` vs `0`).
2. **Cross-API consistency for malformed/edge inputs** — duplicate keys (Finding 3) is one axis; also worth
   sweeping null handling, trailing data, and number coercion uniformly across `fromJson(String)` /
   `fromJson(Reader)` / `fromJson(JsonElement)` / tree / reflective / custom-adapter paths.
3. **`TypeToken`/`GsonTypes` robustness against hostile/foreign `Type` implementations** (array-index guards,
   wildcard `getUpperBounds().length == 0`).
4. **`@JsonAdapter` precedence and `nullSafe` interactions** across the four adapter kinds (re-verified clean
   here, but it is the most precedence-sensitive surface and a good target for exhaustive matrix testing).

## Validation summary

- **Commands run:**
  - `mvn -pl gson compile` — success (exit 0); reproducers compiled against `gson/target/classes`.
  - `mvn -pl gson test -Dtest=JsonPrimitiveTest` — success (exit 0): confirms the existing zero-only tests
    pass, demonstrating the test gap that masks FINDING-1/2.
  - `mvn -pl gson test -Dtest=TempHashCodeReproTest` — **2 failures** (as designed), demonstrating FINDING-1.
  - `mvn -pl gson test` (full module suite) — `Tests run: 4605, Failures: 2, Errors: 0, Skipped: 20`. The
    only 2 failures were the `TempHashCodeReproTest` methods (FINDING-1 demonstrators); the suite is otherwise
    green. With the temp test removed, the baseline suite is all-passing.
  - Standalone reproducers `Repro.java`, `Repro2.java`, `Repro3.java`, `Repro4.java` compiled and run against
    `gson/target/classes` to validate Findings 1–3 (outputs quoted inline above).
- **Temporary tests created:** `gson/src/test/java/com/google/gson/TempHashCodeReproTest.java` (JUnit,
  demonstrated FINDING-1, confirmed failing) and `/tmp/gsonrepro/Repro*.java` standalone reproducers.
- **Temporary files removed:** `TempHashCodeReproTest.java` was **deleted** from the source tree, and the
  `/tmp/gsonrepro/` standalone reproducers were deleted. `git status` shows only the intended deliverable
  (`GSON_REVIEW_FINDINGS.md`) as untracked; no source/test changes remain.
- **Areas not fully verified:** I did not exhaustively re-run every module's suite (focused on `gson` core);
  Android-runtime and JPMS-modular execution paths were reasoned about from source but not executed on those
  platforms; the `extras`/`proto` modules were out of scope.
</content>
