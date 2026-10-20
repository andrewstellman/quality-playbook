# Behavioral Requirements — Gson

Generated: 2026-04-04
Pipeline: contract-extraction v2 with narrative pass

## Project Overview

Gson is a small, zero-dependency Java library for moving data between ordinary Java objects and JSON. In the Java ecosystem it sits in the layer between application models and wire formats: a developer hands Gson a domain object, configuration object, API payload class, or intermediate tree structure, and Gson turns that value into JSON text; the same library can take JSON from a file, socket, queue, or HTTP response and rebuild a Java representation on the other side. That simplicity is why Gson still shows up in applications, Android codebases, test fixtures, frameworks, and internal tools years after its original release. It gives teams a default path that is easy to start with, but it also leaves room for precise control when a schema, platform, or legacy integration demands more than the defaults.

The people who use Gson are not all solving the same problem. Many are application developers who want to serialize POJOs with as little ceremony as possible: create a `Gson`, call `toJson` or `fromJson`, and keep moving. Others are library and framework authors who need a stable, reusable JSON layer with custom adapters, naming rules, exclusion policies, or number handling that can be shared across many callers. Some teams adopt Gson while migrating from another JSON library and need a bridge that can preserve existing wire formats while they move gradually. Others work against older or imperfect APIs that emit comments, unusual numbers, alternate field names, or other non-standard JSON, and they rely on Gson's strictness controls, tree model, and adapter hooks to make that data manageable without rewriting the whole stack.

The two main data flows in Gson mirror those everyday jobs. On serialization, a caller starts with a `Gson` instance, usually created either directly for defaults or through `GsonBuilder` for configuration. Gson then resolves a `TypeAdapter` for the requested type, often by consulting user registrations before falling back to its built-in and reflective adapters. That adapter writes JSON through the streaming layer, using `JsonWriter` to produce the final text or, if the caller wants an in-memory representation first, a `JsonElement` tree such as `JsonObject`, `JsonArray`, or `JsonPrimitive`. On deserialization, the path runs in the opposite direction: JSON text is tokenized by `JsonReader`, Gson finds the adapter chain for the target type, and the selected adapter rebuilds Java values either by direct custom logic or by reflective binding through `ReflectiveTypeAdapterFactory`. Along the way, the builder's choices around naming, exclusion, number strategies, null handling, strictness, and formatting shape what is accepted and what is produced.

The library's design philosophy explains why those paths look the way they do. Gson favors an adapter factory chain over a single global type registry because composition, override order, and delegation matter as much as simple lookup. It offers both streaming and tree APIs because some users need low-allocation token control while others need a mutable JSON model they can inspect or transform. It uses a builder pattern because most callers want sensible defaults first and optional configuration second, and it treats built `Gson` instances as immutable snapshots so they can be reused safely across threads. Most importantly, Gson's default reflective behavior navigates the target Java type tree rather than the raw JSON tree, which keeps the caller's requested model in charge: expected fields are filled, extra JSON is ignored unless a custom adapter says otherwise, and the extension points remain available whenever the defaults stop being enough.

## Use Cases

### Use Case 1: Serialize and deserialize a POJO with defaults

**Actor:** Application developer

**Preconditions:** The developer has a domain class with an acyclic object graph and a target type that Gson can handle with its default behavior.

**Steps:**
1. The developer creates `new Gson()` or reuses an existing default instance.
2. The developer passes a Java object to `toJson(...)`.
3. Gson applies its documented default configuration and resolves the default reflective path for the object's type.
4. Gson writes compact JSON using eligible fields and omits `null` object members under the default policy.
5. The developer later passes JSON text and the target class to `fromJson(...)`.
6. Gson consumes the complete value, constructs the target object, and populates eligible fields while leaving absent members in their post-construction state.

**Postconditions:** The object is rendered and restored according to the default Gson contract, subject to the documented limits of reflective binding.

**Alternative paths:** If trailing data remains after the top-level value, deserialization fails. If the object graph contains unsupported cycles or anonymous/local classes, the default reflective path does not produce a normal round trip.

**Requirements:** REQ-001, REQ-002, REQ-007, REQ-023, REQ-060, REQ-024, REQ-025

### Use Case 2: Register and use a custom type adapter

**Actor:** Library integrator

**Preconditions:** The integrator has a type whose JSON representation needs to differ from Gson's default handling and an adapter implementation that follows Gson's streaming contract.

**Steps:**
1. The integrator creates a `GsonBuilder`.
2. The integrator registers an exact-type adapter, hierarchy adapter, or factory for the target type.
3. The integrator calls `create()` to build an immutable `Gson` snapshot.
4. A caller serializes or deserializes a value of the target type.
5. Gson resolves the effective adapter according to registration scope, precedence, and delegation rules.
6. The adapter reads or writes exactly one JSON value and composes safely with the surrounding stream.

**Postconditions:** The customized type uses the registered behavior without altering unrelated types or silently corrupting stream state.

**Alternative paths:** If the registration scope is too narrow, the adapter is not used for subtypes. If the adapter recurses incorrectly or forms a delegation cycle, composition fails according to the documented adapter limits.

**Requirements:** REQ-001, REQ-014, REQ-016, REQ-012, REQ-013, REQ-017, REQ-020, REQ-021

### Use Case 3: Configure naming, exclusion, and strictness through `GsonBuilder`

**Actor:** Framework author

**Preconditions:** The framework needs one reusable JSON configuration with schema-specific naming, field filters, and parser/writer compliance settings.

**Steps:**
1. The framework creates a `GsonBuilder`.
2. The framework applies naming, exclusion, annotation, and strictness options in the desired order.
3. The framework builds a `Gson` instance and shares it with the rest of the application.
4. Callers use that instance through ordinary `toJson`, `fromJson`, `JsonReader`, or `JsonWriter` entry points.
5. Gson applies the built snapshot's configuration consistently without leaking those settings into other independently created instances.

**Postconditions:** The resulting `Gson` instance enforces one coherent configuration surface that stays stable for its lifetime.

**Alternative paths:** If another module needs a different policy, it creates a separate `Gson` instance. If callers want annotation-free behavior, they can omit the annotation-related builder settings entirely.

**Requirements:** REQ-001, REQ-003, REQ-006, REQ-095, REQ-093, REQ-094, REQ-096, REQ-101

### Use Case 4: Deserialize a generic type with `TypeToken`

**Actor:** Application developer

**Preconditions:** The developer needs to deserialize a parameterized type such as `List<MyType>` or `Map<String, Result<Foo>>`.

**Steps:**
1. The developer constructs a `TypeToken` or programmatic `Type` that carries the full generic shape.
2. The developer passes that type information to `fromJson(...)`.
3. Gson validates the token and resolves adapters against the full generic type instead of a raw class.
4. Gson deserializes collection members and nested values using the supplied type metadata.

**Postconditions:** The returned object graph reflects the requested generic type rather than a raw fallback shape.

**Alternative paths:** If the developer passes a raw class or captures a forbidden type variable, Gson fails or falls back only within the documented erased-type boundaries.

**Requirements:** REQ-004, REQ-053, REQ-054, REQ-055, REQ-056, REQ-057

### Use Case 5: Parse incrementally with the streaming API

**Actor:** Performance-sensitive developer

**Preconditions:** The developer needs low-allocation, token-by-token access to a JSON stream or wants to implement a custom `TypeAdapter`.

**Steps:**
1. The developer creates or receives a `JsonReader`.
2. The developer consumes tokens with `begin*`, `next*`, `hasNext()`, and `end*` calls.
3. When unknown content appears, the developer uses `skipValue()` to advance past the entire subtree.
4. Gson or the custom adapter continues reading from the next valid token boundary.
5. If writing is needed, the developer uses matching `JsonWriter` operations to emit a well-formed value.

**Postconditions:** The caller processes exactly the intended portion of the stream while preserving correct reader and writer state.

**Alternative paths:** If the input exceeds nesting limits, uses syntax outside the active strictness mode, or violates state-machine rules, parsing fails with location context instead of drifting forward in a corrupted state.

**Requirements:** REQ-039, REQ-040, REQ-041, REQ-042, REQ-043, REQ-044

### Use Case 6: Inspect and transform JSON through the tree model

**Actor:** Tooling developer

**Preconditions:** The developer needs an in-memory JSON representation for inspection, patching, or bridging between tree-based and streaming logic.

**Steps:**
1. The developer parses JSON into `JsonElement` form or builds a tree manually.
2. The developer reads and mutates `JsonObject`, `JsonArray`, `JsonPrimitive`, and `JsonNull` nodes.
3. The developer optionally exposes that tree through `JsonTreeReader` or constructs one through `JsonTreeWriter`.
4. The developer serializes the resulting tree back to JSON text.

**Postconditions:** The tree remains internally consistent, serializable, and faithful to Gson's normal token/path model.

**Alternative paths:** If code introduces unsupported custom `JsonElement` subclasses or expects raw Java `null` to behave like JSON null, the tree bridge fails or normalizes values according to the documented tree rules.

**Requirements:** REQ-066, REQ-067, REQ-065, REQ-048, REQ-049, REQ-051, REQ-068

### Use Case 7: Consume legacy or non-standard JSON intentionally

**Actor:** Developer integrating with a legacy API

**Preconditions:** The upstream system emits JSON that may rely on comments, relaxed literals, compatibility prefixes, or other non-standard syntax.

**Steps:**
1. The developer chooses the appropriate strictness policy for the integration.
2. The developer configures that policy on `GsonBuilder` or directly on the streaming reader or writer.
3. Gson parses the input under the selected acceptance rules and, when needed, tolerates the non-executable JSON prefix.
4. The developer processes the resulting values while keeping the integration isolated from stricter code paths.

**Postconditions:** Legacy inputs are accepted only where the caller explicitly chose the compatibility mode.

**Alternative paths:** If the caller switches to strict mode, the same payload may fail for comments, invalid escapes, or other non-standard syntax. Producers that need RFC-only interoperability can keep those relaxed forms out of the payload entirely.

**Requirements:** REQ-099, REQ-006, REQ-041, REQ-045, REQ-046, REQ-047

### Use Case 8: Reuse one configured `Gson` instance across threads

**Actor:** Server developer

**Preconditions:** The application has one fully configured `Gson` instance and any registered adapters are safe for concurrent reuse.

**Steps:**
1. The application builds a `Gson` instance during startup.
2. Multiple threads call `toJson(...)`, `fromJson(...)`, or adapter-driven APIs concurrently.
3. Gson resolves or reuses adapters without leaking placeholder or half-initialized state between threads.
4. Each request gets the same stable configuration snapshot.

**Postconditions:** The shared instance behaves consistently under concurrent load without requiring a separate `Gson` per request.

**Alternative paths:** If a custom adapter keeps unsafe mutable state, it can invalidate the guarantee for its own type. If a module needs different settings, it should create a separate `Gson` instance rather than mutating a shared one.

**Requirements:** REQ-105, REQ-001, REQ-003, REQ-106, REQ-107

## Cross-Cutting Concerns

### Threading model

Gson is built around reusable configuration snapshots rather than per-call mutable sessions. A built `Gson` instance is meant to be shared, but that guarantee depends on two supporting rules: registered adapters must themselves be stateless or otherwise thread-safe, and first-use adapter resolution must not deadlock or leak partially initialized delegates to other threads. In practice, that means the safe sharing boundary is the immutable `Gson` plus safe adapter implementations, not arbitrary mutable helper state around them (REQ-001, REQ-105, REQ-106, REQ-107).

### Null contract

Gson treats absence, explicit JSON `null`, and Java `null` as related but distinct states. Writer configuration controls whether object members with Java `null` are omitted or emitted, reflective binding leaves missing members in their constructed state, primitive fields react differently from wrapper fields when explicit `null` is read, and the tree model uses `JsonNull` instead of raw Java `null` to represent a present JSON null. Reviewers working in this area should check whether a change affects object binding, adapter boundaries, collection elements, and tree nodes in the same way, because null behavior is rarely isolated to one layer (REQ-059, REQ-060, REQ-061, REQ-062, REQ-063, REQ-064, REQ-065, REQ-066, REQ-068).

### Error philosophy

Gson's failures are supposed to be early, typed, and actionable. The library distinguishes malformed JSON, I/O problems, and general parse or binding failures through unchecked exception types such as `JsonSyntaxException`, `JsonIOException`, and `JsonParseException`, and the requirements emphasize diagnostic context like JSON path, incomplete-document detection, duplicate-name rejection, and remediation for blocked reflection. The goal is not to recover silently from bad input, but to stop at the boundary with enough context that a caller can fix the data, the model, or the configuration (REQ-005, REQ-007, REQ-103, REQ-042, REQ-027, REQ-104).

### Backward compatibility strategy

Gson is conservative about changing behavior that other libraries, stored payloads, or framework integrations already depend on. That is why compatibility concepts such as legacy strictness, deprecated-but-preserved APIs, stable default wire shapes, and documented adapter precedence appear throughout the requirements instead of being treated as incidental history. A change in this codebase is not finished when it is locally correct; it also has to be evaluated against upgrade safety and existing JSON already in the wild (REQ-006, REQ-041, REQ-019, REQ-108, REQ-109, REQ-110).

### Configuration composition

Builder options do not simply accumulate in an abstract sense; they compose through specific rules that determine what a `Gson` instance means. Snapshotting at `create()`, instance-local configuration, exact-versus-hierarchy adapter scope, last-wins registration, naming and exclusion semantics, and stable factory-order consultation all combine to define the final behavior a caller sees. When reviewing changes in configuration code, it helps to ask not only whether one option works in isolation, but also which earlier or later options it should override, preserve, or delegate to (REQ-001, REQ-003, REQ-093, REQ-094, REQ-012, REQ-013, REQ-110).

## Core API

### Category: configuration surface

This category covers the choices callers make before any JSON is read or written. These requirements define what a `Gson` instance means once it has been built, and later sections rely on those defaults and configuration boundaries staying stable.

**REQ-001** — Builder snapshots are immutable after creation  
- **Summary:** Once `GsonBuilder.create()` returns a `Gson`, later builder mutations must not change the behavior of the already-created instance.  
- **User story:** As a library integrator, I want builder configuration to be snapshotted at creation time so that later setup code cannot silently change a `Gson` instance already in use.  
- **Implementation note:** This is a builder lifecycle contract rather than a formatting detail; it protects adapter order, exclusion policy, and numeric or strictness settings from retroactive drift.  
- **Conditions of satisfaction:** Creating a `Gson` freezes the then-current builder state; later builder registrations or flag changes only affect newly created instances; previously created instances remain behaviorally stable.  
- **Alternative paths:** If callers need multiple variants, they may create multiple `Gson` instances or clone builders, but not mutate an already-built instance through shared builder state.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** specific

**REQ-002** — Default `new Gson()` behavior is stable  
- **Summary:** The default no-builder configuration must emit compact JSON, omit `null` object fields, escape HTML-sensitive characters, use identity field naming, exclude `static` and `transient` fields, and apply default date handling unless explicitly overridden.  
- **User story:** As a user taking the simplest entry point, I want `new Gson()` to have stable, documented defaults so that I can predict wire format without reading implementation code.  
- **Implementation note:** This is the most widely depended-on contract in the library; drift here changes output for all zero-configuration users.  
- **Conditions of satisfaction:** Default serialization omits `null` object members, preserves compact formatting, excludes `static` and `transient` fields, escapes HTML-sensitive characters, and uses documented defaults for dates and names.  
- **Alternative paths:** Callers may override any of these defaults with `GsonBuilder`, but the no-args constructor must remain predictable on its own.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

**REQ-003** — Configuration remains instance-local  
- **Summary:** Adapter registrations, exclusion rules, naming policies, numeric strategies, strictness, and formatting settings must apply only to the `Gson` instance that was configured with them.  
- **User story:** As an application maintainer, I want independent `Gson` instances to stay isolated so that framework defaults and app-specific overrides cannot bleed into each other.  
- **Implementation note:** This is especially important for troubleshooting cases where multiple frameworks or modules create their own `Gson` instances.  
- **Conditions of satisfaction:** A registration on one `GsonBuilder` affects only the instances built from that builder state; another independently created `Gson` keeps its own defaults or its own explicit configuration.  
- **Alternative paths:** Shared helper factories may centralize construction, but configuration isolation must still hold between distinct instances.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** directional

**REQ-004** — Generic deserialization requires explicit type information  
- **Summary:** Deserializing parameterized types must require explicit `Type` or `TypeToken` information; Gson must not imply that a raw `Class` target preserves element or member types.  
- **User story:** As a developer deserializing collections and generic wrappers, I want missing generic type information to fail safe so that I do not get plausible-looking but wrongly typed object graphs.  
- **Implementation note:** This is one of Gson's most important correctness boundaries because raw types are a common source of `LinkedTreeMap` fallbacks and late `ClassCastException`s.  
- **Conditions of satisfaction:** `fromJson` with full generic type information preserves member typing; raw-type usage yields generic representations or validation errors rather than pretending to reconstruct domain types.  
- **Alternative paths:** Callers may use `TypeToken`, `TypeToken.getParameterized(...)`, parser APIs, or custom adapters to restore type information.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-005** — Type adapter result types must remain compatible with the requested target  
- **Summary:** If a custom adapter produces a runtime value incompatible with the requested target type, Gson must fail with a clear type-mismatch error instead of silently returning the wrong object.  
- **User story:** As an adapter author, I want misregistered or buggy adapters to fail immediately so that type-safety problems are caught at the JSON boundary instead of much later in application code.  
- **Implementation note:** This protects the public API from success-shaped corruption when adapter wiring is wrong.  
- **Conditions of satisfaction:** Incompatible adapter output does not silently escape `fromJson`; the failure identifies the mismatch rather than returning an object of the wrong type.  
- **Alternative paths:** Correct adapter registration or narrower target types avoid this failure path.  
- **References:** `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** specific

**REQ-006** — Strictness configuration propagates to reader and writer entry points  
- **Summary:** Builder-level strictness configuration must propagate to `JsonReader`, `JsonWriter`, and all `Gson` read/write entry points so that parsing and writing enforce the same selected compliance mode.  
- **User story:** As a caller selecting a strictness mode, I want every JSON entry point to honor it so that one code path cannot silently parse or emit content under different rules.  
- **Implementation note:** This includes direct `Gson` operations and factory-created readers or writers.  
- **Conditions of satisfaction:** A configured strictness value is applied consistently to created readers and writers; per-call helpers do not silently revert to legacy defaults; read and write semantics stay aligned.  
- **Alternative paths:** Callers may configure strictness directly on a `JsonReader` or `JsonWriter`, but builder-level configuration must remain sufficient for ordinary usage.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

### Category: document entry points

These requirements describe the promises on Gson's top-level `toJson` and `fromJson` style APIs. Reviewers should read them as framing rules: they define what counts as a complete document and what kinds of top-level values those entry points are expected to accept.

**REQ-007** — Full-value entry points reject trailing data  
- **Summary:** Deserialization entry points that claim to consume one complete JSON value must detect and reject trailing non-whitespace data after that value.  
- **User story:** As a caller reading framed JSON, I want extra bytes after the target value to be surfaced as errors so that protocol corruption and concatenated payloads are not mistaken for success.  
- **Implementation note:** This is a framing guarantee at the `Gson` API boundary, not just a lexer feature.  
- **Conditions of satisfaction:** Reading a complete value fails if unread trailing data remains beyond permitted whitespace; success means the intended value was fully consumed.  
- **Alternative paths:** Stream-oriented callers may use incremental parsing APIs when multiple JSON values in one stream are intentional.  
- **References:** `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/JsonStreamParser.java`  
- **Specificity rating:** specific

**REQ-008** — Top-level primitive JSON values are supported where documented  
- **Summary:** Gson must accept JSON documents whose top-level value is a string, number, boolean, or `null` in the modes and entry points documented as supporting RFC 7159/8259 top-level values.  
- **User story:** As a user exchanging scalar JSON values, I want top-level primitives to work where Gson says they work so that valid JSON is not unnecessarily rejected.  
- **Implementation note:** Historical releases tightened this behavior; the requirement is about externally visible acceptance, not the parser's internal path.  
- **Conditions of satisfaction:** Supported reader paths accept documented top-level primitive documents and serialize matching scalar values correctly.  
- **Alternative paths:** Callers may still wrap values in arrays or objects for protocol reasons, but the documented scalar paths must remain available.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/javadoc_gson_class.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-009** — Tree-based Gson entry points preserve tree-local null and type semantics  
- **Summary:** `Gson.toJsonTree(...)` and `Gson.fromJson(JsonElement, ...)` must remain distinct tree-based entry points whose contracts are about in-memory `JsonElement` values rather than complete text-document framing.  
- **User story:** As a caller moving between typed objects and `JsonElement` trees, I want the tree entry points to keep their own null and type-resolution rules so that I can bridge through trees without accidentally inheriting text-stream framing assumptions.  
- **Implementation note:** These overloads are thin wrappers over `JsonTreeWriter` and `JsonTreeReader`, so they inherit tree-reader coercion and path semantics rather than string-reader full-consumption checks.  
- **Conditions of satisfaction:** `toJsonTree(null)` returns `JsonNull.INSTANCE`; `toJsonTree(src, typeOfSrc)` uses the supplied declared type instead of runtime erasure; `fromJson((JsonElement) null, ...)` returns Java `null`; `fromJson(JsonElement, TypeToken)` delegates through `JsonTreeReader`, so it consumes exactly the provided tree and does not impose separate trailing-document checks.  
- **Alternative paths:** Callers who need complete-document framing or stream ownership semantics should use the string, reader, or `JsonReader` entry points instead of the tree overloads.  
- **References:** `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java`; `gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java`  
- **Specificity rating:** specific

**REQ-010** — Standalone tree parsers keep their own lenient framing rules  
- **Summary:** `JsonParser.parseString(...)` and `JsonParser.parseReader(...)` must keep the standalone tree-parser contract: parse leniently by default, require full consumption only on the string/`Reader` overloads, and preserve caller-visible `JsonReader` state on the streaming overload.  
- **User story:** As a caller parsing JSON directly into a tree without binding it to a Java type, I want the standalone parser entry points to have explicit framing and strictness rules so that tree parsing behaves predictably across strings, readers, and preconfigured `JsonReader`s.  
- **Implementation note:** These methods are intentionally not aliases for `Gson.fromJson(..., JsonElement.class)`; they codify standalone parser behavior, including backward-compatible temporary leniency for `LEGACY_STRICT` readers.  
- **Conditions of satisfaction:** `parseString(String)` and `parseReader(Reader)` parse one complete JSON document and reject multiple top-level values or trailing data; both use lenient parsing by default; `parseReader(JsonReader)` parses only the next JSON value and intentionally allows later top-level values or trailing data; if the supplied reader is `STRICT`, parsing stays strict, otherwise `LEGACY_STRICT` is temporarily changed to `LENIENT` and restored before return; malformed syntax and numeric format failures surface as `JsonSyntaxException`, while I/O failures surface as `JsonIOException`.  
- **Alternative paths:** Callers who need typed binding should use `Gson.fromJson(...)`, and callers who intentionally consume many concatenated values should use `JsonStreamParser` or manual `JsonReader` loops.  
- **References:** `gson/src/main/java/com/google/gson/JsonParser.java`; `gson/src/main/java/com/google/gson/internal/Streams.java`  
- **Specificity rating:** specific

**REQ-011** — `JsonStreamParser` is the multi-value entry point for concatenated JSON  
- **Summary:** `JsonStreamParser` must remain the dedicated entry point for iterating over concatenated top-level JSON values in lenient mode, with caller-managed synchronization for compound access.  
- **User story:** As a caller processing a stream that intentionally contains multiple JSON values, I want one API that exposes that framing model explicitly so that concatenated input is not mistaken for a malformed single document.  
- **Implementation note:** This class wraps one `JsonReader` set to `LENIENT`, exposes `Iterator<JsonElement>`, and only synchronizes the `hasNext()` peek internally; callers still have to synchronize `hasNext()`/`next()` pairs themselves.  
- **Conditions of satisfaction:** Both constructors create a parser over concatenated values and configure the underlying `JsonReader` to `Strictness.LENIENT`; `hasNext()` returns whether another top-level value remains by peeking for `END_DOCUMENT`; `next()` returns the next `JsonElement` or throws `NoSuchElementException` if none remain; malformed JSON is surfaced as `JsonSyntaxException`, I/O failures as `JsonIOException`, and `remove()` always throws `UnsupportedOperationException`; cross-thread compound iteration remains caller-synchronized rather than internally serialized.  
- **Alternative paths:** Callers who need one complete document should use `Gson.fromJson(...)` or `JsonParser`, and callers who need custom token handling can stay on `JsonReader`.  
- **References:** `gson/src/main/java/com/google/gson/JsonStreamParser.java`  
- **Specificity rating:** specific

## Type Adapter System

### Category: registration and resolution

This category explains how Gson decides which adapter owns a type. It builds directly on the core configuration surface above, and small ordering mistakes here can cascade through every extension scenario below.

**REQ-012** — Exact-type and hierarchy registrations stay distinct  
- **Summary:** `registerTypeAdapter(...)` must apply to the exact registered type, while subclass coverage requires `registerTypeHierarchyAdapter(...)` or a factory that intentionally matches a wider set of types.  
- **User story:** As a caller registering custom handling, I want the scope of adapter registration to be predictable so that a parent-type registration neither misses expected subtypes nor silently hijacks unrelated ones.  
- **Implementation note:** This is a frequent source of "adapter not used" confusion and a key part of adapter precedence.  
- **Conditions of satisfaction:** Exact-type registrations do not automatically apply to subclasses; hierarchy registrations or factories do; incorrect type registration remains diagnosable.  
- **Alternative paths:** Users may register both exact and hierarchy handlers or use a `TypeAdapterFactory` for more complex matching logic.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-013** — Later adapter registrations for the same type win  
- **Summary:** If multiple adapters are registered for the same effective type on one builder, the last relevant registration must determine the effective behavior.  
- **User story:** As a maintainer composing builder setup from several modules, I want override order to be deterministic so that final configuration is understandable and testable.  
- **Implementation note:** Community guidance highlights this as a subtle but important builder behavior.  
- **Conditions of satisfaction:** Repeated registrations for the same type produce deterministic last-one-wins behavior; the effective adapter is not order-random.  
- **Alternative paths:** Teams may centralize builder construction to avoid accidental overriding, but the override rule must still remain stable.  
- **References:** `retrieved_documentation/community/futurestud_custom_serialization.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** specific

### Category: adapter protocol and composition

These requirements describe what adapters must do once selected, including delegation, runtime-type interactions, and supported escape hatches around reflection. Implementers should keep stream ownership and writer or null semantics in mind, because composition bugs often look correct until a nested edge case appears.

**REQ-014** — Custom adapters remain a supported escape hatch from blocked reflection  
- **Summary:** If reflective member access is unavailable or undesirable, caller-supplied adapters and factories must remain a supported path for serializing and deserializing the affected types.  
- **User story:** As a user on JPMS, Android, or restricted runtimes, I want explicit adapters to replace reflection so that platform limits do not make Gson unusable.  
- **Implementation note:** This is a compatibility escape hatch heavily referenced by troubleshooting guidance.  
- **Conditions of satisfaction:** Types blocked from reflection can still be handled through registered adapters; adapter registration takes precedence where documented; reflection errors are not raised for types fully covered by explicit adapters.  
- **Alternative paths:** Tree APIs, stream APIs, and reflection-access filters that block all reflection are also supported ways to avoid reflective binding.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-015** — Declared-type adapters remain usable when runtime implementations are inaccessible  
- **Summary:** If the runtime object type is an inaccessible internal implementation but Gson has a supported adapter for the declared supertype, serialization must use the declared-type contract rather than failing only because the concrete runtime type is inaccessible.  
- **User story:** As a caller working with interfaces returned by libraries, I want serialization to honor accessible declared types so that internal implementation classes do not leak into my JSON boundary.  
- **Implementation note:** This is a runtime-type and accessibility interaction rule.  
- **Conditions of satisfaction:** Declared-type serialization can succeed when the declared type has a supported adapter; inaccessible implementation details do not force reflection into blocked internals unnecessarily.  
- **Alternative paths:** Deserializing directly into the inaccessible implementation may still fail; callers can also register a concrete adapter if needed.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java`  
- **Specificity rating:** directional

**REQ-016** — `TypeAdapter` reads and writes exactly one value  
- **Summary:** A `TypeAdapter` implementation must read exactly one JSON value and write exactly one JSON value so that stream position stays correct for surrounding adapters.  
- **User story:** As an adapter author, I want Gson to rely on a precise adapter contract so that custom adapters compose safely without corrupting the reader or writer state.  
- **Implementation note:** This is the core TypeAdapter protocol.  
- **Conditions of satisfaction:** Primitive adapters consume one primitive token; array and object adapters consume one balanced array or object; surrounding stream position is correct after delegation returns.  
- **Alternative paths:** Callers who prefer tree-based customization may use `JsonSerializer` or `JsonDeserializer`, but `TypeAdapter` users must obey the stricter stream contract.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-017** — Parent deserializers must not strip subclass serialization fields  
- **Summary:** Registering a custom deserializer for a parent type must not change the serialization behavior of subclass instances unless a serializer explicitly replaces that behavior.  
- **User story:** As a developer with polymorphic models, I want deserialization customization to be independent from runtime-type serialization so that subclass-specific fields are not silently dropped.  
- **Implementation note:** This was a real regression and is now a durable compatibility requirement.  
- **Conditions of satisfaction:** Subclass instances still serialize subclass fields when only a parent deserializer is registered; parent deserializer registration alone does not collapse runtime serialization to parent fields.  
- **Alternative paths:** If callers want fully custom parent-and-subclass handling, they can use a coordinated `TypeAdapterFactory`.  
- **References:** `retrieved_documentation/github_issues/issue_2032_deserializer_changes_serialization.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java`  
- **Specificity rating:** specific

**REQ-018** — Polymorphic wrappers must preserve delegated writer settings  
- **Summary:** If a polymorphic adapter delegates serialization to a subtype-specific adapter that intentionally changes the active writer configuration, the delegated setting must survive to the final output instead of being discarded during an intermediate tree conversion.  
- **User story:** As a library user combining polymorphism with custom null semantics, I want delegated subtype behavior to survive the wrapper layer so that the final JSON reflects the subtype adapter's documented output policy.  
- **Implementation note:** This is the precise behavioral gap surfaced by `RuntimeTypeAdapterFactory` null-setting loss.  
- **Conditions of satisfaction:** Delegated subtype writer settings such as `serializeNulls` remain observable in the emitted JSON; wrapper indirection does not silently erase them.  
- **Alternative paths:** Users can enable the setting globally or avoid tree-based polymorphic wrappers, but subtype-specific settings should not be lost by default adapter composition.  
- **References:** `retrieved_documentation/github_issues/issue_0676_runtime_type_adapter_serialize_nulls.md`; `retrieved_documentation/github_issues/issue_0913_selective_serialize_nulls.md`; `gson/src/main/java/com/google/gson/internal/bind/TreeTypeAdapter.java`  
- **Specificity rating:** directional

**REQ-019** — Overriding built-in tree adapters remains backward-compatible  
- **Summary:** Attempting to register handlers for `JsonElement` and its subclasses must remain backward-compatible in builder behavior, even though callers must not rely on such registrations to replace core tree semantics.  
- **User story:** As a library maintainer upgrading Gson, I want minor-version changes around built-in adapter validation to avoid breaking existing builder code at startup.  
- **Implementation note:** The compatibility requirement is about registration-time behavior and upgrade safety, not endorsement of the pattern.  
- **Conditions of satisfaction:** Minor-version upgrades do not turn formerly tolerated `JsonElement` adapter registrations into hard startup failures without a migration path; callers are still not guaranteed to replace core tree behavior successfully.  
- **Alternative paths:** Libraries should move special handling out of `JsonElement` overrides and into their own code or supported extension points.  
- **References:** `retrieved_documentation/github_issues/issue_2787_backwards_compat_broken.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`  
- **Specificity rating:** directional

**REQ-020** — Recursive custom serialization must not rely on `context.serialize(thisType)`  
- **Summary:** Gson must preserve the rule that a custom serializer for a type cannot safely call `context.serialize()` on the same type without triggering recursive re-entry.  
- **User story:** As a custom serializer author, I want the recursion boundary to be clear so that I do not create infinite recursion by delegating incorrectly.  
- **Implementation note:** Community tutorials surface this as an easy trap rather than a hidden implementation quirk.  
- **Conditions of satisfaction:** Same-type recursive delegation is not treated as a supported composition pattern; authors must delegate selectively, use different types, or hand-write output.  
- **Alternative paths:** Delegate field-by-field, serialize sub-components of different types, or use a `TypeAdapterFactory` that wraps a delegate adapter explicitly.  
- **References:** `retrieved_documentation/community/futurestud_custom_serialization.md`; `retrieved_documentation/official/javadoc_type_adapter.md`; `gson/src/main/java/com/google/gson/JsonSerializationContext.java`  
- **Specificity rating:** directional

**REQ-021** — Delegating type-adapter chains rely on caller-managed acyclicity  
- **Summary:** Gson may traverse nested `SerializationDelegatingTypeAdapter` instances to discover the terminal serialization delegate, but it does not detect or break custom delegation cycles automatically.  
- **User story:** As an adapter author layering custom delegation, I want the acyclic-chain assumption to be explicit so that I do not mistake recursive delegate graphs for a supported pattern.  
- **Implementation note:** `TypeAdapterRuntimeTypeWrapper` follows delegation chains to decide whether a delegate is reflective; that traversal assumes custom adapters do not eventually point back to themselves.  
- **Conditions of satisfaction:** A delegating adapter may return itself or another adapter as its serialization delegate; callers may traverse repeated `SerializationDelegatingTypeAdapter` layers to find a terminal delegate; if a custom adapter chain forms a cycle, Gson does not provide cycle detection and traversal recurses until ordinary recursion failure semantics apply.  
- **Alternative paths:** Adapter authors may wrap a delegate explicitly, return a non-delegating terminal adapter, or add their own cycle guards when composing custom delegation graphs.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/SerializationDelegatingTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java`  
- **Specificity rating:** specific

## Reflection Layer

### Category: reflective binding rules

This category covers Gson's default object mapping behavior when no custom adapter takes over. It depends on the adapter system above and feeds many of the null, collection, and compatibility behaviors described later in the document.

**REQ-022** — `ObjectTypeAdapter` avoids direct self-recursion by emitting `{}`  
- **Summary:** When `ObjectTypeAdapter` serializes a runtime value whose chosen runtime adapter is again an `ObjectTypeAdapter`, Gson must emit an empty JSON object instead of delegating recursively, even though that fallback silently loses the original value's structure.  
- **User story:** As a developer debugging generic `Object` serialization, I want Gson's self-recursion fallback to be explicit so that unexpected `{}` output is recognizable as a deliberate guard rather than arbitrary corruption.  
- **Implementation note:** This is a compatibility-oriented recursion guard on the raw-`Object` path, not a general-purpose self-reference solution for arbitrary object graphs.  
- **Conditions of satisfaction:** `ObjectTypeAdapter.write(...)` chooses the runtime adapter for non-null values; if that adapter is another `ObjectTypeAdapter`, Gson writes `{}` instead of recursing; if the runtime adapter is more specific, Gson delegates to it normally; the `{}` fallback does not add a warning or separate diagnostic.  
- **Alternative paths:** Callers who need faithful output for erased `Object` values may deserialize to a more specific type, register an explicit adapter, or avoid the raw-`Object` fallback path.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ObjectTypeAdapter.java`; `gson/src/test/java/com/google/gson/ObjectTypeAdapterTest.java`  
- **Specificity rating:** specific

**REQ-023** — Reflection-based binding is field-based, not getter-based  
- **Summary:** Reflective mapping must use eligible fields rather than JavaBean getters, including inherited non-static, non-transient, non-synthetic fields unless an exclusion rule removes them.  
- **User story:** As a user serializing classes I cannot modify, I want field-based mapping so that Gson's wire contract does not depend on getter naming conventions or side effects.  
- **Implementation note:** This is a foundational design decision documented in the design notes and user guide.  
- **Conditions of satisfaction:** Private fields can participate; inherited eligible fields are included; getters alone do not define JSON members; excluded field categories stay excluded.  
- **Alternative paths:** Callers who need property-based behavior may use custom adapters instead of changing the reflective contract.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-024** — Object cycles are not silently normalized by default  
- **Summary:** Gson must not pretend to provide general-purpose cycle handling for object graphs; arbitrary bidirectional or cyclic references remain unsupported unless callers break the cycle or provide a custom adapter strategy.  
- **User story:** As a developer modeling graphs or bidirectional relationships, I want the library's cycle limitations to be explicit so that I do not mistake unsupported graphs for safe, round-trippable object models.  
- **Implementation note:** This is a negative contract: correctness requires either acyclic models or explicit caller intervention.  
- **Conditions of satisfaction:** Acyclic object graphs serialize normally; general cycles are not silently rewritten into a supported reference format; callers have to opt into exclusion or custom cycle handling.  
- **Alternative paths:** Users may exclude back-references, use `@Expose` selectively, or register custom graph-aware adapters.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0530_circular_references.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** directional

**REQ-025** — Anonymous and non-static local classes are unsupported by reflective binding  
- **Summary:** Anonymous classes and non-static local classes must not be reflectively treated as ordinary domain models; by default Gson must serialize them as JSON `null` and deserialize them as Java `null`.  
- **User story:** As a developer debugging unexplained `null` output, I want anonymous and local class handling to be explicit so that unsupported runtime types are not mistaken for missing data bugs.  
- **Implementation note:** This is an intentional limitation, not an incidental bug.  
- **Conditions of satisfaction:** Unsupported anonymous or local classes do not produce ordinary reflective output; default deserialization yields `null`; the limitation is stable and diagnosable.  
- **Alternative paths:** Callers may use static nested classes, explicit declared base types, records where supported, or custom adapters.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_2059_anonymous_class_null.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-026** — Pure inner classes require caller-supplied construction support  
- **Summary:** Gson must not auto-deserialize pure inner classes that require an enclosing instance unless the caller supplies an `InstanceCreator` or equivalent custom construction path.  
- **User story:** As a caller deserializing nested Java types, I want impossible construction cases to fail or require explicit support so that Gson does not create half-valid objects bound to the wrong outer instance.  
- **Implementation note:** This is a construction-boundary requirement, not just a serialization quirk.  
- **Conditions of satisfaction:** Plain inner classes are not auto-instantiated without an enclosing instance; static nested classes work normally; registered custom creators can supply the necessary outer binding.  
- **Alternative paths:** Make the type `static`, provide an `InstanceCreator`, or deserialize into a different DTO.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/design_document.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-027** — Duplicate resolved field names are rejected  
- **Summary:** If two fields in the reflective hierarchy resolve to the same JSON member name after naming policy and annotation processing, Gson must reject the type definition instead of choosing one field implicitly.  
- **User story:** As a user relying on unambiguous object binding, I want naming collisions to fail fast so that duplicate field names do not silently corrupt data.  
- **Implementation note:** This applies to collisions caused by inheritance, `@SerializedName`, or field naming policies.  
- **Conditions of satisfaction:** Name collisions are detected before ordinary use; serialization and deserialization do not proceed with ambiguous field selection; the error identifies the collision.  
- **Alternative paths:** Rename one field, exclude one field, or adjust the naming strategy to remove the collision.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-028** — Static final fields are never mutated by deserialization  
- **Summary:** Deserialization must not write JSON values into `static final` fields; encountering such a target must fail explicitly rather than mutate process-wide constant state.  
- **User story:** As a maintainer of shared JVM state, I want constant fields protected from JSON input so that one parse cannot introduce a hidden global side effect.  
- **Implementation note:** This is both a JVM-safety rule and a data-integrity rule.  
- **Conditions of satisfaction:** `static final` targets are not assigned through reflective binding; failure is explicit; other eligible instance fields continue to work normally.  
- **Alternative paths:** Exclude the field or provide a custom adapter that maps input without mutating static constants.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-029** — Reflective field serialization order is observed behavior, not a standalone schema promise  
- **Summary:** Default reflective serialization must continue to emit fields in the current bound-field discovery order, but reviewers must treat that order as observed implementation behavior rather than a separately promised long-term schema contract.  
- **User story:** As a maintainer reading diffs or snapshot failures, I want it to be explicit whether reflective field order is a real compatibility guarantee or just a current implementation detail so that I do not flag harmless order churn as a semantic defect.  
- **Implementation note:** `ReflectiveTypeAdapterFactory` walks the runtime class from the most-derived type up through superclasses, records serialized fields in `LinkedHashMap`, and preserves the per-class `getDeclaredFields()` iteration order it sees.  
- **Conditions of satisfaction:** For one runtime and Gson version, default reflective serialization emits eligible fields from the most-derived class before inherited fields, preserving the discovery order within each class; duplicate serialized names are still rejected rather than producing ambiguous order; the requirements treat this emitted order as observed compatibility-sensitive behavior, not as an alphabetical or specification-level JSON ordering guarantee callers should depend on across all JVMs and future implementations.  
- **Alternative paths:** Callers who need a canonical member order should use ordered `JsonObject`/`Map` trees or custom adapters instead of relying on reflective field traversal.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/JsonObject.java`  
- **Specificity rating:** specific

### Category: construction and platform access

These requirements explain how Gson creates instances and how far it may go to reach constructors and fields on modern runtimes. Reviewers should treat this area as both a correctness boundary and a platform boundary, because construction order, module access, and unsafe fallbacks all affect the resulting object state.

**REQ-030** — Construction order is stable and documented  
- **Summary:** Gson must use a stable preference order for constructing instances: registered `InstanceCreator`, special collection/map constructors, accessible no-args constructor, safe default implementation, and only then JDK `Unsafe` when allowed.  
- **User story:** As a caller depending on constructor behavior and collection semantics, I want instance creation order to be stable so that deserialization does not bypass my intended construction path unexpectedly.  
- **Implementation note:** The order is a major part of Gson's design rationale and strongly affects invariants.  
- **Conditions of satisfaction:** Custom creators win when registered; ordinary no-args constructors are preferred over unsafe allocation; documented default implementations are used for abstract collection interfaces; unsafe allocation is last resort.  
- **Alternative paths:** Users may replace construction with adapters or creators when the default order does not fit their model.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-031** — `disableJdkUnsafe()` turns hidden construction gaps into explicit failures  
- **Summary:** When `disableJdkUnsafe()` is enabled and no valid non-unsafe construction path exists, Gson must fail immediately with guidance rather than silently falling back to unsafe allocation; when unsafe allocation remains enabled, backend selection must still follow Gson's stable documented preference order.  
- **User story:** As a maintainer debugging missing defaults and broken invariants, I want unsafe allocation to be opt-out and loudly disabled so that construction problems show up early.  
- **Implementation note:** This is a deliberate diagnostics and safety feature, not just a performance toggle.  
- **Conditions of satisfaction:** Disabling unsafe allocation prevents fallback use of `Unsafe`; unsupported construction cases fail fast; the error points callers toward constructors or custom creators; when unsafe allocation is enabled, Gson tries `sun.misc.Unsafe.allocateInstance`, then `ObjectStreamClass.newInstance(Class, int)`, then `ObjectInputStream.newInstance(Class, Class)`, and only then reports that no unsafe backend is available.  
- **Alternative paths:** Leave unsafe allocation enabled, add a no-args constructor, make the class static/top-level, or register an `InstanceCreator`.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-032** — Non-instantiable abstract targets are rejected explicitly  
- **Summary:** Interfaces and abstract classes must not be instantiated through default or unsafe construction paths unless a custom creator or adapter supplies a concrete type.  
- **User story:** As a developer deserializing abstract APIs, I want unsupported instantiation to fail clearly so that Gson does not fabricate impossible objects or produce misleading errors.  
- **Implementation note:** Later releases strengthened the error messaging here, but the behavioral contract is older and broader.  
- **Conditions of satisfaction:** Abstract or interface targets fail without a concrete construction strategy; failures explain the need for a concrete subtype, creator, or adapter; no unsafe fake instance is produced.  
- **Alternative paths:** Register an `InstanceCreator`, provide a custom `TypeAdapter`, or deserialize to a concrete subtype.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-033** — Unsafe allocation skips constructors and field initializers  
- **Summary:** When Gson falls back to JDK `Unsafe` or similar allocation, constructors and field initializers must be treated as not having run, and callers must not assume their defaults were preserved.  
- **User story:** As a user seeing unexpectedly `null` or zero-valued fields, I want the unsafe-construction semantics to be explicit so that missing initialization is diagnosable.  
- **Implementation note:** This is a consequence contract of the unsafe path, not a desired feature.  
- **Conditions of satisfaction:** Classes created through unsafe allocation begin with JVM default field values; constructor or initializer side effects are not assumed; troubleshooting guidance remains accurate.  
- **Alternative paths:** Provide a no-args constructor, register an `InstanceCreator`, make the type static/top-level, or disable unsafe allocation to force detection.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-034** — JPMS callers must open reflected packages to Gson  
- **Summary:** In JPMS environments, any application package whose fields Gson must access reflectively must be opened to `com.google.gson`; otherwise reflective binding must fail rather than bypassing module boundaries.  
- **User story:** As a JPMS user, I want module access rules to be enforced consistently so that reflective JSON binding does not undermine module encapsulation.  
- **Implementation note:** This is both a platform contract and a security boundary.  
- **Conditions of satisfaction:** Closed packages are not reflectively accessed behind JPMS rules; opening the package enables reflective binding; failure messages point to the missing `opens` declaration.  
- **Alternative paths:** Use explicit adapters, tree APIs, or stream APIs to avoid reflection entirely.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/module-info.java`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-035** — Reflection-free usage remains supported as a deployment strategy  
- **Summary:** Environments that cannot safely retain reflection metadata must be able to use Gson through explicit adapters, factories, tree APIs, or streaming APIs without depending on reflective fallback.  
- **User story:** As a platform owner restricting reflection, I want a supported reflection-free usage path so that Gson can still be adopted under tighter security or AOT constraints.  
- **Implementation note:** Troubleshooting guidance explicitly recommends this as an alternative architecture.  
- **Conditions of satisfaction:** Reflection can be blocked completely while tree, stream, or adapter-driven workflows still function; Gson does not require reflective fallback when every needed type has explicit handling.  
- **Alternative paths:** Keep reflection enabled and preserve metadata, but the reflection-free architecture must remain viable.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/TypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-036** — Class-loading structure must avoid circular static initialization hazards  
- **Summary:** Gson's built-in adapter infrastructure must not rely on circular static initialization paths that can deadlock class loading under multi-threaded startup.  
- **User story:** As a production operator, I want application startup to be free of class-loading hangs so that low-level adapter initialization cannot wedge the process before work begins.  
- **Implementation note:** This is narrower than general thread safety and specifically targets static initialization architecture.  
- **Conditions of satisfaction:** Static initialization order for built-in adapters is acyclic or otherwise safe under concurrent class loading; no thread can block forever on reciprocal class-initialization locks.  
- **Alternative paths:** Lazy initialization, holder classes, or split initialization contexts may be used so long as the deadlock risk is removed.  
- **References:** `retrieved_documentation/github_issues/issue_2739_class_loading_deadlock.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

**REQ-037** — Record binding honors canonical construction and accessor-based serialization  
- **Summary:** On JVMs with record support, Gson must deserialize records through their canonical constructor and serialize them through their record accessors rather than treating them as mutable field bags.  
- **User story:** As a Java developer using records for invariants and derived state, I want record construction and accessor overrides to remain observable during Gson round-trips so that validation and normalization encoded in the record contract are not bypassed.  
- **Implementation note:** `ReflectiveTypeAdapterFactory` switches record types onto a dedicated `RecordAdapter`, using `ReflectionHelper` to discover record components, canonical constructors, and accessor methods.  
- **Conditions of satisfaction:** Deserializing a record runs canonical-constructor logic; constructor failures surface instead of being bypassed by unsafe allocation; serialization observes accessor overrides; accessor exceptions surface as JSON I/O failures with the accessor identified.  
- **Alternative paths:** Callers may still supply custom adapters or block reflection, but default reflective record support must preserve the semantics that make records different from ordinary classes, including for local records.  
- **References:** Java record contract; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/reflect/ReflectionHelper.java`; `gson/src/test/java/com/google/gson/functional/Java17RecordTest.java`; `gson/src/test/java/com/google/gson/internal/bind/Java17ReflectiveTypeAdapterFactoryTest.java`  
- **Specificity rating:** specific

**REQ-038** — Record component defaults and null handling follow constructor-argument semantics  
- **Summary:** Missing record components must behave like omitted constructor arguments synthesized by Gson (`null` for references, JVM defaults for primitives), while explicit JSON `null` for primitive components must fail with component-specific diagnostics.  
- **User story:** As a caller deserializing immutable record types, I want Gson's handling of absent versus explicit `null` values to match record-constructor semantics so that immutable models fail or default predictably instead of being mutated piecemeal.  
- **Implementation note:** The record adapter accumulates constructor arguments in an array pre-seeded with primitive defaults and rejects `null` results for primitive components before invoking the canonical constructor.  
- **Conditions of satisfaction:** A missing reference component deserializes as `null`; a missing primitive component deserializes as `0`, `false`, or `'\0'` as appropriate; an explicit JSON `null` for a primitive component fails with the component name and JSON path; a custom adapter that returns `null` for a primitive component fails the same way.  
- **Alternative paths:** Callers who need required-field enforcement beyond these defaults must implement it in the canonical constructor or a custom adapter, not expect reflective field mutation after construction.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/test/java/com/google/gson/functional/Java17RecordTest.java`  
- **Specificity rating:** specific

## Streaming Layer

### Category: token navigation and structure

This category is the streaming foundation beneath custom adapters and several internal bridges. If these token and state-machine rules drift, seemingly unrelated higher-level APIs start failing in subtle and hard-to-diagnose ways.

**REQ-039** — `JsonReader` exposes a depth-first token stream  
- **Summary:** `JsonReader` must present JSON as a depth-first token stream with explicit begin/end boundaries for arrays and objects.  
- **User story:** As an adapter author, I want stable token-order and boundary semantics so that custom streaming adapters can consume nested JSON deterministically.  
- **Implementation note:** This is the foundation for all low-allocation custom adapter logic.  
- **Conditions of satisfaction:** Valid JSON is traversed in depth-first order; arrays and objects require matching begin/end calls; token consumption remains deterministic across nested values.  
- **Alternative paths:** Callers may use tree APIs instead, but the streaming API must remain correct for high-control adapters.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-040** — `skipValue()` consumes the entire nested value  
- **Summary:** When callers skip an unknown or unsupported value, `skipValue()` must consume the entire subtree and leave the reader positioned correctly for the next token.  
- **User story:** As a consumer tolerant of extra JSON members, I want to skip unsupported values safely so that unknown fields do not corrupt parsing of later fields.  
- **Implementation note:** This underpins Gson's design choice to ignore extra JSON fields while navigating the target type tree.  
- **Conditions of satisfaction:** Skipping a primitive, array, or object leaves the reader at the next logical position; later fields remain readable; skipping does not corrupt nesting state.  
- **Alternative paths:** Custom adapters may inspect or reject unknown members explicitly, but generic skipping must remain safe when used.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-041** — Strictness modes enforce distinct acceptance rules  
- **Summary:** `LENIENT`, legacy/default strictness, and `STRICT` must enforce distinct and documented acceptance rules for comments, single quotes, trailing commas, invalid escapes, control characters, and case sensitivity of literals.  
- **User story:** As a caller choosing between compatibility and standards compliance, I want each strictness level to have predictable acceptance boundaries so that parser behavior matches my interoperability or validation needs.  
- **Implementation note:** This requirement comes directly from the Strictness API and the troubleshooting distinction between legacy permissiveness and true strict RFC compliance.  
- **Conditions of satisfaction:** `STRICT` rejects non-standard forms called out by the documentation; lenient modes accept the documented extensions; changing strictness changes acceptance behavior in those specific areas.  
- **Alternative paths:** Older boolean leniency settings may remain as compatibility aliases, but their meaning must map clearly onto the newer strictness model.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `gson/src/main/java/com/google/gson/Strictness.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

**REQ-042** — Deep nesting is bounded  
- **Summary:** Reader-side nesting depth must be bounded by the configured or documented limit, and excessively deep documents must fail instead of exhausting the stack or heap.  
- **User story:** As a service processing untrusted JSON, I want overly deep input to fail predictably so that one malicious document cannot crash the process.  
- **Implementation note:** This requirement follows the later nesting-limit hardening work and general parser safety expectations.  
- **Conditions of satisfaction:** The default `JsonReader` nesting limit is 255 simultaneously open arrays/objects; `setNestingLimit(...)` and `getNestingLimit()` round-trip caller-supplied non-negative limits; negative limits are rejected explicitly; parsing beyond the active limit fails with `MalformedJsonException` and location context rather than a process crash.  
- **Alternative paths:** Callers may raise or lower the nesting limit where supported, but unbounded recursion is not an acceptable default.  
- **References:** `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-043** — Reader and writer state transitions remain internally consistent  
- **Summary:** Reader and writer state machines must preserve internal consistency across `begin*`, `end*`, `next*`, `name`, `value`, and `skipValue()` operations so that valid prior operations do not make later valid operations fail.  
- **User story:** As a custom adapter author, I want stream state transitions to be stable so that correct token-handling logic does not fail because of hidden state corruption.  
- **Implementation note:** This is a cross-cutting correctness rule for both streaming APIs.  
- **Conditions of satisfaction:** Matching begin/end calls remain balanced; field names and values alternate correctly in objects; skipping or peeking does not corrupt later reads; writes preserve valid JSON structure.  
- **Alternative paths:** Tree-based APIs avoid direct state-machine management, but the streaming APIs must remain sound for low-level use.  
- **References:** `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** directional

**REQ-044** — Reader and writer lifecycle owns the wrapped stream once constructed  
- **Summary:** Once a `JsonReader` or `JsonWriter` is constructed around a `Reader` or `Writer`, Gson must propagate `close()`/`flush()` to the wrapped stream according to the documented lifecycle contract and fail explicitly on use-after-close or incomplete close.  
- **User story:** As a caller composing Gson with my own I/O stack, I want stream ownership and close behavior to be predictable so that resource leaks, double-use after close, and silently truncated output are not hidden behind the JSON layer.  
- **Implementation note:** This requirement covers public streaming types and the `AppendableWriter` bridge used when Gson adapts non-`Writer` appendables.  
- **Conditions of satisfaction:** `JsonReader.close()` closes the underlying `Reader` and subsequent operations fail as a closed reader; `JsonWriter.flush()` flushes the underlying `Writer` unless already closed; `JsonWriter.close()` closes the underlying `Writer`, then throws `IOException("Incomplete document")` if the JSON document was not structurally complete, and subsequent writes fail as closed-writer use; `Streams.writerForAppendable(...)` only forwards `flush()` or `close()` when the wrapped appendable implements `Flushable` or `Closeable`.  
- **Alternative paths:** Callers who need different ownership boundaries may wrap the underlying I/O object themselves, but Gson's reader/writer lifecycle must stay explicit and stable once those public types are in use.  
- **References:** `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`; `gson/src/main/java/com/google/gson/internal/Streams.java`  
- **Specificity rating:** specific

### Category: syntax and wire-format boundaries

These requirements define exactly what JSON syntax Gson accepts and how tree-backed reader and writer bridges must mimic stream-backed behavior. Keep them separate from higher-level binding rules: this is the wire-grammar layer where escaping, separators, and traversal fidelity matter most.

**REQ-045** — Byte order mark handling is limited to the start of the document  
- **Summary:** Gson must tolerate a Unicode BOM only as the very first character of a JSON document and must reject the same code point everywhere else in the payload.  
- **User story:** As an integrator receiving JSON from mixed producers, I want a leading BOM to be tolerated without turning BOMs elsewhere into silent whitespace so that interoperability hacks do not weaken parsing correctness.  
- **Implementation note:** `JsonReader` strips `\ufeff` only on the first buffer fill before any other content has been consumed; later occurrences stay ordinary input and must fail if they appear where JSON has no valid token.  
- **Conditions of satisfaction:** A document beginning with `\ufeff` parses the same as the BOM-free equivalent; a BOM inside an array, object, string delimiter boundary, or later token position fails with location context instead of being skipped.  
- **Alternative paths:** Callers can remove BOMs before parsing, but Gson's built-in tolerance must stay narrowly scoped to the document start rather than acting as a general whitespace extension.  
- **References:** RFC 8259 section 8.1; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** specific

**REQ-046** — Token-separating whitespace remains RFC-exact  
- **Summary:** Outside strings, Gson must treat only RFC JSON whitespace as ignorable token separation; characters such as U+2028 and U+2029 are valid string contents but must not be accepted as structural whitespace.  
- **User story:** As a caller relying on standards-compatible parsing, I want Gson to distinguish legal string content from legal inter-token whitespace so that payloads accepted by Gson do not drift away from other RFC-oriented parsers.  
- **Implementation note:** `JsonReader`'s non-whitespace scan and escape handling together define this boundary: line separators may appear unescaped in strings, but not as separators between tokens.  
- **Conditions of satisfaction:** JSON separated by space, tab, CR, or LF parses normally; payloads that rely on U+2028 or U+2029 as array/object whitespace fail; those same characters remain readable inside string values.  
- **Alternative paths:** Producers that need maximum interoperability may escape these characters in strings, but Gson must not silently broaden the structural whitespace grammar.  
- **References:** RFC 8259 sections 2 and 7; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** specific

**REQ-047** — Unicode escape handling stays lossless for valid input and explicit for malformed input  
- **Summary:** Gson must decode complete Unicode escapes and valid surrogate pairs without loss, while malformed Unicode escapes or other invalid escape forms must fail explicitly instead of being silently rewritten or normalized.  
- **User story:** As a developer exchanging non-ASCII JSON across systems, I want valid supplementary characters to round-trip correctly and broken escape sequences to fail deterministically so that internationalized payloads do not degrade into mojibake or parser-specific surprises.  
- **Implementation note:** `JsonReader` already decodes `\uXXXX` escapes and raises syntax errors for malformed escape sequences, while `JsonWriter` preserves ordinary Unicode text and force-escapes U+2028/U+2029 for interoperability; the missing contract is that these Unicode paths are part of Gson's intended behavior, not incidental implementation detail.  
- **Conditions of satisfaction:** Escaped BMP characters decode to the expected Java `String`; escaped supplementary code points such as `\uD83D\uDE0A` decode to the correct single Unicode scalar value; malformed `\u` escapes fail with syntax context; writer-side string escaping does not emit raw U+2028/U+2029 even when the source string contains them.  
- **Alternative paths:** Producers may pre-normalize or pre-escape text, but Gson must not require callers to avoid supplementary characters or guess whether malformed escapes will be accepted.  
- **References:** RFC 8259 sections 7 and 8.2; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`; `gson/src/test/java/com/google/gson/functional/InternationalizationTest.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderTest.java`  
- **Specificity rating:** directional

**REQ-048** — `JsonTreeReader` must expose tree values through the standard token and path model  
- **Summary:** Reading from a `JsonElement` tree through `JsonTreeReader` must preserve the same depth-first token ordering, cross-accessor coercions, skip semantics, and JSONPath tracking that callers expect from the streaming reader contract.  
- **User story:** As an adapter author delegating between tree and streaming code paths, I want tree-backed reads to behave like stream-backed reads so that switching representations does not change token order, coercion behavior, or path reporting.  
- **Implementation note:** `JsonTreeReader` replaces the character-stream lexer with explicit traversal of `JsonObject`, `JsonArray`, `JsonPrimitive`, and `JsonNull`, but it still implements the `JsonReader` surface including `peek`, `next*`, `skipValue`, `getPath`, and `getPreviousPath`.  
- **Conditions of satisfaction:** Tree-backed arrays and objects emit the same begin/name/value/end token sequence as the equivalent parsed stream; numeric/string cross-accessors behave consistently with `JsonPrimitive`; `skipValue()` consumes exactly the skipped subtree and leaves path state correct; `getPath()` and `getPreviousPath()` identify the current tree position closely enough to support diagnostics.  
- **Alternative paths:** Callers may consume `JsonElement` directly, but the reader bridge must remain faithful so mixed tree/stream adapter code keeps one behavioral model.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java`; `gson/src/main/java/com/google/gson/internal/bind/JsonElementTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/Streams.java`; `gson/src/test/java/com/google/gson/internal/bind/JsonTreeReaderTest.java`; `gson/src/test/java/com/google/gson/internal/bind/JsonElementReaderTest.java`; `gson/src/test/java/com/google/gson/stream/JsonReaderPathTest.java`  
- **Specificity rating:** specific

**REQ-049** — `JsonTreeReader` must reject unsupported custom `JsonElement` subclasses  
- **Summary:** `JsonTreeReader` must fail explicitly when asked to traverse a custom `JsonElement` subclass that is not one of Gson's built-in tree node types instead of silently treating it as a supported tree value.  
- **User story:** As a maintainer debugging tree-model misuse, I want unsupported custom subclasses to fail immediately and name the offending class so that adapter bugs are surfaced at the boundary instead of producing undefined traversal behavior.  
- **Implementation note:** The tree reader only knows how to traverse `JsonObject`, `JsonArray`, `JsonPrimitive`, and `JsonNull`; other subclasses are rejected as malformed input to the bridge layer.  
- **Conditions of satisfaction:** Encountering a custom `JsonElement` subclass raises an explicit failure that identifies the subclass; supported built-in node types continue to work normally; the error occurs at traversal time rather than silently emitting a misleading token stream.  
- **Alternative paths:** Libraries that need custom tree semantics should convert to standard Gson tree nodes or provide their own bridge layer instead of depending on `JsonTreeReader` to understand arbitrary subclasses.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java`; `gson/src/test/java/com/google/gson/internal/bind/JsonTreeReaderTest.java`  
- **Specificity rating:** specific

**REQ-050** — `JsonTreeReader` nesting limits are advisory only for prebuilt trees  
- **Summary:** Configured nesting limits on `JsonTreeReader` must be observable through the accessor API but must not block traversal of a prebuilt `JsonElement` tree, because the bridge operates on an already-materialized tree rather than defending a parser from hostile input depth.  
- **User story:** As a caller handed an existing `JsonElement`, I want tree traversal to keep working even when a nesting limit is configured so that internal tree-to-stream bridges do not fail on depth that was already accepted upstream.  
- **Implementation note:** `JsonTreeReader` overrides the reading logic but intentionally does not enforce `JsonReader`'s depth guard; the limit remains part of the inherited API surface for compatibility, not as an active traversal constraint.  
- **Conditions of satisfaction:** `setNestingLimit(...)` and `getNestingLimit()` round-trip their configured value; deeply nested prebuilt trees can still be traversed through `JsonTreeReader`; this bypass does not change the separate nesting-limit behavior of ordinary character-stream parsing.  
- **Alternative paths:** Applications that need depth limits as an input defense must enforce them when constructing the tree or while parsing from the original stream, not by relying on the tree bridge afterward.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java`; `gson/src/test/java/com/google/gson/internal/bind/JsonTreeReaderTest.java`  
- **Specificity rating:** specific

**REQ-051** — `JsonTreeWriter` builds tree output only through the structured writer API  
- **Summary:** `JsonTreeWriter` must construct a `JsonElement` tree that reflects the same structured begin/name/value/end operations as a normal `JsonWriter`, while preserving writer-side null and strictness behavior and rejecting unsupported raw-value injection.  
- **User story:** As an adapter author using a tree writer as a drop-in `JsonWriter`, I want the same structured write calls to produce a faithful tree result so that tree-based delegation does not relax null handling, strictness, or document-completion rules.  
- **Implementation note:** `JsonTreeWriter` accumulates `JsonObject`, `JsonArray`, `JsonPrimitive`, and `JsonNull` nodes in memory, applies `serializeNulls` only to object members, rejects non-finite numbers in non-lenient modes, and leaves `jsonValue(...)` unsupported because there is no raw JSON text sink behind it.  
- **Conditions of satisfaction:** Matching begin/end/name/value calls produce the expected `JsonElement` tree shape; `serializeNulls(false)` omits object members whose value is `null`; strict modes reject `NaN` and infinities while lenient mode can retain them as tree primitives; closing an incomplete document fails; writes after close fail; `jsonValue(...)` remains unsupported.  
- **Alternative paths:** Callers who need raw JSON splicing can write to a real `JsonWriter`, but the tree writer path must remain a structured-tree builder rather than a text-injection API.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java`; `gson/src/test/java/com/google/gson/internal/bind/JsonTreeWriterTest.java`  
- **Specificity rating:** specific

**REQ-052** — Untrusted-input size limits beyond nesting and numeric text remain caller-managed  
- **Summary:** Gson must make it explicit that its built-in denial-of-service guards cover nesting depth and arbitrary-precision numeric text size, but not an application-level maximum JSON string length or total document size.  
- **User story:** As a service owner handling untrusted payloads, I want the remaining input-size limitation to be documented so that I do not mistake Gson's parser hardening for a complete payload-size defense.  
- **Implementation note:** `JsonReader` exposes a nesting limit and `NumberLimits` bounds huge `BigDecimal`/`BigInteger` text, but there is no corresponding public knob for overall string length or document byte/character count.  
- **Conditions of satisfaction:** The public API continues to expose nesting-limit control and numeric text limits as in REQ-042 and REQ-080; Gson does not expose a built-in maximum string-length or total-document-size setting; long ordinary strings are limited only by the underlying input source and available memory rather than a Gson-specific cap; callers who need hard payload-size limits must enforce them before or while feeding data to Gson.  
- **Alternative paths:** Applications may wrap readers, bound input streams, or pre-validate payload sizes outside Gson, but the library must not imply that those limits are already built in.  
- **References:** `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/internal/NumberLimits.java`; `gson/src/main/java/com/google/gson/JsonParser.java`; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** specific

## Type System

### Category: type-token safety

This category covers the public type-plumbing APIs that make generic deserialization safe. Reviewers should watch for any change that quietly broadens erased or ambiguous types, because those regressions often show up much later as wrong object shapes.

**REQ-053** — Raw `TypeToken` usage is rejected  
- **Summary:** Constructing a `TypeToken` without a real type argument must fail rather than behaving as though raw generic type information were safe.  
- **User story:** As a caller using `TypeToken`, I want raw or malformed tokens to fail immediately so that generic type metadata errors do not become late runtime surprises.  
- **Implementation note:** Shrinker and generic-signature preservation guidance exists largely to protect this contract.  
- **Conditions of satisfaction:** Raw `TypeToken` creation fails with a clear message; correct parameterized usage succeeds; shrinker-induced signature stripping remains diagnosable.  
- **Alternative paths:** Use `TypeToken.getParameterized(...)` or preserve generic signatures through shrinker rules.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-054** — Captured type variables are rejected or explicitly opted back in  
- **Summary:** `TypeToken` construction must reject captured type variables by default, or else only allow them through the explicit backward-compatibility escape hatch documented by Gson.  
- **User story:** As a developer using generics, I want unsafe captured type variables blocked by default so that deserialization does not silently degrade to `Object`-typed graphs.  
- **Implementation note:** This is a type-safety hardening rule and a compatibility rule at once.  
- **Conditions of satisfaction:** Captured type variables fail by default; the error explains the problem and points to safer alternatives; the compatibility system property remains an explicit opt-in rather than the default behavior.  
- **Alternative paths:** Use `TypeToken.getParameterized(...)`, pass around full `TypeToken` instances, or, if absolutely necessary, opt into the compatibility property with awareness of the risks.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-055** — `TypeToken.getParameterized(...)` validates arity and bounds  
- **Summary:** Programmatic `TypeToken` construction must validate parameter count, bounds, and primitive-type misuse before producing a token.  
- **User story:** As a caller building generic types dynamically, I want invalid parameterized type requests to fail early so that impossible type combinations are not turned into misleading tokens.  
- **Implementation note:** This is a factory-side validation rule for safer runtime type construction.  
- **Conditions of satisfaction:** Invalid arity, out-of-bounds substitutions, and primitive misuse are rejected explicitly; valid parameterized requests produce a usable token.  
- **Alternative paths:** Callers may use anonymous subclass syntax when compile-time generic information is available.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/reflect/TypeToken.java`  
- **Specificity rating:** specific

**REQ-056** — Bounded type variables must not degrade to raw `Object` semantics  
- **Summary:** When a generic type variable has an upper bound, deserialization logic must not ignore that bound and behave as though the field were an unconstrained `Object`.  
- **User story:** As a developer using bounded generics, I want type bounds to guide deserialization so that constrained generic fields do not silently become `LinkedTreeMap` or other generic placeholders.  
- **Implementation note:** This is an open behavior gap surfaced by issue-driven requirement elicitation and is especially valuable for review.  
- **Conditions of satisfaction:** Bounded generic fields are not treated as raw `Object` when bound information is available; deserialization either respects the bound or fails explicitly instead of silently materializing a generic map.  
- **Alternative paths:** Use concrete types, register explicit adapters, or deserialize in two steps if the generic bound cannot be resolved automatically.  
- **References:** `retrieved_documentation/github_issues/issue_2563_generic_type_boundary.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/$Gson$Types.java`; prior `quality/REQUIREMENTS.md` gap analysis  
- **Specificity rating:** directional

### Category: generic container metadata

This category covers the fallback runtime types Gson exposes when callers deserialize without enough static type information. It follows the stricter `TypeToken` contracts above, and reviewers should watch for changes that make erased or generic-object paths look more type-safe, stable, or Java-serializable than they really are.

**REQ-057** — Raw collection deserialization does not pretend to restore domain element types  
- **Summary:** Gson may serialize collections of arbitrary objects, but deserializing raw or insufficiently typed collections must produce generic JSON representations or require caller-supplied typing rather than fabricating domain element types.  
- **User story:** As a developer round-tripping heterogeneous collections, I want Gson's asymmetry here to be explicit so that raw-collection reads are not mistaken for type-safe reconstruction.  
- **Implementation note:** This is a design-document-level contract about serialization being richer than deserialization in some generic cases.  
- **Conditions of satisfaction:** Raw collection deserialization yields generic structures or requires parser/custom-adapter intervention; Gson does not falsely reconstruct heterogeneous domain objects from erased type information.  
- **Alternative paths:** Use the parser API element-by-element, a typed collection, or a custom collection adapter.  
- **References:** `retrieved_documentation/official/design_document.md`; `retrieved_documentation/official/user_guide.md`  
- **Specificity rating:** specific

**REQ-058** — Gson-exposed generic container values remain Java-serializable  
- **Summary:** Runtime container and numeric helper values that Gson returns for generic/object-style deserialization must remain safely Java-serializable, preserving logical contents without requiring callers to know Gson's internal classes.  
- **User story:** As an application integrating Gson with Java serialization or session replication, I want deserialized `Map`, `List`, and lazily parsed numeric values to survive `ObjectOutputStream` round-trips so that generic JSON results do not leak non-serializable implementation details.  
- **Implementation note:** This contract is carried by returned collection implementations such as `LinkedTreeMap` and helper number types such as `LazilyParsedNumber`, which use serialization hooks to round-trip as stable logical values.  
- **Conditions of satisfaction:** Generic `Map` and `List` results from `fromJson` are serializable and preserve equality and map iteration order after Java serialization; lazily parsed numbers serialize into stable numeric values rather than failing due to Gson-internal runtime types.  
- **Alternative paths:** Callers deserializing directly into their own domain classes control those classes' Java-serialization behavior themselves, but Gson's own fallback/runtime helper types must not be the thing that breaks serialization.  
- **References:** `gson/src/test/java/com/google/gson/JavaSerializationTest.java`; `gson/src/main/java/com/google/gson/internal/LinkedTreeMap.java`; `gson/src/test/java/com/google/gson/internal/LinkedTreeMapTest.java`; `gson/src/main/java/com/google/gson/internal/LazilyParsedNumber.java`; `gson/src/test/java/com/google/gson/internal/LazilyParsedNumberTest.java`  
- **Specificity rating:** specific

## Null Handling

### Category: missing values and explicit nulls

Null handling is one of Gson's most pervasive behaviors, touching writers, reflection, adapters, and the tree model. The requirements here explain where Gson preserves absence, where it emits or stores explicit `null`, and where callers need explicit modeling to keep those states distinct.

**REQ-059** — Writer-side null handling is applied consistently  
- **Summary:** The active `serializeNulls` setting on the writer must govern all nested serialization paths so that `null` member emission remains consistent inside reflective adapters, tree adapters, and delegated custom adapters.  
- **User story:** As a caller choosing whether omitted and explicit-`null` fields are distinct, I want nested serialization to follow the same null-emission rule everywhere so that one object graph cannot produce contradictory wire formats.  
- **Implementation note:** This is the core null-policy propagation rule that later requirements refine for selective or polymorphic cases.  
- **Conditions of satisfaction:** Under the same `Gson` configuration, equivalent `null` members are either omitted or emitted consistently across nested paths; delegation does not silently lose the configured writer policy.  
- **Alternative paths:** Per-type overrides may temporarily toggle the active writer state, but they must do so explicitly and restore it cleanly.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

**REQ-060** — Missing JSON members preserve post-construction state  
- **Summary:** When a JSON member is absent, Gson must leave the field in whatever state the constructed target instance already had, and it must not invoke the field adapter for a missing member.  
- **User story:** As a developer using defaults, I want absent JSON fields to preserve the object's post-construction state so that omitted data does not silently trigger unexpected replacement logic.  
- **Implementation note:** This rule is tightly coupled to construction strategy; constructor-backed instances preserve initializers, while unsafe construction may not run them at all.  
- **Conditions of satisfaction:** Missing members do not cause synthetic adapter invocations; constructor or field-initializer defaults survive when the construction path ran them; object-reference fields remain JVM defaults when unsafe allocation bypassed initialization.  
- **Alternative paths:** Callers who need required-or-default semantics may use constructors, records, custom deserializers, or explicit post-processing.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

**REQ-061** — Reflective primitive fields and wrapper fields diverge on explicit JSON `null`  
- **Summary:** During ordinary reflective field binding, an explicit JSON `null` or adapter-produced Java `null` must leave primitive Java fields unchanged while assigning `null` to wrapper/reference fields.  
- **User story:** As a developer relying on `int` versus `Integer` semantics, I want Gson to preserve the difference between "primitive keeps its existing/default value" and "wrapper becomes null" so that explicit JSON nulls do not blur the contract of my model types.  
- **Implementation note:** This is separate from record-constructor semantics: field reflection skips `null` assignment for primitives because `Field.set(...)` cannot store Java `null` into a primitive slot.  
- **Conditions of satisfaction:** When reflective binding targets a primitive field, an explicit JSON `null` does not overwrite the field and the field keeps its constructed/default value; when the target field is a wrapper or other reference type, the same input stores Java `null`; missing fields still follow REQ-060 rather than triggering synthetic adapter calls; custom field adapters that return `null` for primitive fields are treated the same as explicit JSON `null`.  
- **Alternative paths:** Callers who need explicit-null rejection for primitive-like fields may use records, custom adapters, or validation after deserialization rather than relying on reflective field mutation to reject the input.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

**REQ-062** — Null handling is explicit at the adapter boundary  
- **Summary:** Gson's default adapter pipeline must bypass custom adapter logic for `null` values unless the adapter path explicitly opts out of null safety or handles `null` through a wrapper strategy.  
- **User story:** As an adapter author, I want null interception rules to be explicit so that I know when my adapter will and will not see `null` values.  
- **Implementation note:** This is one of Gson's most consequential adapter semantics and is intentionally different from some other JSON libraries.  
- **Conditions of satisfaction:** Default adapter paths do not invoke custom adapter logic for `null`; `nullSafe()` provides wrapper-based null handling; callers do not get silent custom null transformations unless they explicitly built for them.  
- **Alternative paths:** Use a `TypeAdapter` with `nullSafe(false)`-style control where available, or move null semantics to wrapper types or outer logic.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/github_issues/issue_0948_type_adapter_null_bypass.md`; `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-063** — Selective null semantics require direct writer control  
- **Summary:** Per-type or per-field null-emission semantics must be implemented through an adapter path that directly controls the active `JsonWriter`; returning a `JsonElement` alone is not enough to force explicit `null` members when the outer `Gson` omits them.  
- **User story:** As an API author distinguishing omitted fields from explicit `null`, I want the requirement to point to the right extension path so that I do not mistakenly rely on a serializer shape that cannot preserve the distinction.  
- **Implementation note:** This captures the core lesson from the selective-serialize-null issues and tutorials.  
- **Conditions of satisfaction:** Per-type null emission works only when the active writer setting is changed on the real output path; tree-returning serializers do not override the outer omit-null policy by themselves.  
- **Alternative paths:** Use a `TypeAdapterFactory` that toggles `JsonWriter.setSerializeNulls(...)` and chains with `getDelegateAdapter(...)`, wrapper types that track presence, or a custom type-level `TypeAdapter`.  
- **References:** `retrieved_documentation/github_issues/issue_0913_selective_serialize_nulls.md`; `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `retrieved_documentation/official/javadoc_type_adapter.md`  
- **Specificity rating:** specific

**REQ-064** — Required-nullable and optional fields remain distinguishable only with explicit modeling  
- **Summary:** Gson must not claim that plain nullable Java references preserve the distinction between "present with `null`" and "omitted"; callers who need that distinction must model it explicitly.  
- **User story:** As an API client bound to schemas that distinguish required-nullable from optional fields, I want the limitation to be explicit so that I do not assume plain `null` is enough to preserve presence information.  
- **Implementation note:** This is a limitation contract that shapes safe extension patterns.  
- **Conditions of satisfaction:** Plain reflective binding does not magically recover field presence once data is in a plain nullable reference; preserving that distinction requires wrapper types, presence tracking, or custom adapters.  
- **Alternative paths:** Use wrapper types, field-presence sets, `TypeAdapterFactory` presence tracking, or explicit tree handling.  
- **References:** `retrieved_documentation/github_issues/issue_1558_optional_vs_null.md`; `retrieved_documentation/github_issues/issue_1005_default_values_missing.md`; `retrieved_documentation/official/user_guide.md`  
- **Specificity rating:** directional

**REQ-065** — Tree-model elements preserve JSON semantics and null invariants  
- **Summary:** Gson's tree model must distinguish JSON null from Java null, expose stable kind and cast operations, and ensure container mutations either normalize Java `null` to `JsonNull` or reject it explicitly so the tree always remains serializable.  
- **User story:** As a caller editing `JsonElement` trees directly, I want kind checks, casts, stringification, and null handling to stay consistent so that mixed tree and binding code does not produce half-valid JSON structures.  
- **Implementation note:** This requirement spans `JsonElement`, `JsonNull`, and the null-handling boundaries of `JsonArray` and `JsonObject`.  
- **Conditions of satisfaction:** `JsonNull.INSTANCE` remains the canonical JSON-null node; tree kind predicates and casts reflect the runtime node type and fail clearly on mismatches; `JsonElement.toString()` produces JSON text for supported tree nodes; tree containers never retain raw Java `null` as a JSON element and instead normalize it to `JsonNull` or reject it explicitly.  
- **Alternative paths:** Callers may pass `JsonNull.INSTANCE` explicitly when they need a present JSON null, but they must not need to reason about hidden raw-null state inside the tree.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/JsonElement.java`; `gson/src/main/java/com/google/gson/JsonNull.java`; `gson/src/main/java/com/google/gson/JsonArray.java`; `gson/src/main/java/com/google/gson/JsonObject.java`  
- **Specificity rating:** directional

## Collections and Maps

### Category: tree collections

These requirements cover Gson's mutable JSON tree types rather than ordinary Java collections. They matter because tree nodes are both a user-facing API and an internal interchange format for many adapters and bridges.

**REQ-066** — `JsonObject` preserves insertion order and normalizes Java `null`  
- **Summary:** `JsonObject` must preserve member insertion order and normalize added Java `null` values to `JsonNull.INSTANCE` rather than storing raw Java `null`.  
- **User story:** As a user manipulating the JSON tree model directly, I want object-member ordering and null representation to be stable so that tree operations remain predictable and serializable.  
- **Implementation note:** This is a tree-model invariant used by both direct callers and higher-level adapters.  
- **Conditions of satisfaction:** Iteration observes insertion order; adding Java `null` results in `JsonNull`; the tree remains serializable without special-case raw null handling.  
- **Alternative paths:** Callers may build objects through adapters or streaming APIs, but the tree model must remain internally consistent.  
- **References:** `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/JsonObject.java`; `gson/src/main/java/com/google/gson/internal/LinkedTreeMap.java`  
- **Specificity rating:** specific

**REQ-067** — Re-adding a `JsonObject` member replaces the previous value  
- **Summary:** Adding a member to a `JsonObject` with a name that already exists must replace the previous value for that name instead of retaining multiple entries.  
- **User story:** As a caller mutating a tree object, I want repeated writes to a member name to have deterministic replacement semantics so that later updates do not create hidden duplicates.  
- **Implementation note:** This behavior is intentionally different from duplicate-key rejection in map deserialization.  
- **Conditions of satisfaction:** The final value for a repeated member name is the stored value; object member iteration contains one entry for that name; replacement is deterministic.  
- **Alternative paths:** Callers who need duplicate-key preservation must not use `JsonObject` as their model because the object abstraction is name-unique.  
- **References:** `gson/src/main/java/com/google/gson/JsonObject.java`  
- **Specificity rating:** specific

**REQ-068** — `JsonArray` preserves ordered mutation semantics and exposes a live list view that forbids raw Java `null`  
- **Summary:** `JsonArray` must preserve insertion order, support indexed replacement and removal semantics, keep its single-element scalar coercion behavior, and expose an `asList()` view that stays live while rejecting raw Java `null` elements.  
- **User story:** As a caller mixing tree-style and collection-style APIs, I want `JsonArray` mutations and list-view operations to behave predictably so that array editing preserves order and never smuggles raw Java `null` into the JSON tree.  
- **Implementation note:** This requirement covers direct `JsonArray` mutation APIs and the stricter `NonNullElementWrapperList` contract behind `asList()`.  
- **Conditions of satisfaction:** `add(...)` and `addAll(...)` append in order; `set(...)`, `remove(...)`, and `get(...)` follow indexed-list semantics and fail explicitly on out-of-range indexes; single-element `getAs*()` calls delegate to the sole element while empty or multi-element arrays fail clearly; changes through `asList()` are reflected in the backing array and vice versa; list-view mutators reject raw Java `null` but accept `JsonNull.INSTANCE`.  
- **Alternative paths:** Callers may use `JsonArray.add(...)` directly when they want Java-null normalization, but the list view must preserve a stricter collection contract around raw `null`.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/JsonArray.java`; `gson/src/main/java/com/google/gson/internal/NonNullElementWrapperList.java`; `gson/src/test/java/com/google/gson/JsonArrayAsListTest.java`; `gson/src/test/java/com/google/gson/JsonArrayAsListSuiteTest.java`  
- **Specificity rating:** specific

**REQ-069** — `JsonElement.deepCopy()` preserves structural independence for mutable trees  
- **Summary:** Deep-copying a mutable JSON tree must allocate independent container structure all the way down, while immutable leaf nodes may be reused by identity.  
- **User story:** As a caller cloning a tree before mutation, I want `deepCopy()` to provide real structural separation so that edits to the clone never bleed back into the original tree.  
- **Implementation note:** `JsonObject` and `JsonArray` recursively copy children into new containers; `JsonPrimitive` and `JsonNull` are immutable and therefore may return themselves.  
- **Conditions of satisfaction:** `JsonObject.deepCopy()` returns a new object whose member values are themselves deep copies and whose insertion order matches the source; `JsonArray.deepCopy()` returns a new array whose children are deep copies in the same order; mutating a copied `JsonObject` or `JsonArray` does not change the original and vice versa; `JsonPrimitive.deepCopy()` and `JsonNull.deepCopy()` may return the original instance because their observable state is immutable.  
- **Alternative paths:** Callers who need copy-on-write or domain-specific clone policies may build those on top of the tree model, but `deepCopy()` must remain the library's structural-isolation primitive.  
- **References:** `gson/src/main/java/com/google/gson/JsonElement.java`; `gson/src/main/java/com/google/gson/JsonObject.java`; `gson/src/main/java/com/google/gson/JsonArray.java`; `gson/src/main/java/com/google/gson/JsonPrimitive.java`; `gson/src/main/java/com/google/gson/JsonNull.java`  
- **Specificity rating:** specific

**REQ-070** — Public tree-node identity and rendering semantics remain stable  
- **Summary:** Gson's public tree node types must keep their documented `equals(...)`, `hashCode()`, and `toString()` behavior because callers depend on those methods for comparisons, map keys, and logging.  
- **User story:** As a caller storing `JsonElement` values in collections or logging them for diagnostics, I want identity and rendering semantics to be explicit so that upgrades do not silently change equality or printable JSON behavior.  
- **Implementation note:** `JsonArray` equality is order-sensitive, `JsonObject` equality ignores insertion order and compares member mappings, `JsonNull` treats all instances as equivalent, `JsonPrimitive` has numeric normalization rules captured by REQ-082, and `JsonElement.toString()` renders JSON text through a lenient writer.  
- **Conditions of satisfaction:** `JsonArray.equals(...)` and `hashCode()` stay sequence-based; `JsonObject.equals(...)` and `hashCode()` compare member mappings without making insertion order part of equality; all `JsonNull` instances compare equal and share one hash behavior; `JsonPrimitive` continues to follow REQ-082 for numeric equivalence; `JsonElement.toString()` renders standard JSON text with ordinary escaping and still succeeds for trees containing non-finite numeric primitives by using the lenient rendering path rather than failing unexpectedly.  
- **Alternative paths:** Callers who need schema-specific comparison or pretty printing may build that externally, but the default object identity and rendering methods must remain dependable.  
- **References:** `gson/src/main/java/com/google/gson/JsonElement.java`; `gson/src/main/java/com/google/gson/JsonArray.java`; `gson/src/main/java/com/google/gson/JsonObject.java`; `gson/src/main/java/com/google/gson/JsonNull.java`; `gson/src/main/java/com/google/gson/JsonPrimitive.java`  
- **Specificity rating:** specific

### Category: map key and duplicate-key behavior

This category explains how Gson maps Java container semantics onto JSON objects and entry arrays. It sits at the intersection of the type system, adapter protocol, and compatibility story, so ordering, duplicate handling, and key encoding all matter.

**REQ-071** — Duplicate map keys are rejected during deserialization  
- **Summary:** When deserializing into a Java `Map`, duplicate keys must be rejected whether the JSON came from object-member form or array-of-entry form.  
- **User story:** As a caller depending on map uniqueness, I want duplicate-key input to fail so that ambiguous last-write-wins behavior does not silently corrupt my data.  
- **Implementation note:** This is one of Gson's long-standing map-specific integrity guarantees and remains distinct from `JsonObject` replacement semantics.  
- **Conditions of satisfaction:** Duplicate keys in either supported map encoding raise a syntax or parse failure; Gson does not silently keep first or last value for Java map deserialization, including edge cases where the first occurrence carried a `null` value.  
- **Alternative paths:** Callers who need duplicate-key preservation must deserialize into a different model such as a list of entries or a tree that they process manually.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-072** — Raw map-key stringification has documented consequences  
- **Summary:** When complex-map-key serialization is not enabled, Gson must stringify map keys with the documented default behavior, including using the literal member name `"null"` for Java `null` keys.  
- **User story:** As a caller serializing maps, I want the default key encoding behavior to be predictable so that non-string keys do not appear reversible when they are not.  
- **Implementation note:** This requirement is paired with the complex-key alternative below.  
- **Conditions of satisfaction:** Default map serialization uses member names, stringifies keys, and uses `"null"` for Java `null` keys; round-tripping is not implied for arbitrary complex keys under this mode.  
- **Alternative paths:** Enable complex-map-key serialization to get adapter-based key handling and reversible array-of-entry output where needed.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-073** — Complex map keys use adapter-based encoding  
- **Summary:** When `enableComplexMapKeySerialization()` is enabled, Gson must use the registered key adapter and switch to array-of-entry encoding whenever any key serializes as a JSON array or object.  
- **User story:** As a caller round-tripping maps with non-trivial key types, I want complex-key mode to preserve key structure so that serialization and deserialization use the same logical representation.  
- **Implementation note:** This is the supported reversible path for complex keys.  
- **Conditions of satisfaction:** Key adapters are used for key serialization; object or array-shaped keys force the array-of-entry encoding; plain scalar-shaped keys may still use object-member form.  
- **Alternative paths:** Without complex-key mode, callers should expect lossy stringification and may need a custom container format instead.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-074** — Enum map-key deserialization falls back to `toString()` when documented  
- **Summary:** For enum map keys, if deserialization cannot find a matching `name()` or `@SerializedName` value, Gson must fall back to the enum constant's `toString()` value as documented, while keeping the annotation-name lookup table's last-write-wins alias behavior stable.  
- **User story:** As a developer using enums with custom string representations, I want documented fallback behavior to remain stable so that map-key round-tripping does not break unexpectedly.  
- **Implementation note:** This is a targeted interoperability rule, not a general fallback for all key types.  
- **Conditions of satisfaction:** Enum key lookup checks primary enum names and serialized names first, then uses `toString()` only for the documented enum-key fallback path; alternate `@SerializedName` aliases participate in that first lookup table; if duplicate primary or alternate aliases collide, the later registration overwrites the earlier one rather than raising a duplicate-name error.  
- **Alternative paths:** Users may avoid relying on `toString()` by using explicit `@SerializedName` values or scalar string keys.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

**REQ-075** — Arrays and Java collections preserve encounter order and element null semantics  
- **Summary:** Built-in array and collection adapters must serialize elements in encounter order, deserialize from JSON arrays only, and propagate element nulls through the element adapter instead of inventing collection-specific null normalization.  
- **User story:** As a caller round-tripping arrays, lists, sets, or queues, I want collection shape, ordering, and null-element behavior to follow the underlying Java container contract so that Gson does not silently reorder or rewrite container contents.  
- **Implementation note:** Array order is index-based, collection order follows the collection's iterator, and construction of collection interface targets composes with REQ-030's default-implementation rules.  
- **Conditions of satisfaction:** Java arrays serialize to JSON arrays in index order and deserialize back to the declared component type; Java `Collection` values serialize to JSON arrays in the collection's own iteration order and deserialize by adding each JSON element to a freshly constructed target collection; Java `null` array or collection values serialize as JSON `null` and JSON `null` deserializes to Java `null`; element-level `null` values are passed through the element adapter and are accepted or rejected according to the target component/container semantics rather than being normalized by Gson.  
- **Alternative paths:** Callers who need canonical ordering for unordered collections may normalize the collection before serialization or use a more specific container type, but Gson's built-in adapters must remain faithful to the source container's encounter order.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/ArrayTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/bind/CollectionTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`  
- **Specificity rating:** specific

### Category: enum value adapters

Enum values have their own adapter rules because serialized names, aliases, and unknown-value handling are compatibility-sensitive. Reviewers should keep both value-level and map-key-level enum semantics in mind when changing this area.

**REQ-076** — Enum values use primary serialized names, deserialization aliases, and null-on-unknown fallback  
- **Summary:** Built-in enum value adapters must serialize each constant using its primary logical name, accept `@SerializedName.alternate()` aliases and `toString()` fallback on read, and return Java `null` rather than throwing when an input string matches no known constant.  
- **User story:** As a developer exchanging enums across evolving schemas, I want enum serialization and deserialization rules to be explicit so that aliases, obfuscation resilience, and unknown values behave predictably.  
- **Implementation note:** `EnumTypeAdapter` builds immutable lookup tables once from enum constant fields, using `getDeclaredFields()` rather than `values()` to remain stable under obfuscation.  
- **Conditions of satisfaction:** Serialization uses the primary enum name or `@SerializedName.value()` for each constant; deserialization checks that primary/alternate-name table first and only then falls back to the constant's `toString()` value; a JSON `null` enum value deserializes to Java `null`; an unknown non-null enum token yields Java `null` without raising a syntax exception; if primary or alternate aliases collide, the later discovered constant silently overwrites the earlier mapping.  
- **Alternative paths:** Callers who need unknown-enum rejection, different fallback behavior, or a non-null sentinel may register a custom enum adapter instead of relying on the built-in adapter.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/EnumTypeAdapter.java`; `gson/src/main/java/com/google/gson/annotations/SerializedName.java`  
- **Specificity rating:** specific

## Numeric and Date Types

### Category: numeric coercion and policies

These requirements describe Gson's scalar number behavior, from accessors and untyped parsing to helper classes and tree-model equality. Small changes here can alter interoperability, precision, or denial-of-service characteristics across the whole library.

**REQ-077** — Numeric accessors accept documented string forms  
- **Summary:** Numeric values must be readable both as JSON numbers and as documented numeric string representations when callers use numeric accessors or compatible adapters.  
- **User story:** As an integrator consuming APIs that stringify large numbers, I want Gson to accept documented numeric string forms so that interoperability does not force lossy conversions.  
- **Implementation note:** This is not a blanket coercion rule for arbitrary text; it is a documented compatibility rule for numeric representations.  
- **Conditions of satisfaction:** Supported numeric strings are parsed by the corresponding numeric accessors or adapters; invalid strings still fail explicitly; large-number workflows can avoid unnecessary precision loss.  
- **Alternative paths:** Callers may deserialize as `String` first or register a custom numeric adapter when stricter or domain-specific rules are needed.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-078** — Non-finite numeric output is gated by lenient behavior  
- **Summary:** Writing `NaN`, positive infinity, or negative infinity must be rejected in normal JSON writing modes and only allowed on the explicitly lenient path documented by Gson.  
- **User story:** As a producer of interoperable JSON, I want invalid numeric literals to be blocked unless I explicitly opt into non-standard output so that downstream parsers are not broken by surprise.  
- **Implementation note:** This is a writer-side standards boundary.  
- **Conditions of satisfaction:** Standard writing modes reject non-finite numbers; lenient writing can emit them where documented; the behavior is not silently inverted across write entry points.  
- **Alternative paths:** Callers may serialize such values as strings or use domain-specific adapters if interoperable JSON is required.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`; Gson project quirks documented in `AGENTS.md`  
- **Specificity rating:** specific

**REQ-079** — Untyped object-number deserialization honors configured number strategy  
- **Summary:** When callers deserialize numbers as `Object` or `Number`, Gson must apply the configured object-to-number or number-to-number strategy instead of always collapsing to `double`.  
- **User story:** As a caller sensitive to integer precision and numeric shape, I want untyped number parsing to follow the configured strategy so that large integral values do not lose meaning silently.  
- **Implementation note:** This is a configuration propagation rule for untyped numeric materialization.  
- **Conditions of satisfaction:** Untyped numeric parsing reflects the configured strategy; default behavior remains documented; strategy changes alter untyped numeric result types predictably.  
- **Alternative paths:** Callers may deserialize into explicit numeric Java types or strings when full control is required.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/ToNumberPolicy.java`; `gson/src/main/java/com/google/gson/internal/bind/ObjectTypeAdapter.java`  
- **Specificity rating:** specific

**REQ-080** — Arbitrary-precision numeric parsing enforces textual size and scale limits  
- **Summary:** Gson's arbitrary-precision numeric parsing paths must reject excessively large numeric text and unsupported decimal scales instead of attempting unbounded `BigDecimal` or `BigInteger` work.  
- **User story:** As an operator handling untrusted numeric JSON, I want pathological huge-number inputs to fail fast so that numeric parsing does not become an avoidable denial-of-service vector.  
- **Implementation note:** `NumberLimits` centralizes this guard for `BigDecimal`, `BigInteger`, and helpers that delegate to them, including lazy numeric conversion paths.  
- **Conditions of satisfaction:** `parseBigDecimal(...)` and `parseBigInteger(...)` reject numeric strings longer than 10,000 characters; `parseBigDecimal(...)` also rejects values whose absolute decimal scale is 10,000 or greater; callers on these arbitrary-precision paths receive explicit numeric parse failures instead of truncated values or unbounded work; ordinary shorter numeric values continue to parse normally.  
- **Alternative paths:** Callers who need different numeric bounds may deserialize into strings or install custom number strategies, but Gson's built-in arbitrary-precision paths must retain their defensive limits.  
- **References:** `gson/src/main/java/com/google/gson/internal/NumberLimits.java`; `gson/src/main/java/com/google/gson/ToNumberPolicy.java`; `gson/src/main/java/com/google/gson/internal/LazilyParsedNumber.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

**REQ-081** — `JsonPrimitive` construction and accessor coercions remain explicit  
- **Summary:** `JsonPrimitive` constructors must reject raw Java `null`, normalize `Character` inputs to one-character strings, and preserve the documented coercion rules between boolean, string, and numeric accessors instead of silently inventing broader conversions.  
- **User story:** As a developer using the tree model directly, I want primitive node construction and accessor behavior to be predictable so that tree manipulation does not hide implicit null normalization or surprising scalar coercions.  
- **Implementation note:** `JsonPrimitive` stores exactly one boxed scalar value, uses `Boolean.parseBoolean(...)` for non-boolean `getAsBoolean()`, creates `LazilyParsedNumber` for numeric access from strings, and leaves unsupported coercions to fail explicitly.  
- **Conditions of satisfaction:** All public constructors reject raw Java `null`; `new JsonPrimitive('z')` behaves as the string `"z"`; string values such as `"true"` and `"1"` are interpreted by the documented boolean and numeric accessors; `getAsNumber()` rejects boolean primitives; empty-string `getAsCharacter()` fails explicitly rather than returning a default char.  
- **Alternative paths:** Callers who need schema-specific scalar coercion may build that on top of the tree model, but Gson's primitive node behavior must remain stable and explicit.  
- **References:** `gson/src/main/java/com/google/gson/JsonPrimitive.java`; `gson/src/test/java/com/google/gson/JsonPrimitiveTest.java`  
- **Specificity rating:** specific

**REQ-082** — `JsonPrimitive` equality is value-based for numbers but not string-vs-non-string aliases  
- **Summary:** `JsonPrimitive.equals(...)` must continue to compare numerically equivalent number representations by value, while keeping string-backed primitives distinct from non-string primitives even when their textual contents look equivalent.  
- **User story:** As a caller using `JsonPrimitive` nodes as map keys or comparison targets, I want numeric equivalence to be preserved across number implementations without collapsing strings into booleans or numbers that merely print the same way.  
- **Implementation note:** Gson normalizes integral and decimal numeric comparisons across boxed numbers, `BigInteger`, `BigDecimal`, and floating-point `NaN`, but it treats string-typed primitives as a different semantic category.  
- **Conditions of satisfaction:** `byte`, `short`, `int`, `long`, and `BigInteger` nodes with the same integral value compare equal; `float`, `double`, and `BigDecimal` nodes with the same numeric value compare equal, including `NaN` and scale-only zero differences; `"0"` does not equal `0`, and `"true"` does not equal `true`; character-backed primitives compare as their string form.  
- **Alternative paths:** Callers who want text-only comparison can compare `getAsString()` results explicitly, but `JsonPrimitive.equals(...)` must retain its mixed numeric and non-string category rules.  
- **References:** `gson/src/main/java/com/google/gson/JsonPrimitive.java`; `gson/src/test/java/com/google/gson/JsonPrimitiveTest.java`  
- **Specificity rating:** specific

**REQ-083** — `LazilyParsedNumber` stores source text without eager null validation  
- **Summary:** `LazilyParsedNumber` must preserve the original numeric source string exactly and defer both numeric conversion and any resulting null-related failure until callers use a numeric accessor.  
- **User story:** As a maintainer debugging late number-conversion failures, I want `LazilyParsedNumber`'s deferred-validation behavior to be explicit so that constructor success does not imply a valid non-null numeric payload.  
- **Implementation note:** This requirement complements REQ-058's Java-serialization guarantees by specifying the observable construction and accessor behavior of the helper itself.  
- **Conditions of satisfaction:** Constructing `LazilyParsedNumber` stores the provided string verbatim instead of parsing it eagerly; `toString()` returns that stored source text unchanged; passing `null` is not rejected at construction time and instead surfaces later as a null-related failure when numeric access needs the string value.  
- **Alternative paths:** Callers who need eager validation may parse immediately into a concrete numeric type or validate inputs before constructing the helper.  
- **References:** `gson/src/main/java/com/google/gson/internal/LazilyParsedNumber.java`; `gson/src/test/java/com/google/gson/internal/LazilyParsedNumberTest.java`  
- **Specificity rating:** specific

**REQ-084** — Built-in arbitrary-precision and atomic adapters preserve exact numeric/container semantics  
- **Summary:** Gson's dedicated arbitrary-precision and atomic-type adapters must keep their current numeric precision, policy inheritance, and array-shape semantics instead of collapsing those types to generic doubles or opaque objects.  
- **User story:** As a caller using `BigDecimal`, `BigInteger`, or atomic wrappers, I want the built-in adapters to preserve exact numeric meaning and documented container shape so that concurrency-friendly or precision-sensitive values round-trip without silent degradation.  
- **Implementation note:** `BigDecimal` and `BigInteger` parse through `NumberLimits`; `AtomicInteger` and `AtomicBoolean` use scalar adapters; `AtomicLong` and `AtomicLongArray` delegate to the active long adapter, so they inherit any configured long-as-string policy; atomic arrays stay JSON arrays in index order.  
- **Conditions of satisfaction:** `BigDecimal` and `BigInteger` deserialize from numeric token text using `NumberLimits` and write through `JsonWriter.value(Number)` without Gson-specific reformatting beyond the Java number's own string form; `BigDecimal` scale is therefore preserved when the value's `toString()` preserves that scale; `AtomicInteger` and `AtomicBoolean` round-trip as one JSON number or boolean value; `AtomicLong` and `AtomicLongArray` inherit the configured long adapter's number-vs-string policy; `AtomicIntegerArray` and `AtomicLongArray` serialize as JSON arrays in index order and deserialize back to arrays of the same length and element order.  
- **Alternative paths:** Callers who need different numeric text normalization or non-array encodings for atomic containers may replace these adapters explicitly.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/LongSerializationPolicy.java`  
- **Specificity rating:** specific

### Category: built-in scalar adapters

These adapters cover JDK scalar types that are neither plain numbers nor reflective object graphs, but still have stable wire forms that callers depend on. They belong with the other domain-specific built-ins because the review risk is the same: a seemingly small adapter change can silently rewrite stored JSON or integration contracts.

**REQ-085** — Built-in textual scalar adapters use documented string forms and validation rules  
- **Summary:** Gson's dedicated adapters for URL-like and textual JDK scalar types must keep their current string forms, null quirks, and explicit validation behavior so that round-tripping these types does not silently normalize to a different representation.  
- **User story:** As a caller exchanging identifiers and addresses such as `URI`, `URL`, `UUID`, or `Locale`, I want each built-in adapter's exact wire form and failure mode to be documented so that upgrades do not subtly change normalization or accepted input.  
- **Implementation note:** These adapters are not reflective fallbacks; they deliberately use type-specific string forms such as `URL.toExternalForm()`, `URI.toASCIIString()`, `UUID.toString()`, `Currency.getCurrencyCode()`, `Locale.toString()`, and `InetAddress.getHostAddress()`, with a small set of compatibility quirks for string token `"null"`.  
- **Conditions of satisfaction:** `URL` writes `toExternalForm()` and `URI` writes `toASCIIString()`, and both treat a JSON string token whose literal contents are `"null"` as Java `null` for backward compatibility; malformed `URI` input fails as `JsonIOException`; `UUID` writes the canonical UUID string form and invalid input fails as `JsonSyntaxException` with path context; `Currency` writes the ISO currency code and invalid codes fail explicitly; `Locale` writes `Locale.toString()` and reconstructs from one, two, or three underscore-delimited components; `InetAddress` writes `getHostAddress()` and reads through `InetAddress.getByName(...)` rather than preserving an original host name.  
- **Alternative paths:** Callers who need hostname preservation, URI normalization beyond `toASCIIString()`, or schema-specific locale/currency formats may register custom adapters.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

### Category: date and time adapters

Date and time adapters are specialized enough to deserve their own category, but they still compose with the builder, adapter system, and compatibility rules around them. Reviewers should pay close attention to captured locale or time-zone state and the exact wire shapes promised by built-in adapters.

**REQ-086** — Built-in `Date` adapters capture locale and time zone per Gson instance  
- **Summary:** Built-in `Date` adapter factories must create adapter instances at Gson-construction time so that locale and default-time-zone behavior is captured per Gson instance rather than accidentally freezing process-global defaults at class-load time.  
- **User story:** As an application developer changing default locale or time zone across environments, I want each `Gson` instance to bind date-format behavior when it is created so that serialization stays predictable and does not depend on which thread first loaded Gson classes.  
- **Implementation note:** `DefaultDateTypeAdapter.DEFAULT_STYLE_FACTORY` intentionally creates a fresh adapter instead of reusing a static singleton because `DateFormat` and `SimpleDateFormat` capture default locale and time zone on creation; the adapter also keeps a US-locale format first, then optional local and pre-Java-9 compatibility formats for parsing.  
- **Conditions of satisfaction:** Formatting uses the default time zone that was active when the adapter was created; serialization keeps using the adapter's original formatter time zone even after parsing a string with a different explicit time zone; parsing accepts both US-locale and system-locale variants documented by the adapter setup; two Gson instances created under different defaults do not silently share one captured formatter state.  
- **Alternative paths:** Callers may install explicit date patterns or custom date adapters, but the built-in factory path must remain instance-local and safe against brittle class-initialization timing.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/DefaultDateTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/PreJava9DateFormatProvider.java`; `gson/src/test/java/com/google/gson/internal/bind/DefaultDateTypeAdapterTest.java`  
- **Specificity rating:** specific

**REQ-087** — ISO-8601 helpers accept documented variants and fail explicitly on malformed input  
- **Summary:** Gson's ISO-8601 utility path must format and parse the documented date/time variants, including UTC `Z`, signed offsets, optional milliseconds, and date-only input, while malformed calendar, clock, or time-zone values fail with explicit parse errors and full-string consumption remains outside the helper's contract.  
- **User story:** As a caller exchanging timestamps with systems that vary in offset and precision formatting, I want Gson's ISO-8601 fallback to accept the supported variants and reject malformed timestamps deterministically so that date interoperability does not depend on JDK-specific formatter quirks.  
- **Implementation note:** `ISO8601Utils` is the fallback parser used by `DefaultDateTypeAdapter` after locale-based formats fail; it formats with `Z` for UTC and `+/-hh:mm` offsets otherwise, and it wraps parsing failures in `ParseException` with the original cause.  
- **Conditions of satisfaction:** Formatting in UTC emits `Z`; formatting in non-UTC time zones emits a signed offset; parsing accepts documented forms such as date-only input, `T00:00Z`, full seconds, milliseconds, `+01`, and `+01:00`; invalid month, day, time, or time-zone indicators raise a parse failure instead of silently normalizing to a different instant; the helper advances `ParsePosition` only through the recognized timestamp portion and does not independently reject trailing characters beyond that parsed prefix.  
- **Alternative paths:** Callers may bypass the fallback by installing their own date adapter, but Gson's built-in ISO-8601 path must remain a stable interoperability escape hatch when locale-based parsing does not apply.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/util/ISO8601Utils.java`; `gson/src/main/java/com/google/gson/internal/bind/DefaultDateTypeAdapter.java`; `gson/src/test/java/com/google/gson/internal/bind/util/ISO8601UtilsTest.java`; `gson/src/test/java/com/google/gson/internal/bind/DefaultDateTypeAdapterTest.java`  
- **Specificity rating:** specific

**REQ-088** — SQL type support activates only when `java.sql` is available  
- **Summary:** Gson must probe for `java.sql` support safely at runtime and only expose SQL-specific date/time adapters when the `java.sql` module is present; otherwise it must degrade to an empty, no-support state without class-loading failures.  
- **User story:** As a platform owner trimming JDK modules, I want Gson to remain loadable without `java.sql` so that optional SQL support does not turn into startup-time `ClassNotFoundException`s on smaller runtimes.  
- **Implementation note:** `SqlTypesSupport` centralizes this guard by probing `java.sql.Date` once, publishing non-null factories only when available, and otherwise leaving the SQL factory list empty.  
- **Conditions of satisfaction:** Environments with `java.sql` expose SQL type factories and date-type bridges for `java.sql.Date`, `Time`, and `Timestamp`; environments without `java.sql` leave those hooks unavailable but still load Gson successfully; callers can test support through the published boolean/list contract instead of relying on exception-driven probing.  
- **Alternative paths:** Applications that always require SQL support may depend on a full JDK, but Gson itself must preserve optional-module behavior rather than assuming `java.sql` is always present.  
- **References:** `gson/src/main/java/com/google/gson/internal/sql/SqlTypesSupport.java`; `gson/src/main/java/com/google/gson/internal/sql/SqlDateTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/sql/SqlTimeTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/sql/SqlTimestampTypeAdapter.java`  
- **Specificity rating:** specific

**REQ-089** — Built-in `java.time` support preserves the frozen reflective wire shape  
- **Summary:** Gson's built-in `java.time` adapters must serialize supported temporal types as the frozen object-shaped field layouts derived from JDK 21 reflective behavior rather than switching them to ISO strings or another compact representation.  
- **User story:** As a library upgrader with existing stored JSON for `java.time` values, I want built-in support to preserve the established reflective wire shape so that adding native adapters does not silently break backward compatibility.  
- **Implementation note:** `JavaTimeTypeAdapters` intentionally freezes the field-oriented representation that reflective binding used to expose, covering scalar types such as `LocalDate`, `LocalTime`, `Year`, and `ZoneOffset`, and nested composite types such as `LocalDateTime` and `ZonedDateTime`.  
- **Conditions of satisfaction:** `LocalDate` serializes as `{year, month, day}`; `LocalTime` serializes as `{hour, minute, second, nano}`; `LocalDateTime`, `OffsetDateTime`, `OffsetTime`, and `ZonedDateTime` use the documented nested object structure; `ZoneOffset` uses `totalSeconds`; `ZoneId` region values use `id`; round-tripping preserves those shapes instead of silently migrating to ISO text.  
- **Alternative paths:** Callers who want ISO-8601 strings may register custom adapters, but built-in support must keep the compatibility-oriented object shape as the default contract.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JavaTimeTypeAdapters.java`; `gson/src/test/java/com/google/gson/functional/DefaultTypeAdaptersTest.java`  
- **Specificity rating:** specific

**REQ-090** — Composite `java.time` adapters require named components and still honor nested overrides  
- **Summary:** Composite `java.time` adapters must ignore unknown fields, require their documented component fields to be present, and continue to honor user-registered nested adapters such as a custom `ZoneId` adapter instead of hardwiring every nested encoding.  
- **User story:** As a developer mixing built-in temporal support with one or two custom temporal overrides, I want the composite adapters to enforce required fields while still composing with my nested adapter registrations so that I can customize part of the temporal graph without replacing all of it.  
- **Implementation note:** `JavaTimeTypeAdapters` uses explicit field names like `date`, `time`, `offset`, and `zone`, throws `JsonSyntaxException` with path context when required members are absent, and looks up nested adapters through `gson.getAdapter(...)` so user registrations can participate.  
- **Conditions of satisfaction:** Missing required members such as `date`, `time`, `offset`, or `zone` fail with field-specific path context; unknown extra members are skipped rather than corrupting deserialization; a custom `ZoneId` adapter is used when serializing and deserializing the `zone` component of `ZonedDateTime`; null handling remains controlled by the adapter's `nullSafe()` boundary.  
- **Alternative paths:** Callers may replace an entire temporal type with their own adapter, but the default composite adapters must remain composable for targeted nested overrides.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/JavaTimeTypeAdapters.java`; `gson/src/test/java/com/google/gson/functional/DefaultTypeAdaptersTest.java`  
- **Specificity rating:** specific

**REQ-091** — Built-in SQL `Timestamp` handling preserves only millisecond precision  
- **Summary:** Gson's built-in `java.sql.Timestamp` adapter path must delegate through the registered `Date` adapter and therefore preserve only millisecond precision, silently truncating any nanosecond component beyond `getTime()`.  
- **User story:** As a caller exchanging SQL timestamps, I want Gson's precision boundary to be explicit so that nanosecond data loss is not mistaken for a transport or database bug elsewhere.  
- **Implementation note:** The timestamp adapter does not carry its own formatter; it reuses the `Date` adapter for both read and write, then rebuilds `Timestamp` from the resulting epoch milliseconds.  
- **Conditions of satisfaction:** Writing a `Timestamp` delegates directly to the active `Date` adapter; reading wraps the resulting `Date` as `new Timestamp(date.getTime())`; `null` still round-trips as `null`; nanoseconds finer than milliseconds are silently discarded rather than preserved or warned about.  
- **Alternative paths:** Callers who need nanosecond fidelity may install a custom `Timestamp` adapter or serialize timestamps in a schema-specific textual or structured representation.  
- **References:** `gson/src/main/java/com/google/gson/internal/sql/SqlTimestampTypeAdapter.java`; `gson/src/main/java/com/google/gson/internal/bind/DefaultDateTypeAdapter.java`  
- **Specificity rating:** specific

**REQ-092** — Built-in `Calendar` handling preserves the legacy six-field object shape  
- **Summary:** Gson's dedicated `Calendar`/`GregorianCalendar` adapter must keep the existing six-field object representation instead of switching to epoch millis, ISO text, or a locale-formatted date string.  
- **User story:** As a maintainer round-tripping legacy calendar payloads, I want the built-in calendar wire shape to remain explicit so that changing date-adapter behavior elsewhere does not silently rewrite this older structured format.  
- **Implementation note:** The adapter is implemented through `IntegerFieldsTypeAdapter` and therefore mirrors the same ordered integer-field object shape used by several legacy temporal adapters.  
- **Conditions of satisfaction:** `Calendar` and `GregorianCalendar` serialize as an object with `year`, `month`, `dayOfMonth`, `hourOfDay`, `minute`, and `second` fields in that order; deserialization reads those named integer fields, ignores unknown extra fields, and reconstructs a `GregorianCalendar`; `null` continues to round-trip as `null`; values outside Java `int` range fail explicitly during reconstruction rather than silently truncating.  
- **Alternative paths:** Callers who prefer epoch-based or ISO-8601 calendar encodings may register custom adapters instead of relying on the legacy built-in shape.  
- **References:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

## Field Management

### Category: naming and exclusion controls

This category covers the field-level controls that shape reflective binding without replacing it. It connects the core configuration surface to annotation handling below and is often where schema migrations first become visible.

**REQ-093** — Naming policies and explicit serialized names compose predictably  
- **Summary:** Field naming policy must apply deterministically to ordinary fields, while `@SerializedName` must take precedence for explicitly named fields and support documented alternates for deserialization.  
- **User story:** As a developer maintaining stable wire names, I want global naming policies and explicit per-field overrides to interact predictably so that schema migrations do not become guesswork.  
- **Implementation note:** This requirement spans builder configuration, annotation handling, and duplicate-name detection.  
- **Conditions of satisfaction:** Unannotated fields follow the configured naming policy; annotated fields use the declared primary name; alternate names are accepted on read where supported; conflicts are rejected rather than silently shadowed.  
- **Alternative paths:** Callers may use only naming policies or only `@SerializedName`, but mixed usage must remain deterministic.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/annotations/SerializedName.java`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`  
- **Specificity rating:** specific

**REQ-094** — Exclusion configuration replaces defaults only as documented  
- **Summary:** Calling `excludeFieldsWithModifiers(...)` must replace the default modifier exclusions exactly as documented, including the possibility that `static` or `transient` fields become included unless explicitly re-excluded.  
- **User story:** As a caller customizing exclusion rules, I want modifier overrides to be explicit and predictable so that I do not accidentally reintroduce fields I assumed stayed excluded.  
- **Implementation note:** This is a configuration semantics rule and a common troubleshooting source.  
- **Conditions of satisfaction:** The configured modifier set is the effective exclusion set; defaults are not partially retained behind the scenes; output matches the documented replacement behavior.  
- **Alternative paths:** Callers who want the defaults can skip the method entirely or include `Modifier.STATIC` and `Modifier.TRANSIENT` explicitly in their override.  
- **References:** `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

## Annotations

### Category: annotation-driven binding

These requirements describe the declarative metadata Gson reads from application classes. They build on the naming, exclusion, and adapter-resolution rules around them, so annotation behavior needs to stay predictable rather than magical.

**REQ-095** — Version filters apply symmetrically to serialization and deserialization  
- **Summary:** When a version is configured, fields and classes above that version threshold must be excluded from both serialization and deserialization; when no version is configured, version annotations must not exclude anything.  
- **User story:** As a client maintaining backward-compatible JSON contracts, I want `@Since`-based filtering to behave consistently in both directions so that versioned payloads round-trip predictably.  
- **Implementation note:** Versioning is a behavioral contract, not just a serializer-side convenience.  
- **Conditions of satisfaction:** Fields or types above the configured version are skipped on write and ignored on read; unversioned operation includes everything unless another exclusion rule applies.  
- **Alternative paths:** Callers may avoid version annotations entirely, but if they use them the filtering behavior must be consistent.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

**REQ-096** — `@Expose` gates only the configured instance  
- **Summary:** `@Expose` annotations must affect inclusion only when `excludeFieldsWithoutExposeAnnotation()` is enabled, and the annotation's `serialize` and `deserialize` flags must be respected independently.  
- **User story:** As an API author, I want opt-in field exposure to be explicit so that simply adding `@Expose` does not unexpectedly change behavior on unrelated `Gson` instances.  
- **Implementation note:** This is both an instance-local configuration rule and a field-direction rule.  
- **Conditions of satisfaction:** Without the builder flag, `@Expose` does not hide otherwise eligible fields; with the flag, only exposed fields participate; direction-specific flags are honored independently.  
- **Alternative paths:** Users who need richer rules may use `ExclusionStrategy` or custom adapters instead of `@Expose`.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/internal/Excluder.java`  
- **Specificity rating:** specific

**REQ-097** — `@JsonAdapter` binds one adapter class per annotated target  
- **Summary:** `@JsonAdapter` must bind exactly one adapter class to the annotated type or field, so combined custom read and write behavior requires either a single `TypeAdapter` or builder-level registration of separate serializer and deserializer components.  
- **User story:** As a developer choosing between annotations and builder registration, I want the capability boundary to be clear so that I do not expect two separate annotated handlers to compose magically.  
- **Implementation note:** This is an extension-surface contract rather than a JSON syntax rule.  
- **Conditions of satisfaction:** One annotation names one effective adapter class; separate custom serializer and deserializer classes do not both activate through multiple annotations on the same target; a single `TypeAdapter` can provide both directions.  
- **Alternative paths:** Use builder registration for separate read and write handlers, or a single `TypeAdapter` with `@JsonAdapter`.  
- **References:** `retrieved_documentation/community/futurestud_jsonadapter_annotation.md`; `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/annotations/JsonAdapter.java`  
- **Specificity rating:** specific

## HTML Escaping and Output

### Category: output hardening and presentation

This category covers writer-side presentation and hardening features that sit above raw syntax but below application-specific schemas. These settings should change how JSON is framed or formatted, not what data Gson believes it is representing.

**REQ-098** — Non-executable JSON prefix is written consistently  
- **Summary:** When `generateNonExecutableJson()` is enabled, every JSON document written through that `Gson` instance must be prefixed with `)]}'\n`.  
- **User story:** As a security-conscious service owner, I want the non-executable prefix to appear on every configured output so that clients do not get a false sense of XSSI protection.  
- **Implementation note:** This is a writer-side security policy and must not vary by entry point.  
- **Conditions of satisfaction:** All relevant `toJson` paths emit the prefix when enabled and omit it when not enabled; no supported serialization entry point silently skips the prefix.  
- **Alternative paths:** Callers may leave the feature disabled, but if enabled they should not need custom wrappers to get complete coverage.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`  
- **Specificity rating:** specific

**REQ-099** — Gson readers tolerate the non-executable prefix  
- **Summary:** Gson deserialization must accept input containing the non-executable JSON prefix, regardless of whether the local `Gson` instance is configured to emit that prefix.  
- **User story:** As a consumer of JSON from another Gson-based service, I want prefixed payloads to deserialize correctly so that producer and consumer settings can differ safely.  
- **Implementation note:** This is a cross-process interoperability requirement, not just a local symmetry rule.  
- **Conditions of satisfaction:** Prefixed JSON is accepted on normal read paths; the prefix is stripped before logical JSON parsing; readers that did not emit the prefix themselves can still consume it.  
- **Alternative paths:** Callers may strip the prefix manually, but built-in support should make that unnecessary in ordinary Gson-to-Gson communication.  
- **References:** `retrieved_documentation/official/changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`  
- **Specificity rating:** specific

**REQ-100** — Pretty printing changes formatting, not meaning  
- **Summary:** Pretty-printing configuration may change whitespace and layout, but it must not change the logical JSON value or inclusion rules for fields beyond the explicitly configured formatting settings.  
- **User story:** As a developer switching between compact and human-readable output, I want formatting choices to affect presentation only so that debugging and production payloads remain semantically equivalent.  
- **Implementation note:** This is a wire-format stability rule; whitespace is allowed to change, value semantics are not.  
- **Conditions of satisfaction:** Pretty-printed and compact output parse to the same JSON value for the same input object under the same non-formatting configuration.  
- **Alternative paths:** Callers may use compact output everywhere, but pretty printing must remain a safe readability toggle.  
- **References:** `retrieved_documentation/official/user_guide.md`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

**REQ-101** — `FormattingStyle` remains immutable, validated, and semantically orthogonal  
- **Summary:** `FormattingStyle` instances must remain immutable value objects whose newline and indent domains are validated narrowly, while formatting choices stay orthogonal to JSON meaning and only affect the permitted whitespace layout.  
- **User story:** As a caller reusing formatting presets across writers, I want formatting styles to be safely shareable and strictly validated so that presentation customization does not accidentally introduce invalid control characters or semantic drift.  
- **Implementation note:** `FormattingStyle` exposes `COMPACT` and `PRETTY` presets plus `withX(...)` copy methods, restricts newline strings to `\r`/`\n` combinations and indent strings to spaces/tabs, and lets newline handling suppress comma-spacing on multi-line output.  
- **Conditions of satisfaction:** `withNewline(...)`, `withIndent(...)`, and `withSpaceAfterSeparators(...)` return new styles rather than mutating the original; invalid newline or indent characters fail immediately; non-empty newline styles emit line breaks and indentation while compact styles may use single-line separator spacing; JSON produced under different valid styles parses to the same logical value.  
- **Alternative paths:** Callers may still use legacy pretty-printing toggles or `JsonWriter#setIndent(...)`, but `FormattingStyle` must remain the reusable, validated configuration object for writer formatting.  
- **References:** `gson/src/main/java/com/google/gson/FormattingStyle.java`; `gson/src/test/java/com/google/gson/functional/FormattingStyleTest.java`; `gson/src/test/java/com/google/gson/stream/JsonWriterTest.java`  
- **Specificity rating:** specific

**REQ-102** — HTML-safe escaping and writer-level overrides compose predictably  
- **Summary:** Gson must keep JSON string escaping and HTML-safe escaping as separate layers: base JSON escaping is always applied, HTML-safe escaping is opt-in at `JsonWriter` level and enabled by default only for Gson-managed writers, and per-call Gson serialization must restore any caller-provided writer setting afterward.  
- **User story:** As a caller mixing direct `JsonWriter` use with `Gson`-managed output, I want escaping rules and override precedence to be explicit so that I can predict exactly which characters are escaped and when a writer's local configuration will be preserved.  
- **Implementation note:** `JsonWriter` always escapes control characters, quotes, backslashes, and U+2028/U+2029; HTML-safe mode adds `<`, `>`, `&`, `=`, and `'`; `Gson.newJsonWriter(...)` applies the instance's configured HTML-safety, and `Gson.toJson(..., JsonWriter)` temporarily overrides then restores the writer flag.  
- **Conditions of satisfaction:** Direct `JsonWriter` instances default to `htmlSafe == false`; Gson-created writers for `new Gson()` use HTML-safe output by default; disabling HTML escaping removes only the extra `<`, `>`, `&`, `=`, and `'` escapes and does not disable ordinary JSON escaping or U+2028/U+2029 escaping; `Gson.toJson(Object, Type, JsonWriter)` and `Gson.toJson(JsonElement, JsonWriter)` apply the `Gson` instance's HTML-safe flag for the duration of the call and restore the original writer setting afterward.  
- **Alternative paths:** Callers who need a different policy for one specific write can configure the `JsonWriter` directly or build a separate `Gson` instance, but the interaction between builder-level and writer-level settings must stay deterministic.  
- **References:** `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/main/java/com/google/gson/stream/JsonWriter.java`  
- **Specificity rating:** specific

## Error Handling

### Category: actionable failures

These requirements make failure behavior part of the public API. Gson often sits at trust boundaries, so errors need to preserve enough context to drive a fix instead of forcing callers into debugger archaeology.

**REQ-103** — Malformed JSON reports actionable location context  
- **Summary:** When JSON syntax is malformed or the structure does not match the requested read operation, Gson must fail with location information that includes the path within the JSON document.  
- **User story:** As an operator debugging bad input, I want parse failures to identify where the problem occurred so that malformed payloads can be diagnosed quickly.  
- **Implementation note:** Troubleshooting guidance explicitly depends on line, column, and JSONPath context.  
- **Conditions of satisfaction:** Syntax and structural errors identify the problem location; paths point to the offending member or array index closely enough to support diagnosis; errors are not generic or pathless.  
- **Alternative paths:** Callers may log raw JSON for more context, but Gson's exception messages must already be actionable.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/stream/JsonReader.java`; `gson/src/main/java/com/google/gson/stream/MalformedJsonException.java`  
- **Specificity rating:** specific

**REQ-104** — Reflection failures surface actionable remediation  
- **Summary:** When reflection is blocked by JPMS boundaries, Android platform restrictions, or a `ReflectionAccessFilter`, Gson must fail with an actionable message that points callers toward `opens`, exclusions, or explicit adapters.  
- **User story:** As an operator diagnosing deployment-specific failures, I want reflective access errors to explain how to restore intended behavior so that the fix is not a blind search.  
- **Implementation note:** Troubleshooting guidance turns this into a public contract for failure messaging.  
- **Conditions of satisfaction:** Reflection failures do not degrade into opaque low-level exceptions; the error identifies blocked access and suggests supported remedies; explicit adapters can still replace reflection.  
- **Alternative paths:** Callers may open packages, exclude fields, add filters, or avoid reflection entirely with adapters or tree/stream APIs.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`; `gson/src/main/java/com/google/gson/ReflectionAccessFilter.java`  
- **Specificity rating:** specific

## Thread Safety

### Category: reusable instances and initialization safety

Thread safety in Gson is mostly about safe reuse of immutable configuration and stateless adapters. This category ties together the core API promise, adapter expectations, and initialization behavior that must hold under concurrent load.

**REQ-105** — Thread-safe instance reuse  
- **Summary:** A `Gson` instance must be safely reusable across repeated and concurrent serialization and deserialization calls without leaking per-call adapter resolution state between operations.  
- **User story:** As an application developer, I want to share one configured `Gson` instance across threads so that JSON handling stays correct without extra synchronization or per-call construction.  
- **Implementation note:** This contract is carried by `Gson`, its adapter cache, and re-entrant adapter lookup guards; custom adapters can weaken it if they keep mutable shared state.  
- **Conditions of satisfaction:** Concurrent callers can invoke `toJson` and `fromJson` on the same instance; one call does not see another call's temporary resolution state; correctness does not depend on external locking.  
- **Alternative paths:** Callers may still create multiple `Gson` instances for configuration isolation, but correctness must not require one instance per thread or one instance per call.  
- **References:** `retrieved_documentation/official/javadoc_gson_class.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0613_thread_safety.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-106** — Custom adapters must be stateless or otherwise thread-safe  
- **Summary:** Adapters reused by a `Gson` instance must be safe for concurrent reuse, or they invalidate Gson's documented thread-safety guarantee.  
- **User story:** As a developer sharing one `Gson`, I want adapter reuse to be safe so that my JSON layer does not become the hidden source of race conditions.  
- **Implementation note:** Gson's own thread safety depends on this expectation for registered adapters.  
- **Conditions of satisfaction:** Adapter instances do not keep mutable per-call shared state unless they synchronize safely; concurrent calls through one adapter do not corrupt one another.  
- **Alternative paths:** State can be externalized to immutable configuration or `ThreadLocal` where sharing mutable state would otherwise be unsafe.  
- **References:** `retrieved_documentation/official/javadoc_type_adapter.md`; `retrieved_documentation/official/user_guide.md`; `retrieved_documentation/github_issues/issue_0613_thread_safety.md`; `gson/src/main/java/com/google/gson/TypeAdapter.java`  
- **Specificity rating:** specific

**REQ-107** — Concurrent adapter initialization must not deadlock or expose partial state  
- **Summary:** Concurrent creation or initialization of built-in and recursive adapters must not deadlock and must not expose half-initialized adapters to other threads.  
- **User story:** As a server starting under concurrent load, I want adapter initialization to be safe so that startup and first-use paths cannot hang or return corrupted behavior.  
- **Implementation note:** This includes both recursive user-type resolution and built-in class-loading interactions.  
- **Conditions of satisfaction:** Concurrent adapter lookup and built-in adapter initialization complete without deadlock; recursive adapter placeholders are resolved safely; other threads do not observe partially initialized adapters as final state.  
- **Alternative paths:** Eager warm-up is optional for performance, but correctness must not depend on single-threaded initialization.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/github_issues/issue_2739_class_loading_deadlock.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/java/com/google/gson/Gson.java`; `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java`  
- **Specificity rating:** specific

## Backward Compatibility

### Category: legacy behaviors and migration safety

Backward compatibility is a first-class concern for a library embedded in frameworks, Android apps, and long-lived stored JSON formats. This closing category collects the migration and precedence rules that let Gson evolve without turning maintenance upgrades into schema surprises.

**REQ-108** — Shrinker and obfuscation workflows must preserve binding metadata or use explicit aliases  
- **Summary:** Android and shrinker-based deployments must preserve field names, generic signatures, and needed constructors, or callers must supply explicit `@SerializedName` aliases and adapter strategies that preserve compatibility across releases.  
- **User story:** As a mobile or minified-build maintainer, I want Gson's metadata dependencies to be explicit so that release builds do not silently corrupt JSON contracts or lose type information.  
- **Implementation note:** This is a deployment constraint that directly affects reflective binding, `TypeToken`, and backward compatibility.  
- **Conditions of satisfaction:** Required metadata is retained or replaced by explicit aliases and adapters; release builds continue to deserialize older payloads where compatibility is expected; missing metadata fails diagnosably.  
- **Alternative paths:** Constrain reflected classes, avoid reflection, use explicit field annotations, or supply custom ProGuard/R8 rules.  
- **References:** `retrieved_documentation/official/troubleshooting.md`; `retrieved_documentation/official/releases_changelog.md`; `gson/src/main/resources/META-INF/proguard/gson.pro`  
- **Specificity rating:** specific

**REQ-109** — Built-in compatibility changes should preserve upgrade safety  
- **Summary:** Minor-version fixes and validations around adapter registration, strictness, number handling, and reflective access should preserve upgrade safety by keeping documented compatibility shims or clear migration paths.  
- **User story:** As a library upgrader, I want Gson to evolve without turning ordinary upgrades into unplanned rewrites so that bug fixes and safety improvements remain adoptable.  
- **Implementation note:** This requirement is intentionally broad because multiple release notes and issues show backward compatibility itself is part of Gson's behavioral surface.  
- **Conditions of satisfaction:** Behavior changes that tighten validation or change defaults preserve compatibility aliases, explicit migration guidance, or backward-compatible registration behavior; minor upgrades do not introduce silent wire incompatibility without documentation.  
- **Alternative paths:** Breaking behavior may still be justified in major shifts, but minor and maintenance releases should prefer compatibility-preserving transitions.  
- **References:** `retrieved_documentation/official/changelog.md`; `retrieved_documentation/official/releases_changelog.md`; `retrieved_documentation/github_issues/issue_2295_strict_mode.md`; `retrieved_documentation/github_issues/issue_2787_backwards_compat_broken.md`  
- **Specificity rating:** directional

**REQ-110** — Adapter-factory consultation order remains a stable compatibility contract  
- **Summary:** Gson must preserve the documented effective order in which adapter factories are consulted: protected core adapters first, then user registrations in last-in-first-out order, then built-in platform/composite adapters, and reflective fallback last.  
- **User story:** As a library maintainer registering custom adapters, I want adapter precedence to stay stable across upgrades so that a patch release does not silently reroute a type from my adapter to a built-in or reflective adapter.  
- **Implementation note:** `GsonBuilder.createFactories()` assembles this chain deliberately: JSON tree/object handling and the excluder occupy fixed positions, user adapters are reversed into LIFO order, and composite/reflective factories terminate the search.  
- **Conditions of satisfaction:** Later user registrations still win within their precedence band; exact and hierarchy adapters continue to compose consistently with REQ-012 and REQ-013; delegate lookup skips factories by reference and resumes at the next effective factory; reflective binding is consulted only after earlier applicable factories decline the type.  
- **Alternative paths:** Callers can still centralize registrations or use `getDelegateAdapter(...)` for controlled delegation, but they must not need version-specific workarounds for factory ordering drift.  
- **References:** `gson/src/main/java/com/google/gson/GsonBuilder.java`; `gson/src/test/java/com/google/gson/functional/TypeAdapterPrecedenceTest.java`; `gson/src/test/java/com/google/gson/GsonTest.java`; `gson/src/test/java/com/google/gson/functional/DefaultTypeAdaptersTest.java`  
- **Specificity rating:** specific
