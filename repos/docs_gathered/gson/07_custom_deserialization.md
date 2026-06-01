# Gson Custom Deserialization

## Overview

For complex deserialization scenarios, implement `JsonDeserializer<T>` to handle specialized parsing logic beyond Gson's defaults.

## JsonDeserializer Interface

```java
public interface JsonDeserializer<T> {
    T deserialize(JsonElement json, Type typeOfT,
                  JsonDeserializationContext context)
        throws JsonSyntaxException;
}
```

### Parameters

- **json:** The JSON element being deserialized
- **typeOfT:** The type of the object to deserialize into
- **context:** Allows recursive deserialization of nested elements

## Basic Deserializer Implementation

### Example: Custom Date Deserializer

```java
class DateDeserializer implements JsonDeserializer<Date> {
    private static final SimpleDateFormat dateFormat =
        new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    @Override
    public Date deserialize(JsonElement json, Type typeOfT,
                            JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            return dateFormat.parse(json.getAsString());
        } catch (ParseException e) {
            throw new JsonSyntaxException("Date parsing failed", e);
        }
    }
}
```

### Registration

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Date.class, new DateDeserializer())
    .create();

// Now JSON date strings are parsed using the custom deserializer
String json = "\"2024-03-07 14:30:45\"";
Date date = gson.fromJson(json, Date.class);
```

## Advanced Example: Combining Fields

Common scenario: API returns split date fields (day, month, year) that need combining:

```java
class LocalDateDeserializer implements JsonDeserializer<LocalDate> {
    @Override
    public LocalDate deserialize(JsonElement json, Type typeOfT,
                                  JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();

        int day = obj.get("day").getAsInt();
        int month = obj.get("month").getAsInt();
        int year = obj.get("year").getAsInt();

        return LocalDate.of(year, month, day);
    }
}
```

**Input JSON:**
```json
{
  "name": "John",
  "birthDate": {
    "day": 15,
    "month": 3,
    "year": 1990
  }
}
```

## Polymorphic Deserialization

Handling different object types based on a discriminator field:

```java
class AnimalDeserializer implements JsonDeserializer<Animal> {
    @Override
    public Animal deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();
        String type = obj.get("type").getAsString();

        if ("dog".equals(type)) {
            return context.deserialize(json, Dog.class);
        } else if ("cat".equals(type)) {
            return context.deserialize(json, Cat.class);
        }

        throw new JsonSyntaxException("Unknown animal type: " + type);
    }
}
```

**Input JSON:**
```json
{
  "type": "dog",
  "name": "Rex",
  "breed": "German Shepherd"
}
```

## Recursive Deserialization

Using `JsonDeserializationContext.deserialize()` for nested objects:

```java
class CompanyDeserializer implements JsonDeserializer<Company> {
    @Override
    public Company deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();

        String name = obj.get("name").getAsString();

        // Recursively deserialize the employees list
        Type employeeListType = new TypeToken<List<Employee>>() {}.getType();
        List<Employee> employees = context.deserialize(
            obj.get("employees"),
            employeeListType
        );

        return new Company(name, employees);
    }
}
```

Benefits:
- Applies custom deserializers to nested objects
- Respects Gson configuration
- Cleaner than manual JSON parsing

## Type Checking and Error Handling

```java
class SafeDeserializer implements JsonDeserializer<MyType> {
    @Override
    public MyType deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context)
        throws JsonSyntaxException {
        // Check element type
        if (!json.isJsonObject()) {
            throw new JsonSyntaxException("Expected JSON object");
        }

        JsonObject obj = json.getAsJsonObject();

        // Safe property access
        if (!obj.has("required_field")) {
            throw new JsonSyntaxException("Missing required field");
        }

        try {
            String value = obj.get("field").getAsString();
            // ... processing
        } catch (ClassCastException e) {
            throw new JsonSyntaxException("Wrong field type", e);
        }
    }
}
```

## InstanceCreator vs JsonDeserializer

| Feature | InstanceCreator | JsonDeserializer |
|---------|-----------------|-----------------|
| Purpose | Create instances of types without default constructors | Custom parsing logic |
| Responsibility | Create empty/initialized object | Parse JSON and set fields |
| When Used | Before deserialization | During deserialization |
| Registration | `registerTypeAdapter()` | `registerTypeAdapter()` |

Often used together for complex types:

```java
public class MyComplexClass {
    private final String id;
    private final String value;

    // No default constructor
    public MyComplexClass(String id, String value) {
        this.id = id;
        this.value = value;
    }
}

class MyComplexInstanceCreator implements InstanceCreator<MyComplexClass> {
    @Override
    public MyComplexClass createInstance(Type type) {
        return new MyComplexClass("", "");
    }
}

class MyComplexDeserializer implements JsonDeserializer<MyComplexClass> {
    @Override
    public MyComplexClass deserialize(JsonElement json, Type typeOfT,
                                      JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();
        return new MyComplexClass(
            obj.get("id").getAsString(),
            obj.get("value").getAsString()
        );
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(MyComplexClass.class, new MyComplexInstanceCreator())
    .registerTypeAdapter(MyComplexClass.class, new MyComplexDeserializer())
    .create();
```

## Reference

- **Baeldung Deserialization Guide:** https://www.baeldung.com/gson-deserialization-guide
- **FutureStudio Custom Deserialization:** https://futurestud.io/tutorials/gson-advanced-custom-deserialization-basics
