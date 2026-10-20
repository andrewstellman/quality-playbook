---
source: https://github.com/google/gson/issues/676
retrieved: 2026-04-03
type: github_issue
description: RuntimeTypeAdapterFactory overrides explicit control over serializeNulls behavior
---

# Issue #676: RuntimeTypeAdapterFactory overrides explicit control over serializeNulls behavior of contained objects

## Status
**Open** — labeled as bug

## Description

When using `RuntimeTypeAdapterFactory` to handle polymorphic type serialization, any custom `TypeAdapter` that explicitly enables null value serialization via `out.setSerializeNulls(true)` has its settings discarded. This prevents developers from using polymorphic type hierarchies while maintaining fine-grained control over null serialization behavior for specific classes.

The problem manifests when:
1. A custom TypeAdapter for class A explicitly calls `out.setSerializeNulls(true)`
2. Class A is wrapped in a RuntimeTypeAdapterFactory for polymorphic handling
3. Instances of class A are serialized through the factory
4. The null serialization settings from the custom adapter are lost

## Root Cause

The `RuntimeTypeAdapterFactory` implementation uses a temporary `JsonTreeWriter` to capture the serialized element representation of the object. This process:

1. Delegates to the appropriate type adapter for the runtime type
2. The adapter writes to the temporary writer with its own serializeNulls setting
3. The factory then re-serializes the captured JsonElement using the outer writer's configuration
4. This re-serialization ignores the explicit null settings from the original adapter

The two-step serialization process (first to a JsonElement, then from JsonElement to the outer writer) breaks the connection between the adapter's explicit configuration and the final output.

## Impact on Use Cases

This issue prevents developers from distinguishing between:
- **Uninitialized properties** — null because the field was never set
- **Explicitly null-assigned properties** — null because the code set the value to null

This distinction is critical when:
- Building APIs where explicit nulls vs. missing fields have different meanings
- Using polymorphic type hierarchies with different null-handling strategies per type
- Implementing domain models where null has semantic significance

## Example Problem

```java
public class Dog extends Animal {
    @Override
    public void write(JsonWriter out, Dog dog) throws IOException {
        out.setSerializeNulls(true);  // Explicit: serialize nulls for Dog
        out.beginObject();
        out.name("breed").value(dog.breed);  // May be null, but should serialize
        out.endObject();
    }
}

// When serialized through RuntimeTypeAdapterFactory:
RuntimeTypeAdapterFactory<Animal> factory =
    RuntimeTypeAdapterFactory.of(Animal.class)
        .registerSubtype(Dog.class);

// The out.setSerializeNulls(true) in Dog's adapter is lost!
```

## Workarounds

1. **Enable serializeNulls globally** — Use `new GsonBuilder().serializeNulls()` for the entire Gson instance, then selectively disable it for other types. This is inelegant but works.

2. **Avoid RuntimeTypeAdapterFactory** — Use custom JsonSerializer/JsonDeserializer instead of the factory pattern, though this adds complexity.

3. **Pre-process data** — Ensure nulls are never present in the object before serialization, or convert them to sentinel values.

## Related Issues and PRs

**PR #2151** proposes improving settings propagation through the RuntimeTypeAdapterFactory to preserve adapter-specific configurations like serializeNulls.

## Technical Details

The issue exists because `JsonTreeWriter` and `JsonWriter` maintain independent configuration state. When the factory re-serializes a captured JsonElement, it uses only the outer writer's settings, discarding any adapter-specific configuration.

A proper fix would require either:
1. Propagating adapter-level settings through the JsonElement representation
2. Avoiding the intermediate JsonElement and writing directly to the outer writer
3. Creating a decorator writer that preserves settings during delegation

## Severity

This is a significant limitation for libraries and applications that need both polymorphic type handling and fine-grained null serialization control. It forces users to choose between two important features rather than combine them.
