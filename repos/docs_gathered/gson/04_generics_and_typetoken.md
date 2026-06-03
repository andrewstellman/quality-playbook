# Gson Generics and TypeToken

## The Problem with Java Generics

Java's **type erasure** removes generic type information at runtime. Without special handling, Gson cannot determine which parameter types to use when deserializing generic classes.

Example of the problem:
```java
List<String> stringList = gson.fromJson("[\"a\",\"b\"]", List.class);
// Without TypeToken, Gson doesn't know the List contains Strings
// Result: will be List<Object> or fail to deserialize correctly
```

## TypeToken Solution

`TypeToken<T>` represents a generic type `T` and preserves type information at runtime. It provides Gson with the specific generic type details needed for correct deserialization.

### Why TypeToken Works

TypeToken uses **anonymous inner class trick** to capture type information at runtime. Java preserves generic type information in a class's superclass reference, even though method signatures lose it.

### Creating a TypeToken

TypeToken has no public constructor - you must extend it with an anonymous subclass:

```java
// Correct way
TypeToken<List<String>> token = new TypeToken<List<String>>() {};

// Get the Type object
Type type = token.getType();
```

### Deserialization with TypeToken

```java
String json = "[\"apple\",\"banana\",\"cherry\"]";
List<String> fruits = gson.fromJson(json, new TypeToken<List<String>>() {}.getType());
```

### Complex Generic Types

```java
// Map with specific key/value types
Map<String, Person> personMap = gson.fromJson(
    jsonString,
    new TypeToken<Map<String, Person>>() {}.getType()
);

// Nested generics
FooResponse<Person> response = gson.fromJson(
    jsonString,
    new TypeToken<FooResponse<Person>>() {}.getType()
);

// Collections of parameterized types
Collection<Integer> integers = gson.fromJson(
    "[1,2,3]",
    new TypeToken<Collection<Integer>>() {}.getType()
);
```

## Practical Examples

### List Deserialization

```java
String json = "[{\"name\":\"John\"},{\"name\":\"Jane\"}]";
List<Person> people = gson.fromJson(
    json,
    new TypeToken<List<Person>>() {}.getType()
);
```

### TypeToken with Dynamic Types

For scenarios where the type is determined at runtime:

```java
Type type = new TypeToken<List<String>>() {}.getType();
```

## TypeToken.getParameterized()

As of Gson 2.8+, there's a factory method for creating parameterized types:

```java
Type mapType = TypeToken.getParameterized(
    Map.class, String.class, Person.class
).getType();
```

## Important Considerations

### Type Variables Aren't Captured

Due to Java's type erasure, type variables in TypeToken won't work correctly:

```java
// Don't do this - T will be erased!
<T> void foo(Class<T> type) {
    new TypeToken<List<T>>() {}.getType(); // T is Object, not what you expect
}
```

### Backward Compatibility Note

For backward compatibility, it's possible to restore Gson's old behavior of allowing TypeToken to capture type variables by setting the system property:
```
-Dgson.allowCapturingTypeVariables=true
```

However, this is not recommended for new code.

## Kotlin Usage

Kotlin's reified type parameters provide a cleaner syntax:

```kotlin
inline fun <reified T> fromJson(json: String): T {
    return gson.fromJson(json, object : TypeToken<T>() {}.type)
}

// Usage
val people: List<Person> = fromJson(jsonString)
```

## Reference

- **TypeToken Javadoc:** https://javadoc.io/static/com.google.code.gson/gson/latest/com.google.gson/com/google/gson/reflect/TypeToken.html
- **Baeldung TypeToken Guide:** https://www.baeldung.com/gson-typetoken-dynamic-list-item-type
