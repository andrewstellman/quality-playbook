# Gson Field Naming Strategies

## Overview

Field naming strategies control how Java field names are transformed into JSON property names during serialization and deserialization. They solve the common problem of naming convention mismatches between Java (camelCase) and JSON APIs (snake_case, kebab-case, etc.).

## Built-in FieldNamingPolicy

Gson provides the `FieldNamingPolicy` enum with predefined conventions:

### IDENTITY (Default)

Java field names are used as-is in JSON. No transformation applied.

```java
class User {
    String firstName;  // JSON: "firstName"
    String lastName;   // JSON: "lastName"
}
```

### UPPER_CAMEL_CASE

First letter of the Java field name is capitalized.

```java
class User {
    String firstName;  // JSON: "FirstName"
    String lastName;   // JSON: "LastName"
}
```

Usage:
```java
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.UPPER_CAMEL_CASE)
    .create();
```

### LOWER_CASE_WITH_UNDERSCORES

Converts camelCase to snake_case.

```java
class User {
    String firstName;        // JSON: "first_name"
    String lastName;         // JSON: "last_name"
    String emailAddress;     // JSON: "email_address"
}
```

Usage:
```java
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
    .create();
```

### LOWER_CASE_WITH_DASHES

Converts camelCase to kebab-case.

```java
class User {
    String firstName;        // JSON: "first-name"
    String lastName;         // JSON: "last-name"
    String emailAddress;     // JSON: "email-address"
}
```

Usage:
```java
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_DASHES)
    .create();
```

### UPPER_CAMEL_CASE_WITH_SPACES

Capitalizes first letter and separates words with spaces.

```java
class User {
    String firstName;        // JSON: "First Name"
    String lastName;         // JSON: "Last Name"
    String emailAddress;     // JSON: "Email Address"
}
```

Usage:
```java
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.UPPER_CAMEL_CASE_WITH_SPACES)
    .create();
```

## Custom FieldNamingStrategy

For specialized naming conventions, implement `FieldNamingStrategy`:

```java
public interface FieldNamingStrategy {
    String translateName(Field f);
}
```

### Example: Custom Convention

```java
class CustomNamingStrategy implements FieldNamingStrategy {
    @Override
    public String translateName(Field field) {
        String name = field.getName();

        // Prefix private fields with underscore
        if (field.getModifiers() == Modifier.PRIVATE) {
            return "_" + name;
        }

        // Convert firstName to first_name
        return name.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase();
    }
}
```

### Registration

```java
Gson gson = new GsonBuilder()
    .setFieldNamingStrategy(new CustomNamingStrategy())
    .create();
```

## Common Use Cases

### 1. REST API Integration

API returns snake_case but Java code uses camelCase:

```java
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
    .create();

// JSON: {"user_id": 123, "first_name": "John"}
// Java: userId, firstName
```

### 2. Legacy System Integration

Supporting outdated naming conventions:

```java
class LegacyNamingStrategy implements FieldNamingStrategy {
    @Override
    public String translateName(Field field) {
        // All caps with underscores, like: FIELD_NAME
        return field.getName().toUpperCase()
            .replaceAll("([a-z])([A-Z])", "$1_$2");
    }
}
```

### 3. Conditional Naming

Different naming based on field properties:

```java
class ConditionalNamingStrategy implements FieldNamingStrategy {
    @Override
    public String translateName(Field field) {
        // Special handling for ID fields
        if (field.getName().endsWith("Id")) {
            return field.getName() + "_key";
        }

        // Standard snake_case for others
        return toSnakeCase(field.getName());
    }

    private String toSnakeCase(String str) {
        return str.replaceAll("([a-z])([A-Z])", "$1_$2")
                  .toLowerCase();
    }
}
```

## Interaction with @SerializedName

**Important:** @SerializedName always takes precedence over field naming policies.

```java
class User {
    @SerializedName("full_name")
    String firstName;  // JSON: "full_name" (uses annotation, ignores strategy)

    String lastName;   // JSON: "last_name" (uses strategy)
}

Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
    .create();
```

## Best Practices

### 1. Use Built-in Policies When Possible

They're optimized and well-tested:

```java
// Good - simple and clear
Gson gson = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
    .create();
```

### 2. Avoid Ambiguity

Ensure transformed names don't create collisions:

```java
// Avoid this in custom strategies
class Bad {
    String firstName;   // Could become "first_name"
    String first_name;  // Could also become "first_name" - collision!
}
```

### 3. Document Naming Convention

```java
/**
 * Returns a Gson instance configured for REST API serialization.
 * Field names are converted from camelCase (Java) to snake_case (API).
 */
public static Gson createRestGson() {
    return new GsonBuilder()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create();
}
```

### 4. Cache Gson Instances

Avoid recreating with the same strategy:

```java
private static final Gson REST_GSON = new GsonBuilder()
    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
    .create();
```

## Performance Notes

- Built-in policies are cached and optimized
- Custom strategies are called per-field during serialization/deserialization
- For high-performance scenarios with custom strategies, consider caching strategy results

## Reference

- **FieldNamingPolicy Javadoc:** https://javadoc.io/static/com.google.code.gson/gson/latest/com.google.gson/com/google/gson/FieldNamingPolicy.html
- **FutureStudio Naming Policies:** https://futurestud.io/tutorials/gson-builder-basics-naming-policies
