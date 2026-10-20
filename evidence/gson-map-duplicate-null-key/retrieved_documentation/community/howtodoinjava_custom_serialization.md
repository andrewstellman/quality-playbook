---
source: https://howtodoinjava.com/gson/custom-serialization-deserialization/
retrieved: 2026-04-03
type: community
description: Tutorial on implementing custom JsonSerializer and JsonDeserializer interfaces
---

# Custom Serialization and Deserialization with Gson

## Custom Serialization

The `JsonSerializer<T>` interface requires implementing a serialize method that receives a value, type information, and a serialization context. After creating a custom serializer, register it via `GsonBuilder.registerTypeAdapter()`.

### Example: Boolean to Integer Serialization

Converting boolean values to 1/0 instead of true/false:

```java
public class BooleanSerializer implements JsonSerializer<Boolean> {
    public JsonElement serialize(Boolean aBoolean, Type type,
        JsonSerializationContext jsonSerializationContext) {
        return aBoolean ? new JsonPrimitive(1) : new JsonPrimitive(0);
    }
}
```

### Registration

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Boolean.class, new BooleanSerializer())
    .setPrettyPrinting()
    .create();
```

## Custom Deserialization

The `JsonDeserializer<T>` interface requires implementing a deserialize method. A common use case combines separate day/month/year JSON fields into a `LocalDate` or `Date` object.

### Key Advice

**Check field existence with `has()` to prevent NullPointerExceptions** when accessing optional properties. Always verify that a field exists in the JSON object before calling `get()` on it:

```java
if (jsonObject.has("fieldName")) {
    // Safe to access the field
    String value = jsonObject.get("fieldName").getAsString();
}
```

### Implementation Pattern

1. Implement the `JsonDeserializer<T>` interface
2. Cast the JSON element to `JsonObject` using `json.getAsJsonObject()`
3. Check field existence with `has(fieldName)`
4. Extract values using type-specific accessors: `getAsString()`, `getAsInt()`, `getAsBoolean()`
5. Perform necessary transformations
6. Register via `GsonBuilder.registerTypeAdapter()`

### Registration

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(MyType.class, new MyDeserializer())
    .create();
```

## Summary

Custom serialization and deserialization in Gson provides fine-grained control over how Java objects are converted to and from JSON. The key is to implement the appropriate interface, handle optional fields safely, and register the adapter with GsonBuilder before creating the Gson instance.
