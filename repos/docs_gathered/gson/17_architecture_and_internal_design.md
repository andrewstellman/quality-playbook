# Gson Architecture and Internal Design

## Overall Architecture

Gson's architecture is designed around these core principles:

1. **Streaming-first design** - Processes JSON tokens sequentially
2. **Type-driven deserialization** - Navigates target type tree, not JSON tree
3. **Pluggable adaptation** - Custom serializers/deserializers extend functionality
4. **Stateless instances** - No per-use state, safe for concurrent access

## Core Components

### 1. Entry Points

**Gson Class:**
- Public API for serialization/deserialization
- Delegates to type adapters
- Caches type adapters for performance
- Stateless, reusable across threads

```
User Code
    ↓
Gson (facade)
    ↓
TypeAdapter Registry
    ↓
JsonReader/JsonWriter or TypeAdapters
```

**GsonBuilder Class:**
- Fluent configuration API
- Constructs customized Gson instances
- Manages adapter registration
- Allows fine-grained control

### 2. Type System

**TypeToken<T>:**
- Preserves generic type information at runtime
- Works around Java type erasure
- Captures type at compile time, uses it at runtime
- Essential for generic type support

**Gson Type Hierarchy:**
```
Type (Java reflection type)
├── Class (concrete class)
├── ParameterizedType (List<String>)
├── GenericArrayType (String[])
├── TypeVariable (T in generics)
└── WildcardType (List<? extends Number>)
```

### 3. Serialization/Deserialization Chain

```
User Object
    ↓
TypeAdapterFactory.create()
    ↓
TypeAdapter.write() / TypeAdapter.read()
    ↓
JsonWriter / JsonReader
    ↓
JSON String / Java Object
```

## Type Adapter System

### TypeAdapter<T> Base Class

All custom type handling extends TypeAdapter:

```
TypeAdapter<T>
├── write(JsonWriter, T) - Serialization
├── read(JsonReader) - Deserialization
└── toJson() / fromJson() - Convenience methods
```

### TypeAdapterFactory

Factory pattern for creating type adapters:

```java
public interface TypeAdapterFactory {
    <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type);
}
```

**Responsibilities:**
- Determines if factory can handle a type
- Creates appropriate TypeAdapter instance
- Caches adapters for performance

### Built-in Type Adapters

Gson includes adapters for:
- Primitives (int, long, double, boolean, etc.)
- Collections (List, Set, Map, Queue, etc.)
- Objects (automatic field-based)
- Enums (by name or custom)
- Dates and times
- Special values (null, JsonElement, etc.)

## Streaming Layer

### JsonReader

**Token-based pull parser:**
```
Input Stream
    ↓
Tokenizer (identifies JSON tokens)
    ↓
JsonReader (exposes tokens)
    ↓
Client Code
```

**Token Types:**
- BEGIN_OBJECT, END_OBJECT
- BEGIN_ARRAY, END_ARRAY
- NAME (object key)
- STRING, NUMBER, BOOLEAN, NULL
- END_DOCUMENT

**Push vs Pull:**
- Gson uses pull parsing (client controls reading)
- Simpler to implement custom logic
- More memory efficient

### JsonWriter

**Token-based writer:**
```
Output Stream
    ↓
JsonWriter (accepts values)
    ↓
Serializer (converts to JSON tokens)
    ↓
JSON String
```

**Output Modes:**
- Compact (no whitespace)
- Pretty-printed (with indentation)

## Reflection and Field Access

### FieldNamingStrategy

Controls Java→JSON field name mapping:

```
Java Field Name
    ↓
Strategy.translateName()
    ↓
JSON Property Name
```

Built-in strategies:
- IDENTITY - No change
- LOWER_CASE_WITH_UNDERSCORES - CamelCase to snake_case
- UPPER_CAMEL_CASE - capitalize first letter
- LOWER_CASE_WITH_DASHES - CamelCase to kebab-case

### Exclusion Strategy

Determines which fields to include:

```
All Fields
    ↓
ExclusionStrategy.shouldSkipField()
    ↓
Included Fields
    ↓
Serialized JSON
```

Filters based on:
- Modifiers (transient, static)
- Annotations (@Expose)
- Custom criteria

## Object Instantiation

### Default Constructor Path

```
Class.class
    ↓
Constructor.newInstance()
    ↓
Object Instance
```

Required: No-arg (default) constructor

### Unsafe Instantiation

```
Class.class
    ↓
Unsafe.allocateInstance() (bypasses constructor)
    ↓
Object Instance
    ↓
Fields Set Via Reflection
```

Benefits:
- No default constructor needed
- Faster than reflection
- Fields can be final

Trade-off:
- Default field values ignored
- No constructor initialization logic

### InstanceCreator Path

```
Class.class
    ↓
InstanceCreator.createInstance()
    ↓
Object Instance (potentially initialized)
    ↓
Fields Set Via Reflection
```

Use when:
- No default constructor exists
- Custom initialization needed
- Want to preserve default values

## Generic Type Handling

### Type Erasure Problem

```java
// At runtime, type information is lost
List<String> strings = ...;
List<Integer> integers = ...;

// Both look identical: class java.util.ArrayList
```

### Gson's Solution

**TypeToken captures generics:**
```
TypeToken<List<String>>() {}
    ↓
Superclass reference contains generic info
    ↓
Reflection extracts Type
    ↓
TypeAdapter knows concrete types
```

### Generic Resolution

```
TypeToken<List<Person>>
    ↓
ParameterizedType(List.class, Person.class)
    ↓
ListTypeAdapter(Person.class)
    ↓
Can deserialize List<Person> correctly
```

## Performance Optimizations

### Type Adapter Caching

```
First Request:
gson.fromJson(json, User.class)
    ↓
Create TypeAdapter<User>
    ↓
Cache Adapter
    ↓
Deserialize

Subsequent Requests:
gson.fromJson(json, User.class)
    ↓
Retrieve Cached Adapter
    ↓
Deserialize (no creation overhead)
```

**Impact:** Repeated serialization of same type is fast

### Reflection Caching

```
First Field Access:
User.class → reflect on fields
    ↓
Cache field metadata
    ↓
Set field value

Subsequent Field Access:
Use Cached Metadata
```

### Stream Pooling

Some implementations reuse:
- StringWriter/StringReader
- Byte buffers
- But core Gson doesn't explicitly pool

## Circular Reference Handling

**Current Design:** Not supported

**Reason:**
- Simplifies implementation
- Matches most JSON API usage
- Explicitly forbids cycles

**Workaround:**
```
Circular Object Graph
    ↓
Custom Serializer
    ↓
Replace Child Reference with ID/URL
    ↓
Acyclic JSON
```

## Error Handling Strategy

### Exception Hierarchy

```
IOException
    ↓
JsonIOException

Exception (checked)
    ↓
JsonSyntaxException (unchecked)

RuntimeException (base)
    ↓
JsonSyntaxException, IllegalStateException, etc.
```

### Failure Modes

**Serialization Failures:**
- Generally fail fast with descriptive errors
- Use unchecked exceptions
- Clients typically cannot recover

**Deserialization Failures:**
- Type mismatches caught immediately
- Missing required fields reported
- Extra fields ignored (lenient by default)

## Extensibility Design

### Plugin Points

1. **Custom TypeAdapter** - Full control over read/write
2. **JsonSerializer/JsonDeserializer** - Simplified interfaces
3. **TypeAdapterFactory** - Conditional adapter creation
4. **InstanceCreator** - Custom object instantiation
5. **ExclusionStrategy** - Selective field inclusion
6. **FieldNamingStrategy** - Custom field name mapping

### Design Philosophy

- Use composition over inheritance
- Final classes prevent fragile extension
- Explicit registration of custom logic
- No automatic discovery of plugins

## Thread Safety

### Stateless Design

```
Request 1: gson.toJson(obj1)
Request 2: gson.toJson(obj2)  // Can run concurrently
Request 3: gson.toJson(obj3)  // No shared state conflicts
```

**Why Safe:**
- No instance variables storing state
- Type adapters don't mutate
- Cached adapters are immutable
- Reflection results are thread-safe

### Implications

- Single static Gson instance safe for all threads
- No synchronization overhead
- High concurrency without locks

## Module System (Java 9+)

### JPMS Module

```
module com.google.gson {
    exports com.google.gson;
    exports com.google.gson.reflect;
    exports com.google.gson.stream;
}
```

**Exported Packages:**
- com.google.gson - Main API
- com.google.gson.reflect - TypeToken
- com.google.gson.stream - JsonReader, JsonWriter

**Internal Packages (not exported):**
- com.google.gson.internal - Implementation details

## Reference

- **Design Document:** https://github.com/google/gson/blob/main/GsonDesignDocument.md
- **Source Code:** https://github.com/google/gson/tree/main/gson/src/main/java/com/google/gson
