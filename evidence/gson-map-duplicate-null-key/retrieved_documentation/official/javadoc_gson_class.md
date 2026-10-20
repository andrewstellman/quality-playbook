---
source: https://github.com/google/gson/blob/main/gson/src/main/java/com/google/gson/Gson.java (class-level Javadoc)
retrieved: 2026-04-03
type: official
description: Gson class Javadoc — thread safety, usage patterns, JSON strictness handling, default behavior
---

# Gson Class Javadoc

The main class for using Gson. Typically used by constructing a Gson instance and then invoking `toJson(Object)` or `fromJson(String, Class)` methods.

## Basic Usage

```java
Gson gson = new Gson();
String json = gson.toJson(myObj);
MyType obj = gson.fromJson(json, MyType.class);
```

## Thread Safety

**Gson instances are Thread-safe so you can reuse them freely across multiple threads.**

The Gson instance does not maintain any state while invoking JSON operations. This makes it safe to:
- Share a single Gson instance across your application
- Invoke methods from multiple threads simultaneously
- Reuse the same Gson instance for all serialization and deserialization operations

## Parameterized Types

For generic types like `List<MyType>`, deserialization requires explicit type specification via `Type` or `TypeToken` parameters. Serialization can optionally include type info.

### Deserialization with TypeToken

```java
Type listType = new TypeToken<List<MyType>>(){}.getType();
List<MyType> list = gson.fromJson(json, listType);
```

### Deserialization with TypeToken Direct Parameter (Gson 2.10+)

```java
List<MyType> list = gson.fromJson(json, new TypeToken<List<MyType>>(){});
```

## Default Configuration (new Gson())

When you create a Gson instance with `new Gson()` (no builder), these defaults apply:

### Field Serialization
- Does NOT serialize null fields — null-valued fields are omitted from JSON output
- Escapes HTML characters in strings (`<`, `>`, `&`, `=`, `'`)
- Uses identity field naming — Java field name directly becomes JSON key name
- Serializes enums by name (not by ordinal)
- Excludes `transient` fields from serialization
- Excludes `static` fields from serialization

### Date Handling
- Uses default date format: "Dec 1, 2005 3:45:22 PM"
- Applied to `java.util.Date` objects

## JSON Strictness Handling (Gson 2.11+)

"For legacy reasons most of the Gson methods allow JSON data which does not comply with the JSON specification when no explicit Strictness is set (the default)."

### Strictness Enum

Three levels of JSON compliance validation:

- **LENIENT** — Most permissive; accepts non-compliant JSON (comments, unquoted keys, trailing commas, etc.)
- **DEFAULT** — Moderate strictness; the default when not specified explicitly
- **STRICT** — Enforces full RFC 8259 compliance; rejects any non-conforming JSON

### Usage (Gson 2.11+)

```java
Gson gson = new GsonBuilder()
    .setObjectToNumberStrategy(ToNumberPolicy.LONG_OR_DOUBLE)
    .create();

gson.fromJson(json, MyType.class, Strictness.STRICT);
```

## Thread Safety Guarantee

As long as you use Gson correctly (don't modify the instance or its configuration after construction), the thread-safety guarantee applies:
- No synchronization overhead
- No locks needed
- Safe to use in concurrent applications
- Safe to use in multi-threaded servers

## Null Handling

By default, `null` fields are not serialized:

```java
class Person {
    String name;
    String email;  // null
}

Person p = new Person();
p.name = "Alice";
p.email = null;

Gson gson = new Gson();
String json = gson.toJson(p);
// Result: {"name":"Alice"}  — email field omitted
```

To serialize nulls:

```java
Gson gson = new GsonBuilder()
    .serializeNulls()
    .create();
// Now null fields will be included as "fieldName":null
```

## Summary

The Gson class provides simple, thread-safe JSON serialization and deserialization. Use `new Gson()` for basic needs with sensible defaults, or `GsonBuilder` for customization. For generic types, use `TypeToken` to specify the full type information required for proper deserialization.
