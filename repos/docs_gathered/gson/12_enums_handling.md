# Gson Enums Handling

## Overview

Gson provides multiple ways to handle Java enums, from default behavior to custom serialization/deserialization strategies.

## Default Enum Handling

### Default Serialization

By default, Gson serializes enums using their constant names:

```java
enum Color {
    RED, GREEN, BLUE
}

Color color = Color.RED;
String json = gson.toJson(color);
// Output: "RED"
```

### Default Deserialization

```java
String json = "\"BLUE\"";
Color color = gson.fromJson(json, Color.class);
// Result: Color.BLUE
```

**Important:** The JSON value is case-sensitive and must match the enum constant name exactly.

## @SerializedName for Custom Values

Use `@SerializedName` to map enums to different JSON values:

```java
enum Day {
    @SerializedName("Mon")
    MONDAY,

    @SerializedName("Tue")
    TUESDAY,

    @SerializedName("Wed")
    WEDNESDAY,

    @SerializedName("LazyDay1")
    SATURDAY,

    @SerializedName("LazyDay2")
    SUNDAY
}

Gson gson = new Gson();

// Serialization
String json = gson.toJson(Day.MONDAY);
// Output: "Mon"

// Deserialization
Day day = gson.fromJson("\"Wed\"", Day.class);
// Result: Day.WEDNESDAY
```

### Alternate Names

Support multiple JSON values mapping to the same enum (Gson 2.8.5+):

```java
enum Status {
    @SerializedName(value = "active", alternate = {"enabled", "on"})
    ACTIVE,

    @SerializedName(value = "inactive", alternate = {"disabled", "off"})
    INACTIVE
}

Gson gson = new Gson();

// All these deserialize to Status.ACTIVE
Status s1 = gson.fromJson("\"active\"", Status.class);
Status s2 = gson.fromJson("\"enabled\"", Status.class);
Status s3 = gson.fromJson("\"on\"", Status.class);

// Serialization always uses the primary value
String json = gson.toJson(Status.ACTIVE);
// Output: "active"
```

## Ordinal Value Mapping

Gson can serialize/deserialize enums by their ordinal (index) values:

### Serialization by Ordinal

```java
enum Priority {
    LOW,      // ordinal 0
    MEDIUM,   // ordinal 1
    HIGH      // ordinal 2
}

Gson gson = new Gson();
String json = gson.toJson(Priority.HIGH);
// Output: 2 (ordinal value)
```

### Deserialization by Ordinal

```java
Priority priority = gson.fromJson("1", Priority.class);
// Result: Priority.MEDIUM (ordinal 1)
```

**Use Case:** Compact JSON representation or legacy APIs

## Case-Insensitive Deserialization

Default Gson is case-sensitive. For case-insensitive handling, create a custom deserializer:

```java
class CaseInsensitiveEnumDeserializer<T extends Enum<T>>
    implements JsonDeserializer<T> {

    @Override
    public T deserialize(JsonElement json, Type typeOfT,
                         JsonDeserializationContext context)
        throws JsonSyntaxException {
        String value = json.getAsString().toUpperCase();

        @SuppressWarnings("unchecked")
        Class<T> enumClass = (Class<T>) typeOfT;

        for (T enumConstant : enumClass.getEnumConstants()) {
            if (enumConstant.name().equals(value)) {
                return enumConstant;
            }
        }

        throw new JsonSyntaxException("Unknown enum value: " +
            json.getAsString());
    }
}

// Registration
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Color.class,
        new CaseInsensitiveEnumDeserializer<>())
    .create();

// Now accepts lowercase values
Color color = gson.fromJson("\"red\"", Color.class);
// Result: Color.RED
```

## Enums with Methods

Custom enum methods are supported without special handling:

```java
enum Status {
    PENDING("pending", "Waiting for approval"),
    APPROVED("approved", "Ready to proceed"),
    REJECTED("rejected", "Needs revision");

    private final String code;
    private final String label;

    Status(String code, String label) {
        this.code = code;
        this.label = label;
    }

    public String getCode() {
        return code;
    }

    public String getLabel() {
        return label;
    }
}
```

Default serialization:
```java
String json = gson.toJson(Status.APPROVED);
// Output: "APPROVED"
```

## Custom Type Adapter for Enums

For complex logic, implement a custom type adapter:

```java
class CustomStatusAdapter extends TypeAdapter<Status> {
    @Override
    public void write(JsonWriter out, Status value) throws IOException {
        out.value(value.getCode());
    }

    @Override
    public Status read(JsonReader in) throws IOException {
        String code = in.nextString();
        return Status.fromCode(code);
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Status.class, new CustomStatusAdapter())
    .create();
```

## Handling Unknown Enum Values

By default, unknown enum values throw an exception. Handle gracefully:

```java
class SafeEnumDeserializer<T extends Enum<T>>
    implements JsonDeserializer<T> {

    private final T defaultValue;

    SafeEnumDeserializer(T defaultValue) {
        this.defaultValue = defaultValue;
    }

    @Override
    public T deserialize(JsonElement json, Type typeOfT,
                         JsonDeserializationContext context)
        throws JsonSyntaxException {
        String value = json.getAsString();

        @SuppressWarnings("unchecked")
        Class<T> enumClass = (Class<T>) typeOfT;

        for (T enumConstant : enumClass.getEnumConstants()) {
            if (enumConstant.name().equalsIgnoreCase(value)) {
                return enumConstant;
            }
        }

        // Return default instead of throwing
        return defaultValue;
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Status.class,
        new SafeEnumDeserializer<>(Status.PENDING))
    .create();

// Unknown value returns default
Status status = gson.fromJson("\"INVALID\"", Status.class);
// Result: Status.PENDING
```

## Enum Serialization Strategies

### Strategy 1: Name (Default)

```java
@SerializedName("active")
ACTIVE
// JSON: "active"
```

Best for: API compatibility, readability

### Strategy 2: Ordinal

```java
enum Priority {
    LOW,    // 0
    HIGH    // 1
}
// JSON: 0 or 1
```

Best for: Compact representation, backward compatibility

### Strategy 3: Custom Value with @SerializedName

```java
@SerializedName("STAT_ACTIVE")
ACTIVE
// JSON: "STAT_ACTIVE"
```

Best for: Legacy systems, naming conventions

## Collections of Enums

Enums work naturally in collections:

```java
class Permissions {
    List<Role> roles;
    Set<Permission> permissions;
}

Gson gson = new Gson();
String json = gson.toJson(permissions);

Permissions restored = gson.fromJson(json, Permissions.class);
```

If enums need custom handling, register once and it applies to all collections:

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Role.class, new CustomRoleAdapter())
    .create();

// Custom adapter applies to Role in any context
```

## Kotlin Enum Extension

In Kotlin, use reified type parameters for cleaner code:

```kotlin
inline fun <reified T : Enum<T>> enumFromJson(json: String): T {
    return gson.fromJson(json, T::class.java)
}

val status = enumFromJson<Status>("\"approved\"")
```

## Common Patterns

### REST API with Enum Values

```java
enum HttpMethod {
    @SerializedName("GET")
    GET,

    @SerializedName("POST")
    POST,

    @SerializedName("PUT")
    PUT,

    @SerializedName("DELETE")
    DELETE
}

Gson gson = new Gson();

// API request
HttpMethod method = HttpMethod.POST;
String json = gson.toJson(method);
// JSON: "POST"
```

### Database with Enum Storage

```java
// Store by ordinal for compact storage
enum Status {
    ACTIVE(1),
    INACTIVE(0);

    final int dbValue;
    Status(int dbValue) { this.dbValue = dbValue; }
}
```

## Reference

- **JavaGuides Enum Serialization:** https://www.javaguides.net/2018/10/gson-serializing-and-deserializing-enums.html
- **FutureStudio Enum Mapping:** https://futurestud.io/tutorials/gson-advanced-mapping-of-enums
