# Behavioral Requirements: Gson

## Derivation notes

- **Purpose summary:** Gson is a zero-dependency Java JSON library whose core promise is stable object-to-JSON and JSON-to-object conversion across reflective binding, streaming APIs, tree APIs, and custom adapters.
- **Primary source corpus:** `retrieved_documentation/official/*.md`, `retrieved_documentation/github_issues/*.md`, `retrieved_documentation/community/*.md`, and the existing `quality/REQUIREMENTS.md` baseline.
- **Derivation method:** Requirements were re-derived per subsystem, checked against the Step 7 inspection criteria, and expanded to include the behavioral contracts surfaced by troubleshooting guidance, GitHub issues, release notes, and community adapter usage patterns.
- **Scope note:** The corpus includes behavior introduced after older Gson releases; those newer contracts are still included because the requirement file is meant to capture the mature library's intended and expected behavior, including backward-compatibility constraints and known edge-case expectations.

## Subsystem 1: Core API, builder, and configuration surface

### Category: operational contracts

**REQ-001** — Thread-safe instance reuse  
- **Summary:** A `Gson` instance must be safely reusable across repeated and concurrent serialization and deserialization calls without leaking per-call adapter resolution state between operations.  
- **User story:** As an application developer, I want to share one configured `Gson` instance across threads so that JSON handling stays correct without extra synchronization or per-call construction.  
- **Implementation note:** This contract is carried by `Gson`, its adapter cache, and re-entrant adapter lookup guards; custom adapters can weaken it if they keep mutable shared state.  
- **Conditions of satisfaction:** Concurrent callers can invoke `toJson` and `fromJson` on the same instance; one call does not see another call's temporary resolution state; correctness does not depend on external locking.  
- **Alternative paths:** Callers may still create multiple `Gson` instances for configuration isolation, but correctness must not require one instance per thread or one instance per call.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0613_thread_safety.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-002** — Builder snapshots are immutable after creation  
- **Summary:** Once `GsonBuilder.create()` returns a `Gson`, later builder mutations must not change the behavior of the already-created instance.  
- **User story:** As a library integrator, I want builder configuration to be snapshotted at creation time so that later setup code cannot silently change a `Gson` instance already in use.  
- **Implementation note:** This is a builder lifecycle contract rather than a formatting detail; it protects adapter order, exclusion policy, and numeric or strictness settings from retroactive drift.  
- **Conditions of satisfaction:** Creating a `Gson` freezes the then-current builder state; later builder registrations or flag changes only affect newly created instances; previously created instances remain behaviorally stable.  
- **Alternative paths:** If callers need multiple variants, they may create multiple `Gson` instances or clone builders, but not mutate an already-built instance through shared builder state.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/Gson.java`; existing baseline coverage in prior `quality/REQUIREMENTS.md`  
- **Specificity rating:** specific

**REQ-003** — Default `new Gson()` behavior is stable  
- **Summary:** The default no-builder configuration must emit compact JSON, omit `null` object fields, escape HTML-sensitive characters, use identity field naming, exclude `static` and `transient` fields, and apply default date handling unless explicitly overridden.  
- **User story:** As a user taking the simplest entry point, I want `new Gson()` to have stable, documented defaults so that I can predict wire format without reading implementation code.  
- **Implementation note:** This is the most widely depended-on contract in the library; drift here changes output for all zero-configuration users.  
- **Conditions of satisfaction:** Default serialization omits `null` object members, preserves compact formatting, excludes `static` and `transient` fields, escapes HTML-sensitive characters, and uses documented defaults for dates and names.  
- **Alternative paths:** Callers may override any of these defaults with `GsonBuilder`, but the no-args constructor must remain predictable on its own.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

**REQ-004** — Configuration remains instance-local  
- **Summary:** Adapter registrations, exclusion rules, naming policies, numeric strategies, strictness, and formatting settings must apply only to the `Gson` instance that was configured with them.  
- **User story:** As an application maintainer, I want independent `Gson` instances to stay isolated so that framework defaults and app-specific overrides cannot bleed into each other.  
- **Implementation note:** This is especially important for troubleshooting cases where multiple frameworks or modules create their own `Gson` instances.  
- **Conditions of satisfaction:** A registration on one `GsonBuilder` affects only the instances built from that builder state; another independently created `Gson` keeps its own defaults or its own explicit configuration.  
- **Alternative paths:** Shared helper factories may centralize construction, but configuration isolation must still hold between distinct instances.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** directional

### Category: API contracts and wire-format constraints

**REQ-005** — Non-executable JSON prefix is written consistently  
- **Summary:** When `generateNonExecutableJson()` is enabled, every JSON document written through that `Gson` instance must be prefixed with `)]}'\n`.  
- **User story:** As a security-conscious service owner, I want the non-executable prefix to appear on every configured output so that clients do not get a false sense of XSSI protection.  
- **Implementation note:** This is a writer-side security policy and must not vary by entry point.  
- **Conditions of satisfaction:** All relevant `toJson` paths emit the prefix when enabled and omit it when not enabled; no supported serialization entry point silently skips the prefix.  
- **Alternative paths:** Callers may leave the feature disabled, but if enabled they should not need custom wrappers to get complete coverage.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-006** — Gson readers tolerate the non-executable prefix  
- **Summary:** Gson deserialization must accept input containing the non-executable JSON prefix, regardless of whether the local `Gson` instance is configured to emit that prefix.  
- **User story:** As a consumer of JSON from another Gson-based service, I want prefixed payloads to deserialize correctly so that producer and consumer settings can differ safely.  
- **Implementation note:** This is a cross-process interoperability requirement, not just a local symmetry rule.  
- **Conditions of satisfaction:** Prefixed JSON is accepted on normal read paths; the prefix is stripped before logical JSON parsing; readers that did not emit the prefix themselves can still consume it.  
- **Alternative paths:** Callers may strip the prefix manually, but built-in support should make that unnecessary in ordinary Gson-to-Gson communication.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-007** — Pretty printing changes formatting, not meaning  
- **Summary:** Pretty-printing configuration may change whitespace and layout, but it must not change the logical JSON value or inclusion rules for fields beyond the explicitly configured formatting settings.  
- **User story:** As a developer switching between compact and human-readable output, I want formatting choices to affect presentation only so that debugging and production payloads remain semantically equivalent.  
- **Implementation note:** This is a wire-format stability rule; whitespace is allowed to change, value semantics are not.  
- **Conditions of satisfaction:** Pretty-printed and compact output parse to the same JSON value for the same input object under the same non-formatting configuration.  
- **Alternative paths:** Callers may use compact output everywhere, but pretty printing must remain a safe readability toggle.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

### Category: input validation boundaries

**REQ-008** — Generic deserialization requires explicit type information  
- **Summary:** Deserializing parameterized types must require explicit `Type` or `TypeToken` information; Gson must not imply that a raw `Class` target preserves element or member types.  
- **User story:** As a developer deserializing collections and generic wrappers, I want missing generic type information to fail safe so that I do not get plausible-looking but wrongly typed object graphs.  
- **Implementation note:** This is one of Gson's most important correctness boundaries because raw types are a common source of `LinkedTreeMap` fallbacks and late `ClassCastException`s.  
- **Conditions of satisfaction:** `fromJson` with full generic type information preserves member typing; raw-type usage yields generic representations or validation errors rather than pretending to reconstruct domain types.  
- **Alternative paths:** Callers may use `TypeToken`, `TypeToken.getParameterized(...)`, parser APIs, or custom adapters to restore type information.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-009** — Type adapter result types must remain compatible with the requested target  
- **Summary:** If a custom adapter produces a runtime value incompatible with the requested target type, Gson must fail with a clear type-mismatch error instead of silently returning the wrong object.  
- **User story:** As an adapter author, I want misregistered or buggy adapters to fail immediately so that type-safety problems are caught at the JSON boundary instead of much later in application code.  
- **Implementation note:** This protects the public API from success-shaped corruption when adapter wiring is wrong.  
- **Conditions of satisfaction:** Incompatible adapter output does not silently escape `fromJson`; the failure identifies the mismatch rather than returning an object of the wrong type.  
- **Alternative paths:** Correct adapter registration or narrower target types avoid this failure path.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** specific

### Category: error handling contracts

**REQ-010** — Strictness configuration propagates to reader and writer entry points  
- **Summary:** Builder-level strictness configuration must propagate to `JsonReader`, `JsonWriter`, and all `Gson` read/write entry points so that parsing and writing enforce the same selected compliance mode.  
- **User story:** As a caller selecting a strictness mode, I want every JSON entry point to honor it so that one code path cannot silently parse or emit content under different rules.  
- **Implementation note:** This includes direct `Gson` operations and factory-created readers or writers.  
- **Conditions of satisfaction:** A configured strictness value is applied consistently to created readers and writers; per-call helpers do not silently revert to legacy defaults; read and write semantics stay aligned.  
- **Alternative paths:** Callers may configure strictness directly on a `JsonReader` or `JsonWriter`, but builder-level configuration must remain sufficient for ordinary usage.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

**REQ-011** — Version filters apply symmetrically to serialization and deserialization  
- **Summary:** When a version is configured, fields and classes above that version threshold must be excluded from both serialization and deserialization; when no version is configured, version annotations must not exclude anything.  
- **User story:** As a client maintaining backward-compatible JSON contracts, I want `@Since`-based filtering to behave consistently in both directions so that versioned payloads round-trip predictably.  
- **Implementation note:** Versioning is a behavioral contract, not just a serializer-side convenience.  
- **Conditions of satisfaction:** Fields or types above the configured version are skipped on write and ignored on read; unversioned operation includes everything unless another exclusion rule applies.  
- **Alternative paths:** Callers may avoid version annotations entirely, but if they use them the filtering behavior must be consistent.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

**REQ-012** — Naming policies and explicit serialized names compose predictably  
- **Summary:** Field naming policy must apply deterministically to ordinary fields, while `@SerializedName` must take precedence for explicitly named fields and support documented alternates for deserialization.  
- **User story:** As a developer maintaining stable wire names, I want global naming policies and explicit per-field overrides to interact predictably so that schema migrations do not become guesswork.  
- **Implementation note:** This requirement spans builder configuration, annotation handling, and duplicate-name detection.  
- **Conditions of satisfaction:** Unannotated fields follow the configured naming policy; annotated fields use the declared primary name; alternate names are accepted on read where supported; conflicts are rejected rather than silently shadowed.  
- **Alternative paths:** Callers may use only naming policies or only `@SerializedName`, but mixed usage must remain deterministic.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/annotations/SerializedName.java`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-013** — Exclusion configuration replaces defaults only as documented  
- **Summary:** Calling `excludeFieldsWithModifiers(...)` must replace the default modifier exclusions exactly as documented, including the possibility that `static` or `transient` fields become included unless explicitly re-excluded.  
- **User story:** As a caller customizing exclusion rules, I want modifier overrides to be explicit and predictable so that I do not accidentally reintroduce fields I assumed stayed excluded.  
- **Implementation note:** This is a configuration semantics rule and a common troubleshooting source.  
- **Conditions of satisfaction:** The configured modifier set is the effective exclusion set; defaults are not partially retained behind the scenes; output matches the documented replacement behavior.  
- **Alternative paths:** Callers who want the defaults can skip the method entirely or include `Modifier.STATIC` and `Modifier.TRANSIENT` explicitly in their override.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

**REQ-014** — `@Expose` gates only the configured instance  
- **Summary:** `@Expose` annotations must affect inclusion only when `excludeFieldsWithoutExposeAnnotation()` is enabled, and the annotation's `serialize` and `deserialize` flags must be respected independently.  
- **User story:** As an API author, I want opt-in field exposure to be explicit so that simply adding `@Expose` does not unexpectedly change behavior on unrelated `Gson` instances.  
- **Implementation note:** This is both an instance-local configuration rule and a field-direction rule.  
- **Conditions of satisfaction:** Without the builder flag, `@Expose` does not hide otherwise eligible fields; with the flag, only exposed fields participate; direction-specific flags are honored independently.  
- **Alternative paths:** Users who need richer rules may use `ExclusionStrategy` or custom adapters instead of `@Expose`.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

## Subsystem 2: Streaming parser and writer

### Category: API contracts and wire-format constraints

**REQ-015** — `JsonReader` exposes a depth-first token stream  
- **Summary:** `JsonReader` must present JSON as a depth-first token stream with explicit begin/end boundaries for arrays and objects.  
- **User story:** As an adapter author, I want stable token-order and boundary semantics so that custom streaming adapters can consume nested JSON deterministically.  
- **Implementation note:** This is the foundation for all low-allocation custom adapter logic.  
- **Conditions of satisfaction:** Valid JSON is traversed in depth-first order; arrays and objects require matching begin/end calls; token consumption remains deterministic across nested values.  
- **Alternative paths:** Callers may use tree APIs instead, but the streaming API must remain correct for high-control adapters.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-016** — `skipValue()` consumes the entire nested value  
- **Summary:** When callers skip an unknown or unsupported value, `skipValue()` must consume the entire subtree and leave the reader positioned correctly for the next token.  
- **User story:** As a consumer tolerant of extra JSON members, I want to skip unsupported values safely so that unknown fields do not corrupt parsing of later fields.  
- **Implementation note:** This underpins Gson's design choice to ignore extra JSON fields while navigating the target type tree.  
- **Conditions of satisfaction:** Skipping a primitive, array, or object leaves the reader at the next logical position; later fields remain readable; skipping does not corrupt nesting state.  
- **Alternative paths:** Custom adapters may inspect or reject unknown members explicitly, but generic skipping must remain safe when used.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-017** — Full-value entry points reject trailing data  
- **Summary:** Deserialization entry points that claim to consume one complete JSON value must detect and reject trailing non-whitespace data after that value.  
- **User story:** As a caller reading framed JSON, I want extra bytes after the target value to be surfaced as errors so that protocol corruption and concatenated payloads are not mistaken for success.  
- **Implementation note:** This is a framing guarantee at the `Gson` API boundary, not just a lexer feature.  
- **Conditions of satisfaction:** Reading a complete value fails if unread trailing data remains beyond permitted whitespace; success means the intended value was fully consumed.  
- **Alternative paths:** Stream-oriented callers may use incremental parsing APIs when multiple JSON values in one stream are intentional.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/JsonStreamParser.java`  
- **Specificity rating:** specific

**REQ-018** — Top-level primitive JSON values are supported where documented  
- **Summary:** Gson must accept JSON documents whose top-level value is a string, number, boolean, or `null` in the modes and entry points documented as supporting RFC 7159/8259 top-level values.  
- **User story:** As a user exchanging scalar JSON values, I want top-level primitives to work where Gson says they work so that valid JSON is not unnecessarily rejected.  
- **Implementation note:** Historical releases tightened this behavior; the requirement is about externally visible acceptance, not the parser's internal path.  
- **Conditions of satisfaction:** Supported reader paths accept documented top-level primitive documents and serialize matching scalar values correctly.  
- **Alternative paths:** Callers may still wrap values in arrays or objects for protocol reasons, but the documented scalar paths must remain available.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/javadoc_gson_class.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

### Category: input validation boundaries

**REQ-019** — Malformed JSON reports actionable location context  
- **Summary:** When JSON syntax is malformed or the structure does not match the requested read operation, Gson must fail with location information that includes the path within the JSON document.  
- **User story:** As an operator debugging bad input, I want parse failures to identify where the problem occurred so that malformed payloads can be diagnosed quickly.  
- **Implementation note:** Troubleshooting guidance explicitly depends on line, column, and JSONPath context.  
- **Conditions of satisfaction:** Syntax and structural errors identify the problem location; paths point to the offending member or array index closely enough to support diagnosis; errors are not generic or pathless.  
- **Alternative paths:** Callers may log raw JSON for more context, but Gson's exception messages must already be actionable.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/MalformedJsonException.java`  
- **Specificity rating:** specific

**REQ-020** — Strictness modes enforce distinct acceptance rules  
- **Summary:** `LENIENT`, legacy/default strictness, and `STRICT` must enforce distinct and documented acceptance rules for comments, single quotes, trailing commas, invalid escapes, control characters, and case sensitivity of literals.  
- **User story:** As a caller choosing between compatibility and standards compliance, I want each strictness level to have predictable acceptance boundaries so that parser behavior matches my interoperability or validation needs.  
- **Implementation note:** This requirement comes directly from the Strictness API and the troubleshooting distinction between legacy permissiveness and true strict RFC compliance.  
- **Conditions of satisfaction:** `STRICT` rejects non-standard forms called out by the documentation; lenient modes accept the documented extensions; changing strictness changes acceptance behavior in those specific areas.  
- **Alternative paths:** Older boolean leniency settings may remain as compatibility aliases, but their meaning must map clearly onto the newer strictness model.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `gson/src/main/java/com/google/gson/Strictness.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

**REQ-021** — Deep nesting is bounded  
- **Summary:** Reader-side nesting depth must be bounded by the configured or documented limit, and excessively deep documents must fail instead of exhausting the stack or heap.  
- **User story:** As a service processing untrusted JSON, I want overly deep input to fail predictably so that one malicious document cannot crash the process.  
- **Implementation note:** This requirement follows the later nesting-limit hardening work and general parser safety expectations.  
- **Conditions of satisfaction:** Deep documents beyond the allowed nesting threshold fail deterministically; normal documents under the threshold still parse; failure is explicit rather than a process crash.  
- **Alternative paths:** Callers may raise or lower the nesting limit where supported, but unbounded recursion is not an acceptable default.  
- **References:** `retrieved_documentation/official/releases_changelog.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** directional

**REQ-022** — Numeric accessors accept documented string forms  
- **Summary:** Numeric values must be readable both as JSON numbers and as documented numeric string representations when callers use numeric accessors or compatible adapters.  
- **User story:** As an integrator consuming APIs that stringify large numbers, I want Gson to accept documented numeric string forms so that interoperability does not force lossy conversions.  
- **Implementation note:** This is not a blanket coercion rule for arbitrary text; it is a documented compatibility rule for numeric representations.  
- **Conditions of satisfaction:** Supported numeric strings are parsed by the corresponding numeric accessors or adapters; invalid strings still fail explicitly; large-number workflows can avoid unnecessary precision loss.  
- **Alternative paths:** Callers may deserialize as `String` first or register a custom numeric adapter when stricter or domain-specific rules are needed.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-023** — Non-finite numeric output is gated by lenient behavior  
- **Summary:** Writing `NaN`, positive infinity, or negative infinity must be rejected in normal JSON writing modes and only allowed on the explicitly lenient path documented by Gson.  
- **User story:** As a producer of interoperable JSON, I want invalid numeric literals to be blocked unless I explicitly opt into non-standard output so that downstream parsers are not broken by surprise.  
- **Implementation note:** This is a writer-side standards boundary.  
- **Conditions of satisfaction:** Standard writing modes reject non-finite numbers; lenient writing can emit them where documented; the behavior is not silently inverted across write entry points.  
- **Alternative paths:** Callers may serialize such values as strings or use domain-specific adapters if interoperable JSON is required.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`; Gson project quirks documented in `AGENTS.md`  
- **Specificity rating:** specific

### Category: operational contracts

**REQ-024** — Reader and writer state transitions remain internally consistent  
- **Summary:** Reader and writer state machines must preserve internal consistency across `begin*`, `end*`, `next*`, `name`, `value`, and `skipValue()` operations so that valid prior operations do not make later valid operations fail.  
- **User story:** As a custom adapter author, I want stream state transitions to be stable so that correct token-handling logic does not fail because of hidden state corruption.  
- **Implementation note:** This is a cross-cutting correctness rule for both streaming APIs.  
- **Conditions of satisfaction:** Matching begin/end calls remain balanced; field names and values alternate correctly in objects; skipping or peeking does not corrupt later reads; writes preserve valid JSON structure.  
- **Alternative paths:** Tree-based APIs avoid direct state-machine management, but the streaming APIs must remain sound for low-level use.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** directional

**REQ-025** — Writer-side null handling is applied consistently  
- **Summary:** The active `serializeNulls` setting on the writer must govern all nested serialization paths so that `null` member emission remains consistent inside reflective adapters, tree adapters, and delegated custom adapters.  
- **User story:** As a caller choosing whether omitted and explicit-`null` fields are distinct, I want nested serialization to follow the same null-emission rule everywhere so that one object graph cannot produce contradictory wire formats.  
- **Implementation note:** This is the core null-policy propagation rule that later requirements refine for selective or polymorphic cases.  
- **Conditions of satisfaction:** Under the same `Gson` configuration, equivalent `null` members are either omitted or emitted consistently across nested paths; delegation does not silently lose the configured writer policy.  
- **Alternative paths:** Per-type overrides may temporarily toggle the active writer state, but they must do so explicitly and restore it cleanly.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

## Subsystem 3: Reflective binding, exclusion, and object construction

### Category: data integrity and consistency

**REQ-026** — Reflection-based binding is field-based, not getter-based  
- **Summary:** Reflective mapping must use eligible fields rather than JavaBean getters, including inherited non-static, non-transient, non-synthetic fields unless an exclusion rule removes them.  
- **User story:** As a user serializing classes I cannot modify, I want field-based mapping so that Gson's wire contract does not depend on getter naming conventions or side effects.  
- **Implementation note:** This is a foundational design decision documented in the design notes and user guide.  
- **Conditions of satisfaction:** Private fields can participate; inherited eligible fields are included; getters alone do not define JSON members; excluded field categories stay excluded.  
- **Alternative paths:** Callers who need property-based behavior may use custom adapters instead of changing the reflective contract.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-027** — Missing JSON members preserve post-construction state  
- **Summary:** When a JSON member is absent, Gson must leave the field in whatever state the constructed target instance already had, and it must not invoke the field adapter for a missing member.  
- **User story:** As a developer using defaults, I want absent JSON fields to preserve the object's post-construction state so that omitted data does not silently trigger unexpected replacement logic.  
- **Implementation note:** This rule is tightly coupled to construction strategy; constructor-backed instances preserve initializers, while unsafe construction may not run them at all.  
- **Conditions of satisfaction:** Missing members do not cause synthetic adapter invocations; constructor or field-initializer defaults survive when the construction path ran them; object-reference fields remain JVM defaults when unsafe allocation bypassed initialization.  
- **Alternative paths:** Callers who need required-or-default semantics may use constructors, records, custom deserializers, or explicit post-processing.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-028** — Object cycles are not silently normalized by default  
- **Summary:** Gson must not pretend to provide general-purpose cycle handling for object graphs; arbitrary bidirectional or cyclic references remain unsupported unless callers break the cycle or provide a custom adapter strategy.  
- **User story:** As a developer modeling graphs or bidirectional relationships, I want the library's cycle limitations to be explicit so that I do not mistake unsupported graphs for safe, round-trippable object models.  
- **Implementation note:** This is a negative contract: correctness requires either acyclic models or explicit caller intervention.  
- **Conditions of satisfaction:** Acyclic object graphs serialize normally; general cycles are not silently rewritten into a supported reference format; callers have to opt into exclusion or custom cycle handling.  
- **Alternative paths:** Users may exclude back-references, use `@Expose` selectively, or register custom graph-aware adapters.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0530_circular_references.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** directional

### Category: error handling contracts

**REQ-029** — Anonymous and non-static local classes are unsupported by reflective binding  
- **Summary:** Anonymous classes and non-static local classes must not be reflectively treated as ordinary domain models; by default Gson must serialize them as JSON `null` and deserialize them as Java `null`.  
- **User story:** As a developer debugging unexplained `null` output, I want anonymous and local class handling to be explicit so that unsupported runtime types are not mistaken for missing data bugs.  
- **Implementation note:** This is an intentional limitation, not an incidental bug.  
- **Conditions of satisfaction:** Unsupported anonymous or local classes do not produce ordinary reflective output; default deserialization yields `null`; the limitation is stable and diagnosable.  
- **Alternative paths:** Callers may use static nested classes, explicit declared base types, records where supported, or custom adapters.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_2059_anonymous_class_null.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-030** — Pure inner classes require caller-supplied construction support  
- **Summary:** Gson must not auto-deserialize pure inner classes that require an enclosing instance unless the caller supplies an `InstanceCreator` or equivalent custom construction path.  
- **User story:** As a caller deserializing nested Java types, I want impossible construction cases to fail or require explicit support so that Gson does not create half-valid objects bound to the wrong outer instance.  
- **Implementation note:** This is a construction-boundary requirement, not just a serialization quirk.  
- **Conditions of satisfaction:** Plain inner classes are not auto-instantiated without an enclosing instance; static nested classes work normally; registered custom creators can supply the necessary outer binding.  
- **Alternative paths:** Make the type `static`, provide an `InstanceCreator`, or deserialize into a different DTO.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/design_document.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-031** — Reflection failures surface actionable remediation  
- **Summary:** When reflection is blocked by JPMS boundaries, Android platform restrictions, or a `ReflectionAccessFilter`, Gson must fail with an actionable message that points callers toward `opens`, exclusions, or explicit adapters.  
- **User story:** As an operator diagnosing deployment-specific failures, I want reflective access errors to explain how to restore intended behavior so that the fix is not a blind search.  
- **Implementation note:** Troubleshooting guidance turns this into a public contract for failure messaging.  
- **Conditions of satisfaction:** Reflection failures do not degrade into opaque low-level exceptions; the error identifies blocked access and suggests supported remedies; explicit adapters can still replace reflection.  
- **Alternative paths:** Callers may open packages, exclude fields, add filters, or avoid reflection entirely with adapters or tree/stream APIs.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/ReflectionAccessFilter.java`  
- **Specificity rating:** specific

**REQ-032** — Duplicate resolved field names are rejected  
- **Summary:** If two fields in the reflective hierarchy resolve to the same JSON member name after naming policy and annotation processing, Gson must reject the type definition instead of choosing one field implicitly.  
- **User story:** As a user relying on unambiguous object binding, I want naming collisions to fail fast so that duplicate field names do not silently corrupt data.  
- **Implementation note:** This applies to collisions caused by inheritance, `@SerializedName`, or field naming policies.  
- **Conditions of satisfaction:** Name collisions are detected before ordinary use; serialization and deserialization do not proceed with ambiguous field selection; the error identifies the collision.  
- **Alternative paths:** Rename one field, exclude one field, or adjust the naming strategy to remove the collision.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-033** — Static final fields are never mutated by deserialization  
- **Summary:** Deserialization must not write JSON values into `static final` fields; encountering such a target must fail explicitly rather than mutate process-wide constant state.  
- **User story:** As a maintainer of shared JVM state, I want constant fields protected from JSON input so that one parse cannot introduce a hidden global side effect.  
- **Implementation note:** This is both a JVM-safety rule and a data-integrity rule.  
- **Conditions of satisfaction:** `static final` targets are not assigned through reflective binding; failure is explicit; other eligible instance fields continue to work normally.  
- **Alternative paths:** Exclude the field or provide a custom adapter that maps input without mutating static constants.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

### Category: resource lifecycle

**REQ-034** — Construction order is stable and documented  
- **Summary:** Gson must use a stable preference order for constructing instances: registered `InstanceCreator`, special collection/map constructors, accessible no-args constructor, safe default implementation, and only then JDK `Unsafe` when allowed.  
- **User story:** As a caller depending on constructor behavior and collection semantics, I want instance creation order to be stable so that deserialization does not bypass my intended construction path unexpectedly.  
- **Implementation note:** The order is a major part of Gson's design rationale and strongly affects invariants.  
- **Conditions of satisfaction:** Custom creators win when registered; ordinary no-args constructors are preferred over unsafe allocation; documented default implementations are used for abstract collection interfaces; unsafe allocation is last resort.  
- **Alternative paths:** Users may replace construction with adapters or creators when the default order does not fit their model.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-035** — `disableJdkUnsafe()` turns hidden construction gaps into explicit failures  
- **Summary:** When `disableJdkUnsafe()` is enabled and no valid non-unsafe construction path exists, Gson must fail immediately with guidance rather than silently falling back to unsafe allocation.  
- **User story:** As a maintainer debugging missing defaults and broken invariants, I want unsafe allocation to be opt-out and loudly disabled so that construction problems show up early.  
- **Implementation note:** This is a deliberate diagnostics and safety feature, not just a performance toggle.  
- **Conditions of satisfaction:** Disabling unsafe allocation prevents fallback use of `Unsafe`; unsupported construction cases fail fast; the error points callers toward constructors or custom creators.  
- **Alternative paths:** Leave unsafe allocation enabled, add a no-args constructor, make the class static/top-level, or register an `InstanceCreator`.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-036** — Non-instantiable abstract targets are rejected explicitly  
- **Summary:** Interfaces and abstract classes must not be instantiated through default or unsafe construction paths unless a custom creator or adapter supplies a concrete type.  
- **User story:** As a developer deserializing abstract APIs, I want unsupported instantiation to fail clearly so that Gson does not fabricate impossible objects or produce misleading errors.  
- **Implementation note:** Later releases strengthened the error messaging here, but the behavioral contract is older and broader.  
- **Conditions of satisfaction:** Abstract or interface targets fail without a concrete construction strategy; failures explain the need for a concrete subtype, creator, or adapter; no unsafe fake instance is produced.  
- **Alternative paths:** Register an `InstanceCreator`, provide a custom `TypeAdapter`, or deserialize to a concrete subtype.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

### Category: operational contracts

**REQ-037** — Unsafe allocation skips constructors and field initializers  
- **Summary:** When Gson falls back to JDK `Unsafe` or similar allocation, constructors and field initializers must be treated as not having run, and callers must not assume their defaults were preserved.  
- **User story:** As a user seeing unexpectedly `null` or zero-valued fields, I want the unsafe-construction semantics to be explicit so that missing initialization is diagnosable.  
- **Implementation note:** This is a consequence contract of the unsafe path, not a desired feature.  
- **Conditions of satisfaction:** Classes created through unsafe allocation begin with JVM default field values; constructor or initializer side effects are not assumed; troubleshooting guidance remains accurate.  
- **Alternative paths:** Provide a no-args constructor, register an `InstanceCreator`, make the type static/top-level, or disable unsafe allocation to force detection.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-038** — Custom adapters remain a supported escape hatch from blocked reflection  
- **Summary:** If reflective member access is unavailable or undesirable, caller-supplied adapters and factories must remain a supported path for serializing and deserializing the affected types.  
- **User story:** As a user on JPMS, Android, or restricted runtimes, I want explicit adapters to replace reflection so that platform limits do not make Gson unusable.  
- **Implementation note:** This is a compatibility escape hatch heavily referenced by troubleshooting guidance.  
- **Conditions of satisfaction:** Types blocked from reflection can still be handled through registered adapters; adapter registration takes precedence where documented; reflection errors are not raised for types fully covered by explicit adapters.  
- **Alternative paths:** Tree APIs, stream APIs, and reflection-access filters that block all reflection are also supported ways to avoid reflective binding.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-039** — Declared-type adapters remain usable when runtime implementations are inaccessible  
- **Summary:** If the runtime object type is an inaccessible internal implementation but Gson has a supported adapter for the declared supertype, serialization must use the declared-type contract rather than failing only because the concrete runtime type is inaccessible.  
- **User story:** As a caller working with interfaces returned by libraries, I want serialization to honor accessible declared types so that internal implementation classes do not leak into my JSON boundary.  
- **Implementation note:** This is a runtime-type and accessibility interaction rule.  
- **Conditions of satisfaction:** Declared-type serialization can succeed when the declared type has a supported adapter; inaccessible implementation details do not force reflection into blocked internals unnecessarily.  
- **Alternative paths:** Deserializing directly into the inaccessible implementation may still fail; callers can also register a concrete adapter if needed.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java`  
- **Specificity rating:** directional

## Subsystem 4: Type adapters, custom serialization, and polymorphic behavior

### Category: API contracts and wire-format constraints

**REQ-040** — `TypeAdapter` reads and writes exactly one value  
- **Summary:** A `TypeAdapter` implementation must read exactly one JSON value and write exactly one JSON value so that stream position stays correct for surrounding adapters.  
- **User story:** As an adapter author, I want Gson to rely on a precise adapter contract so that custom adapters compose safely without corrupting the reader or writer state.  
- **Implementation note:** This is the core TypeAdapter protocol.  
- **Conditions of satisfaction:** Primitive adapters consume one primitive token; array and object adapters consume one balanced array or object; surrounding stream position is correct after delegation returns.  
- **Alternative paths:** Callers who prefer tree-based customization may use `JsonSerializer` or `JsonDeserializer`, but `TypeAdapter` users must obey the stricter stream contract.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-041** — Null handling is explicit at the adapter boundary  
- **Summary:** Gson's default adapter pipeline must bypass custom adapter logic for `null` values unless the adapter path explicitly opts out of null safety or handles `null` through a wrapper strategy.  
- **User story:** As an adapter author, I want null interception rules to be explicit so that I know when my adapter will and will not see `null` values.  
- **Implementation note:** This is one of Gson's most consequential adapter semantics and is intentionally different from some other JSON libraries.  
- **Conditions of satisfaction:** Default adapter paths do not invoke custom adapter logic for `null`; `nullSafe()` provides wrapper-based null handling; callers do not get silent custom null transformations unless they explicitly built for them.  
- **Alternative paths:** Use a `TypeAdapter` with `nullSafe(false)`-style control where available, or move null semantics to wrapper types or outer logic.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/github_issues/issue_0948_type_adapter_null_bypass.md`; `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-042** — Custom adapters must be stateless or otherwise thread-safe  
- **Summary:** Adapters reused by a `Gson` instance must be safe for concurrent reuse, or they invalidate Gson's documented thread-safety guarantee.  
- **User story:** As a developer sharing one `Gson`, I want adapter reuse to be safe so that my JSON layer does not become the hidden source of race conditions.  
- **Implementation note:** Gson's own thread safety depends on this expectation for registered adapters.  
- **Conditions of satisfaction:** Adapter instances do not keep mutable per-call shared state unless they synchronize safely; concurrent calls through one adapter do not corrupt one another.  
- **Alternative paths:** State can be externalized to immutable configuration or `ThreadLocal` where sharing mutable state would otherwise be unsafe.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0613_thread_safety.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-043** — Exact-type and hierarchy registrations stay distinct  
- **Summary:** `registerTypeAdapter(...)` must apply to the exact registered type, while subclass coverage requires `registerTypeHierarchyAdapter(...)` or a factory that intentionally matches a wider set of types.  
- **User story:** As a caller registering custom handling, I want the scope of adapter registration to be predictable so that a parent-type registration neither misses expected subtypes nor silently hijacks unrelated ones.  
- **Implementation note:** This is a frequent source of "adapter not used" confusion and a key part of adapter precedence.  
- **Conditions of satisfaction:** Exact-type registrations do not automatically apply to subclasses; hierarchy registrations or factories do; incorrect type registration remains diagnosable.  
- **Alternative paths:** Users may register both exact and hierarchy handlers or use a `TypeAdapterFactory` for more complex matching logic.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-044** — Later adapter registrations for the same type win  
- **Summary:** If multiple adapters are registered for the same effective type on one builder, the last relevant registration must determine the effective behavior.  
- **User story:** As a maintainer composing builder setup from several modules, I want override order to be deterministic so that final configuration is understandable and testable.  
- **Implementation note:** Community guidance highlights this as a subtle but important builder behavior.  
- **Conditions of satisfaction:** Repeated registrations for the same type produce deterministic last-one-wins behavior; the effective adapter is not order-random.  
- **Alternative paths:** Teams may centralize builder construction to avoid accidental overriding, but the override rule must still remain stable.  
- **References:** `retrieved_documentation/community/futurestud_custom_serialization.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

### Category: data integrity and consistency

**REQ-045** — Parent deserializers must not strip subclass serialization fields  
- **Summary:** Registering a custom deserializer for a parent type must not change the serialization behavior of subclass instances unless a serializer explicitly replaces that behavior.  
- **User story:** As a developer with polymorphic models, I want deserialization customization to be independent from runtime-type serialization so that subclass-specific fields are not silently dropped.  
- **Implementation note:** This was a real regression and is now a durable compatibility requirement.  
- **Conditions of satisfaction:** Subclass instances still serialize subclass fields when only a parent deserializer is registered; parent deserializer registration alone does not collapse runtime serialization to parent fields.  
- **Alternative paths:** If callers want fully custom parent-and-subclass handling, they can use a coordinated `TypeAdapterFactory`.  
- **References:** `retrieved_documentation/github_issues/issue_2032_deserializer_changes_serialization.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java`  
- **Specificity rating:** specific

**REQ-046** — Selective null semantics require direct writer control  
- **Summary:** Per-type or per-field null-emission semantics must be implemented through an adapter path that directly controls the active `JsonWriter`; returning a `JsonElement` alone is not enough to force explicit `null` members when the outer `Gson` omits them.  
- **User story:** As an API author distinguishing omitted fields from explicit `null`, I want the requirement to point to the right extension path so that I do not mistakenly rely on a serializer shape that cannot preserve the distinction.  
- **Implementation note:** This captures the core lesson from the selective-serialize-null issues and tutorials.  
- **Conditions of satisfaction:** Per-type null emission works only when the active writer setting is changed on the real output path; tree-returning serializers do not override the outer omit-null policy by themselves.  
- **Alternative paths:** Use a `TypeAdapterFactory` that toggles `JsonWriter.setSerializeNulls(...)` and chains with `getDelegateAdapter(...)`, wrapper types that track presence, or a custom type-level `TypeAdapter`.  
- **References:** `retrieved_documentation/github_issues/issue_0913_selective_serialize_nulls.md`; `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `retrieved_documentation/official/javadoc_type_adapter.md`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-047** — Polymorphic wrappers must preserve delegated writer settings  
- **Summary:** If a polymorphic adapter delegates serialization to a subtype-specific adapter that intentionally changes the active writer configuration, the delegated setting must survive to the final output instead of being discarded during an intermediate tree conversion.  
- **User story:** As a library user combining polymorphism with custom null semantics, I want delegated subtype behavior to survive the wrapper layer so that the final JSON reflects the subtype adapter's documented output policy.  
- **Implementation note:** This is the precise behavioral gap surfaced by `RuntimeTypeAdapterFactory` null-setting loss.  
- **Conditions of satisfaction:** Delegated subtype writer settings such as `serializeNulls` remain observable in the emitted JSON; wrapper indirection does not silently erase them.  
- **Alternative paths:** Users can enable the setting globally or avoid tree-based polymorphic wrappers, but subtype-specific settings should not be lost by default adapter composition.  
- **References:** `retrieved_documentation/github_issues/issue_0676_runtime_type_adapter_serialize_nulls.md`; `retrieved_documentation/github_issues/issue_0913_selective_serialize_nulls.md`; `gson/src/main/java/com/google/gson/internal/bind/TreeTypeAdapter.java`  
- **Specificity rating:** directional

**REQ-048** — Required-nullable and optional fields remain distinguishable only with explicit modeling  
- **Summary:** Gson must not claim that plain nullable Java references preserve the distinction between "present with `null`" and "omitted"; callers who need that distinction must model it explicitly.  
- **User story:** As an API client bound to schemas that distinguish required-nullable from optional fields, I want the limitation to be explicit so that I do not assume plain `null` is enough to preserve presence information.  
- **Implementation note:** This is a limitation contract that shapes safe extension patterns.  
- **Conditions of satisfaction:** Plain reflective binding does not magically recover field presence once data is in a plain nullable reference; preserving that distinction requires wrapper types, presence tracking, or custom adapters.  
- **Alternative paths:** Use wrapper types, field-presence sets, `TypeAdapterFactory` presence tracking, or explicit tree handling.  
- **References:** `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `retrieved_documentation/official/user_guide.md`  
- **Specificity rating:** directional

### Category: error handling contracts

**REQ-049** — `@JsonAdapter` binds one adapter class per annotated target  
- **Summary:** `@JsonAdapter` must bind exactly one adapter class to the annotated type or field, so combined custom read and write behavior requires either a single `TypeAdapter` or builder-level registration of separate serializer and deserializer components.  
- **User story:** As a developer choosing between annotations and builder registration, I want the capability boundary to be clear so that I do not expect two separate annotated handlers to compose magically.  
- **Implementation note:** This is an extension-surface contract rather than a JSON syntax rule.  
- **Conditions of satisfaction:** One annotation names one effective adapter class; separate custom serializer and deserializer classes do not both activate through multiple annotations on the same target; a single `TypeAdapter` can provide both directions.  
- **Alternative paths:** Use builder registration for separate read and write handlers, or a single `TypeAdapter` with `@JsonAdapter`.  
- **References:** `retrieved_documentation/community/futurestud_jsonadapter_annotation.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/annotations/JsonAdapter.java`  
- **Specificity rating:** specific

**REQ-050** — Overriding built-in tree adapters remains backward-compatible  
- **Summary:** Attempting to register handlers for `JsonElement` and its subclasses must remain backward-compatible in builder behavior, even though callers must not rely on such registrations to replace core tree semantics.  
- **User story:** As a library maintainer upgrading Gson, I want minor-version changes around built-in adapter validation to avoid breaking existing builder code at startup.  
- **Implementation note:** The compatibility requirement is about registration-time behavior and upgrade safety, not endorsement of the pattern.  
- **Conditions of satisfaction:** Minor-version upgrades do not turn formerly tolerated `JsonElement` adapter registrations into hard startup failures without a migration path; callers are still not guaranteed to replace core tree behavior successfully.  
- **Alternative paths:** Libraries should move special handling out of `JsonElement` overrides and into their own code or supported extension points.  
- **References:** `retrieved_documentation/github_issues/issue_2787_backwards_compat_broken.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** directional

**REQ-051** — Recursive custom serialization must not rely on `context.serialize(thisType)`  
- **Summary:** Gson must preserve the rule that a custom serializer for a type cannot safely call `context.serialize()` on the same type without triggering recursive re-entry.  
- **User story:** As a custom serializer author, I want the recursion boundary to be clear so that I do not create infinite recursion by delegating incorrectly.  
- **Implementation note:** Community tutorials surface this as an easy trap rather than a hidden implementation quirk.  
- **Conditions of satisfaction:** Same-type recursive delegation is not treated as a supported composition pattern; authors must delegate selectively, use different types, or hand-write output.  
- **Alternative paths:** Delegate field-by-field, serialize sub-components of different types, or use a `TypeAdapterFactory` that wraps a delegate adapter explicitly.  
- **References:** `retrieved_documentation/community/futurestud_custom_serialization.md`; `retrieved_documentation/official/javadoc_type_adapter.md`; `gson/src/main/java/com/google/gson/JsonSerializationContext.java`  
- **Specificity rating:** directional

## Subsystem 5: Collections, maps, tree model, and type metadata

### Category: data integrity and consistency

**REQ-052** — `JsonObject` preserves insertion order and normalizes Java `null`  
- **Summary:** `JsonObject` must preserve member insertion order and normalize added Java `null` values to `JsonNull.INSTANCE` rather than storing raw Java `null`.  
- **User story:** As a user manipulating the JSON tree model directly, I want object-member ordering and null representation to be stable so that tree operations remain predictable and serializable.  
- **Implementation note:** This is a tree-model invariant used by both direct callers and higher-level adapters.  
- **Conditions of satisfaction:** Iteration observes insertion order; adding Java `null` results in `JsonNull`; the tree remains serializable without special-case raw null handling.  
- **Alternative paths:** Callers may build objects through adapters or streaming APIs, but the tree model must remain internally consistent.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/JsonObject.java`; `gson/src/main/java/com/google/gson/internal/LinkedTreeMap.java`  
- **Specificity rating:** specific

**REQ-053** — Re-adding a `JsonObject` member replaces the previous value  
- **Summary:** Adding a member to a `JsonObject` with a name that already exists must replace the previous value for that name instead of retaining multiple entries.  
- **User story:** As a caller mutating a tree object, I want repeated writes to a member name to have deterministic replacement semantics so that later updates do not create hidden duplicates.  
- **Implementation note:** This behavior is intentionally different from duplicate-key rejection in map deserialization.  
- **Conditions of satisfaction:** The final value for a repeated member name is the stored value; object member iteration contains one entry for that name; replacement is deterministic.  
- **Alternative paths:** Callers who need duplicate-key preservation must not use `JsonObject` as their model because the object abstraction is name-unique.  
- **References:** prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/JsonObject.java`  
- **Specificity rating:** specific

**REQ-054** — Duplicate map keys are rejected during deserialization  
- **Summary:** When deserializing into a Java `Map`, duplicate keys must be rejected whether the JSON came from object-member form or array-of-entry form.  
- **User story:** As a caller depending on map uniqueness, I want duplicate-key input to fail so that ambiguous last-write-wins behavior does not silently corrupt my data.  
- **Implementation note:** This is one of Gson's long-standing map-specific integrity guarantees and remains distinct from `JsonObject` replacement semantics.  
- **Conditions of satisfaction:** Duplicate keys in either supported map encoding raise a syntax or parse failure; Gson does not silently keep first or last value for Java map deserialization, including edge cases where the first occurrence carried a `null` value.  
- **Alternative paths:** Callers who need duplicate-key preservation must deserialize into a different model such as a list of entries or a tree that they process manually.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/troubleshooting.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-055** — Raw map-key stringification has documented consequences  
- **Summary:** When complex-map-key serialization is not enabled, Gson must stringify map keys with the documented default behavior, including using the literal member name `"null"` for Java `null` keys.  
- **User story:** As a caller serializing maps, I want the default key encoding behavior to be predictable so that non-string keys do not appear reversible when they are not.  
- **Implementation note:** This requirement is paired with the complex-key alternative below.  
- **Conditions of satisfaction:** Default map serialization uses member names, stringifies keys, and uses `"null"` for Java `null` keys; round-tripping is not implied for arbitrary complex keys under this mode.  
- **Alternative paths:** Enable complex-map-key serialization to get adapter-based key handling and reversible array-of-entry output where needed.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-056** — Complex map keys use adapter-based encoding  
- **Summary:** When `enableComplexMapKeySerialization()` is enabled, Gson must use the registered key adapter and switch to array-of-entry encoding whenever any key serializes as a JSON array or object.  
- **User story:** As a caller round-tripping maps with non-trivial key types, I want complex-key mode to preserve key structure so that serialization and deserialization use the same logical representation.  
- **Implementation note:** This is the supported reversible path for complex keys.  
- **Conditions of satisfaction:** Key adapters are used for key serialization; object or array-shaped keys force the array-of-entry encoding; plain scalar-shaped keys may still use object-member form.  
- **Alternative paths:** Without complex-key mode, callers should expect lossy stringification and may need a custom container format instead.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-057** — Enum map-key deserialization falls back to `toString()` when documented  
- **Summary:** For enum map keys, if deserialization cannot find a matching `name()` or `@SerializedName` value, Gson must fall back to the enum constant's `toString()` value as documented.  
- **User story:** As a developer using enums with custom string representations, I want documented fallback behavior to remain stable so that map-key round-tripping does not break unexpectedly.  
- **Implementation note:** This is a targeted interoperability rule, not a general fallback for all key types.  
- **Conditions of satisfaction:** Enum key lookup checks primary enum names and serialized names first, then uses `toString()` only for the documented enum-key fallback path.  
- **Alternative paths:** Users may avoid relying on `toString()` by using explicit `@SerializedName` values or scalar string keys.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

### Category: input validation boundaries

**REQ-058** — Raw `TypeToken` usage is rejected  
- **Summary:** Constructing a `TypeToken` without a real type argument must fail rather than behaving as though raw generic type information were safe.  
- **User story:** As a caller using `TypeToken`, I want raw or malformed tokens to fail immediately so that generic type metadata errors do not become late runtime surprises.  
- **Implementation note:** Shrinker and generic-signature preservation guidance exists largely to protect this contract.  
- **Conditions of satisfaction:** Raw `TypeToken` creation fails with a clear message; correct parameterized usage succeeds; shrinker-induced signature stripping remains diagnosable.  
- **Alternative paths:** Use `TypeToken.getParameterized(...)` or preserve generic signatures through shrinker rules.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-059** — Captured type variables are rejected or explicitly opted back in  
- **Summary:** `TypeToken` construction must reject captured type variables by default, or else only allow them through the explicit backward-compatibility escape hatch documented by Gson.  
- **User story:** As a developer using generics, I want unsafe captured type variables blocked by default so that deserialization does not silently degrade to `Object`-typed graphs.  
- **Implementation note:** This is a type-safety hardening rule and a compatibility rule at once.  
- **Conditions of satisfaction:** Captured type variables fail by default; the error explains the problem and points to safer alternatives; the compatibility system property remains an explicit opt-in rather than the default behavior.  
- **Alternative paths:** Use `TypeToken.getParameterized(...)`, pass around full `TypeToken` instances, or, if absolutely necessary, opt into the compatibility property with awareness of the risks.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-060** — `TypeToken.getParameterized(...)` validates arity and bounds  
- **Summary:** Programmatic `TypeToken` construction must validate parameter count, bounds, and primitive-type misuse before producing a token.  
- **User story:** As a caller building generic types dynamically, I want invalid parameterized type requests to fail early so that impossible type combinations are not turned into misleading tokens.  
- **Implementation note:** This is a factory-side validation rule for safer runtime type construction.  
- **Conditions of satisfaction:** Invalid arity, out-of-bounds substitutions, and primitive misuse are rejected explicitly; valid parameterized requests produce a usable token.  
- **Alternative paths:** Callers may use anonymous subclass syntax when compile-time generic information is available.  
- **References:** `retrieved_documentation/official/changelog.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-061** — Bounded type variables must not degrade to raw `Object` semantics  
- **Summary:** When a generic type variable has an upper bound, deserialization logic must not ignore that bound and behave as though the field were an unconstrained `Object`.  
- **User story:** As a developer using bounded generics, I want type bounds to guide deserialization so that constrained generic fields do not silently become `LinkedTreeMap` or other generic placeholders.  
- **Implementation note:** This is an open behavior gap surfaced by issue-driven requirement elicitation and is especially valuable for review.  
- **Conditions of satisfaction:** Bounded generic fields are not treated as raw `Object` when bound information is available; deserialization either respects the bound or fails explicitly instead of silently materializing a generic map.  
- **Alternative paths:** Use concrete types, register explicit adapters, or deserialize in two steps if the generic bound cannot be resolved automatically.  
- **References:** `retrieved_documentation/github_issues/issue_2563_generic_type_boundary.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/$Gson$Types.java`; prior `quality/REQUIREMENTS.md` gap analysis  
- **Specificity rating:** directional

### Category: API contracts and wire-format constraints

**REQ-062** — Untyped object-number deserialization honors configured number strategy  
- **Summary:** When callers deserialize numbers as `Object` or `Number`, Gson must apply the configured object-to-number or number-to-number strategy instead of always collapsing to `double`.  
- **User story:** As a caller sensitive to integer precision and numeric shape, I want untyped number parsing to follow the configured strategy so that large integral values do not lose meaning silently.  
- **Implementation note:** This is a configuration propagation rule for untyped numeric materialization.  
- **Conditions of satisfaction:** Untyped numeric parsing reflects the configured strategy; default behavior remains documented; strategy changes alter untyped numeric result types predictably.  
- **Alternative paths:** Callers may deserialize into explicit numeric Java types or strings when full control is required.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/ToNumberPolicy.java`; `gson/src/main/java/com/google/gson/internal/bind/ObjectTypeAdapter.java`  
- **Specificity rating:** specific

**REQ-063** — Raw collection deserialization does not pretend to restore domain element types  
- **Summary:** Gson may serialize collections of arbitrary objects, but deserializing raw or insufficiently typed collections must produce generic JSON representations or require caller-supplied typing rather than fabricating domain element types.  
- **User story:** As a developer round-tripping heterogeneous collections, I want Gson's asymmetry here to be explicit so that raw-collection reads are not mistaken for type-safe reconstruction.  
- **Implementation note:** This is a design-document-level contract about serialization being richer than deserialization in some generic cases.  
- **Conditions of satisfaction:** Raw collection deserialization yields generic structures or requires parser/custom-adapter intervention; Gson does not falsely reconstruct heterogeneous domain objects from erased type information.  
- **Alternative paths:** Use the parser API element-by-element, a typed collection, or a custom collection adapter.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`; prior `quality/REQUIREMENTS.md` baseline  
- **Specificity rating:** specific

**REQ-064** — Tree-model null mutators preserve tree invariants  
- **Summary:** Tree-model mutator operations that receive Java `null` where a JSON element is expected must either normalize the value to `JsonNull` or reject it explicitly, but must not leave the tree in a half-null, half-JSON state.  
- **User story:** As a caller editing JSON trees directly, I want null-related mutators to preserve tree invariants so that later traversal and serialization remain safe.  
- **Implementation note:** Release notes show repeated hardening in this area, making it a valuable invariant to preserve.  
- **Conditions of satisfaction:** Supported mutators normalize or reject Java `null` consistently; tree traversal and serialization remain valid after the operation.  
- **Alternative paths:** Callers may pass `JsonNull.INSTANCE` explicitly when they want a JSON null node.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/JsonArray.java`; `gson/src/main/java/com/google/gson/JsonObject.java`  
- **Specificity rating:** directional

## Subsystem 6: Platform, deployment, compatibility, and initialization boundaries

### Category: security policy propagation

**REQ-065** — JPMS callers must open reflected packages to Gson  
- **Summary:** In JPMS environments, any application package whose fields Gson must access reflectively must be opened to `com.google.gson`; otherwise reflective binding must fail rather than bypassing module boundaries.  
- **User story:** As a JPMS user, I want module access rules to be enforced consistently so that reflective JSON binding does not undermine module encapsulation.  
- **Implementation note:** This is both a platform contract and a security boundary.  
- **Conditions of satisfaction:** Closed packages are not reflectively accessed behind JPMS rules; opening the package enables reflective binding; failure messages point to the missing `opens` declaration.  
- **Alternative paths:** Use explicit adapters, tree APIs, or stream APIs to avoid reflection entirely.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/module-info.java`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-066** — Shrinker and obfuscation workflows must preserve binding metadata or use explicit aliases  
- **Summary:** Android and shrinker-based deployments must preserve field names, generic signatures, and needed constructors, or callers must supply explicit `@SerializedName` aliases and adapter strategies that preserve compatibility across releases.  
- **User story:** As a mobile or minified-build maintainer, I want Gson's metadata dependencies to be explicit so that release builds do not silently corrupt JSON contracts or lose type information.  
- **Implementation note:** This is a deployment constraint that directly affects reflective binding, `TypeToken`, and backward compatibility.  
- **Conditions of satisfaction:** Required metadata is retained or replaced by explicit aliases and adapters; release builds continue to deserialize older payloads where compatibility is expected; missing metadata fails diagnosably.  
- **Alternative paths:** Constrain reflected classes, avoid reflection, use explicit field annotations, or supply custom ProGuard/R8 rules.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/resources/META-INF/proguard/gson.pro`  
- **Specificity rating:** specific

**REQ-067** — Reflection-free usage remains supported as a deployment strategy  
- **Summary:** Environments that cannot safely retain reflection metadata must be able to use Gson through explicit adapters, factories, tree APIs, or streaming APIs without depending on reflective fallback.  
- **User story:** As a platform owner restricting reflection, I want a supported reflection-free usage path so that Gson can still be adopted under tighter security or AOT constraints.  
- **Implementation note:** Troubleshooting guidance explicitly recommends this as an alternative architecture.  
- **Conditions of satisfaction:** Reflection can be blocked completely while tree, stream, or adapter-driven workflows still function; Gson does not require reflective fallback when every needed type has explicit handling.  
- **Alternative paths:** Keep reflection enabled and preserve metadata, but the reflection-free architecture must remain viable.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; prior `quality/REQUIREMENTS.md` baseline; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

### Category: operational contracts

**REQ-068** — Concurrent adapter initialization must not deadlock or expose partial state  
- **Summary:** Concurrent creation or initialization of built-in and recursive adapters must not deadlock and must not expose half-initialized adapters to other threads.  
- **User story:** As a server starting under concurrent load, I want adapter initialization to be safe so that startup and first-use paths cannot hang or return corrupted behavior.  
- **Implementation note:** This includes both recursive user-type resolution and built-in class-loading interactions.  
- **Conditions of satisfaction:** Concurrent adapter lookup and built-in adapter initialization complete without deadlock; recursive adapter placeholders are resolved safely; other threads do not observe partially initialized adapters as final state.  
- **Alternative paths:** Eager warm-up is optional for performance, but correctness must not depend on single-threaded initialization.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/github_issues/issue_2739_class_loading_deadlock.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

**REQ-069** — Built-in compatibility changes should preserve upgrade safety  
- **Summary:** Minor-version fixes and validations around adapter registration, strictness, number handling, and reflective access should preserve upgrade safety by keeping documented compatibility shims or clear migration paths.  
- **User story:** As a library upgrader, I want Gson to evolve without turning ordinary upgrades into unplanned rewrites so that bug fixes and safety improvements remain adoptable.  
- **Implementation note:** This requirement is intentionally broad because multiple release notes and issues show backward compatibility itself is part of Gson's behavioral surface.  
- **Conditions of satisfaction:** Behavior changes that tighten validation or change defaults preserve compatibility aliases, explicit migration guidance, or backward-compatible registration behavior; minor upgrades do not introduce silent wire incompatibility without documentation.  
- **Alternative paths:** Breaking behavior may still be justified in major shifts, but minor and maintenance releases should prefer compatibility-preserving transitions.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/releases_changelog.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `retrieved_documentation/github_issues/issue_2787_backwards_compat_broken.md`  
- **Specificity rating:** directional

**REQ-070** — Class-loading structure must avoid circular static initialization hazards  
- **Summary:** Gson's built-in adapter infrastructure must not rely on circular static initialization paths that can deadlock class loading under multi-threaded startup.  
- **User story:** As a production operator, I want application startup to be free of class-loading hangs so that low-level adapter initialization cannot wedge the process before work begins.  
- **Implementation note:** This is narrower than general thread safety and specifically targets static initialization architecture.  
- **Conditions of satisfaction:** Static initialization order for built-in adapters is acyclic or otherwise safe under concurrent class loading; no thread can block forever on reciprocal class-initialization locks.  
- **Alternative paths:** Lazy initialization, holder classes, or split initialization contexts may be used so long as the deadlock risk is removed.  
- **References:** `retrieved_documentation/github_issues/issue_2739_class_loading_deadlock.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

## Baseline coverage self-check

- **Baseline count preserved:** The previous file had **48** requirements. This revision expands the set to **70** requirements without dropping any baseline theme.
- **Coverage result:** Every baseline requirement is covered here, either directly or by a stricter, more explicit replacement.

| Baseline area | Covered by | Notes |
|---|---|---|
| Core API reuse, defaults, null handling, non-executable JSON, strictness propagation | REQ-001 to REQ-014 | Preserved and expanded with versioning, naming, exclusion, and instance-local configuration semantics. |
| Streaming semantics, malformed input, leniency, depth, trailing data, writer null policy | REQ-015 to REQ-025 | Preserved and expanded with explicit strictness-mode differences, top-level primitives, and non-finite numeric output gating. |
| Reflective binding, construction order, anonymous/local classes, duplicate fields, unsafe behavior | REQ-026 to REQ-039 | Preserved and expanded with cycle limitations, reflective remediation guidance, and declared-type/runtime-type accessibility behavior. |
| Maps, tree model, `TypeToken`, numeric strategy, raw generic fallbacks | REQ-052 to REQ-064 | Preserved and expanded with enum-key fallback, captured type-variable rejection, and bounded-generic requirements. |
| Platform and deployment boundaries | REQ-065 to REQ-070 | Preserved and expanded with reflection-free deployment, adapter/class-loading concurrency, and compatibility requirements. |
| Previously undercovered gaps now added | REQ-045 to REQ-051, REQ-061, REQ-068 to REQ-070 | Adds issue-driven contracts around deserializer-vs-serializer interference, selective null handling, `@JsonAdapter` limits, bounded generic loss, backward compatibility, and class-loading deadlocks. |

## Subsystem 7: Domain-knowledge gap audit (Pass 2)

### Category: RFC 8259 edge cases

**REQ-071** — Byte order mark handling is limited to the start of the document  
- **Summary:** Gson must tolerate a Unicode BOM only as the very first character of a JSON document and must reject the same code point everywhere else in the payload.  
- **User story:** As an integrator receiving JSON from mixed producers, I want a leading BOM to be tolerated without turning BOMs elsewhere into silent whitespace so that interoperability hacks do not weaken parsing correctness.  
- **Implementation note:** `JsonReader` strips `\ufeff` only on the first buffer fill before any other content has been consumed; later occurrences stay ordinary input and must fail if they appear where JSON has no valid token.  
- **Conditions of satisfaction:** A document beginning with `\ufeff` parses the same as the BOM-free equivalent; a BOM inside an array, object, string delimiter boundary, or later token position fails with location context instead of being skipped.  
- **Alternative paths:** Callers can remove BOMs before parsing, but Gson's built-in tolerance must stay narrowly scoped to the document start rather than acting as a general whitespace extension.  
- **References:** RFC 8259 section 8.1; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** specific

**REQ-072** — Token-separating whitespace remains RFC-exact  
- **Summary:** Outside strings, Gson must treat only RFC JSON whitespace as ignorable token separation; characters such as U+2028 and U+2029 are valid string contents but must not be accepted as structural whitespace.  
- **User story:** As a caller relying on standards-compatible parsing, I want Gson to distinguish legal string content from legal inter-token whitespace so that payloads accepted by Gson do not drift away from other RFC-oriented parsers.  
- **Implementation note:** `JsonReader`'s non-whitespace scan and escape handling together define this boundary: line separators may appear unescaped in strings, but not as separators between tokens.  
- **Conditions of satisfaction:** JSON separated by space, tab, CR, or LF parses normally; payloads that rely on U+2028 or U+2029 as array/object whitespace fail; those same characters remain readable inside string values.  
- **Alternative paths:** Producers that need maximum interoperability may escape these characters in strings, but Gson must not silently broaden the structural whitespace grammar.  
- **References:** RFC 8259 sections 2 and 7; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** specific

**REQ-073** — Unicode escape handling stays lossless for valid input and explicit for malformed input  
- **Summary:** Gson must decode complete Unicode escapes and valid surrogate pairs without loss, while malformed Unicode escapes or other invalid escape forms must fail explicitly instead of being silently rewritten or normalized.  
- **User story:** As a developer exchanging non-ASCII JSON across systems, I want valid supplementary characters to round-trip correctly and broken escape sequences to fail deterministically so that internationalized payloads do not degrade into mojibake or parser-specific surprises.  
- **Implementation note:** `JsonReader` already decodes `\uXXXX` escapes and raises syntax errors for malformed escape sequences, while `JsonWriter` preserves ordinary Unicode text and force-escapes U+2028/U+2029 for interoperability; the missing contract is that these Unicode paths are part of Gson's intended behavior, not incidental implementation detail.  
- **Conditions of satisfaction:** Escaped BMP characters decode to the expected Java `String`; escaped supplementary code points such as `\uD83D\uDE0A` decode to the correct single Unicode scalar value; malformed `\u` escapes fail with syntax context; writer-side string escaping does not emit raw U+2028/U+2029 even when the source string contains them.  
- **Alternative paths:** Producers may pre-normalize or pre-escape text, but Gson must not require callers to avoid supplementary characters or guess whether malformed escapes will be accepted.  
- **References:** RFC 8259 sections 7 and 8.2; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`; `gson/src/test/java/com/google/gson/functional/InternationalizationTest.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** directional

### Category: Java language and runtime integration

**REQ-074** — Record binding honors canonical construction and accessor-based serialization  
- **Summary:** On JVMs with record support, Gson must deserialize records through their canonical constructor and serialize them through their record accessors rather than treating them as mutable field bags.  
- **User story:** As a Java developer using records for invariants and derived state, I want record construction and accessor overrides to remain observable during Gson round-trips so that validation and normalization encoded in the record contract are not bypassed.  
- **Implementation note:** `ReflectiveTypeAdapterFactory` switches record types onto a dedicated `RecordAdapter`, using `ReflectionHelper` to discover record components, canonical constructors, and accessor methods.  
- **Conditions of satisfaction:** Deserializing a record runs canonical-constructor logic; constructor failures surface instead of being bypassed by unsafe allocation; serialization observes accessor overrides; accessor exceptions surface as JSON I/O failures with the accessor identified.  
- **Alternative paths:** Callers may still supply custom adapters or block reflection, but default reflective record support must preserve the semantics that make records different from ordinary classes, including for local records.  
- **References:** Java record contract; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/reflect/ReflectionHelper.java`; `gson/src/test/java/com/google/gson/functional/Java17RecordTest.java`; `gson/src/test/java/com/google/gson/internal/bind/Java17ReflectiveTypeAdapterFactoryTest.java`  
- **Specificity rating:** specific

**REQ-075** — Record component defaults and null handling follow constructor-argument semantics  
- **Summary:** Missing record components must behave like omitted constructor arguments synthesized by Gson (`null` for references, JVM defaults for primitives), while explicit JSON `null` for primitive components must fail with component-specific diagnostics.  
- **User story:** As a caller deserializing immutable record types, I want Gson's handling of absent versus explicit `null` values to match record-constructor semantics so that immutable models fail or default predictably instead of being mutated piecemeal.  
- **Implementation note:** The record adapter accumulates constructor arguments in an array pre-seeded with primitive defaults and rejects `null` results for primitive components before invoking the canonical constructor.  
- **Conditions of satisfaction:** A missing reference component deserializes as `null`; a missing primitive component deserializes as `0`, `false`, or `'\0'` as appropriate; an explicit JSON `null` for a primitive component fails with the component name and JSON path; a custom adapter that returns `null` for a primitive component fails the same way.  
- **Alternative paths:** Callers who need required-field enforcement beyond these defaults must implement it in the canonical constructor or a custom adapter, not expect reflective field mutation after construction.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/test/java/com/google/gson/functional/Java17RecordTest.java`  
- **Specificity rating:** specific

### Category: Ecosystem and Java serialization interop

**REQ-076** — Gson-exposed generic container values remain Java-serializable  
- **Summary:** Runtime container and numeric helper values that Gson returns for generic/object-style deserialization must remain safely Java-serializable, preserving logical contents without requiring callers to know Gson's internal classes.  
- **User story:** As an application integrating Gson with Java serialization or session replication, I want deserialized `Map`, `List`, and lazily parsed numeric values to survive `ObjectOutputStream` round-trips so that generic JSON results do not leak non-serializable implementation details.  
- **Implementation note:** This contract is carried by returned collection implementations such as `LinkedTreeMap` and helper number types such as `LazilyParsedNumber`, which use serialization hooks to round-trip as stable logical values.  
- **Conditions of satisfaction:** Generic `Map` and `List` results from `fromJson` are serializable and preserve equality and map iteration order after Java serialization; lazily parsed numbers serialize into stable numeric values rather than failing due to Gson-internal runtime types.  
- **Alternative paths:** Callers deserializing directly into their own domain classes control those classes' Java-serialization behavior themselves, but Gson's own fallback/runtime helper types must not be the thing that breaks serialization.  
- **References:** `gson/src/test/java/com/google/gson/JavaSerializationTest.java`; `gson/src/main/java/com/google/gson/internal/LinkedTreeMap.java`; `gson/src/test/java/com/google/gson/internal/LinkedTreeMapTest.java`; `gson/src/main/java/com/google/gson/internal/LazilyParsedNumber.java`; `gson/src/test/java/com/google/gson/internal/LazilyParsedNumberTest.java`  
- **Specificity rating:** specific

### Category: Backward-compatibility invariants

**REQ-077** — Adapter-factory consultation order remains a stable compatibility contract  
- **Summary:** Gson must preserve the documented effective order in which adapter factories are consulted: protected core adapters first, then user registrations in last-in-first-out order, then built-in platform/composite adapters, and reflective fallback last.  
- **User story:** As a library maintainer registering custom adapters, I want adapter precedence to stay stable across upgrades so that a patch release does not silently reroute a type from my adapter to a built-in or reflective adapter.  
- **Implementation note:** `GsonBuilder.createFactories()` assembles this chain deliberately: JSON tree/object handling and the excluder occupy fixed positions, user adapters are reversed into LIFO order, and composite/reflective factories terminate the search.  
- **Conditions of satisfaction:** Later user registrations still win within their precedence band; exact and hierarchy adapters continue to compose consistently with REQ-043 and REQ-044; delegate lookup skips factories by reference and resumes at the next effective factory; reflective binding is consulted only after earlier applicable factories decline the type.  
- **Alternative paths:** Callers can still centralize registrations or use `getDelegateAdapter(...)` for controlled delegation, but they must not need version-specific workarounds for factory ordering drift.  
- **References:** `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/test/java/com/google/gson/functional/TypeAdapterPrecedenceTest.java`; `gson/src/test/java/com/google/gson/GsonTest.java`; `gson/src/test/java/com/google/gson/functional/DefaultTypeAdaptersTest.java`  
- **Specificity rating:** specific

### Pass 2 summary

- **New requirements added:** 7
- **Domain areas covered:** RFC 8259 parser edge cases, Unicode escape and supplementary-character handling, Java record integration, Java-serialization interoperability for Gson-exposed runtime types, and backward-compatibility invariants around adapter-factory ordering.
- **Considered but already covered elsewhere:** duplicate map-key rejection (REQ-054), raw/null map-key stringification (REQ-055), captured type variables and bounded generic validation (REQ-059 to REQ-061), deep nesting limits (REQ-021), adapter/thread initialization safety (REQ-001, REQ-042, REQ-068), anonymous/local class reflective unsupportedness (REQ-029), and numeric strategy / non-finite number behavior (REQ-023, REQ-062).
