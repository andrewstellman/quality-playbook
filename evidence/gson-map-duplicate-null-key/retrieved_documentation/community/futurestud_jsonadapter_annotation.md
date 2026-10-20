---
source: https://futurestud.io/tutorials/gson-advanced-customizing-de-serialization-and-adding-instance-creators-via-jsonadapter
retrieved: 2026-04-03
type: community
description: Tutorial on @JsonAdapter annotation for simplified custom (de)serialization without GsonBuilder
---

# @JsonAdapter Annotation — Simplified Custom Serialization/Deserialization

## Overview

The `@JsonAdapter` annotation (available in Gson 2.7+) simplifies customizing serialization and deserialization without requiring verbose GsonBuilder boilerplate. Apply the annotation directly to your model classes or fields to register custom adapters.

## Custom Serialization with @JsonAdapter

### Without @JsonAdapter (Verbose)

```java
public class Merchant {
    public String id;
    public String name;
    public String email;
}

// Custom serializer
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

// GsonBuilder setup required
Gson gson = new GsonBuilder()
    .registerTypeAdapter(new TypeToken<List<Merchant>>(){}.getType(),
        new MerchantListSerializer())
    .create();
```

### With @JsonAdapter (Simplified)

Apply the annotation directly to the field:

```java
public class UserSubscription {
    @JsonAdapter(MerchantListSerializer.class)
    public List<Merchant> merchants;
}

// Now you can use plain Gson without GsonBuilder
Gson gson = new Gson();
String json = gson.toJson(userSubscription);
```

The serializer class remains the same:

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

## Custom Deserialization with @JsonAdapter

### Apply Annotation to Class

For deserialization, annotate the entire class with the custom deserializer:

```java
@JsonAdapter(UserDateDeserializer.class)
public class UserDate {
    public int userId;
    public Date date;
}

public class UserDateDeserializer implements JsonDeserializer<UserDate> {
    public UserDate deserialize(JsonElement json, Type typeOfT,
        JsonDeserializationContext context) throws JsonParseException {

        JsonObject jsonObject = json.getAsJsonObject();
        UserDate userDate = new UserDate();

        userDate.userId = jsonObject.get("userId").getAsInt();

        int year = jsonObject.get("year").getAsInt();
        int month = jsonObject.get("month").getAsInt();
        int day = jsonObject.get("day").getAsInt();

        Calendar calendar = Calendar.getInstance();
        calendar.set(year, month - 1, day);
        userDate.date = calendar.getTime();

        return userDate;
    }
}

// Now use plain Gson
Gson gson = new Gson();
UserDate userDate = gson.fromJson(json, UserDate.class);
```

## Benefits of @JsonAdapter

- **Cleaner Code**: No GsonBuilder boilerplate for simple cases
- **Declarative**: Annotation shows intent directly on the model
- **Self-Documenting**: Readers immediately see which adapter is used
- **Less Setup**: Usable with plain `new Gson()` constructor

## Key Limitation

**The annotation only accepts a single class reference.** If you need both custom serialization AND deserialization for the same type, you must use `GsonBuilder.registerTypeAdapter()` instead.

### Example of Limitation

This will NOT work as expected:
```java
// WRONG - can only specify one adapter class
@JsonAdapter(MySerializer.class)
@JsonAdapter(MyDeserializer.class)  // Second annotation ignored
public class MyType { }
```

### Solution: Combine in Single Adapter Class

Create an adapter class implementing both interfaces:

```java
public class MyTypeAdapter extends TypeAdapter<MyType> {
    // Implements both serialization and deserialization

    @Override
    public void write(JsonWriter out, MyType value) throws IOException {
        // serialization logic
    }

    @Override
    public MyType read(JsonReader in) throws IOException {
        // deserialization logic
    }
}

@JsonAdapter(MyTypeAdapter.class)
public class MyType { }
```

Or use `GsonBuilder`:

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(MyType.class, new MySerializer())
    .registerTypeAdapter(MyType.class, new MyDeserializer())
    .create();
```

## Summary

Use `@JsonAdapter` for:
- Simple custom serialization or deserialization
- Single adapter per type
- Reducing GsonBuilder complexity

Use `GsonBuilder.registerTypeAdapter()` for:
- Both custom serialization AND deserialization on same type
- Complex adapter registration scenarios
- Multiple adapters for the same type
