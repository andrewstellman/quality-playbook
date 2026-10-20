# Gson code review — 2026-04-03

## Pass 1: Structural Review

#### `gson/src/main/java/com/google/gson/GsonBuilder.java`
- **Lines 29-49, 92-104, 130-131, 688-694:** **BUG** — `GsonBuilder` is still wired to an older `Gson` API surface (`$Gson$Preconditions`, `DEFAULT_*` constants, `prettyPrinting`, `lenient`, and a many-argument `Gson(...)` constructor), but the current `Gson` implementation has moved to `FormattingStyle`, `Strictness`, and `Gson(GsonBuilder)`. These files cannot compile together, which makes both `new Gson()` and `new GsonBuilder().create()` unusable.

#### `gson/src/main/java/com/google/gson/Gson.java`
- **Lines 19, 223-255:** **BUG** — `Gson` now assumes newer builder helpers and package-visible builder state (`GsonBuilder.DEFAULT`, `newImmutableList(...)`, `createFactories(...)`, `builder.strictness`, `builder.formattingStyle`), but `GsonBuilder` does not provide them. The core API bootstrap path is therefore broken before any serialization or deserialization logic can run.
- **Lines 982, 1196-1199:** **BUG** — the public `fromJson(Reader, TypeToken)` path promises trailing-data rejection, but `assertFullConsumption(...)` only checks for trailing tokens when `obj != null`. Any payload whose logical result is `null` can silently leave unread top-level data behind.

#### `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`
- **Lines 191-206:** **BUG** — duplicate-key detection is implemented as `if (map.put(key, value) != null)`, which misses duplicates when the first value for that key is `null`. In that case the second entry overwrites the first without throwing, even though duplicate map keys are supposed to be rejected.

## Pass 2: Requirement Verification

#### REQ-002: builder snapshots must not mutate already-created `Gson` instances
**Status:** **VIOLATED**  
**Evidence:** `gson/src/main/java/com/google/gson/GsonBuilder.java:677-695`, `gson/src/main/java/com/google/gson/Gson.java:222-256`  
**Analysis:** The builder cannot even construct a `Gson` because it targets a stale constructor and stale fields. Snapshotting behavior cannot hold when `create()` itself is structurally broken.  
**Severity:** High

#### REQ-003: default `new Gson()` must provide the documented default configuration
**Status:** **VIOLATED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:222-223`, `gson/src/main/java/com/google/gson/Gson.java:247-255`  
**Analysis:** `new Gson()` delegates to `GsonBuilder.DEFAULT`, but the builder implementation does not define that default object or the companion cached factories the constructor expects. The default entry point is therefore not buildable, so the documented default behavior is unavailable.  
**Severity:** High

#### REQ-005: wrong-type adapter results must fail fast
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:1079-1090` — runtime type is checked against `Primitives.wrap(typeOfT.getRawType())`, and mismatches throw a `ClassCastException` with adapter and target details.  
**Analysis:** The check is immediate after adapter read and prevents silently returning an object of the wrong runtime type.

#### REQ-006: `generateNonExecutableJson()` must prefix every emitted document
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:774-783` — `newJsonWriter(...)` writes `JSON_NON_EXECUTABLE_PREFIX` before constructing the writer when the flag is enabled.  
**Analysis:** The writer-side prefix is applied centrally, so all `toJson(...)` paths that create a writer through `Gson` inherit it.

#### REQ-007: default Gson deserialization must tolerate the non-executable prefix
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:798-800`, `gson/src/main/java/com/google/gson/Gson.java:1069-1073`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:659-662`  
**Analysis:** Default readers start `LEGACY_STRICT`, and `fromJson(JsonReader, TypeToken)` upgrades that default to `LENIENT`; `JsonReader` consumes the non-executable prefix in lenient mode. That matches the interoperability contract exercised in `SecurityTest`.

#### REQ-008: parameterized deserialization must require explicit type information
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:68-87`, `gson/src/main/java/com/google/gson/reflect/TypeToken.java:35-48`  
**Analysis:** The public API and the type-token implementation both make the erasure boundary explicit and direct callers toward `Type`/`TypeToken` for typed collection deserialization.

#### REQ-009: builder leniency/strictness configuration must propagate to readers and writers
**Status:** **VIOLATED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:779-782`, `gson/src/main/java/com/google/gson/Gson.java:798-800`, `gson/src/main/java/com/google/gson/GsonBuilder.java:1-728`  
**Analysis:** `Gson` expects builder fields such as `strictness` and `formattingStyle`, but `GsonBuilder` does not define them. The propagation logic in `Gson` exists, but the builder surface required to drive it is missing.  
**Severity:** High

#### REQ-013: lenient syntax extensions must only be accepted when parser mode allows them
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/stream/JsonReader.java:593-595`, `622-624`, `634-640`, `697-699`, `727-728`  
**Analysis:** All of the lenient-only branches funnel through `checkLenient()`, so the parser-side gating is correct even though the builder wiring above is broken.

#### REQ-016: full-value deserialization entry points must reject trailing data
**Status:** **VIOLATED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:978-983`, `gson/src/main/java/com/google/gson/Gson.java:1196-1200`  
**Analysis:** The public overloads call `assertFullConsumption(...)`, but the helper only checks for `END_DOCUMENT` when the returned object is non-null. A legal `null` result therefore suppresses the trailing-data check entirely.  
**Severity:** High

#### REQ-021: anonymous and non-static local classes must serialize/deserialize as `null`
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:117-139`  
**Analysis:** The factory short-circuits these classes to a dedicated adapter that skips input and writes `null`, matching the documented unsupported-class behavior.

#### REQ-023: reflection barriers must fail with actionable remediation
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:142-149`, `168-178`, `336-342`  
**Analysis:** Both direct-type and supertype reflection failures throw `JsonIOException` messages that tell callers to register adapters, adjust filters, or open visibility.

#### REQ-026: object construction must follow the documented fallback order
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:107-170`  
**Analysis:** The implementation checks exact-type `InstanceCreator`, raw-type `InstanceCreator`, special collections, no-args constructor, default implementations, instantiability, and only then `Unsafe`.

#### REQ-027: `disableJdkUnsafe()` must fail loudly with remediation guidance
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:149-155`, `400-416`  
**Analysis:** When unsafe construction is disallowed, Gson returns a throwing constructor with explicit guidance about registering an adapter, adding a no-args constructor, enabling unsafe, or adjusting R8.

#### REQ-028: abstract classes and interfaces must never be instantiated through `Unsafe`
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:66-89`, `142-147`  
**Analysis:** Non-instantiable types are rejected before the unsafe allocator branch is reached.

#### REQ-031: `JsonObject` must preserve insertion order and normalize Java `null`
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/JsonObject.java:41`, `69-71`, `136-138`  
**Analysis:** `JsonObject` stores members in `LinkedTreeMap` and converts raw Java `null` to `JsonNull.INSTANCE` on insert.

#### REQ-033: `Map` deserialization must reject duplicate keys in both object and array encodings
**Status:** **VIOLATED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:189-206`  
**Analysis:** Duplicate rejection depends on the previous map value being non-null. If the first occurrence of a duplicated key maps to `null`, the overwrite succeeds silently in both the array and object code paths.  
**Severity:** Medium

#### REQ-035: reversible complex map keys require explicit opt-in
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:221-259`  
**Analysis:** Without `complexMapKeySerialization`, keys are stringified; with it, complex keys switch to the array-of-entry form only when necessary.

#### REQ-036: raw `Map` / `Map<String, ...>` must use `LinkedTreeMap`, other maps appropriate JDK defaults
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:339-381`  
**Analysis:** String-key maps select `LinkedTreeMap`; concrete or non-string-key variants fall through to `LinkedHashMap`, `TreeMap`, or concurrent map implementations.

#### REQ-037: `TypeToken` must reject raw tokens and captured type variables with actionable errors
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/reflect/TypeToken.java:95-118`, `121-157`  
**Analysis:** Raw-token creation and captured type variables are rejected eagerly, and the exception messages point callers to troubleshooting guidance.

#### REQ-040: raw collection deserialization must materialize generic JSON structures, not fake domain types
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:68-87`, `gson/src/main/java/com/google/gson/reflect/TypeToken.java:35-48`  
**Analysis:** The API explicitly preserves the erasure boundary instead of implying typed-element recovery from raw classes.

#### REQ-041: JPMS openness must be respected; blocked reflection must fail
**Status:** **SATISFIED**  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:168-178`, `336-342`  
**Analysis:** The reflective adapter never attempts to tunnel through blocked module access; it surfaces the barrier as an explicit failure.

## Pass 3: Cross-Requirement Consistency

#### Shared Concept: XSSI prefix generation and consumption
**Requirements:** REQ-006, REQ-007  
**What REQ-006 claims:** prefixed output must be emitted whenever the option is enabled.  
**What REQ-007 claims:** default Gson readers must still accept prefixed input.  
**Consistency:** **CONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/Gson.java:774-783`, `gson/src/main/java/com/google/gson/Gson.java:1069-1073`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:659-662`  
**Analysis:** Writer-side prefixing and reader-side lenient-prefix consumption line up as a coupled interoperability story.

#### Shared Concept: typed collection guidance vs raw-type degradation
**Requirements:** REQ-008, REQ-040  
**What REQ-008 claims:** callers need explicit generic type information for typed collection deserialization.  
**What REQ-040 claims:** absent that type information, Gson must return generic JSON representations instead of pretending it recovered domain types.  
**Consistency:** **CONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/Gson.java:68-87`, `gson/src/main/java/com/google/gson/reflect/TypeToken.java:35-48`  
**Analysis:** The docs and the type-token guardrails describe the same erasure boundary.

#### Shared Concept: anonymous/local-class nulling vs inner-class instantiation
**Requirements:** REQ-021, REQ-022  
**What REQ-021 claims:** anonymous and non-static local classes are unsupported and must collapse to `null`.  
**What REQ-022 claims:** pure inner classes need a caller-supplied enclosing-instance construction path.  
**Consistency:** **CONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:117-139`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:217-285`  
**Analysis:** The code keeps the unsupported-class shortcut distinct from normal construction logic for deserializable named classes.

#### Shared Concept: reflection barriers and escape hatches
**Requirements:** REQ-023, REQ-030, REQ-041  
**What REQ-023 claims:** blocked reflection must fail with remediation guidance.  
**What REQ-030 claims:** custom adapters remain the supported escape hatch when reflection is blocked.  
**What REQ-041 claims:** JPMS openness is required for reflective field access.  
**Consistency:** **CONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:142-149`, `168-178`, `336-342`; `gson/src/main/java/com/google/gson/GsonBuilder.java:542-603`  
**Analysis:** Reflection failures are explicit, module boundaries are respected, and the builder still exposes custom-adapter registration as the intended alternative path.

#### Shared Concept: tree-model replacement vs map duplicate rejection
**Requirements:** REQ-031, REQ-033  
**What REQ-031 claims:** `JsonObject` stores one value per member name and replacement is explicit via `put`.  
**What REQ-033 claims:** typed `Map` deserialization must reject duplicate keys instead of silently replacing them.  
**Consistency:** **INCONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/JsonObject.java:69-71`, `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:191-206`  
**Analysis:** `JsonObject` consistently replaces on duplicate names, but `MapTypeAdapterFactory` only rejects duplicates when the earlier value was non-null. A duplicated key whose first value is `null` now silently replaces, collapsing typed-map behavior toward tree-model replacement semantics.  
**Impact:** Medium — duplicate-key handling becomes data-dependent, which is exactly the ambiguity REQ-033 is supposed to eliminate.

#### Shared Concept: constructor fallback order and unsafe disablement
**Requirements:** REQ-026, REQ-027, REQ-028  
**What REQ-026 claims:** construction must follow the stable fallback order and only reach `Unsafe` last.  
**What REQ-027 claims:** disabling `Unsafe` must turn missing construction paths into actionable failures.  
**What REQ-028 claims:** abstract types and interfaces must never reach `Unsafe`.  
**Consistency:** **CONSISTENT**  
**Code evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:107-170`, `149-155`, `66-89`  
**Analysis:** The constructor pipeline preserves the intended order and blocks non-instantiable types before unsafe allocation is considered.

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1 | `GsonBuilder` and `Gson` target different API generations and do not compile together | High | BUG |
| Pass 1 | Full-consumption check is skipped whenever deserialization returns `null` | High | BUG |
| Pass 1 | Duplicate `Map` keys are silently accepted when the first mapped value is `null` | Medium | BUG |
| Pass 2 | REQ-002 builder snapshot contract is broken because `create()` is structurally unusable | High | VIOLATED |
| Pass 2 | REQ-003 default `new Gson()` contract is broken because the default builder bootstrap path is missing | High | VIOLATED |
| Pass 2 | REQ-009 builder strictness propagation is broken because the builder no longer exposes the fields `Gson` expects | High | VIOLATED |
| Pass 2 | REQ-016 trailing-data rejection fails for `null` results | High | VIOLATED |
| Pass 2 | REQ-033 duplicate-key rejection fails for duplicate keys whose first value is `null` | Medium | VIOLATED |
| Pass 3 | REQ-031 and REQ-033 are inconsistent because typed-map duplicate handling becomes replacement when the first value is `null` | Medium | INCONSISTENT |

- Total findings by pass: Pass 1 = 3, Pass 2 = 5 violated, Pass 3 = 1 inconsistent
- Highest-risk subsystem touched: **Core API and builder configuration**
- Overall assessment: **FIX FIRST**
