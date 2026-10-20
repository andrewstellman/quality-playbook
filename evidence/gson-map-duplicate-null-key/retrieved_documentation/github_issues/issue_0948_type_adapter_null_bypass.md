---
source: https://github.com/google/gson/issues/948
retrieved: 2026-04-03
type: github_issue
description: Gson skip call of specified TypeAdapter if value is null
---

# Issue #948: Gson skip call of specified TypeAdapter if value is null

## Status
**Closed** — Completed (intentional behavior, by design)

## Description

When a field value is null, Gson does not invoke the custom TypeAdapter's `read()` or `write()` methods, even when `serializeNulls()` is explicitly enabled. This behavior is documented as intentional and represents a fundamental design decision in Gson.

The issue arises when developers expect custom TypeAdapters to have an opportunity to handle null values — for example, to convert null to a default value or to a sentinel object. However, Gson short-circuits the adapter entirely when it encounters a null value.

## Documented Behavior

Gson's official documentation states: "Null values don't invoke type adapters."

This is a deliberate design choice that prioritizes performance and simplicity. It means:
- Null values are handled separately from the adapter chain
- Adapters cannot intercept null values to provide custom handling
- Even with `serializeNulls()` enabled, null values are still serialized by the core library, not by adapters

## Impact on Use Cases

This prevents developers from implementing certain common patterns:

### Pattern 1: Null-to-Default Conversion
```java
public class IntegerAdapter extends TypeAdapter<Integer> {
    @Override
    public Integer read(JsonReader in) throws IOException {
        if (in.peek() == JsonToken.NULL) {
            in.nextNull();
            return 0;  // Convert null to default
        }
        return in.nextInt();
    }

    @Override
    public void write(JsonWriter out, Integer value) throws IOException {
        if (value == null) {
            out.value(0);  // Serialize null as default
            return;
        }
        out.value(value);
    }
}
```

This pattern doesn't work for serialization because if `value` is null, the write() method is never called.

### Pattern 2: Null-to-Optional Conversion
```java
public class OptionalAdapter extends TypeAdapter<Optional<?>> {
    public void write(JsonWriter out, Optional<?> value) throws IOException {
        // Expect value to be Optional or null
        if (value == null) {
            out.value((String) null);  // Never reached!
        } else if (value.isEmpty()) {
            out.nullValue();
        } else {
            // serialize the wrapped value
        }
    }
}
```

If the Optional field itself is null (field not initialized), the write() method never executes.

## Workarounds

### Workaround 1: Use nullSafe() Wrapper Pattern
```java
new GsonBuilder()
    .registerTypeAdapter(MyType.class,
        new MyTypeAdapter().nullSafe())
    .create()
```

The `nullSafe()` method wraps the adapter to handle null values automatically by writing/reading a JSON null. This works for deserialization but doesn't allow custom null handling.

### Workaround 2: Handle Nulls Outside the Adapter
Move null handling logic to the calling code or to a wrapper class:

```java
class MyValueHolder {
    private MyType value;

    public MyType getValue() {
        return value != null ? value : getDefault();
    }
}
```

### Workaround 3: Use Wrapper Objects
Avoid nullable fields by using wrapper objects that are never null:

```java
class OptionalValue<T> {
    private final T value;
    private final boolean present;

    public OptionalValue(T value) {
        this.value = value;
        this.present = value != null;
    }
}
```

### Workaround 4: Custom TypeAdapterFactory with Reflection
Use a TypeAdapterFactory that inspects the actual object state before deciding to invoke the adapter, though this adds significant complexity.

## Design Rationale

The design decision to skip adapters for null values has several justifications:

1. **Performance** — Null value serialization is a common case; skipping adapter overhead improves throughput
2. **Simplicity** — The core library handles null consistently without adapter involvement
3. **Consistency** — All null values are treated uniformly across the serialization pipeline
4. **Predictability** — Developers know that null means null, not "call my adapter to decide"

## Related Issues

This behavior is intertwined with:
- **Issue #1005** — Default values for missing fields (Gson doesn't call adapters for missing fields either)
- **Issue #676** — RuntimeTypeAdapterFactory null handling
- **Issue #2059** — Anonymous class serialization

## Limitations for Use Cases

This design limitation prevents Gson from being used effectively in scenarios requiring:
- Conversion of null to computed default values
- Type-safe null handling with Optional/wrapper types
- Validation or transformation of null in deserialization
- Explicit control over how nulls are represented in JSON

These use cases are better served by frameworks like Jackson that allow adapters to intercept null values.
