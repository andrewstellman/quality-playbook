---
source: https://futurestud.io/tutorials/gson-advanced-custom-serialization-part-1
retrieved: 2026-04-03
type: community
description: Advanced tutorial on custom serialization for payload reduction with four solution approaches
---

# Advanced Custom Serialization with Gson — Part 1

## The Problem

Consider a `UserSubscription` object containing a full `Merchant` object. When sending data to the server, the server only needs the merchant ID, not the entire Merchant object. Serializing the complete Merchant creates unnecessary payload bloat.

## Four Solution Approaches

### Solution 1: Property Exclusion Using @Expose Annotation

Exclude properties from serialization by annotating them with `@Expose(serialize = false)`:

```java
public class Merchant {
    @Expose
    public String id;

    @Expose(serialize = false)
    public String name;

    @Expose(serialize = false)
    public String email;
}
```

### Solution 2: Custom Serialization for Single Objects

Register a custom `JsonSerializer<Merchant>` that only includes the ID field:

```java
public class MerchantSerializer implements JsonSerializer<Merchant> {
    public JsonElement serialize(Merchant merchant, Type type,
        JsonSerializationContext context) {
        JsonObject jsonObject = new JsonObject();
        jsonObject.addProperty("id", merchant.getId());
        return jsonObject;
    }
}
```

Register it:
```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Merchant.class, new MerchantSerializer())
    .create();
```

### Solution 3: Custom Serialization for Lists

Target entire lists using `TypeToken`. This approach produces a comma-separated string of IDs instead of full merchant objects:

```java
Type merchantListType = new TypeToken<List<Merchant>>(){}.getType();

GsonBuilder gsonBuilder = new GsonBuilder()
    .registerTypeAdapter(merchantListType, new JsonSerializer<List<Merchant>>() {
        public JsonElement serialize(List<Merchant> merchants, Type type,
            JsonSerializationContext context) {
            JsonArray array = new JsonArray();
            for (Merchant merchant : merchants) {
                array.add(merchant.getId());
            }
            return array;
        }
    });
```

### Solution 4: Custom Serialization as Array

Use `JsonArray` to produce compact array output like `["23", "42"]`:

```java
public class MerchantListSerializer implements JsonSerializer<List<Merchant>> {
    public JsonElement serialize(List<Merchant> merchants, Type type,
        JsonSerializationContext context) {
        JsonArray jsonArray = new JsonArray();
        for (Merchant merchant : merchants) {
            jsonArray.add(merchant.getId());
        }
        return jsonArray;
    }
}
```

## Critical Warnings

### Multiple Type Adapter Registrations

"If you declare a type adapter for the same type multiple times, Gson will only respect the last registerTypeAdapter() call." Only the final registration applies. This can be a source of subtle bugs if you're not careful with your GsonBuilder setup.

### Avoid Infinite Recursion

Calling `context.serialize()` within a custom serializer for the same type creates infinite recursion. Never do this:

```java
// WRONG - causes infinite recursion
public class MerchantSerializer implements JsonSerializer<Merchant> {
    public JsonElement serialize(Merchant merchant, Type type,
        JsonSerializationContext context) {
        return context.serialize(merchant); // Infinite loop!
    }
}
```

## Summary

Choose your approach based on your needs:
- **@Expose** for simple property exclusion without custom logic
- **Single object serializer** for objects that need transformation
- **List serializers** for controlling how collections are serialized
- **Array output** for minimal payload size

Always register type adapters carefully and avoid recursion traps.
