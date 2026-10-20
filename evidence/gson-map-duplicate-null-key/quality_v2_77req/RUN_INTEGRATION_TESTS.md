# Integration Test Protocol: Gson

## Integration Test Plan Summary

This repository is a **library with environment-boundary integration modules**, not a service. The integration surface is where Gson meets:

- standard JVM execution
- JPMS modules
- Android/shrinker-compatible bytecode
- GraalVM native-image

Because this session is non-interactive, this file records the plan-first view that would normally be presented for confirmation before writing the full protocol.

| # | Test Group | What It Exercises | Dependencies | Est. Duration |
|---|------------|-------------------|--------------|---------------|
| 1 | Core contract smoke | reflection binding, parser strictness, complex map keys, XSSI prefix, raw-type degradation | Maven, JDK 17-21 | ~3m |
| 2 | JPMS boundary | `module-info` openness and reflective access under modules | Maven, JDK with JPMS | ~2m |
| 3 | Shrinker compatibility | field-name stability and `@SerializedName`/metadata preservation under obfuscation | Maven, shrinker toolchain from repo | ~4m |
| 4 | Native-image boundary | reachability metadata for reflective paths in AOT builds | GraalVM native-image, Maven | ~8m |

## Working Directory

Run all commands from the project root — the directory containing `pom.xml`.

## Safety Constraints

1. Stop immediately if the core library does not compile.
2. Do not claim environment-boundary coverage if the relevant toolchain is missing; record the skipped group explicitly.
3. Keep commands relative-path only.
4. Treat this repository’s current baseline mismatch as a blocking pre-flight signal if it is still present:
   - `Gson.java` expects modern builder internals (`strictness`, `newImmutableList`, default factories)
   - `GsonBuilder.java` in this snapshot still exposes older fields (`prettyPrinting`, `lenient`, legacy constructor)

## Pre-Flight Dependency Checks

Run these before any integration workload:

```bash
java -version
mvn -q -version
mvn -q -pl gson -DskipTests compile
```

Optional environment checks:

```bash
native-image --version
```

### Pre-flight pass criteria

- Java version is between 17 and 21 inclusive for builds.
- Maven is available.
- `mvn -q -pl gson -DskipTests compile` succeeds.
- If `native-image` is absent, Group 4 is marked **SKIPPED (toolchain missing)** rather than silently ignored.

## Field Reference Tables

Gson does not keep standalone schema files, so the protocol uses canonical fixture shapes from the core test suite and quality tests. Re-read these source files before every change to the table:

- `gson/src/test/java/com/google/gson/common/TestTypes.java`
- `gson/src/test/java/com/google/gson/quality/FunctionalTest.java`
- `gson/src/test/java/com/google/gson/functional/MapAsArrayTypeAdapterTest.java`

### Fixture Schema: `BagOfPrimitives`

| Field | Type | Accepts | Quality Gate |
|------|------|---------|--------------|
| `longValue` | `long` | integer JSON number | round-trip value unchanged |
| `intValue` | `int` | integer JSON number | round-trip value unchanged |
| `booleanValue` | `boolean` | `true` / `false` | round-trip value unchanged |
| `stringValue` | `String` | JSON string | round-trip value unchanged |

Source: `gson/src/test/java/com/google/gson/common/TestTypes.java`

### Fixture Schema: `Point`

| Field | Type | Accepts | Quality Gate |
|------|------|---------|--------------|
| `x` | `int` | integer JSON number | key round-trips exactly |
| `y` | `int` | integer JSON number | key round-trips exactly |

Source: `gson/src/test/java/com/google/gson/functional/MapAsArrayTypeAdapterTest.java`

### Fixture Schema: `SamplePojo`

| Field | Type | Accepts | Quality Gate |
|------|------|---------|--------------|
| `name` | `String` | JSON string | serialized name/value exact |
| `count` | `int` | integer JSON number | serialized and deserialized exact |
| `active` | `boolean` | `true` / `false` | serialized and deserialized exact |

Source: `gson/src/test/java/com/google/gson/quality/FunctionalTest.java`

## Test Matrix

| Group | Axis A | Axis B | Axis C | Expected signal |
|------|--------|--------|--------|-----------------|
| 1. Core contract smoke | typed vs raw binding | default vs strict/lenient parsing | default vs prefixed JSON | exact JSON strings, precise exception classes/messages |
| 2. JPMS boundary | open package vs unopened package | reflective binding vs custom adapter | JDK runtime | reflection succeeds only when openness or custom adapters are provided |
| 3. Shrinker compatibility | preserved fields vs obfuscated fields | plain field names vs `@SerializedName` aliases | upgrade compatibility | old JSON remains readable only when metadata contract is preserved |
| 4. Native image | declared reflective types vs undeclared types | reflective binding vs non-reflective adapter | AOT build vs JVM run | native image succeeds only for configured reflective paths |

## Execution UX

When an agent later runs this protocol, it should:

1. Show the groups that are about to run and the groups that will be skipped.
2. Print one-line progress updates:
   - `⧗ Group 1 core contract smoke`
   - `✓ Group 1 core contract smoke`
   - `✗ Group 2 JPMS boundary`
3. End with a summary table and a recommendation (`ready`, `fix before release`, `toolchain gap only`).

## Group 1: Core contract smoke

### Command

```bash
mvn -q -pl gson -Dtest='com.google.gson.quality.FunctionalTest,com.google.gson.functional.MapTest,com.google.gson.functional.SecurityTest,com.google.gson.functional.ReflectionAccessTest,com.google.gson.functional.CircularReferenceTest' test
```

### Pass criteria

1. `FunctionalTest` passes without failures or errors.
2. `MapTest` confirms:
   - `null` map keys become `"null"`
   - `Map<String, ...>` uses `LinkedTreeMap`
   - duplicate-key behavior matches expectations
3. `SecurityTest` confirms the non-executable prefix is both written and readable.
4. `ReflectionAccessTest` confirms inaccessible reflection paths fail with troubleshooting guidance.
5. `CircularReferenceTest` confirms cyclic graphs still fail with a rooted `StackOverflowError`, while DAGs serialize and deserialize.
6. `FunctionalTest` also confirms:
   - parent-type deserializers do not strip subclass fields during serialization
   - wrapped serializers do not see `null` unless the adapter path explicitly opts out of null-safe handling
   - `JsonElement` adapter registrations remain backward-compatible no-ops instead of changing tree-model behavior

### Quality gates

- Serialized `SamplePojo("demo", 7, true)` equals `{"name":"demo","count":7,"active":true}` exactly.
- Prefixed output starts with `)]}'\n`.
- Complex `Map<Point, String>` with `enableComplexMapKeySerialization()` serializes as array-of-entry JSON and round-trips exactly.
- Raw `List.class` deserialization returns generic containers (`LinkedTreeMap`) rather than fake typed POJOs.
- Serializing a `Dog` through a Gson instance with a custom `Animal` deserializer still emits `{"species":"canine","breed":"labrador","age":5}`.
- Serializing a `NullAwareFieldHolder` with `serializeNulls()` and `@JsonAdapter(nullSafe = false)` emits `{"value":"null-seen"}` rather than omitting the field or writing bare JSON `null`.

## Group 2: JPMS boundary

### Command

```bash
mvn -q -pl test-jpms test
```

### Pass criteria

- Module tests pass.
- Any package Gson reflectively binds is explicitly opened to `com.google.gson`.
- A failure must mention module openness or reflection access, not an unrelated parse error.

### Quality gates

- `module-info.java` declares the required `opens` entries.
- Removing or breaking module openness must produce a reproducible reflection-access failure, not partial deserialization.

## Group 3: Shrinker compatibility

### Command

```bash
mvn -q -pl test-shrinker test
```

### Pass criteria

- Shrinker tests pass.
- Field names or documented aliases remain compatible with existing JSON.
- Generic signatures required for `TypeToken` behavior survive shrinking.

### Quality gates

- A serialized fixture class still emits the expected property names after shrinking.
- A deserialization test using historical JSON still maps into the right fields when aliases are configured.
- A raw-`TypeToken` or erased generic signature failure is caught by an explicit error, not a silent wrong-type object graph.

## Group 4: Native-image boundary

### Precondition

`native-image --version` succeeds.

### Command

```bash
mvn -q -pl test-graal-native-image test
```

### Pass criteria

- Native-image compilation succeeds.
- The configured reflective test cases pass in the produced binary.
- Any undeclared reflective path fails in a way that demonstrates missing reachability metadata rather than silently returning partial objects.

### Quality gates

- A declared reflectively-bound fixture type round-trips in the native image.
- A type that depends on runtime reflection without metadata is rejected or documented as unsupported.

## Parallelism plan

After the core `gson` module compiles successfully, the following groups may run concurrently:

```bash
(
  mvn -q -pl gson -Dtest='com.google.gson.quality.FunctionalTest,com.google.gson.functional.MapTest,com.google.gson.functional.SecurityTest' test
) &
(
  mvn -q -pl test-jpms test
) &
wait
```

Run `test-shrinker` and `test-graal-native-image` sequentially afterward because they each consume heavier build-time resources and produce harder-to-diagnose interleaved failures.

## Teardown

Clean up build artifacts when you are done:

```bash
mvn -q clean
```

If a native-image build created extra artifacts outside Maven’s normal cleanup path, remove them with the module’s documented clean target before ending the session.

## Summary table template

| Group | Result | Key signal | Recommendation |
|------|--------|------------|----------------|
| Core contract smoke | PASS / FAIL / SKIP | exact JSON / exception contract | ... |
| JPMS boundary | PASS / FAIL / SKIP | module openness | ... |
| Shrinker compatibility | PASS / FAIL / SKIP | field-name stability | ... |
| Native-image boundary | PASS / FAIL / SKIP | reflection metadata | ... |

If Group 1 fails at compile time, stop and fix the branch before trusting any later result.
