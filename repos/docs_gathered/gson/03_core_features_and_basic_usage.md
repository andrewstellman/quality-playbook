# Gson Core Features and Basic Usage

## Getting Started

### Basic Instantiation

The primary entry point is the `Gson` class:

```java
Gson gson = new Gson();
```

### Dependency Setup

**Maven:**
```xml
<dependency>
    <groupId>com.google.code.gson</groupId>
    <artifactId>gson</artifactId>
    <version>2.13.2</version>
</dependency>
```

**Gradle:**
```gradle
implementation 'com.google.code.gson:gson:2.13.2'
```

## Supported Data Types

Gson handles the following data types out of the box:

- **Primitives:** integers, strings, booleans, floating-point numbers
- **Objects:** Custom classes with default no-args constructors
- **Arrays and Collections:** Lists, sets, and other collection types
- **Maps:** With configurable key handling
- **Generic Types:** Using `TypeToken` for preserving type information
- **Enums:** With optional custom deserialization
- **Nested Objects:** Arbitrary depth
- **Java Records:** (Java 16+, as of Gson 2.10)

## Basic Serialization and Deserialization

### Serialization (Object to JSON)

```java
MyClass obj = new MyClass();
String json = gson.toJson(obj);
```

### Deserialization (JSON to Object)

```java
String json = "{\"name\":\"John\",\"age\":30}";
MyClass obj = gson.fromJson(json, MyClass.class);
```

## Default Behavior

By default, Gson:

- **Excludes transient and static fields** from serialization
- **Ignores null values** during serialization (doesn't include them in JSON)
- **Supports private fields** completely - no getter/setter methods required
- **Handles null automatically** during both serialization and deserialization
- **Generates compact JSON** without whitespace

## Configuration with GsonBuilder

For customization beyond defaults, use `GsonBuilder`:

```java
Gson gson = new GsonBuilder()
    .setPrettyPrinting()
    .serializeNulls()
    .setDateFormat("yyyy-MM-dd")
    .create();
```

## Key Features

### Pretty Printing

```java
Gson gson = new GsonBuilder()
    .setPrettyPrinting()
    .create();
```

Produces human-readable formatted JSON with indentation.

### Null Value Handling

By default, null values are excluded from JSON output. To include them:

```java
new GsonBuilder()
    .serializeNulls()
    .create();
```

### Field Exclusion

Multiple strategies available:
- Exclude by Java modifier (transient, static)
- Use `@Expose` annotation with `excludeFieldsWithoutExposeAnnotation()`
- Implement custom `ExclusionStrategy`

### Circular Reference Handling

**Limitation:** Gson does NOT support circular references. If your object graph contains cycles, serialization will fail. Design your objects to avoid circular dependencies or use custom serializers.

## Performance

Gson demonstrates:
- Deserializes strings exceeding 25MB
- Manages collections of 1.4 million objects
- Minimal memory overhead with streaming APIs
- Thread-safe Gson instances (state-free design)

## Thread Safety

Gson instances are **stateless and thread-safe**. You can safely reuse a single Gson instance across multiple threads without synchronization:

```java
// This is safe
static final Gson gson = new Gson();

// Use gson in multiple threads without worry
gson.toJson(obj);
gson.fromJson(json, MyClass.class);
```

## User Guide Reference

**Official User Guide:** http://google.github.io/gson/UserGuide.html
