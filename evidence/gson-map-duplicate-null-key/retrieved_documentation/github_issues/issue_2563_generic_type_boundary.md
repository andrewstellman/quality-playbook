---
source: https://github.com/google/gson/issues/2563
retrieved: 2026-04-03
type: github_issue
description: Generic deserializer should extract type information from generic boundary
---

# Issue #2563: Generic deserializer should extract type information from generic boundary

## Status
**Open** — requires implementation

## Description

When a field uses a bounded type variable (e.g., `T extends Foo`), Gson ignores the type bound during deserialization and treats the type variable as if it were `Object`. This causes objects to deserialize as `LinkedTreeMap` instead of the bounded type, leading to `ClassCastException` when the deserialized value is accessed or used.

This is a significant limitation for generic code that relies on type bounds to specify valid types. The bound information exists at compile time in the type signature but is lost at runtime by Gson's type resolution logic.

## Problem Demonstration

```java
interface Foo {
    String getValue();
}

class FooImpl implements Foo {
    private String value;

    @Override
    public String getValue() {
        return value;
    }
}

class Container<T extends Foo> {
    T item;
}

// Deserialization scenario
String json = "{\"item\": {\"value\": \"test\"}}";

Gson gson = new Gson();
Container<FooImpl> container = gson.fromJson(json,
    new TypeToken<Container<FooImpl>>() {}.getType());

// Expected: container.item is FooImpl instance
// Actual: container.item is LinkedTreeMap
//         calling container.item.getValue() throws ClassCastException
```

## Root Cause

Gson's type resolution logic in `$Gson$Types.getRawType()` and related methods ignores `TypeVariable` bounds. When encountering a type variable during deserialization, the code:

1. Detects that the type is a `TypeVariable` (e.g., `T extends Foo`)
2. Lacks the context to know what concrete type `T` represents in this instance
3. Falls back to treating it as `Object` type
4. The JSON is then deserialized as a generic `LinkedTreeMap`

The problem is that Java's type erasure removes generic type information at runtime, so `T extends Foo` becomes just `T`, and without special handling, there's no way to recover that it was bounded by `Foo`.

## Why This Matters

For generic code, type bounds are the primary mechanism for expressing constraints:

```java
public <T extends Service> Container<T> deserialize(String json) {
    // The bound "Service" tells Gson what interface T must implement
    // But Gson ignores it and deserializes as LinkedTreeMap
}
```

The bound information exists in the bytecode and is available via reflection (`TypeVariable.getBounds()`), but Gson doesn't use it.

## Comparison with Jackson

Jackson handles this correctly:

```java
// Jackson automatically respects type bounds
ObjectMapper mapper = new ObjectMapper();
Container<FooImpl> container = mapper.readValue(json,
    new TypeReference<Container<FooImpl>>() {});
// container.item IS correctly typed as FooImpl
```

Jackson examines type variable bounds during deserialization and uses them to guide the type selection process.

## Workarounds

### Workaround 1: Explicit Type Specification
Always provide concrete types instead of type variables:

```java
// Instead of:
class Container<T extends Foo> {
    T item;
}

// Use:
class Container {
    FooImpl item;  // Concrete type
}
```

### Workaround 2: @JsonAdapter with Explicit Type
Register a custom TypeAdapter that knows the concrete type:

```java
class ContainerAdapter<T extends Foo> extends TypeAdapter<Container<T>> {
    private Class<T> concreteType;

    public ContainerAdapter(Class<T> concreteType) {
        this.concreteType = concreteType;
    }

    @Override
    public void write(JsonWriter out, Container<T> value) throws IOException {
        out.beginObject();
        out.name("item");
        gson.getAdapter(concreteType).write(out, value.item);
        out.endObject();
    }

    @Override
    public Container<T> read(JsonReader in) throws IOException {
        Container<T> container = new Container<>();
        in.beginObject();
        while (in.hasNext()) {
            if (in.nextName().equals("item")) {
                container.item = gson.getAdapter(concreteType).read(in);
            }
        }
        in.endObject();
        return container;
    }
}
```

However, this workaround is cumbersome because:
1. The @JsonAdapter annotation doesn't have access to the concrete type
2. The adapter must be registered for each concrete instantiation
3. It doesn't work well for nested generics like `List<T>` or `Map<String, T>`

### Workaround 3: Custom Deserializer with Type Information
Register a deserializer that manually reconstructs the bounded type:

```java
new GsonBuilder()
    .registerTypeAdapter(FooImpl.class, (json, typeOfT, context) -> {
        JsonObject obj = json.getAsJsonObject();
        FooImpl impl = new FooImpl();
        impl.value = obj.get("value").getAsString();
        return impl;
    })
    .create()
```

This requires registering adapters for each concrete type separately.

### Workaround 4: Two-Step Deserialization
First deserialize to a map, then manually convert:

```java
Container<FooImpl> container = new Container<>();
LinkedTreeMap rawItem = gson.fromJson(json, LinkedTreeMap.class);
container.item = gson.fromJson(
    gson.toJson(rawItem),  // Re-serialize to force correct type
    FooImpl.class
);
```

This is inefficient but works around the type resolution issue.

## Technical Details

The issue occurs because:

1. Java type erasure removes generic information at runtime
2. Gson relies on the `Type` object passed to deserialize() for type information
3. When a field is `T extends Foo`, the Type object is `TypeVariable("T", bounds=[Foo])`
4. Gson's `$Gson$Types.getRawType(TypeVariable)` returns `Object.class`, ignoring bounds
5. The deserializer then uses `Object.class` as the target type, resulting in LinkedTreeMap

A fix would require:

```java
public static Class<?> getRawType(TypeVariable<?> typeVar) {
    Type[] bounds = typeVar.getBounds();
    if (bounds.length > 0) {
        // Use the first bound (primary constraint)
        return getRawType(bounds[0]);
    }
    return Object.class;  // No bound, truly Object
}
```

## Related Issues and PRs

- **PR #2571** — Related discussion about generic type handling
- **PR #2573** — Additional type variable handling improvements

## Impact on Use Cases

This limitation affects:
- Generic data access objects (DAOs)
- Generic service implementations
- Generic container/wrapper classes
- Type-safe collections using generics
- Framework code with generic parameters

## Potential Solutions

1. **Respect TypeVariable bounds** — Modify getRawType() to extract and use bounds
2. **Bound-aware deserialization** — Create specialized deserialization path for bounded types
3. **Generic type hints** — Allow developers to provide type hints for bounded variables
4. **Configuration option** — Add GsonBuilder option like `.respectGenericBounds(true)`

## Version Information

- Status: Open (as of Gson 2.11+)
- Severity: High (breaks generic code patterns)
- Workaround availability: Yes, but cumbersome
