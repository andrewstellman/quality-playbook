---
source: https://github.com/google/gson/issues/1558
retrieved: 2026-04-03
type: github_issue
description: Distinguish between optional field and field with null value
---

# Issue #1558: Distinguish between optional field and field with null value

## Status
**Open** — labeled as enhancement

## Description

JSON Schema and many API specifications distinguish between two different states:

1. **Required-Nullable Fields** — Fields that always appear in JSON output, even if their value is null. These represent fields where null is a meaningful value.

2. **Optional Fields** — Fields that are omitted from JSON when absent or null. These represent fields that may or may not be present.

However, Java objects collapse both states into a single representation: an object reference that is either set to an object or null. This fundamental mismatch creates a problem: Gson cannot serialize the two different states distinctly because it cannot represent whether a field was omitted or set to null.

## The Problem

```java
class Person {
    String name;          // Required
    String middleName;    // Optional (can be omitted from JSON)
}

// Case 1: Required field with null
{
    "name": null,         // Required field, must appear even as null
    "middleName": "John"
}

// Case 2: Optional field with null vs. omitted
{
    "name": "Alice"
    // middleName: omitted (optional field not present)
}

// BUT: After deserialization, both states look identical:
Person p1 = new Person();
p1.name = null;
p1.middleName = null;

Person p2 = new Person();
p2.name = "Alice";
p2.middleName = null;

// When serializing, Gson cannot tell if middleName should be:
// - Omitted (because it was never set)
// - Included as null (because it's required-nullable)
```

## Required vs. Optional Semantics

In domain-driven design and API contracts, the distinction is crucial:

- **Required field** — Always present in the JSON representation, even if the value is null. The absence of the field is a protocol error.

- **Optional field** — May be absent from JSON. If null, it should either be omitted or explicitly marked as absent.

## Workarounds

### Workaround 1: Use @JsonAdapter with Custom Factory
Requires Gson >= 2.11.0 for correct behavior:

```java
@JsonAdapter(MyTypeAdapterFactory.class)
class Person {
    String name;
    @Optional String middleName;
}

class MyTypeAdapterFactory implements TypeAdapterFactory {
    public <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type) {
        final TypeAdapter<T> delegate = gson.getDelegateAdapter(this, type);

        return new TypeAdapter<T>() {
            @Override
            public void write(JsonWriter out, T value) throws IOException {
                boolean previousSerializeNulls = out.getSerializeNulls();
                try {
                    // For optional fields, temporarily disable serializeNulls
                    out.setSerializeNulls(false);
                    delegate.write(out, value);
                } finally {
                    out.setSerializeNulls(previousSerializeNulls);
                }
            }

            @Override
            public T read(JsonReader in) throws IOException {
                return delegate.read(in);
            }
        };
    }
}
```

**Important:** Must use `getDelegateAdapter(this, type)` instead of `getAdapter(type)` in Gson >= 2.11.0 to prevent infinite recursion.

### Workaround 2: Use Wrapper Objects
Wrap optional fields in a container that explicitly tracks presence:

```java
class OptionalString {
    private final String value;
    private final boolean present;

    public OptionalString(String value) {
        this.value = value;
        this.present = value != null;
    }

    public static OptionalString empty() {
        return new OptionalString(null);
    }
}

class Person {
    String name;
    OptionalString middleName;
}

// Serialization:
// If middleName.present: include "middleName": <value>
// If !middleName.present: omit "middleName"
```

### Workaround 3: Separate Serializer and Deserializer
Register custom handlers that understand field semantics:

```java
new GsonBuilder()
    .registerTypeAdapter(Person.class, new JsonSerializer<Person>() {
        public JsonElement serialize(Person src, Type typeOfSrc,
                JsonSerializationContext context) {
            JsonObject obj = new JsonObject();
            obj.addProperty("name", src.name);  // Always include
            if (src.middleName != null) {  // Only if set
                obj.addProperty("middleName", src.middleName);
            }
            return obj;
        }
    })
    .create()
```

### Workaround 4: Field Presence Tracking
Manually track which fields were present during deserialization:

```java
class Person {
    String name;
    String middleName;

    private transient Set<String> presentFields = new HashSet<>();

    public boolean isFieldPresent(String fieldName) {
        return presentFields.contains(fieldName);
    }
}
```

Requires custom TypeAdapter to populate `presentFields` during deserialization.

## JSON Schema Analogy

In JSON Schema (draft 2020-12), the distinction is explicit:

```json
{
    "type": "object",
    "required": ["name"],           // name must always be present
    "properties": {
        "name": { "type": ["string", "null"] },      // required, can be null
        "middleName": { "type": "string" }           // optional, omitted if missing
    }
}
```

Gson has no equivalent mechanism to express this schema-level distinction at the field level.

## Impact on API Design

This limitation affects:
- REST API client libraries (client serializes POJOs to JSON requests)
- Data transfer objects (DTOs mapping to external APIs)
- Configuration objects (some fields are required, others optional)
- Domain models with clear required vs. optional semantics

## Potential Solutions

1. **@Required and @Optional annotations** — Annotate fields to control serialization:
   ```java
   @Required String name;      // Always serialize, even if null
   @Optional String title;     // Omit if null
   ```

2. **TypeAdapterFactory helper** — Built-in utility to reduce boilerplate:
   ```java
   .registerTypeAdapterFactory(
       optionalFieldsFactory(Person.class, "middleName", "title"))
   ```

3. **Lenient mode option** — Extend strictness modes to handle optional field semantics

4. **FieldNamingStrategy extension** — Query fields at serialization time to determine if they're optional

## Related Issues

This issue connects to:
- **Issue #913** — Selective serializeNulls for specific classes
- **Issue #676** — RuntimeTypeAdapterFactory null behavior
- **Issue #1005** — Default values for missing fields
