# Gson Custom Serialization

## Overview

For specialized handling beyond basic serialization, Gson provides the ability to implement custom serializers and register them with `GsonBuilder`.

## JsonSerializer Interface

Custom serializers implement `JsonSerializer<T>`:

```java
public interface JsonSerializer<T> {
    JsonElement serialize(T src, Type typeOfSrc, JsonSerializationContext context);
}
```

### Parameters

- **src:** The object being serialized
- **typeOfSrc:** The actual type of the object (useful for generics)
- **context:** Allows recursive serialization of nested objects

## Implementing a Custom Serializer

### Example: Custom Date Serializer

```java
class DateSerializer implements JsonSerializer<Date> {
    private static final SimpleDateFormat dateFormat =
        new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    @Override
    public JsonElement serialize(Date date, Type typeOfSrc,
                                  JsonSerializationContext context) {
        return new JsonPrimitive(dateFormat.format(date));
    }
}
```

### Registration

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(Date.class, new DateSerializer())
    .create();

// Now all Date objects use the custom serializer
Date now = new Date();
String json = gson.toJson(now);
// Output: "2024-03-07 14:30:45"
```

## Advanced Example: Custom Object Serialization

```java
class PersonSerializer implements JsonSerializer<Person> {
    @Override
    public JsonElement serialize(Person person, Type typeOfSrc,
                                  JsonSerializationContext context) {
        JsonObject obj = new JsonObject();
        obj.addProperty("name", person.getName());
        obj.addProperty("age", person.getAge());

        // Add computed properties
        obj.addProperty("adult", person.getAge() >= 18);

        // Recursively serialize complex objects
        obj.add("address", context.serialize(person.getAddress()));

        return obj;
    }
}
```

## Null Handling in Serializers

Serializers can customize null handling:

```java
class NullSafeSerializer implements JsonSerializer<MyClass> {
    @Override
    public JsonElement serialize(MyClass src, Type typeOfSrc,
                                  JsonSerializationContext context) {
        if (src == null) {
            return JsonNull.INSTANCE;
        }
        // ... normal serialization
    }
}
```

## Context.serialize() for Recursive Serialization

The `JsonSerializationContext` allows recursive serialization:

```java
class CompanySerializer implements JsonSerializer<Company> {
    @Override
    public JsonElement serialize(Company company, Type typeOfSrc,
                                  JsonSerializationContext context) {
        JsonObject obj = new JsonObject();
        obj.addProperty("name", company.getName());

        // Recursively serialize all employees
        obj.add("employees", context.serialize(company.getEmployees()));

        return obj;
    }
}
```

Benefits:
- Automatic handling of nested Gson customizations
- Proper type adapter selection
- Support for custom deserializers on referenced objects

## Type Registration Options

### registerTypeAdapter()

Registers for a specific type:

```java
new GsonBuilder()
    .registerTypeAdapter(Date.class, new DateSerializer())
    .create();
```

### registerTypeHierarchyAdapter()

Registers for a type and all its subtypes:

```java
new GsonBuilder()
    .registerTypeHierarchyAdapter(Collection.class, new CollectionSerializer())
    .create();
```

Useful for base classes or interfaces where you want the serializer to apply to all implementations.

## Common Use Cases

### 1. Date/Time Formatting

Converting dates to ISO-8601 or custom formats

### 2. Computed Properties

Including calculated fields that don't exist on the original object

### 3. Exclusion Logic

Excluding sensitive information based on runtime conditions

### 4. Type Variants

Handling different serialization for subtypes

### 5. Enum Formatting

Converting enums to user-friendly representations

## Performance Considerations

- Custom serializers are called for every instance of the registered type
- Use `context.serialize()` carefully - unnecessary recursive serialization impacts performance
- Consider caching expensive computations
- Stateless serializers are thread-safe

## Limitations

- Serializers cannot modify the original object
- Cannot control field exclusion via serializer (use @Expose or exclusion strategies for that)
- For complex conditional logic, consider using multiple adapters or composition

## Reference

- **Baeldung Custom Serialization Guide:** https://www.baeldung.com/gson-serialization-guide
- **FutureStudio Custom Serialization:** https://futurestud.io/tutorials/gson-advanced-custom-serialization-part-1
