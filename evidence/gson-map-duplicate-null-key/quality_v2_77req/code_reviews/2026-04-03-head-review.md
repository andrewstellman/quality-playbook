# Gson core code review — 2026-04-03

**Scope:** `Gson.java`, `GsonBuilder.java`, `JsonReader.java`, `ConstructorConstructor.java`, `ReflectiveTypeAdapterFactory.java`, `MapTypeAdapterFactory.java`, `TypeToken.java`, `TypeAdapterRuntimeTypeWrapper.java`, `JsonObject.java`  
**Baseline:** `mvn -q -pl gson test`

## Pass 1: Structural Review

#### `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`
- **Line 191-206:** `BUG` — duplicate-key rejection is implemented as `V replaced = map.put(key, value); if (replaced != null) throw ...`. That only detects duplicates when the *previous value* was non-`null`; if the first occurrence stored `null`, the second occurrence silently overwrites it. This breaks the documented "reject duplicate keys" behavior for both object-form maps (`{"a":null,"a":1}`) and array-of-entry maps (`[[[1],null],[[1],"x"]]`), hiding upstream data corruption behind last-writer-wins behavior.
- **Line 231-259:** `INCOMPLETE` — `enableComplexMapKeySerialization()` still emits object-form JSON whenever every serialized key is a `JsonPrimitive`, even if distinct runtime keys stringify to the same member name. A concrete reproducer is `Map<Number, String>{1.0D -> "a", 1.0F -> "b"}`, which serializes as `{"1.0":"a","1.0":"b"}` and then fails its own round-trip with `duplicate key: 1.0`. The ignored test `MapAsArrayTypeAdapterTest.testTwoTypesCollapseToOneSerialize()` shows this gap is already known, but the writer still produces a wire format the paired reader rejects.

## Pass 2: Requirement Verification

#### REQ-002: builder snapshotting must isolate existing Gson instances from later builder mutations
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:226-255`, `gson/src/main/java/com/google/gson/GsonBuilder.java:165-185`, `gson/src/main/java/com/google/gson/GsonBuilder.java:921-922`  
**Analysis:** `new Gson(this)` copies scalar configuration and snapshots the factory/filter lists into immutable lists before building factories. `newBuilder()` also copies the existing `Gson` state back into a fresh builder instead of sharing mutable builder internals.

#### REQ-006: generateNonExecutableJson must prefix every emitted document
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:774-783`  
**Analysis:** `newJsonWriter()` writes `JSON_NON_EXECUTABLE_PREFIX` before constructing the writer whenever `generateNonExecutableJson` is enabled, so all writer-based entry points inherit the prefix consistently.

#### REQ-007: Gson readers must tolerate the non-executable prefix in the default Gson parsing path
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:798-800`, `gson/src/main/java/com/google/gson/Gson.java:1067-1074`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:659-662`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:1832-1853`  
**Analysis:** default `Gson` readers start at `LEGACY_STRICT`, and `fromJson(JsonReader, ...)` upgrades that default to `LENIENT`. In lenient mode `JsonReader` explicitly consumes the XSSI prefix before parsing the first token, so prefixed payloads remain interoperable with default Gson consumers.

#### REQ-016: complete-value entry points must detect trailing data
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/Gson.java:978-983`, `gson/src/main/java/com/google/gson/Gson.java:1196-1205`  
**Analysis:** the `Reader` and `String` entry points call `assertFullConsumption(...)` after deserialization and reject any non-`END_DOCUMENT` trailing content with `JsonSyntaxException`.

#### REQ-023: reflection barriers must fail with actionable JsonIOException guidance
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:142-149`, `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:168-178`, `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:336-342`  
**Analysis:** blocked reflection paths fail explicitly and point callers toward registering a `TypeAdapter`, adjusting the access filter, or increasing visibility/opening access rather than degrading into partial binding.

#### REQ-026: object construction must follow stable fallback order before Unsafe
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:107-170`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:177-313`  
**Analysis:** construction order is instance creator -> special collection constructors -> accessible no-args constructor -> default collection/map implementation -> instantiability check -> Unsafe. The fallback sequence matches the documented preference order.

#### REQ-027: disableJdkUnsafe must fail fast when no safe instantiation path exists
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/GsonBuilder.java:883-885`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:149-170`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:384-417`  
**Analysis:** `disableJdkUnsafe()` flips the builder flag, and the constructor path then returns a throwing constructor with explicit remediation text instead of allocating through `Unsafe`.

#### REQ-033: Map deserialization must reject duplicate keys in object and array-of-entry forms
**Status:** VIOLATED  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:191-206`, `gson/src/test/java/com/google/gson/functional/MapTest.java:690-693`, `gson/src/test/java/com/google/gson/functional/MapAsArrayTypeAdapterTest.java:74-80`  
**Analysis:** the code only throws when `map.put(...)` returns a non-`null` previous value. Existing tests cover only duplicates whose first value is non-`null`, so `{"a":null,"a":1}` and `[[[1],null],[[1],"x"]]` are silently accepted even though the requirement says duplicates must be rejected in both encodings.  
**Severity:** High

#### REQ-037: TypeToken construction must reject raw tokens and captured type variables
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/reflect/TypeToken.java:95-118`, `gson/src/main/java/com/google/gson/reflect/TypeToken.java:121-157`  
**Analysis:** direct-subclass enforcement rejects raw `TypeToken` usage, and `verifyNoTypeVariable(...)` recursively rejects captured type variables with targeted remediation guidance.

#### REQ-038: TypeToken.getParameterized(...) must validate arity and bounds
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/reflect/TypeToken.java:385-443`  
**Analysis:** the factory verifies `rawType` is a `Class`, checks the exact type-argument count, rejects owner-type-dependent raw types, and enforces declared bounds before creating the token.

#### REQ-046: parent deserializers must not change subclass serialization
**Status:** SATISFIED  
**Evidence:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java:52-71`  
**Analysis:** when the declared-type adapter is custom and the runtime-type adapter is only reflective, serialization keeps the declared custom adapter rather than letting reflective runtime dispatch amputate subclass behavior. That is the intended guard against the historical parent-deserializer regression.

## Pass 3: Cross-Requirement Consistency

#### Shared Concept: XSSI prefix interoperability
**Requirements:** REQ-006, REQ-007  
**What REQ-006 claims:** prefixed output must be emitted consistently when enabled.  
**What REQ-007 claims:** default Gson readers must still accept prefixed payloads.  
**Consistency:** CONSISTENT  
**Code evidence:** `gson/src/main/java/com/google/gson/Gson.java:774-783`, `gson/src/main/java/com/google/gson/Gson.java:1067-1074`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:659-662`, `gson/src/main/java/com/google/gson/stream/JsonReader.java:1832-1853`  
**Analysis:** the writer and reader halves are still coupled correctly: emitted prefixes are always present, and the default Gson read path intentionally lands in the lenient branch that strips them.

#### Shared Concept: constructor fallback versus unsafe disablement
**Requirements:** REQ-026, REQ-027, REQ-028  
**What REQ-026 claims:** construction falls through stable safe paths before Unsafe.  
**What REQ-027 claims:** disabling Unsafe must fail fast with guidance.  
**What REQ-028 claims:** non-instantiable types must never go through Unsafe.  
**Consistency:** CONSISTENT  
**Code evidence:** `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:142-170`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:384-417`, `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java:66-89`  
**Analysis:** the implementation checks instantiability before Unsafe, refuses Unsafe when disabled, and routes all such cases to throwing constructors with explicit messages.

#### Shared Concept: tree-model replacement versus typed-map duplicate rejection
**Requirements:** REQ-031, REQ-033  
**What REQ-031 claims:** `JsonObject` replacement semantics are last-writer-wins.  
**What REQ-033 claims:** typed `Map` binding must reject duplicate keys.  
**Consistency:** INCONSISTENT  
**Code evidence:** `gson/src/main/java/com/google/gson/JsonObject.java:69-71`, `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:191-206`  
**Analysis:** the intended split is explicit in the codebase, but `MapTypeAdapterFactory` currently collapses to last-writer-wins whenever the earlier mapped value was `null`. That makes typed-map deserialization behave like tree replacement for a subset of duplicates instead of preserving the documented distinction.  
**Impact:** callers can lose the only protection they have against duplicate-key corruption precisely in the JSON cases that also use `null` as a meaningful value.

#### Shared Concept: custom null handling paths
**Requirements:** REQ-044, REQ-045  
**What REQ-044 claims:** serializer/deserializer registrations are null-safe by default and bypass custom code for nulls.  
**What REQ-045 claims:** per-type null semantics require an adapter path that controls the active writer directly.  
**Consistency:** CONSISTENT  
**Code evidence:** `gson/src/main/java/com/google/gson/GsonBuilder.java:724-728`, `gson/src/main/java/com/google/gson/GsonBuilder.java:759-767`, `gson/src/main/java/com/google/gson/internal/bind/JsonAdapterAnnotationTypeAdapterFactory.java:114-159`  
**Analysis:** builder registrations and `@JsonAdapter` handling both preserve the rule that tree-style serializers/deserializers are null-safe unless callers explicitly opt into a non-null-safe adapter path.

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1 | `MapTypeAdapterFactory` silently accepts duplicate keys when the earlier value is `null` | High | BUG |
| Pass 1 | Complex-map-key writing can still emit non-round-trippable duplicate member names for colliding primitive key renderings | Medium | INCOMPLETE |
| Pass 2 | REQ-033 duplicate-key rejection is violated for null-valued duplicates | High | VIOLATED |
| Pass 3 | REQ-031 vs REQ-033 distinction collapses for null-valued duplicate map entries | High | INCONSISTENT |

- **Total findings by pass:** Pass 1 = 2, Pass 2 = 1 violated, Pass 3 = 1 inconsistent
- **Highest-risk subsystem touched:** collections / map binding
- **Overall assessment:** **FIX FIRST**

## Regression tests for confirmed bugs

Recommended additions:

1. `MapTest`: assert `gson.fromJson("{\"a\":null,\"a\":1}", new TypeToken<Map<String, Object>>() {})` throws `JsonSyntaxException("duplicate key: a")`.
2. `MapAsArrayTypeAdapterTest`: assert `gson.fromJson("[[[1],null],[[1],\"x\"]]", new TypeToken<Map<List<Integer>, String>>() {})` throws `JsonSyntaxException`.
3. `MapAsArrayTypeAdapterTest`: un-ignore and complete `testTwoTypesCollapseToOneSerialize()` so `enableComplexMapKeySerialization()` does not emit duplicate member names for colliding primitive key renderings.
