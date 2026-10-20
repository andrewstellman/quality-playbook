---
source: https://futurestud.io/tutorials/gson-advanced-custom-deserialization-basics
retrieved: 2026-04-03
type: community
description: Tutorial on custom deserialization when server data doesn't match Java model structure
---

# Custom Deserialization with Gson — Basics

## The Problem

APIs often send data in formats that don't directly match Java model structures. A common scenario: an API sends a date as separate year/month/day integer fields, but your Java model uses a single `Date` or `LocalDate` object.

Example API response:
```json
{
    "userId": 123,
    "year": 2023,
    "month": 5,
    "day": 15
}
```

Expected Java model:
```java
public class UserDate {
    public int userId;
    public Date date;  // not separate year/month/day fields
}
```

## Implementation

### Step 1: Create a Custom Deserializer

Implement `JsonDeserializer<T>` for your target type:

```java
public class UserDateDeserializer implements JsonDeserializer<UserDate> {
    public UserDate deserialize(JsonElement json, Type typeOfT,
        JsonDeserializationContext context) throws JsonParseException {

        JsonObject jsonObject = json.getAsJsonObject();
        UserDate userDate = new UserDate();

        userDate.userId = jsonObject.get("userId").getAsInt();

        int year = jsonObject.get("year").getAsInt();
        int month = jsonObject.get("month").getAsInt();
        int day = jsonObject.get("day").getAsInt();

        // Construct Date or LocalDate from components
        Calendar calendar = Calendar.getInstance();
        calendar.set(year, month - 1, day);  // Note: Calendar months are 0-indexed
        userDate.date = calendar.getTime();

        return userDate;
    }
}
```

### Step 2: Register with GsonBuilder

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(UserDate.class, new UserDateDeserializer())
    .create();
```

### Step 3: Use for Deserialization

```java
String json = "{\"userId\": 123, \"year\": 2023, \"month\": 5, \"day\": 15}";
UserDate userDate = gson.fromJson(json, UserDate.class);
```

## Accessing JSON Properties

### Type-Specific Accessors

After calling `json.getAsJsonObject()`, use type-specific methods to extract values:

- `getAsString()` — extracts as String
- `getAsInt()` — extracts as int
- `getAsBoolean()` — extracts as boolean
- `getAsDouble()` — extracts as double
- `getAsLong()` — extracts as long
- `getAsJsonObject()` — extracts as JsonObject
- `getAsJsonArray()` — extracts as JsonArray

### Retrieving Properties by Name

Use `get(fieldName)` to retrieve a property:

```java
String userId = jsonObject.get("userId").getAsString();
int age = jsonObject.get("age").getAsInt();
```

## Optional Fields and Null Safety

### Key Technique: Check Field Existence

**Always use `has(fieldName)` before accessing optional fields** to prevent NullPointerExceptions:

```java
UserDate userDate = new UserDate();

if (jsonObject.has("userId")) {
    userDate.userId = jsonObject.get("userId").getAsInt();
}

if (jsonObject.has("year") && jsonObject.has("month") && jsonObject.has("day")) {
    int year = jsonObject.get("year").getAsInt();
    int month = jsonObject.get("month").getAsInt();
    int day = jsonObject.get("day").getAsInt();
    // construct date
} else {
    // handle missing date fields
    userDate.date = null;
}
```

This prevents crashes when the API omits optional fields from its response.

## Summary

Custom deserialization allows you to bridge the gap between API data formats and Java object structures. The key steps are:

1. Implement `JsonDeserializer<T>` with custom transformation logic
2. Register it via `GsonBuilder.registerTypeAdapter()`
3. Use `has()` to safely check for optional fields
4. Use type-specific accessors (`getAsInt()`, `getAsString()`, etc.) to extract values
5. Apply any necessary transformations (date construction, object composition, etc.)

Always validate field existence to handle incomplete or variable API responses gracefully.
