# Gson Annotations

## Overview

Gson provides several annotations to control serialization and deserialization behavior without requiring custom adapters for simple cases.

## @SerializedName

Maps a Java field to a different name in the JSON representation.

### Purpose
Control the JSON property name while keeping the Java field name unchanged.

### Usage

```java
class User {
    @SerializedName("full_name")
    String name;

    @SerializedName("user_age")
    int age;
}
```

**Serialization Result:**
```json
{
  "full_name": "John",
  "user_age": 30
}
```

**Deserialization:**
Gson automatically maps the JSON property `full_name` back to the Java field `name`.

### Alternate Names (Gson 2.8.5+)

```java
@SerializedName(value = "primary_name", alternate = {"name", "user_name"})
String fullName;
```

This allows deserialization from any of the specified names, providing backward compatibility during JSON format changes.

## @Expose

Controls whether a field should be included in serialization and deserialization.

### Purpose
Explicitly mark which fields should be serialized/deserialized.

### Usage

```java
class User {
    @Expose
    String name;

    @Expose(serialize = false)
    String password;

    @Expose(deserialize = false)
    String internalId;

    // Not exposed - ignored in serialization/deserialization
    String temporaryData;
}
```

### Attributes

- `serialize`: Include in serialization (default: true)
- `deserialize`: Include in deserialization (default: true)

### Activation

**Important:** @Expose only takes effect with the `excludeFieldsWithoutExposeAnnotation()` builder:

```java
Gson gson = new GsonBuilder()
    .excludeFieldsWithoutExposeAnnotation()
    .create();
```

Without this setting, @Expose is ignored and all non-transient/static fields are serialized by default.

## @SerializedName vs @Expose

**@SerializedName:**
- Changes the JSON property name
- Always active
- Can specify alternate names

**@Expose:**
- Controls inclusion/exclusion
- Only active with `excludeFieldsWithoutExposeAnnotation()`
- Provides fine-grained control over serialize/deserialize independently

### Using Both Together

```java
class User {
    @SerializedName("full_name")
    @Expose(serialize = true, deserialize = false)
    String name;

    @SerializedName("email_address")
    @Expose
    String email;
}
```

## @Since

Marks fields to be serialized/deserialized only in specific Gson versions or later.

### Usage

```java
class User {
    String name;

    @Since(1.0)
    String email;

    @Since(2.0)
    LocalDate createdDate;
}
```

### Activation

```java
Gson gson = new GsonBuilder()
    .setVersion(1.5)
    .create();

// With version 1.5:
// - name: included
// - email: included (since 1.0 <= 1.5)
// - createdDate: excluded (since 2.0 > 1.5)
```

### Use Case

Managing API evolution and backward compatibility when JSON formats change across versions.

## @Until

The complement to @Since - marks fields to be excluded from specified versions onwards.

```java
class User {
    String name;

    @Until(2.0)
    String legacyField;  // Excluded in 2.0 and later
}
```

## @JsonAdapter

Specifies a custom TypeAdapter for a field without requiring Gson builder configuration.

### Usage

```java
class User {
    String name;

    @JsonAdapter(CustomDateAdapter.class)
    LocalDate birthDate;
}
```

### Benefits

- Field-level customization
- No need for GsonBuilder registration
- Cleaner code for isolated custom logic

## Common Patterns

### Field Aliasing for Backward Compatibility

```java
@SerializedName(value = "updated_at", alternate = {"lastModified", "modifiedDate"})
LocalDateTime lastUpdatedAt;
```

### Transient vs @Expose

```java
// Option 1: Use transient (simple)
transient String password;

// Option 2: Use @Expose (more explicit)
@Expose(serialize = false, deserialize = false)
String password;
```

## Reference

- **Official Annotations Documentation:** http://google.github.io/gson/UserGuide.html
- **@SerializedName Alternate Names:** Feature added in Gson 2.8.5+
