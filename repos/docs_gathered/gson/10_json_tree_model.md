# Gson JSON Tree Model

## Overview

Gson provides a tree model through `JsonElement` and related classes that allows working with JSON as in-memory trees. This is useful when you want to query, filter, or transform JSON without committing to a specific object structure.

## JsonElement Hierarchy

All JSON elements extend from `JsonElement`:

- **JsonObject** - Represents a JSON object `{...}`
- **JsonArray** - Represents a JSON array `[...]`
- **JsonPrimitive** - Represents a JSON primitive (string, number, boolean)
- **JsonNull** - Represents JSON null

## Parsing to JsonElement

### Using JsonParser

```java
String json = "{\"name\":\"John\",\"age\":30}";
JsonElement element = JsonParser.parseString(json);
```

### From Reader

```java
JsonElement element = JsonParser.parseReader(new StringReader(json));
```

### From File

```java
try (JsonReader reader = new JsonReader(new FileReader("data.json"))) {
    JsonElement element = JsonParser.parseReader(reader);
}
```

## Type Checking

Always check the type before accessing:

```java
JsonElement element = JsonParser.parseString(jsonString);

if (element.isJsonObject()) {
    JsonObject obj = element.getAsJsonObject();
} else if (element.isJsonArray()) {
    JsonArray array = element.getAsJsonArray();
} else if (element.isJsonPrimitive()) {
    JsonPrimitive primitive = element.getAsJsonPrimitive();
} else if (element.isJsonNull()) {
    // Handle null
}
```

## JsonObject Operations

### Getting Values

```java
JsonObject obj = JsonParser.parseString(json).getAsJsonObject();

// Safe access with type checking
String name = obj.get("name").getAsString();
int age = obj.get("age").getAsInt();

// Direct conversions
boolean exists = obj.has("email");
JsonElement email = obj.get("email");
```

### Setting Values

```java
JsonObject obj = new JsonObject();
obj.addProperty("name", "John");
obj.addProperty("age", 30);
obj.addProperty("active", true);

// Add complex objects
JsonObject address = new JsonObject();
address.addProperty("city", "New York");
obj.add("address", address);
```

### Iterating

```java
JsonObject obj = JsonParser.parseString(json).getAsJsonObject();

// Using entrySet()
for (Map.Entry<String, JsonElement> entry : obj.entrySet()) {
    String key = entry.getKey();
    JsonElement value = entry.getValue();
    System.out.println(key + ": " + value);
}

// Using keySet()
for (String key : obj.keySet()) {
    JsonElement value = obj.get(key);
}
```

### Convenient View Methods (Gson 2.10+)

```java
JsonObject obj = JsonParser.parseString(json).getAsJsonObject();

// Get as Map
Map<String, JsonElement> map = obj.asMap();

// Get as collections
Set<String> keys = obj.keySet();
Collection<JsonElement> values = obj.values();
```

## JsonArray Operations

### Getting Elements

```java
JsonArray array = JsonParser.parseString("[1,2,3]").getAsJsonArray();

// By index
int first = array.get(0).getAsInt();

// Iterate
for (JsonElement element : array) {
    System.out.println(element.getAsInt());
}
```

### Adding Elements

```java
JsonArray array = new JsonArray();
array.add("apple");
array.add(42);
array.add(true);
array.add(JsonNull.INSTANCE);

// Add objects
JsonObject obj = new JsonObject();
obj.addProperty("name", "item");
array.add(obj);
```

### Convenient View Methods (Gson 2.10+)

```java
JsonArray array = JsonParser.parseString(json).getAsJsonArray();

// Get as List
List<JsonElement> list = array.asList();
```

## JsonPrimitive Operations

### Type Checking

```java
JsonPrimitive primitive = element.getAsJsonPrimitive();

if (primitive.isString()) {
    String value = primitive.getAsString();
} else if (primitive.isNumber()) {
    Number number = primitive.getAsNumber();
} else if (primitive.isBoolean()) {
    boolean value = primitive.getAsBoolean();
}
```

### Type Conversions

```java
JsonPrimitive prim = new JsonPrimitive("123");

int intValue = prim.getAsInt();
long longValue = prim.getAsLong();
double doubleValue = prim.getAsDouble();
String stringValue = prim.getAsString();
```

## Common Patterns

### Filtering JSON

```java
String json = "[{\"name\":\"Alice\",\"age\":25},{\"name\":\"Bob\",\"age\":30}]";
JsonArray input = JsonParser.parseString(json).getAsJsonArray();

JsonArray filtered = new JsonArray();
for (JsonElement element : input) {
    JsonObject obj = element.getAsJsonObject();
    if (obj.get("age").getAsInt() >= 30) {
        filtered.add(obj);
    }
}

System.out.println(filtered.toString());
```

### Transforming JSON

```java
JsonObject original = JsonParser.parseString(json).getAsJsonObject();

JsonObject transformed = new JsonObject();
transformed.addProperty("id", original.get("name").getAsString().toUpperCase());
transformed.add("metadata", original.get("details"));

System.out.println(transformed.toString());
```

### Merging Objects

```java
JsonObject obj1 = JsonParser.parseString(json1).getAsJsonObject();
JsonObject obj2 = JsonParser.parseString(json2).getAsJsonObject();

JsonObject merged = new JsonObject();

// Add all from obj1
for (Map.Entry<String, JsonElement> entry : obj1.entrySet()) {
    merged.add(entry.getKey(), entry.getValue());
}

// Add all from obj2 (overwrites duplicates)
for (Map.Entry<String, JsonElement> entry : obj2.entrySet()) {
    merged.add(entry.getKey(), entry.getValue());
}
```

### Deep Copying

```java
JsonElement original = JsonParser.parseString(json);
JsonElement copy = original.deepCopy();  // Gson 2.8.9+
```

Without explicit copy method, use serialization:
```java
Gson gson = new Gson();
JsonElement original = JsonParser.parseString(json);
JsonElement copy = gson.fromJson(gson.toJson(original), JsonElement.class);
```

## Null Handling

### Detecting Null

```java
JsonElement element = obj.get("field");

if (element == null) {
    // Key doesn't exist
}

if (element.isJsonNull()) {
    // Key exists but value is null
}
```

### Null Coalescing Pattern

```java
JsonObject obj = JsonParser.parseString(json).getAsJsonObject();

String value = obj.has("name") && !obj.get("name").isJsonNull()
    ? obj.get("name").getAsString()
    : "default";
```

## Comparison: Tree Model vs Streaming vs Data Binding

| Approach | Memory | Speed | Ease | Use Case |
|----------|--------|-------|------|----------|
| Tree Model | High | Medium | High | Querying, transforming small to medium files |
| Streaming | Low | Very High | Medium | Large files, memory constrained |
| Data Binding | Medium | Fast | High | Mapping to POJOs |

## Best Practices

1. **Always type-check** before accessing elements
2. **Use has()** before accessing optional fields
3. **Cache parsed results** if using multiple times
4. **Consider streaming** for files > 50MB
5. **Use deepCopy()** if modifying parsed elements

## Reference

- **JsonElement Javadoc:** https://javadoc.io/doc/com.google.code.gson/gson/latest/com.google.gson/com/google/gson/JsonElement.html
- **Baeldung Tree Model Guide:** https://www.baeldung.com/gson-string-to-jsonobject
- **HowToDoInJava JsonParser:** https://howtodoinjava.com/gson/gson-jsonparser/
