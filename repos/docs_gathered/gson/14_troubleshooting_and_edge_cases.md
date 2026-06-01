# Gson Troubleshooting and Edge Cases

## Type Safety Issues

### ClassCastException with Raw Types

**Problem:**
```java
List list = gson.fromJson("[\"a\",\"b\"]", List.class);
List<String> strings = list;  // ClassCastException
String first = strings.get(0);  // Raw type loses generic info
```

**Solution:** Use TypeToken for generic types:
```java
List<String> strings = gson.fromJson(
    "[\"a\",\"b\"]",
    new TypeToken<List<String>>() {}.getType()
);
```

### Type Variable Erasure

**Problem:**
```java
<T> void process(Class<T> type) {
    new TypeToken<List<T>>() {};  // T is Object due to erasure
}
```

**Solution:** Use concrete types or capture at runtime:
```java
<T> void process(TypeToken<List<T>> typeToken) {
    Type type = typeToken.getType();
}

// Call with:
process(new TypeToken<List<String>>() {});
```

## Reflection and Access Issues

### InaccessibleObjectException

**Problem:**
```
java.lang.reflect.InaccessibleObjectException: Unable to make field accessible
```

**Cause:** Running on Java 9+ with module system, and Gson can't access internal fields.

**Solution 1: Configure module-info.java**
```java
module myapp {
    requires com.google.gson;
    opens myapp.model to com.google.gson;
}
```

**Solution 2: Create Custom Adapter**
```java
class PublicAdapter extends TypeAdapter<MyClass> {
    @Override
    public MyClass read(JsonReader in) throws IOException {
        // Build object without reflection
        return new MyClass(...);
    }

    @Override
    public void write(JsonWriter out, MyClass value) throws IOException {
        // Write public methods
    }
}
```

## Deserialization Problems

### Default Values Lost

**Problem:**
```java
class Config {
    int timeout = 30;  // Default value
}

// Deserialization ignores default and sets to 0
String json = "{}";
Config config = gson.fromJson(json, Config.class);
// config.timeout is 0, not 30
```

**Cause:** Gson bypasses constructor and directly sets fields.

**Solution 1: Use Custom Deserializer**
```java
class ConfigDeserializer implements JsonDeserializer<Config> {
    @Override
    public Config deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context) {
        Config config = new Config();  // Calls constructor with defaults
        JsonObject obj = json.getAsJsonObject();

        if (obj.has("timeout")) {
            config.timeout = obj.get("timeout").getAsInt();
        }
        return config;
    }
}
```

**Solution 2: Use InstanceCreator**
```java
class ConfigInstanceCreator implements InstanceCreator<Config> {
    @Override
    public Config createInstance(Type type) {
        return new Config();  // Preserves defaults
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Config.class, new ConfigInstanceCreator())
    .create();
```

### Expected X but was Y Error

**Problem:**
```
com.google.gson.JsonSyntaxException: java.lang.IllegalStateException: Expected STRING but was NUMBER
```

**Cause:** JSON data type doesn't match Java field type.

**Solution:**
1. Check JSON format matches expected types
2. Use custom deserializer for flexible parsing
3. Make fields accept multiple types if needed

```java
class FlexibleDeserializer implements JsonDeserializer<String> {
    @Override
    public String deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context) {
        if (json.isJsonPrimitive()) {
            if (json.getAsJsonPrimitive().isNumber()) {
                return String.valueOf(json.getAsNumber());
            }
            return json.getAsString();
        }
        return json.toString();
    }
}
```

### Missing Properties in Output

**Problem:**
```java
class User {
    String name;
    String email;  // null
}

String json = gson.toJson(user);
// Output: {"name":"John"}  (email missing)
```

**Solution:** Use serializeNulls():
```java
Gson gson = new GsonBuilder()
    .serializeNulls()
    .create();

String json = gson.toJson(user);
// Output: {"name":"John","email":null}
```

## JSON Format Issues

### MalformedJsonException

**Problem:**
```
com.google.gson.stream.MalformedJsonException: Unterminated object at line 1
```

**Common Causes:**
- Trailing commas: `{"name":"John",}` (invalid)
- Missing quotes: `{name:"John"}` (invalid)
- Unclosed braces or brackets

**Solution:** Validate JSON format:
```java
try {
    JsonParser.parseString(jsonString);
} catch (JsonSyntaxException e) {
    System.err.println("Invalid JSON: " + e.getMessage());
}
```

**Use setLenient() for relaxed parsing:**
```java
Gson gson = new GsonBuilder()
    .setLenient()
    .create();
```

### Premature Stream Termination

**Problem:**
```
Stream ended prematurely
```

**Cause:** JSON stream closed or ended unexpectedly.

**Solution:** Check stream handling:
```java
try (JsonReader reader = new JsonReader(new StringReader(json))) {
    reader.beginObject();
    // ... read data
    reader.endObject();
}  // Properly closed
```

## Android and Obfuscation Issues

### ProGuard/R8 Obfuscation Breaking JSON

**Problem:**
```
Field name doesn't exist in JSON after minification
myPackage.a (minified) != myPackage.OriginalName
```

**Solution: Add ProGuard/R8 Rules**

Create `proguard-rules.pro`:
```
# Preserve Gson library
-keep class com.google.gson.** { *; }
-keep interface com.google.gson.** { *; }

# Preserve TypeToken
-keep class com.google.gson.reflect.TypeToken { *; }

# Preserve your model classes
-keep class mypackage.models.** { *; }
-keep class mypackage.models.** { <fields>; }

# Preserve signatures of generic types
-keepattributes Signature

# Optional: Keep line numbers for debugging
-keepattributes SourceFile,LineNumberTable
```

## Backward Compatibility Issues

### Serialization of Collection<Object>

**Problem:**
```java
Collection<Object> objects = Arrays.asList("text", 123, true);
String json = gson.toJson(objects);
// Output: ["text",123,true]

// Deserialization loses type information
Collection<Object> restored = gson.fromJson(
    json,
    new TypeToken<Collection<Object>>() {}.getType()
);
// Objects are now all converted to Double or String
```

**Solution:** Include type information:
```java
class TypedItem {
    String type;
    Object value;
}

List<TypedItem> items = new ArrayList<>();
items.add(new TypedItem("string", "text"));
items.add(new TypedItem("number", 123));
items.add(new TypedItem("boolean", true));

String json = gson.toJson(items);
```

### GsonBuilder Binary Compatibility

**Problem (Gson 2.11):**
```
Cannot override built-in adapter for type class java.util.List
```

**Solution:** Don't register adapters for built-in types:
```java
// Wrong - don't override built-ins
new GsonBuilder()
    .registerTypeAdapter(List.class, customListAdapter)
    .create();

// Right - use specific type
new GsonBuilder()
    .registerTypeAdapter(MyList.class, customAdapter)
    .create();
```

## Common Configuration Mistakes

### Forgetting to Call .create()

```java
// Wrong - returns GsonBuilder, not Gson
Gson gson = new GsonBuilder()
    .setPrettyPrinting();

// Right
Gson gson = new GsonBuilder()
    .setPrettyPrinting()
    .create();
```

### Not Using @Expose with excludeFieldsWithoutExposeAnnotation()

```java
class User {
    @Expose
    String name;

    String password;  // Intended to be excluded, but isn't
}

// Wrong - @Expose is ignored
Gson gson = new Gson();

// Right - @Expose takes effect
Gson gson = new GsonBuilder()
    .excludeFieldsWithoutExposeAnnotation()
    .create();
```

### Creating Gson Inside Loops

```java
// Wrong - expensive
for (String json : jsonStrings) {
    Gson gson = new Gson();
    MyClass obj = gson.fromJson(json, MyClass.class);
}

// Right - reuse instance
Gson gson = new Gson();
for (String json : jsonStrings) {
    MyClass obj = gson.fromJson(json, MyClass.class);
}
```

## Performance Issues

### Large Collection Deserialization

**Problem:** Slow deserialization of large arrays

**Solution 1: Use Streaming**
```java
try (JsonReader reader = new JsonReader(new FileReader("large.json"))) {
    reader.beginArray();
    while (reader.hasNext()) {
        MyObject obj = gson.fromJson(reader, MyObject.class);
        // Process one at a time
        process(obj);
    }
    reader.endArray();
}
```

**Solution 2: Batch Processing**
```java
// Instead of loading all at once
List<MyObject> all = gson.fromJson(json,
    new TypeToken<List<MyObject>>() {}.getType());

// Process in chunks
int batchSize = 1000;
for (int i = 0; i < all.size(); i += batchSize) {
    int end = Math.min(i + batchSize, all.size());
    List<MyObject> batch = all.subList(i, end);
    processBatch(batch);
}
```

## Reference

- **Official Troubleshooting:** https://google.github.io/gson/Troubleshooting.html
- **Baeldung Troubleshooting:** https://www.baeldung.com/gson
