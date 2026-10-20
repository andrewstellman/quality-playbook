# Quality Constitution: Gson

## Purpose

Gson’s quality bar is not “the tests pass.” It is **fitness for reliable JSON interchange across hostile and diverse Java environments**: plain JVM applications, JPMS modules, Android shrinkers, and custom adapter stacks. A change is high quality only if it preserves wire-format expectations, keeps reflection-based binding predictable, and fails loudly when callers cross an unsupported boundary.

- **Deming** — quality must be built into the context files and playbook, because Gson’s most expensive failures are not local implementation slips but subtle contract drift: a field suddenly omitted, a type token silently losing generic information, or a reflective fallback crossing a module boundary.
- **Juran** — fitness for use means callers can serialize and deserialize real model objects, maps, and streams without getting plausible-but-wrong output. A `List.class` that yields `LinkedTreeMap` elements, a class instantiated via `Unsafe` with zeroed defaults, or a malformed JSON document accepted in lenient mode all violate fitness even when no compile error occurs.
- **Crosby** — building these safeguards up front is cheaper than debugging production-only failures in obfuscated Android builds, JPMS module access errors, or downstream `ClassCastException`s caused by erased types.

## Coverage Targets

| Subsystem | Target | Why |
|-----------|--------|-----|
| Reflective binding and object construction | 92-95% | This is where unsupported classes degrade into `null`, `Unsafe` bypasses field initializers, and module-access failures surface only at runtime. The failure modes are silent or late. |
| Streaming parser and writer | 90-93% | `JsonReader` is a hand-written parser state machine with lenient/strict branches, path tracking, and nesting limits. Small regressions here cascade into misparsed documents and weak diagnostics. |
| Core API and builder configuration | 85-90% | Builder snapshotting, adapter precedence, and writer/reader configuration are cross-cutting contracts that shape every downstream adapter path. Drift here changes library-wide behavior. |
| Collections, maps, tree model, and type metadata | 85-90% | Duplicate key handling, `LinkedTreeMap` defaults, complex map-key round-tripping, and `TypeToken` validation all guard against plausible-but-wrong data structures. |
| Compatibility modules (JPMS, shrinker, native-image) | 80-85% | These are environment-sensitive edges rather than the core happy path, but they are exactly where reflection-heavy libraries fail in production-only deployments. |

## Coverage Theater Prevention

Fake confidence looks like this in Gson:

- Asserting `toJson()` returns a non-empty string without checking the exact JSON shape, field omission rules, or prefix behavior.
- Deserializing into `List.class` or `Map.class` and only checking collection size instead of checking the runtime element types.
- Testing that an exception was thrown without checking the message content when the message contains the only actionable remediation (`TypeToken`, `opens`, `disableJdkUnsafe`, `@SerializedName`).
- Verifying only one side of a round trip for maps with complex keys, which misses the “serializes fine but cannot deserialize back” failure mode.
- Using only synthetically perfect POJOs with public no-args constructors, which hides the real risks in inner classes, anonymous classes, inaccessible JDK implementations, and constructor-less immutable types.
- Claiming strict JSON coverage while every parser test runs through lenient/default settings.

## Fitness-to-Purpose Scenarios

### Scenario 1: Constructor Bypass Amnesia

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 87-99]

**What happened:** Gson’s object construction path in `ConstructorConstructor` keeps walking after instance creators, special collections, and no-args constructors, and can eventually fall back to `Unsafe` (`ConstructorConstructor.java` lines 107-170). That path creates an object without running field initializers or constructors. For a model that encodes defaults as part of object identity, the JSON looks valid, deserialization “works,” and only much later does a missing default surface as a wrong business value instead of an error.

**The requirement:** When a type has no safe instantiation path, Gson must either preserve constructor-driven defaults or fail loudly if `disableJdkUnsafe()` is enabled; it must not silently fabricate a zero-initialized object while pretending nothing changed.

**How to verify:** Run `FunctionalTest.testScenarioConstructorBypassAmnesiaFailsFastWhenUnsafeIsDisabled` and confirm it fails with a `JsonIOException` that explains how to restore a valid construction path.

---

### Scenario 2: Type Erasure Produces Imposter Objects

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 8-26]

**What happened:** Gson’s public API documentation explicitly warns that raw collection targets lose element-type information, and `TypeToken` exists to restore it (`Gson.java` lines 68-87, `TypeToken.java` lines 35-48). In practice, `fromJson(..., List.class)` can return a list whose elements are `LinkedTreeMap`, not the domain class the caller mentally expected. The output shape looks “close enough” until a downstream cast or field access explodes.

**The requirement:** Raw collection deserialization must never masquerade as typed domain binding; callers must supply a parameterized `TypeToken` if they want typed elements.

**How to verify:** Run `FunctionalTest.testScenarioTypeErasureProducesGenericElementsForRawCollections` and assert the first element is a `LinkedTreeMap`, not a `SamplePojo`.

---

### Scenario 3: Duplicate Key Split-Brain

**Requirement tag:** [Req: inferred — from `JsonObject.add()` and `MapTypeAdapterFactory.Adapter.read()`]

**What happened:** Gson has two object-like worlds. The tree model’s `JsonObject.add()` simply overwrites an existing member (`JsonObject.java` lines 69-71). The map adapter rejects duplicate keys with `JsonSyntaxException` (`MapTypeAdapterFactory.java` lines 191-207). That asymmetry means the same conceptual JSON object can be “last writer wins” in one code path and “hard failure” in another, which matters when code mixes tree manipulation with typed map deserialization.

**The requirement:** Duplicate-name semantics must be intentional, documented, and tested at the boundary where callers choose tree-model APIs versus typed `Map` binding.

**How to verify:** Run `FunctionalTest.testScenarioDuplicateKeySplitBrainBetweenTreeAndMapApis` and check that `JsonObject` replacement and `Map` duplicate-key rejection both occur exactly as documented.

---

### Scenario 4: Complex Map Keys Lose Reversibility

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 113-119]

**What happened:** When `complexMapKeySerialization` is disabled, `MapTypeAdapterFactory` converts map keys to member names using `String.valueOf(key)` (`MapTypeAdapterFactory.java` lines 221-227). That is fine for primitive keys and catastrophic for structured keys. A `Point(5,5)` key serializes into a plausible JSON object member name, but the structure needed to deserialize it back is gone unless Gson switches to the array-of-entry wire format.

**The requirement:** Reversible serialization of non-primitive map keys requires explicit opt-in via `enableComplexMapKeySerialization()`, and the reversible format must be covered by tests.

**How to verify:** Run `FunctionalTest.testScenarioComplexMapKeysRoundTripOnlyWithExplicitOptIn` and check both the emitted JSON shape and successful deserialization.

---

### Scenario 5: Lenient Parser Accepts Broken Inputs by Default

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 154-165]

**What happened:** Gson keeps a legacy-lenient parsing path for compatibility. That means comments, single quotes, and other non-RFC forms can make it through a default pipeline even though callers may assume “JSON parser” means standards enforcement. The bad part is not that leniency exists; it is that malformed input can look accepted and normal until a stricter downstream system rejects the same payload.

**The requirement:** Strictness mode must be explicit in tests and reviews. Anything relying on malformed JSON acceptance must declare leniency; anything claiming RFC behavior must prove strict parsing.

**How to verify:** Run `FunctionalTest.testScenarioLenientParsingMustBeExplicit` and confirm lenient mode accepts commented JSON while strict mode rejects it.

---

### Scenario 6: Local Classes Collapse to Null

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 100-112]

**What happened:** `ReflectiveTypeAdapterFactory` short-circuits anonymous and non-static local classes into an adapter that reads and writes `null` (`ReflectiveTypeAdapterFactory.java` lines 117-139). This protects callers from unstable synthetic-field binding, but it also means a model can disappear into JSON `null` without any field-level indication of what was lost.

**The requirement:** Unsupported local or anonymous classes must be treated as explicitly unsupported by tests and reviews; they must never look like successfully serialized ordinary objects.

**How to verify:** Run `FunctionalTest.testScenarioLocalClassesCollapseToNull` and assert both serialization and deserialization resolve to `null`.

---

### Scenario 7: Module Walls Stop Reflection Cold

**Requirement tag:** [Req: formal — `Troubleshooting.md` lines 28-63]

**What happened:** Modern JVMs do not let Gson walk into sealed or unopened modules just because reflection used to work on older releases. `ReflectiveTypeAdapterFactory` and the reflection-access helpers now fail with an actionable `JsonIOException`, and `ReflectionAccessTest` verifies that behavior. Without that explicit failure, callers would get environment-dependent partial binding or internal-field leakage.

**The requirement:** Reflection barriers must fail loudly with remediation guidance (`opens`, custom adapter, or access filter changes) instead of degrading into partial objects.

**How to verify:** Run `FunctionalTest.testScenarioReflectionBarriersFailWithActionableMessages` and confirm the thrown message references the troubleshooting guidance.

---

### Scenario 8: Cycles Still Look Like Trees Until the Stack Dies

**Requirement tag:** [Req: inferred — from `CircularReferenceTest`]

**What happened:** Gson’s reflective serializer traverses object graphs recursively. It ignores the trivial self-reference where a field points directly back to the same source object (`ReflectiveTypeAdapterFactory.java` lines 246-249), but general object cycles still recurse until the stack overflows (`CircularReferenceTest.java` lines 50-110). On a real domain model, this can look fine in small acyclic fixtures and then fail catastrophically when two shared objects point at each other.

**The requirement:** Reviews and tests must distinguish self-reference elision from general cycle handling; no one should claim “Gson handles cycles” based on the special-case self-reference guard alone.

**How to verify:** Run `FunctionalTest.testScenarioCircularGraphsStillOverflow` and confirm the root cause is a `StackOverflowError`.

---

### Scenario 9: Obfuscation Renames the Contract Out from Under You

**Requirement tag:** [Req: formal — `README.md` lines 15-20]

**What happened:** Gson binds JSON to runtime field names. On Android or any shrinker-driven build, those names can become `a`, `b`, and `c` unless callers keep them or pin aliases with `@SerializedName` (`Troubleshooting.md` lines 65-85). The JSON still parses; it just binds to the wrong names or fails across app versions, which is a compatibility bug, not a syntax bug.

**The requirement:** Android and shrinker-sensitive deployments must treat runtime field names and generic signatures as part of the wire contract, with tests and build configuration proving they survive release builds.

**How to verify:** Run `FunctionalTest.testScenarioObfuscationCompatibleAliasesKeepOlderPayloadsReadable` for the alias contract, then follow `RUN_INTEGRATION_TESTS.md` Group 3 to verify the actual shrinker module preserves names or aliases in a release-like build.

---

### Scenario 10: XSSI Prefix Protection Must Survive Mixed Producers and Consumers

**Requirement tag:** [Req: inferred — from `SecurityTest`]

**What happened:** `generateNonExecutableJson()` changes the serialized wire format, but `SecurityTest` also proves that a normal `Gson` reader can still consume the prefixed payload (`SecurityTest.java` lines 53-101). If writer and reader compatibility drift apart, one service can “secure” its output and instantly break another service that still uses default parsing.

**The requirement:** Prefix generation and prefix consumption are a coupled interoperability contract, not a one-sided writer feature.

**How to verify:** Run `FunctionalTest.testScenarioXssiPrefixRemainsReadableAcrossConfigurations` and assert both prefixed output and successful prefixed input consumption.

---

### Scenario 11: Null Policies Only Work When the Adapter Path Actually Sees Null

**Requirement tag:** [Req: formal — `TypeAdapter.java` and `JsonAdapter.java` Javadoc; issues #913 and #948]

**What happened:** Gson exposes multiple customization layers for null handling, but they are not equivalent. `JsonSerializer` and `JsonDeserializer` registrations are wrapped null-safe (`GsonBuilder.java` lines 724-728, 759-767), so they never see Java `null` or JSON `null`. Field-level `@JsonAdapter` is also null-safe by default unless `nullSafe = false` is set (`JsonAdapter.java` lines 90-92, 127-134). That means a team can believe it implemented “required-nullable” or per-type null semantics while the outer writer still strips the field or bypasses the custom handler entirely.

**The requirement:** Any behavior that distinguishes omitted fields, explicit JSON `null`, and custom null sentinels must opt into an adapter path that actually receives null values, and tests must prove both the bypass path and the opt-in path.

**How to verify:** Run `FunctionalTest.testScenarioCustomNullPoliciesNeedExplicitOptIn` and confirm the wrapped serializer does not observe `null`, while `@JsonAdapter(nullSafe = false)` can.

---

### Scenario 12: Parent Deserializers Must Not Amputate Subclass Output

**Requirement tag:** [Req: formal — `CHANGELOG.md` version 2.10; issue #2032]

**What happened:** Gson previously had a real regression where registering a custom deserializer for a parent type changed how subclasses serialized, dropping subclass-only fields because runtime-type serialization reused the parent adapter (`CHANGELOG.md` lines 15-18; issue #2032). In a polymorphic model this is especially dangerous: the JSON stays valid, only the most specific data disappears, and downstream systems see a plausible but incomplete object.

**The requirement:** A custom deserializer registered for a parent type must not change serialization of subclass instances; runtime-type serialization still has to emit subclass fields unless a serializer explicitly overrides them.

**How to verify:** Run `FunctionalTest.testScenarioParentDeserializerDoesNotAmputateSubclassSerialization` and assert the serialized JSON still includes the subclass fields.

## AI Session Quality Discipline

1. Read `quality/QUALITY.md` and `quality/REQUIREMENTS.md` before editing Gson code.
2. Treat `ReflectiveTypeAdapterFactory`, `ConstructorConstructor`, `JsonReader`, and map/type-token logic as the first files to inspect for correctness-sensitive changes.
3. Add or update tests for any change that affects wire format, reflection access, instantiation behavior, or parsing mode.
4. Use exact JSON assertions for serialization changes; do not settle for “contains” checks when order or omission semantics matter.
5. For generic-type changes, test both the typed `TypeToken` path and the raw-type failure/degradation path.
6. Update this file when a new production-facing failure mode or environment boundary is discovered.
7. Never remove a fitness scenario; extend the constitution instead.

## The Human Gate

- Backward-compatibility decisions around duplicate-key semantics between tree APIs and typed map binding.
- Whether a change should tighten default parsing behavior versus preserving legacy leniency.
- Platform-support policy choices for Android shrinkers, JPMS, and GraalVM native-image.
- Performance tradeoffs for very large payloads, deep nesting, or adapter-cache behavior.
- API ergonomics for future public surface changes, especially around reflection limits and generic-type guidance.
