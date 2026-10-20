---
source: https://github.com/google/gson/issues/1005
retrieved: 2026-04-03
type: github_issue
description: Default Value for Missing fields in Json
---

# Issue #1005: Default Value for Missing fields in Json

## Status
**Open** — labeled as enhancement

## Description

When JSON fields are missing during deserialization, Gson sets the corresponding Java field to null (or 0 for primitive types) instead of preserving or respecting the field's default value from the Java class definition. This is problematic for several common patterns where fields should have meaningful defaults rather than null.

Gson's current behavior is to:
1. Check if the JSON contains a field
2. If the field exists, deserialize it via the appropriate TypeAdapter
3. If the field is missing, skip calling the TypeAdapter entirely and leave the field uninitialized
4. The field defaults to null (or 0/false for primitives)

This means that any default value assigned in the Java class is ignored during deserialization.

## Problem Scenarios

### Scenario 1: Collections Should Default to Empty, Not Null
```java
class User {
    List<String> tags = new ArrayList<>();  // Default: empty list
}

// JSON: { "name": "Alice" }  (tags field missing)
// Gson result: tags = null (not the default empty list)
// Expected: tags = new ArrayList<>()
```

### Scenario 2: Optional Fields
```java
class Config {
    Optional<String> setting = Optional.empty();  // Default: empty Optional
}

// JSON: { "enabled": true }  (setting field missing)
// Gson result: setting = null
// Expected: setting = Optional.empty()
```

### Scenario 3: Enumeration with Default
```java
class Request {
    Status status = Status.PENDING;  // Default status
}

// JSON: { "id": 123 }  (status field missing)
// Gson result: status = null
// Expected: status = Status.PENDING
```

## Root Cause

Gson does not call TypeAdapters for missing fields. The reflection-based deserialization code simply skips fields that don't exist in the JSON, leaving them with their field defaults (which become null for object references).

While this might seem reasonable, it prevents developers from implementing custom deserialization logic for missing fields through TypeAdapters.

## Why TypeAdapter Workaround Fails

A developer might attempt to create a custom TypeAdapter for Collections:

```java
new GsonBuilder()
    .registerTypeAdapter(List.class, new TypeAdapter<List>() {
        @Override
        public List read(JsonReader in) throws IOException {
            if (in.peek() == JsonToken.NULL) {
                in.nextNull();
                return new ArrayList<>();  // Convert null to empty list
            }
            // ... handle array ...
        }
    })
    .create()
```

This doesn't work because:
1. Gson never calls the TypeAdapter for missing fields
2. The field is simply left as null by the reflective deserializer
3. The adapter only runs if the JSON explicitly contains the field

## Related Pull Requests

**PR #1006** — Attempts to implement default value handling by detecting and invoking field initializers during deserialization.

**PR #2358** — Proposes configurable strategies for handling unknown and missing fields, including:
- IGNORE (current behavior)
- DEFAULT (use field default)
- FAIL (throw exception)

## Impact on Java Records

The problem is amplified with Java records (Java 16+):

```java
record User(String name, List<String> tags = new ArrayList<>()) {}

// JSON: { "name": "Alice" }
// Gson result: tags = null (record construction fails, fields are immutable)
```

Records cannot be modified after construction, so missing fields cannot be initialized after deserialization. This makes the issue more acute for modern Java code.

## Workarounds

### Workaround 1: Manual Initialization Method
```java
class User {
    String name;
    List<String> tags;

    @PostConstruct  // or call explicitly
    void initialize() {
        if (tags == null) {
            tags = new ArrayList<>();
        }
    }
}
```

### Workaround 2: Getter with Initialization
```java
class User {
    String name;
    private List<String> _tags;

    List<String> getTags() {
        if (_tags == null) {
            _tags = new ArrayList<>();
        }
        return _tags;
    }
}
```

### Workaround 3: Custom Deserializer
```java
new GsonBuilder()
    .registerTypeAdapter(User.class, new JsonDeserializer<User>() {
        public User deserialize(JsonElement json, Type typeOfT,
                JsonDeserializationContext context) {
            User user = context.deserialize(json, User.class);
            if (user.tags == null) {
                user.tags = new ArrayList<>();
            }
            return user;
        }
    })
    .create()
```

This works but requires custom deserializer registration for each affected class.

### Workaround 4: Nullable Wrapper Pattern
Use Optional to explicitly represent missing vs. null:

```java
class User {
    String name;
    Optional<List<String>> tags = Optional.of(new ArrayList<>());
}
```

## Severity and Impact

This limitation significantly impacts:
- Code using Optional (should be Optional.empty(), not null)
- Domain models with collections (should be empty, not null)
- Configuration objects with defaults (null vs. uninitialized state confusion)
- Record classes (immutable, can't fix after construction)

## Potential Solutions

1. **@Default annotation** — Mark fields whose default should be preserved during deserialization
2. **FieldNamingStrategy extension** — Allow custom handling of missing fields
3. **TypeAdapterFactory for missing fields** — Invoke adapters even for missing fields
4. **Record support** — Special handling to respect record default values in constructor
5. **Configuration option** — Add GsonBuilder option like `.preserveFieldDefaults()` to honor Java defaults

## Integration with Other Features

This issue is related to:
- **Issue #948** — TypeAdapters not being called for null values
- **Issue #1558** — Distinguishing optional vs. required/nullable fields
