---
source: https://github.com/google/gson/blob/main/gson/src/main/java/com/google/gson/TypeAdapter.java (class-level Javadoc)
retrieved: 2026-04-03
type: official
description: TypeAdapter class Javadoc — read/write protocol, null handling contract, thread safety expectations
---

# TypeAdapter<T> Class Javadoc

Converts Java objects to and from JSON. Extend this class to create custom adapters with fine-grained control over the serialization and deserialization process.

## Core Responsibility

A `TypeAdapter<T>` handles the complete conversion between a Java object of type T and JSON representation. Unlike `JsonSerializer` and `JsonDeserializer` which work with `JsonElement` trees, `TypeAdapter` works directly with `JsonReader` and `JsonWriter` streams.

## Read/Write Protocol Contract

The adapter must "read exactly one value" and "write exactly one value." This strict contract ensures proper stream positioning and prevents data corruption.

### Primitives

For primitive values, the adapter must call exactly one of:
- `nextBoolean()` for boolean values
- `nextDouble()` for double values
- `nextInt()` for integer values
- `nextLong()` for long values
- `nextString()` for string values
- `nextNull()` for null values

### Writers

For writing, call exactly one of:
- `value()` to write a non-null value
- `nullValue()` to write null

### Arrays

Reading and writing arrays requires:
- `beginArray()` to open the array
- Multiple calls to read/write elements
- `endArray()` to close the array

```java
@Override
public void write(JsonWriter out, int[] values) throws IOException {
    out.beginArray();
    for (int value : values) {
        out.value(value);
    }
    out.endArray();
}

@Override
public int[] read(JsonReader in) throws IOException {
    List<Integer> list = new ArrayList<>();
    in.beginArray();
    while (in.hasNext()) {
        list.add(in.nextInt());
    }
    in.endArray();
    int[] array = new int[list.size()];
    // convert list to array
    return array;
}
```

### Objects

Reading and writing objects requires:
- `beginObject()` to open the object
- Alternating calls to `nextName()` (to get field names) and read/write methods
- `endObject()` to close the object

```java
@Override
public void write(JsonWriter out, Person person) throws IOException {
    out.beginObject();
    out.name("name").value(person.name);
    out.name("age").value(person.age);
    out.endObject();
}

@Override
public Person read(JsonReader in) throws IOException {
    Person person = new Person();
    in.beginObject();
    while (in.hasNext()) {
        String fieldName = in.nextName();
        if (fieldName.equals("name")) {
            person.name = in.nextString();
        } else if (fieldName.equals("age")) {
            person.age = in.nextInt();
        } else {
            in.skipValue();
        }
    }
    in.endObject();
    return person;
}
```

## Null Handling Contract

Type adapters must "be prepared to read null from the stream and write it to the stream." Handle null values explicitly in your read/write methods:

### Reading Nulls

Always check for null before reading:

```java
@Override
public MyType read(JsonReader in) throws IOException {
    if (in.peek() == JsonToken.NULL) {
        in.nextNull();
        return null;  // or some default value
    }
    // proceed with normal reading
}
```

### Writing Nulls

The adapter must handle null objects:

```java
@Override
public void write(JsonWriter out, MyType value) throws IOException {
    if (value == null) {
        out.nullValue();
        return;
    }
    // proceed with normal writing
}
```

### serializeNulls() Configuration

If `GsonBuilder.serializeNulls()` is configured, nulls are written to the output stream; otherwise they are omitted automatically. Either way, the adapter must handle null values properly — never assume non-null inputs.

## Null Safety Wrapper

If null handling is inconvenient, use the `nullSafe()` method to automatically wrap your adapter:

```java
public TypeAdapter<MyType> create(Gson gson, TypeToken<MyType> type) {
    TypeAdapter<MyType> delegateAdapter = // ... your adapter ...
    return delegateAdapter.nullSafe();  // wraps null handling
}
```

The `nullSafe()` wrapper automatically handles nulls and prevents the adapter's read/write methods from ever seeing null values.

## Thread Safety

**Type adapters should be stateless and thread-safe, otherwise the thread-safety guarantees of Gson might not apply.**

Guidelines:

- **Avoid mutable fields** — Store no state in instance variables
- **Avoid synchronized blocks** — Let Gson handle thread safety
- **Treat all state as read-only** — Access only immutable configuration
- **Reuse across threads** — Gson registers your adapter once and reuses it

Violating these guidelines may cause data corruption or unexpected behavior in multi-threaded environments.

### Example of Thread-Safe Adapter

```java
public class MyTypeAdapter extends TypeAdapter<MyType> {
    // Correct: only non-mutable state
    private final DateFormat dateFormat;  // immutable

    public MyTypeAdapter(DateFormat dateFormat) {
        this.dateFormat = dateFormat;
    }

    @Override
    public void write(JsonWriter out, MyType value) throws IOException {
        // safe to use across threads
        out.value(dateFormat.format(value.date));
    }

    @Override
    public MyType read(JsonReader in) throws IOException {
        // safe to use across threads
        return new MyType(dateFormat.parse(in.nextString()));
    }
}
```

### Example of Non-Thread-Safe Adapter (AVOID)

```java
// WRONG - not thread-safe
public class BadTypeAdapter extends TypeAdapter<MyType> {
    private StringBuilder buffer;  // MUTABLE - shared state!

    @Override
    public void write(JsonWriter out, MyType value) throws IOException {
        buffer = new StringBuilder();  // RACE CONDITION
        buffer.append(value.toString());
        out.value(buffer.toString());
    }
}
```

## Implementation Pattern

1. Extend `TypeAdapter<T>`
2. Implement `write(JsonWriter out, T value)` for serialization
3. Implement `read(JsonReader in)` for deserialization
4. Follow the read/write protocol strictly (exactly one value)
5. Handle nulls explicitly or use `nullSafe()` wrapper
6. Keep the adapter stateless and thread-safe
7. Register with GsonBuilder: `registerTypeAdapter(type, adapter)`

## Summary

`TypeAdapter` provides low-level control over JSON serialization and deserialization by working directly with streaming APIs. While more complex than `JsonSerializer` and `JsonDeserializer`, it offers better performance and more control. Always follow the protocol contract (exactly one value), handle nulls properly, and ensure thread safety by avoiding mutable state.
