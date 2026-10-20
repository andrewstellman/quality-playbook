---
source: https://github.com/google/gson/issues/2032
retrieved: 2026-04-03
type: github_issue
description: Registering a deserializer changes behavior of serialization
---

# Issue #2032: Registering a deserializer changes behavior of serialization

## Status
**Closed** — Fixed in Gson 2.10 via PR #1787

## Description

A critical bug existed where registering a custom `JsonDeserializer` for a parent class unexpectedly changed the serialization behavior of subclasses. When serializing a subclass that extends the parent class, all subclass-specific fields would be silently dropped from the output, leaving only the parent class fields.

This was a serious regression because:
1. Developers expected deserialization configuration to be independent of serialization
2. Fields were silently discarded rather than throwing an error
3. The problem only manifested in production code with complex inheritance hierarchies
4. No error message indicated what went wrong

## Demonstration of the Bug

```java
abstract class Animal {
    String species;
}

class Dog extends Animal {
    String breed;          // Dog-specific field
    int age;              // Dog-specific field
}

// Without custom deserializer:
Dog dog = new Dog();
dog.species = "Canis familiaris";
dog.breed = "Labrador";
dog.age = 5;

Gson gson = new Gson();
String json = gson.toJson(dog);
// Output: {"species":"Canis familiaris","breed":"Labrador","age":5}  ✓ CORRECT

// With custom deserializer registered:
Gson gson2 = new GsonBuilder()
    .registerJsonDeserializer(Animal.class, (json, typeOfT, context) -> {
        // Custom deserialization logic for Animal...
    })
    .create();

String json2 = gson2.toJson(dog);
// Output: {"species":"Canis familiaris"}  ✗ WRONG
// breed and age fields are GONE!
```

## Root Cause

The bug was introduced due to how Gson handles type adapters for inheritance hierarchies. When a custom deserializer is registered for a parent class:

1. Gson creates a `TreeTypeAdapter` to wrap the custom deserializer
2. The type adapter registry is updated to use this wrapper for the parent type
3. During serialization of a subclass, Gson's runtime type checking code (`TypeAdapterRuntimeTypeWrapper`) needed to detect whether an adapter was a "reflective" adapter (safe to reuse for subclasses) or a custom adapter (not safe)
4. The detection logic failed to recognize the wrapped `TreeTypeAdapter` as a custom adapter
5. Instead, Gson incorrectly used the parent class's adapter for the subclass
6. Since the adapter only knew about parent class fields, subclass fields were not serialized

The problem was that `TypeAdapterRuntimeTypeWrapper` could not identify `TreeTypeAdapter` instances created from custom deserializers. It treated them as standard reflective adapters rather than recognizing them as custom, type-specific adapters.

## Solution

PR #1787 fixed the issue by improving the detection logic in `TypeAdapterRuntimeTypeWrapper` to:

1. Correctly identify `TreeTypeAdapter` instances that wrap custom deserializers
2. Avoid reusing custom adapters for subclasses
3. Fall back to reflective serialization for subclasses that don't have explicit custom deserializers
4. Ensure that parent class custom deserializers don't affect subclass serialization

The fix was released in Gson 2.10.

## Workaround (Before Fix)

Before Gson 2.10, developers encountering this issue had to use `TypeAdapterFactory` instead of `JsonDeserializer`:

```java
new GsonBuilder()
    .registerTypeAdapterFactory(new TypeAdapterFactory() {
        @Override
        public <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type) {
            if (!Animal.class.isAssignableFrom(type.getRawType())) {
                return null;  // Not applicable
            }

            return new TypeAdapter<T>() {
                @Override
                public T read(JsonReader in) throws IOException {
                    // Custom deserialization for Animal and subclasses
                    // ...
                }

                @Override
                public void write(JsonWriter out, T value) throws IOException {
                    // Custom serialization if needed
                    // ...
                }
            };
        }
    })
    .create()
```

The `TypeAdapterFactory` approach doesn't have the same detection issue because it's designed to handle both serialization and deserialization in a coordinated way.

## Why This Was Subtle

The bug was difficult to detect because:
1. The problem only occurred with custom deserializers on parent classes
2. It only manifested when serializing subclass instances
3. Fields were silently omitted rather than causing an exception
4. The behavior was consistent and reproducible, making it appear intentional rather than buggy
5. Integration tests often don't test this specific inheritance + custom deserializer pattern

## Impact on Inheritance Hierarchies

This bug had serious implications for systems using:
- Polymorphic type hierarchies (which commonly have custom deserializers for the parent)
- Abstract base classes with concrete subclasses
- Type adapters for factory patterns or type routing

## Version Affected

- Affected versions: Before Gson 2.10
- Fixed in: Gson 2.10 (September 2020)

## Testing

The fix was validated by ensuring that:
1. Custom deserializers for parent classes no longer affect subclass serialization
2. Subclass fields are fully serialized regardless of custom parent deserializers
3. Custom serializers (if registered) are still respected
4. The fix doesn't break legitimate use cases of custom deserializers

## Related Issues

This issue exposed deeper problems with type adapter detection that were also addressed in the same PR, improving the overall robustness of Gson's inheritance handling.
