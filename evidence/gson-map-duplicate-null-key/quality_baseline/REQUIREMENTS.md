# Behavioral Requirements: Gson

## Derivation and verification notes

- **Intent sources reviewed:** `README.md`, `UserGuide.md`, `Troubleshooting.md`, `GsonDesignDocument.md`, core Javadocs, and representative tests under `gson/src/test/java/`.
- **Requirement verification:** Each requirement below was checked for clarity, behavioral focus, testability, consistency with neighboring requirements, and presence of a rationale, matching the Step 7c inspection checklist in the skill.
- **Confidence tags:** `formal` requirements come from user-facing docs or public API documentation. `inferred` requirements come from defensive code, tests, and implementation constraints that are stable enough to guide review.

## Subsystem 1: Core API and configuration surface

### Category: operational contracts

**REQ-001** — [Req: formal — `Gson.java` lines 50-57; `UserGuide.md` lines 69-74]  
Summary: A `Gson` instance must be reusable across multiple serialization and deserialization calls, including concurrent callers, without leaking per-call adapter resolution state between operations.  
Rationale: Gson’s adapter cache and thread-local recursion guards exist to prevent reentrant lookup corruption; if reuse were unsafe, one caller could observe another caller’s incomplete adapter graph or partially resolved type state.  
References: `gson/src/main/java/com/google/gson/Gson.java`:50-57, 139-155, 222-257; `gson/src/test/java/com/google/gson/GsonTest.java`:164-231.  
Specificity: specific

**REQ-002** — [Req: inferred — from `GsonBuilderTest.testModificationAfterCreate()`]  
Summary: Once `GsonBuilder.create()` returns a `Gson` instance, later mutations to that builder must not change the behavior of the already-created `Gson`.  
Rationale: Builders are used to snapshot configuration. If existing `Gson` objects observed later builder changes, registration order, adapter precedence, and instance creation behavior would become nondeterministic across threads and test runs.  
References: `gson/src/test/java/com/google/gson/GsonBuilderTest.java`:68-133; `gson/src/main/java/com/google/gson/Gson.java`:226-255.  
Specificity: specific

**REQ-003** — [Req: formal — `Gson.java` lines 183-220; `README.md` lines 22-27]  
Summary: The default `new Gson()` configuration must produce compact JSON, omit `null` object fields, and apply the library’s default field naming, exclusion, and date handling rules unless explicitly overridden by `GsonBuilder`.  
Rationale: The zero-configuration API is the contract most callers depend on. Silent drift here changes wire format for every consumer using the simplest entry point.  
References: `gson/src/main/java/com/google/gson/Gson.java`:183-220, 222-224; `README.md`:22-27; `UserGuide.md`:151-157.  
Specificity: specific

### Category: error handling contracts

**REQ-004** — [Req: formal — `UserGuide.md` lines 154-156; `Troubleshooting.md` lines 226-235]  
Summary: When `serializeNulls()` is not enabled, `null` object fields must be omitted from emitted JSON; when `serializeNulls()` is enabled, those fields must be written as explicit JSON `null` values.  
Rationale: Null omission versus explicit `null` is a wire-format decision, not an implementation detail. If the toggle is ignored, consumers can misread “unset” as “deliberately null,” or vice versa.  
References: `gson/src/main/java/com/google/gson/Gson.java`:193-197; `gson/src/test/java/com/google/gson/functional/MapTest.java`:114-142; `Troubleshooting.md`:226-235.  
Specificity: specific

**REQ-005** — [Req: inferred — from `GsonTest.testFromJson_WrongResultType()`]  
Summary: If a registered type adapter returns a result whose runtime type is incompatible with the requested target type, Gson must fail immediately with an actionable type-mismatch exception instead of silently returning the wrong object.  
Rationale: A misregistered adapter can otherwise create correctness bugs far from the call site. Failing fast preserves type-safety at the library boundary.  
References: `gson/src/test/java/com/google/gson/GsonTest.java`:100-153; `gson/src/main/java/com/google/gson/Gson.java`:771-788.  
Specificity: specific

### Category: security policy propagation

**REQ-006** — [Req: formal — `SecurityTest.java` lines 32-65]  
Summary: When `generateNonExecutableJson()` is enabled, every JSON document written through that `Gson` instance must be prefixed with the non-executable token `)]}'\n`.  
Rationale: The prefix is a deliberate XSSI defense. If it is applied inconsistently, callers can believe output is protected while some endpoints still emit executable JSON.  
References: `gson/src/test/java/com/google/gson/functional/SecurityTest.java`:32-65; `gson/src/main/java/com/google/gson/Gson.java`:137, 167, 232, 193-220.  
Specificity: specific

**REQ-007** — [Req: inferred — from `SecurityTest` and `JsonReader` behavior]  
Summary: Gson deserialization must tolerate the non-executable prefix on input for the default parser mode used by `Gson`, regardless of whether the writer-side prefix option was enabled when the input was produced.  
Rationale: The producer and consumer settings can differ across services. If readers only accepted the prefix when locally configured to emit it, prefixed payloads would become incompatible across otherwise valid Gson clients.  
References: `gson/src/test/java/com/google/gson/functional/SecurityTest.java`:53-101; `gson/src/main/java/com/google/gson/stream/JsonReader.java`:193-203; `gson/src/main/java/com/google/gson/Gson.java`:92-128.  
Specificity: specific

### Category: API contracts and wire-format constraints

**REQ-008** — [Req: formal — `UserGuide.md` lines 68-87; `TypeToken.java` lines 35-48]  
Summary: Deserializing parameterized types must require the caller to provide an explicit `Type` or `TypeToken`; Gson must not pretend that a raw `Class` target preserves generic element types.  
Rationale: Java erasure removes element-type information at runtime. Treating raw collection classes as if they were typed would create plausible-looking but wrong object graphs that fail later with `ClassCastException`.  
References: `gson/src/main/java/com/google/gson/Gson.java`:68-87; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`:35-48; `Troubleshooting.md`:19-23.  
Specificity: specific

**REQ-009** — [Req: inferred — from `GsonBuilderTest` and `Gson.java` strictness docs]  
Summary: Builder-level leniency or strictness configuration must propagate to the `JsonReader` and `JsonWriter` instances created by that `Gson`, so parsing and writing follow the same configured mode.  
Rationale: A partially applied parser mode is dangerous: callers may think they are operating strictly while only half the pipeline enforces it.  
References: `gson/src/test/java/com/google/gson/GsonBuilderTest.java`:219-249; `gson/src/main/java/com/google/gson/Gson.java`:92-128; `gson/src/main/java/com/google/gson/stream/JsonReader.java`:67-72.  
Specificity: specific

## Subsystem 2: Streaming parser and writer

### Category: API contracts and wire-format constraints

**REQ-010** — [Req: formal — `JsonReader.java` lines 30-63]  
Summary: `JsonReader` must expose JSON as a depth-first token stream with explicit begin/end boundaries for arrays and objects, so callers can consume nested structures deterministically.  
Rationale: Gson’s streaming API is the foundation for custom adapters and low-allocation parsing. If token order or boundary semantics drift, every hand-written adapter becomes fragile.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:30-63, 117-180.  
Specificity: specific

**REQ-011** — [Req: formal — `JsonReader.java` lines 58-63]  
Summary: When callers encounter unknown names or unsupported subtrees, `skipValue()` must skip the entire nested value without leaving the reader in a corrupt state for the next token.  
Rationale: Gson’s documented model tolerates extra JSON members. If skipping fails to consume a whole subtree, later fields are misparsed and produce wrong objects that look structurally valid.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:58-63, 134-180; `GsonDesignDocument.md`:7-10.  
Specificity: specific

**REQ-012** — [Req: formal — `Troubleshooting.md` lines 121-145, 167-199]  
Summary: When JSON syntax or structure is invalid for the requested read operation, Gson must fail with an exception that includes accurate location context, including the path within the JSON document.  
Rationale: Parsing failures are usually not recoverable automatically; actionable location data is what makes malformed input diagnosable in production.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:30-72, 249-260; `Troubleshooting.md`:121-145, 167-199.  
Specificity: specific

### Category: input validation boundaries

**REQ-013** — [Req: formal — `GsonBuilderTest.testSetLenient()`; `LeniencyTest.java`]  
Summary: Lenient parsing mode may accept comments, single-quoted strings, and unquoted names, but those extensions must only be enabled when the parser mode explicitly allows them.  
Rationale: Leniency is an interoperability escape hatch. If non-standard JSON is accepted in strict mode, callers cannot rely on Gson to enforce RFC-conformant input.  
References: `gson/src/test/java/com/google/gson/GsonBuilderTest.java`:229-249; `gson/src/test/java/com/google/gson/functional/LeniencyTest.java`:28-49; `Troubleshooting.md`:154-165.  
Specificity: specific

**REQ-014** — [Req: inferred — from `JsonReader` configuration]  
Summary: Reader nesting depth must be bounded by the configured nesting limit, and overly deep documents must fail instead of exhausting the JVM stack or heap.  
Rationale: Gson processes attacker-controlled JSON in many deployments. Unbounded nesting is a classic parser denial-of-service vector.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:69-72, 252-256; `gson/src/test/java/com/google/gson/ObjectTypeAdapterTest.java` (deep nesting coverage); `gson/src/test/java/com/google/gson/JsonParserTest.java` (deep nesting coverage).  
Specificity: directional

**REQ-015** — [Req: formal — `JsonReader.java` lines 184-191]  
Summary: Numeric values must be readable both as JSON numbers and as strings when the caller requests numeric accessors, to minimize silent precision loss for large values crossing JavaScript-style numeric boundaries.  
Rationale: Many JSON producers stringify large numbers to preserve precision. If Gson refused those representations, interoperable payloads would break; if it coerced them eagerly, precision would be lost.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:184-191; `Troubleshooting.md`:146-153.  
Specificity: specific

### Category: operational contracts

**REQ-016** — [Req: formal — `Gson.java` lines 115-123]  
Summary: Deserialization entry points that claim to read a complete JSON value must detect trailing data after the target value, rather than silently accepting extra bytes as if the payload were fully consumed.  
Rationale: Trailing garbage often indicates protocol corruption, concatenated payloads, or injection. Accepting it as valid hides real framing bugs.  
References: `gson/src/main/java/com/google/gson/Gson.java`:113-123; `gson/src/test/java/com/google/gson/MixedStreamTest.java` (reader/writer interaction coverage).  
Specificity: directional

**REQ-017** — [Req: inferred — from `JsonWriter` configuration and Gson default docs]  
Summary: Writer-side null-field emission must follow the `Gson` configuration for every serialization path, including tree adapters and reflective fallback, so output is consistent no matter which adapter produced it.  
Rationale: Mixed adapter stacks are common. If one path writes `null` members and another omits them under the same `Gson`, the same model can emit two incompatible wire formats.  
References: `gson/src/main/java/com/google/gson/Gson.java`:193-197, 232-246; `gson/src/main/java/com/google/gson/stream/JsonWriter.java` (`serializeNulls` state); `gson/src/test/java/com/google/gson/functional/MapTest.java`:114-142.  
Specificity: directional

**REQ-018** — [Req: inferred — from `JsonReader` parser state machine]  
Summary: Reader state transitions for arrays, objects, and dangling names must remain internally consistent across `begin*`, `end*`, `next*`, and `skipValue()` operations, so a valid stream cannot be reclassified as malformed by prior token handling.  
Rationale: `JsonReader` is effectively a hand-written state machine. A single bad transition produces cascading parse failures well after the actual bug site.  
References: `gson/src/main/java/com/google/gson/stream/JsonReader.java`:214-247, 249-260; `gson/src/main/java/com/google/gson/stream/JsonScope.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderPathTest.java`.  
Specificity: directional

## Subsystem 3: Reflective binding and object construction

### Category: data integrity and consistency

**REQ-019** — [Req: formal — `GsonDesignDocument.md` lines 31-35; `UserGuide.md` lines 149-159]  
Summary: Reflection-based object mapping must use eligible fields, not JavaBean getters, and it must include inherited non-static, non-transient, non-synthetic fields unless an exclusion rule says otherwise.  
Rationale: Gson’s core value proposition is field-based mapping for unmodifiable classes. Switching to property-based behavior would silently change both wire format and supported model classes.  
References: `GsonDesignDocument.md`:31-35; `UserGuide.md`:149-159; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:80-107.  
Specificity: specific

**REQ-020** — [Req: formal — `UserGuide.md` lines 154-157]  
Summary: During deserialization, JSON members that are absent must leave Java fields at their normal default values (`null`, `0`, `false`, etc.) rather than inventing synthetic placeholder data.  
Rationale: Missing-field semantics are part of Gson’s compatibility model. If absent data were materialized differently, version-skewed payloads would deserialize unpredictably.  
References: `UserGuide.md`:154-157; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:269-283.  
Specificity: specific

### Category: error handling contracts

**REQ-021** — [Req: formal — `Troubleshooting.md` lines 100-112; `ReflectiveTypeAdapterFactory.java` lines 117-139]  
Summary: Anonymous classes and non-static local classes must not be reflectively serialized as ordinary objects; Gson must treat them as unsupported and serialize/deserialize them as `null`.  
Rationale: Captured outer state and synthetic fields make these classes unstable reflection targets. Pretending they are ordinary POJOs would leak implementation details and produce nonportable JSON.  
References: `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:117-139; `Troubleshooting.md`:100-112; `UserGuide.md`:157-160.  
Specificity: specific

**REQ-022** — [Req: formal — `UserGuide.md` lines 161-198]  
Summary: Pure inner classes without an enclosing-instance constructor path must not be auto-deserialized; callers must either make them static or register an `InstanceCreator` that provides the containing instance.  
Rationale: Inner classes require an outer object reference that Gson cannot infer from JSON. Auto-instantiating them would create half-constructed objects or bind them to the wrong owner.  
References: `UserGuide.md`:161-198; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`:107-169.  
Specificity: specific

**REQ-023** — [Req: formal — `Troubleshooting.md` lines 28-63]  
Summary: When reflection is blocked by JPMS or an installed `ReflectionAccessFilter`, Gson must fail with an actionable `JsonIOException` that tells callers to open modules, register a custom adapter, or adjust the filter.  
Rationale: Reflection failures are environment-sensitive and hard to diagnose from a generic `IllegalAccessException`. The library needs to surface remediation steps, not just the low-level failure.  
References: `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:142-178; `gson/src/test/java/com/google/gson/functional/ReflectionAccessTest.java`:114-172; `Troubleshooting.md`:28-63.  
Specificity: specific

**REQ-024** — [Req: formal — `Troubleshooting.md` duplicate-fields section; `ReflectiveTypeAdapterFactory.java` lines 302-315]  
Summary: If two Java fields in the reflective binding hierarchy resolve to the same JSON member name, Gson must reject the type definition instead of picking one field implicitly.  
Rationale: Duplicate field-name resolution is ambiguous and produces silent data corruption if one field wins by accident.  
References: `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:302-315; `Troubleshooting.md` duplicate-fields section.  
Specificity: specific

**REQ-025** — [Req: inferred — from `ReflectiveTypeAdapterFactory` defensive code]  
Summary: Deserialization must never write JSON values into `static final` fields; encountering such a target must fail explicitly.  
Rationale: Mutating `static final` state violates JVM rules and turns one document parse into a process-wide side effect.  
References: `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:271-283.  
Specificity: specific

### Category: resource lifecycle

**REQ-026** — [Req: formal — `GsonDesignDocument.md` lines 25-30]  
Summary: Object construction must follow a stable preference order: registered `InstanceCreator`, special collection constructors, accessible no-args constructors, safe default implementations for collection interfaces, and only then JDK `Unsafe` when allowed.  
Rationale: Construction order determines whether model invariants and collection semantics survive deserialization. Skipping ahead to `Unsafe` or ad hoc defaults breaks caller expectations.  
References: `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`:107-170, 177-214, 217-313; `GsonDesignDocument.md`:25-30.  
Specificity: specific

**REQ-027** — [Req: formal — `Troubleshooting.md` lines 87-99; `GsonBuilderTest.java` lines 188-202]  
Summary: When `disableJdkUnsafe()` is enabled and a class has no usable instantiation path, Gson must fail immediately with a message that tells callers how to restore valid construction.  
Rationale: The point of disabling `Unsafe` is to surface model-construction bugs early. Falling back silently would defeat the safeguard.  
References: `gson/src/test/java/com/google/gson/GsonBuilderTest.java`:188-207; `Troubleshooting.md`:87-99; `gson/src/main/java/com/google/gson/GsonBuilder.java` (`disableJdkUnsafe`).  
Specificity: specific

**REQ-028** — [Req: inferred — from `UnsafeAllocatorInstantiationTest` and `ConstructorConstructor.checkInstantiable()`]  
Summary: Interfaces and abstract classes must never be instantiated through the unsafe allocation path; Gson must reject them as non-instantiable targets.  
Rationale: Producing instances for non-instantiable types would violate Java’s type model and create objects that no real constructor could have produced.  
References: `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`:59-89, 142-170; `gson/src/test/java/com/google/gson/internal/UnsafeAllocatorInstantiationTest.java`:30-64.  
Specificity: specific

### Category: operational contracts

**REQ-029** — [Req: inferred — from `ReflectionAccessTest.testSerializeInternalImplementationObject()`]  
Summary: If the runtime object type is an inaccessible internal implementation but Gson has a supported adapter for the declared supertype, serialization must use the supertype contract; direct deserialization into the inaccessible implementation type must still fail.  
Rationale: This preserves usability for common JDK wrappers like `Collections.emptyList()` without encouraging callers to bind to brittle implementation classes.  
References: `gson/src/test/java/com/google/gson/functional/ReflectionAccessTest.java`:134-160; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:142-178.  
Specificity: specific

**REQ-030** — [Req: inferred — from `ReflectionAccessTest.testRestrictiveSecurityManager()`]  
Summary: A caller-provided custom type adapter must remain usable even when reflective member access is unavailable, so explicit adapters can replace blocked reflection paths.  
Rationale: Security managers, filters, and JPMS restrictions intentionally disable reflection. Custom adapters are the escape hatch that keeps Gson usable in those environments.  
References: `gson/src/test/java/com/google/gson/functional/ReflectionAccessTest.java`:53-111; `gson/src/main/java/com/google/gson/internal/bind/JsonAdapterAnnotationTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java` registration APIs.  
Specificity: directional

## Subsystem 4: Collections, maps, tree model, and type metadata

### Category: data integrity and consistency

**REQ-031** — [Req: formal — `JsonObject.java` lines 25-29, 41-71]  
Summary: `JsonObject` must preserve member insertion order and normalize Java `null` values to `JsonNull.INSTANCE` rather than storing raw Java `null`.  
Rationale: Tree-model callers depend on deterministic member order for stable output and deep-copy behavior. Storing raw `null` would make the tree internally inconsistent with JSON semantics.  
References: `gson/src/main/java/com/google/gson/JsonObject.java`:25-29, 41-71, 130-138.  
Specificity: specific

**REQ-032** — [Req: inferred — from `JsonObject.add()` semantics]  
Summary: Adding a `JsonObject` member with a name that already exists must replace the prior value for that name instead of retaining multiple entries under the same key.  
Rationale: The tree model represents JSON objects as unique-member maps. If duplicate names were retained, later lookups and serialization order would become ambiguous.  
References: `gson/src/main/java/com/google/gson/JsonObject.java`:69-71, 176-188; `gson/src/test/java/com/google/gson/JsonObjectTest.java`.  
Specificity: specific

**REQ-033** — [Req: inferred — from `MapTypeAdapterFactory.Adapter.read()`]  
Summary: `Map` deserialization must reject duplicate keys, whether the map is represented as a JSON object or as the array-of-entry form used for complex keys.  
Rationale: Java `Map` semantics require one value per key. Silently keeping the last duplicate would hide upstream data corruption and make wire-format bugs nondeterministic.  
References: `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`:175-211; `gson/src/test/java/com/google/gson/functional/MapAsArrayTypeAdapterTest.java`:73-80.  
Specificity: specific

**REQ-034** — [Req: formal — `UserGuide.md` maps section; `MapTest.java` lines 145-166]  
Summary: When a Java map contains a `null` key and complex-map-key serialization is not enabled, Gson must encode that key as the JSON member name `"null"` and read it back as the string key `"null"`, not as a Java `null` key.  
Rationale: JSON object member names are strings only. Pretending a `null` key can round-trip as Java `null` would misstate what the wire format can represent.  
References: `gson/src/test/java/com/google/gson/functional/MapTest.java`:145-166; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`:221-259.  
Specificity: specific

**REQ-035** — [Req: formal — `UserGuide.md` maps section; `MapAsArrayTypeAdapterTest.java`]  
Summary: For non-primitive map keys, reversible round-tripping requires `enableComplexMapKeySerialization()` so Gson uses the array-of-entry wire format instead of `String.valueOf(key)`.  
Rationale: Stringifying arbitrary keys destroys structure. Without the alternate wire format, different keys can collapse to the same member name or become impossible to deserialize back to the original type.  
References: `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`:221-259; `gson/src/test/java/com/google/gson/functional/MapAsArrayTypeAdapterTest.java`:35-58, 83-98; `Troubleshooting.md`:113-119.  
Specificity: specific

**REQ-036** — [Req: inferred — from `MapTest` and `ConstructorConstructor` comments]  
Summary: Raw `Map` and `Map<String, ...>` deserialization must use Gson’s `LinkedTreeMap` safe default, while non-string-key maps and explicit concrete map types should use appropriate JDK implementations.  
Rationale: `LinkedTreeMap` preserves member order and avoids older-JDK hash-collision problems for the string-key case. Applying it too broadly would change declared type semantics for numeric-key and explicit-map targets.  
References: `gson/src/test/java/com/google/gson/functional/MapTest.java`:218-257; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`:287-313, 305-309.  
Specificity: specific

### Category: input validation boundaries

**REQ-037** — [Req: formal — `TypeToken.java` lines 40-48, 68-75, 121-157; `Troubleshooting.md` type-token sections]  
Summary: `TypeToken` construction must reject raw tokens and captured type variables, and the failure message must point callers toward preserving generic signatures or using `getParameterized(...)`.  
Rationale: Raw and type-variable-backed tokens create a false sense of type-safety that only fails later with runtime casts. Rejecting them at construction time prevents subtle misbinding.  
References: `gson/src/main/java/com/google/gson/reflect/TypeToken.java`:40-48, 68-75, 95-118, 121-157; `Troubleshooting.md` sections `type-token-raw` and `typetoken-type-variable`.  
Specificity: specific

**REQ-038** — [Req: inferred — from `TypeTokenTest.testParameterizedFactory_Invalid()`]  
Summary: `TypeToken.getParameterized(...)` must validate type-argument arity and bounds before producing a token, rejecting primitive arguments and out-of-bounds type substitutions.  
Rationale: Parameterized type tokens feed directly into adapter lookup and collection binding. Invalid tokens should fail where they are constructed, not later inside serialization.  
References: `gson/src/test/java/com/google/gson/reflect/TypeTokenTest.java`:182-260; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`:46-49.  
Specificity: specific

### Category: API contracts and wire-format constraints

**REQ-039** — [Req: formal — `Troubleshooting.md` lines 146-153; scenario coverage in number-policy tests]  
Summary: When callers deserialize JSON numbers as `Object` or `Number`, Gson must apply the configured `ToNumberStrategy` instead of always collapsing values to `double`.  
Rationale: Numeric strategy is the only way callers can preserve precision or choose `BigDecimal`/lazy parsing semantics for heterogeneous JSON.  
References: `Troubleshooting.md`:146-153; `gson/src/test/java/com/google/gson/functional/ToNumberPolicyFunctionalTest.java`; `gson/src/test/java/com/google/gson/ToNumberPolicyTest.java`.  
Specificity: specific

**REQ-040** — [Req: formal — `Troubleshooting.md` lines 8-26; `TypeToken.java` lines 35-48]  
Summary: If callers deserialize collections without concrete element types, Gson must materialize generic JSON representation types (such as `LinkedTreeMap`) rather than pretending to return domain objects of unknown type.  
Rationale: Unknown element types are a type-erasure limitation, not a best-effort guess problem. Returning generic JSON structures makes the loss of type information explicit.  
References: `Troubleshooting.md`:8-26; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`:35-48; `gson/src/test/java/com/google/gson/functional/CollectionTest.java`; `gson/src/test/java/com/google/gson/functional/MapTest.java`:218-257.  
Specificity: specific

## Subsystem 5: Platform and deployment boundaries

### Category: security policy propagation

**REQ-041** — [Req: formal — `Troubleshooting.md` lines 44-63]  
Summary: In JPMS deployments, any application package whose fields Gson must reflect on must be opened to `com.google.gson`; otherwise reflective binding must fail rather than bypass module boundaries.  
Rationale: Module openness is the explicit security contract for deep reflection. Ignoring it would break encapsulation; silently succeeding on some paths and not others would make production behavior environment-dependent.  
References: `Troubleshooting.md`:44-63; `test-jpms` module tests; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`:142-178.  
Specificity: directional

**REQ-042** — [Req: formal — `README.md` lines 15-20; `Troubleshooting.md` lines 65-85, 300+ ]  
Summary: Android and shrinker-driven deployments must preserve field names, generic signatures, and `TypeToken` metadata, or callers must supply explicit `@SerializedName` aliases that preserve backward compatibility across releases.  
Rationale: Gson’s reflection model depends on runtime names and generic metadata. Obfuscation that changes those names breaks both live parsing and compatibility with previously stored JSON.  
References: `README.md`:15-20; `Troubleshooting.md`:65-85, 300+; `test-shrinker` integration module.  
Specificity: directional

### Category: operational contracts

**REQ-043** — [Req: inferred — from `test-graal-native-image` and reflection-based design]  
Summary: Ahead-of-time builds that remove reflective metadata must predeclare any model types Gson is expected to instantiate reflectively; otherwise reflective serialization support is not guaranteed.  
Rationale: Native-image environments do not preserve arbitrary reflective reachability by default. Without explicit metadata, Gson’s normal fallback path disappears.  
References: `test-graal-native-image/`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`.  
Specificity: directional
