# Gson Advanced Topics

## InstanceCreator for Classes Without Default Constructors

### The Problem

Gson instantiates classes using parameterless constructors via reflection. Classes without default constructors will fail:

```java
public class Person {
    private final String id;
    private final String name;

    // No default constructor
    public Person(String id, String name) {
        this.id = id;
        this.name = name;
    }
}

// This fails
Person person = gson.fromJson(json, Person.class);  // Error!
```

### Solution: Implement InstanceCreator

```java
class PersonInstanceCreator implements InstanceCreator<Person> {
    @Override
    public Person createInstance(Type type) {
        // Provide reasonable default values for constructor
        return new Person("", "");
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Person.class, new PersonInstanceCreator())
    .create();

// Now deserialization works
Person person = gson.fromJson(json, Person.class);
```

Gson will then overwrite the fields from the JSON, so the constructor default values don't matter for the final result.

### Alternative: Use GsonBuilder.disableJdkUnsafe()

By default, Gson uses reflection to bypass constructors (via Unsafe). If you need to enforce constructor usage:

```java
Gson gson = new GsonBuilder()
    .disableJdkUnsafe()  // Forces use of constructors
    .create();
```

Note: This requires classes to have accessible no-arg constructors.

## Polymorphic Type Handling

### The Problem

When deserializing to a base class, Gson doesn't know which subclass to instantiate:

```java
class Animal { }
class Dog extends Animal { }
class Cat extends Animal { }

// Which subclass? Dog or Cat?
String json = "{\"name\":\"Rex\"}";
Animal animal = gson.fromJson(json, Animal.class);  // Ambiguous
```

### Solution: Custom Deserializer with Type Field

```java
class AnimalDeserializer implements JsonDeserializer<Animal> {
    @Override
    public Animal deserialize(JsonElement json, Type typeOfT,
                              JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();
        String type = obj.get("type").getAsString();

        switch (type) {
            case "dog":
                return context.deserialize(json, Dog.class);
            case "cat":
                return context.deserialize(json, Cat.class);
            default:
                throw new JsonSyntaxException("Unknown animal type: " + type);
        }
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Animal.class, new AnimalDeserializer())
    .create();

// Input JSON
String json = "{\"type\":\"dog\",\"name\":\"Rex\",\"breed\":\"Labrador\"}";
Animal animal = gson.fromJson(json, Animal.class);
// Result: Dog instance
```

## Recursive Type References

### The Problem

Circular or self-referential types can cause issues:

```java
class TreeNode {
    String value;
    List<TreeNode> children;
}

// Gson can handle this, but care is needed
```

### Solution: Use Custom Adapters if Needed

```java
Gson gson = new GsonBuilder()
    .serializeNulls()  // Include null children
    .create();

TreeNode root = gson.fromJson(json, TreeNode.class);
```

**Important Limitation:** Gson does NOT support circular object graphs (parent pointing to child pointing back to parent).

## Number Deserialization Strategies

### ToNumberPolicy and ToNumberStrategy

Configure how unknown number types are deserialized:

```java
Gson gson = new GsonBuilder()
    .setObjectToNumberStrategy(ToNumberPolicy.LONG_OR_DOUBLE)
    .create();

// Without strategy, numbers might become Double
String json = "{\"value\": 123456789012345}";
Map<String, Object> map = gson.fromJson(
    json,
    new TypeToken<Map<String, Object>>() {}.getType()
);

// map.get("value") is Long, not Double
Object value = map.get("value");  // Long(123456789012345)
```

### Available Policies

- **DOUBLE:** Always deserialize to Double (default)
- **LONG_OR_DOUBLE:** Use Long if possible, otherwise Double
- **BIG_DECIMAL:** Use BigDecimal for arbitrary precision
- **BIG_INTEGER:** Use BigInteger for whole numbers

## Null Handling Customization

### serializeNulls()

Include null fields in JSON output:

```java
Gson gson = new GsonBuilder()
    .serializeNulls()
    .create();

class Person {
    String name;
    String email;  // null
}

String json = gson.toJson(person);
// Output: {"name":"John","email":null}
```

### serializeSpecialFloatingPointValues()

Handle NaN, Infinity, and -Infinity:

```java
Gson gson = new GsonBuilder()
    .serializeSpecialFloatingPointValues()
    .create();

double[] values = {Double.NaN, Double.POSITIVE_INFINITY};
String json = gson.toJson(values);
// Output: [NaN, Infinity]
```

## Exclusion Strategies

### Exclude Transient Fields

```java
class User {
    String name;
    transient String sessionToken;  // Excluded
}

Gson gson = new Gson();  // Default excludes transient
String json = gson.toJson(user);
// Output: {"name":"John"}  (no sessionToken)
```

### Custom Exclusion Strategy

```java
class CustomExclusionStrategy implements ExclusionStrategy {
    @Override
    public boolean shouldSkipField(FieldAttributes fieldAttributes) {
        // Skip fields starting with underscore
        return fieldAttributes.getName().startsWith("_");
    }

    @Override
    public boolean shouldSkipClass(Class<?> clazz) {
        // Don't skip any classes
        return false;
    }
}

Gson gson = new GsonBuilder()
    .setExclusionStrategies(new CustomExclusionStrategy())
    .create();
```

### Conditional Exclusion by Annotation

```java
public @interface Internal { }

class SensitiveDataStrategy implements ExclusionStrategy {
    @Override
    public boolean shouldSkipField(FieldAttributes fieldAttributes) {
        return fieldAttributes.getAnnotation(Internal.class) != null;
    }

    @Override
    public boolean shouldSkipClass(Class<?> clazz) {
        return false;
    }
}

Gson gson = new GsonBuilder()
    .setExclusionStrategies(new SensitiveDataStrategy())
    .create();

class Config {
    String publicKey;
    @Internal
    String apiKey;  // Excluded
}
```

## Lenient JSON Parsing

By default, Gson is strict. Enable lenient mode for relaxed JSON:

```java
Gson gson = new GsonBuilder()
    .setLenient()
    .create();

// Now allows:
// - Single quotes instead of double quotes
// - Unquoted keys
// - Trailing commas
// - Comments (in some cases)
```

Use Case: Parsing JSON from non-compliant sources.

**Warning:** Use sparingly; invalid JSON often indicates problems.

## Version Control with @Since and @Until

Manage JSON format evolution:

```java
class ApiResponse {
    String id;

    @Since(1.0)
    String name;

    @Since(2.0)
    LocalDate createdDate;

    @Until(1.5)
    String legacyField;
}

// Version 1.0: serialize id, name
Gson gsonV1 = new GsonBuilder()
    .setVersion(1.0)
    .create();

// Version 2.0: serialize id, name, createdDate
Gson gsonV2 = new GsonBuilder()
    .setVersion(2.0)
    .create();
```

## Pretty Printing Configuration

### Basic Pretty Print

```java
Gson gson = new GsonBuilder()
    .setPrettyPrinting()
    .create();
```

### Custom Indentation (if needed)

Use streaming API for full control:

```java
JsonWriter writer = new JsonWriter(stringWriter);
writer.setIndent("    ");  // 4-space indent
```

## Thread Safety and Caching

Gson instances are **stateless and thread-safe**:

```java
// Safe to share across threads
private static final Gson GSON = new Gson();

// Use in multiple threads
gson.toJson(obj);  // Thread A
gson.fromJson(json, MyClass.class);  // Thread B
```

Cache frequently created Gson instances:

```java
public class JsonUtil {
    private static final Gson DEFAULT = new Gson();

    private static final Gson REST_API = new GsonBuilder()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create();

    private static final Gson PRETTY = new GsonBuilder()
        .setPrettyPrinting()
        .create();

    // Use appropriate instance for each task
}
```

## Reference

- **Baeldung Advanced Guide:** https://www.baeldung.com/gson-deserialization-guide
- **FutureStudio Polymorphism:** https://futurestud.io/tutorials/how-to-deserialize-a-list-of-polymorphic-objects-with-gson
