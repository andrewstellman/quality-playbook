# Gson Streaming API

## Overview

Gson provides `JsonReader` and `JsonWriter` classes for efficient token-based JSON processing. Streaming is ideal for:

- Processing large JSON files without loading into memory
- Generating JSON incrementally
- Low-overhead JSON parsing
- Handling JSON files larger than available RAM

## JsonReader: Streaming Parser

`JsonReader` is a **pull parser** that reads JSON sequentially, emitting tokens one at a time.

### Basic Usage

```java
JsonReader reader = new JsonReader(new StringReader(jsonString));

reader.beginObject();  // Consume opening '{'
while (reader.hasNext()) {
    String name = reader.nextName();
    String value = reader.nextString();
    System.out.println(name + ": " + value);
}
reader.endObject();    // Consume closing '}'
```

### Key Methods

#### Token Reading

- `nextString()` - Read a JSON string value
- `nextInt()`, `nextLong()`, `nextDouble()` - Read numeric values
- `nextBoolean()` - Read a boolean value
- `nextNull()` - Consume a null value
- `peek()` - See the next token without consuming it

#### Structure Navigation

- `beginObject()` - Consume opening '{'
- `endObject()` - Consume closing '}'
- `beginArray()` - Consume opening '['
- `endArray()` - Consume closing ']'
- `nextName()` - Read an object key

#### Query Methods

- `hasNext()` - Check if more elements exist
- `isLenient()` - Check if lenient parsing is enabled
- `peek()` - Peek at the next token type

### Example: Reading an Array

```java
String json = "[1, 2, 3, 4, 5]";
JsonReader reader = new JsonReader(new StringReader(json));

reader.beginArray();
while (reader.hasNext()) {
    int value = reader.nextInt();
    System.out.println(value);
}
reader.endArray();
```

### Example: Reading Nested Objects

```java
String json = "{\"name\":\"John\",\"address\":{\"city\":\"NYC\"}}";
JsonReader reader = new JsonReader(new StringReader(json));

reader.beginObject();
while (reader.hasNext()) {
    String key = reader.nextName();
    if ("address".equals(key)) {
        reader.beginObject();
        while (reader.hasNext()) {
            String nestedKey = reader.nextName();
            String nestedValue = reader.nextString();
            System.out.println(nestedKey + ": " + nestedValue);
        }
        reader.endObject();
    } else {
        System.out.println(key + ": " + reader.nextString());
    }
}
reader.endObject();
```

### peek() for Conditional Logic

```java
JsonReader reader = new JsonReader(new StringReader(json));

reader.beginObject();
while (reader.hasNext()) {
    String name = reader.nextName();

    // Look ahead without consuming
    JsonToken token = reader.peek();
    if (token == JsonToken.NULL) {
        reader.nextNull();
        System.out.println(name + ": null");
    } else if (token == JsonToken.STRING) {
        System.out.println(name + ": " + reader.nextString());
    }
}
reader.endObject();
```

## JsonWriter: Streaming Generator

`JsonWriter` allows incremental construction of JSON documents.

### Basic Usage

```java
StringWriter stringWriter = new StringWriter();
JsonWriter writer = new JsonWriter(stringWriter);

writer.beginObject();
writer.name("name").value("John");
writer.name("age").value(30);
writer.endObject();

String json = stringWriter.toString();
// Output: {"name":"John","age":30}
```

### Key Methods

#### Writing Values

- `value(String)` - Write a string
- `value(int)`, `value(long)`, `value(double)` - Write numbers
- `value(boolean)` - Write a boolean
- `nullValue()` - Write null

#### Structure Navigation

- `beginObject()` - Start an object
- `endObject()` - End an object
- `beginArray()` - Start an array
- `endArray()` - End an array
- `name(String)` - Write an object key

#### Configuration

- `setIndent(String)` - Pretty-print with indentation
- `setLenient(boolean)` - Allow lenient JSON

### Example: Writing Complex Objects

```java
StringWriter stringWriter = new StringWriter();
JsonWriter writer = new JsonWriter(stringWriter);

writer.setIndent("  ");  // Pretty print with 2 spaces

writer.beginObject();
writer.name("users").beginArray();

// First user
writer.beginObject();
writer.name("name").value("Alice");
writer.name("age").value(25);
writer.endObject();

// Second user
writer.beginObject();
writer.name("name").value("Bob");
writer.name("age").value(30);
writer.endObject();

writer.endArray();
writer.endObject();

System.out.println(stringWriter.toString());
```

**Output:**
```json
{
  "users": [
    {
      "name": "Alice",
      "age": 25
    },
    {
      "name": "Bob",
      "age": 30
    }
  ]
}
```

## Performance Benefits

### Memory Efficiency

- **Tree model (JsonElement):** Loads entire document into memory
- **Streaming (JsonReader/JsonWriter):** Processes one token at a time

For a 100MB JSON file:
- Tree model: Requires ~100MB+ memory
- Streaming: Constant memory usage

### Speed

Streaming APIs are among the fastest approaches to JSON processing in Java.

## Error Handling

```java
try {
    JsonReader reader = new JsonReader(new StringReader(json));
    // ... reading
} catch (IOException e) {
    System.err.println("I/O error: " + e.getMessage());
} catch (IllegalStateException e) {
    System.err.println("Malformed JSON: " + e.getMessage());
}
```

Common exceptions:
- `IOException` - File or stream errors
- `IllegalStateException` - JSON structure violations (e.g., calling nextString() when at an object)
- `JsonSyntaxException` - Malformed JSON

## Lenient Mode

Enable lenient parsing for relaxed JSON rules:

```java
JsonReader reader = new JsonReader(new StringReader(json));
reader.setLenient(true);

// Now allows trailing commas, unquoted keys, single quotes, etc.
```

Use case: Parsing non-strict JSON from legacy systems.

## Reading from Files

```java
try (JsonReader reader = new JsonReader(new FileReader("data.json"))) {
    reader.beginArray();
    while (reader.hasNext()) {
        // Process each array element
    }
    reader.endArray();
}
```

## Writing to Files

```java
try (JsonWriter writer = new JsonWriter(new FileWriter("output.json"))) {
    writer.setIndent("  ");
    writer.beginObject();
    // ... write data
    writer.endObject();
}
```

## Comparison: JsonElement vs Streaming

| Aspect | JsonElement (Tree) | JsonReader/JsonWriter (Streaming) |
|--------|-------------------|-----------------------------------|
| Memory | High (entire document) | Low (sequential) |
| Speed | Medium | Very High |
| Use Cases | Complex queries, transformations | Large files, high throughput |
| Ease | Easy (navigate tree) | Moderate (track position) |
| Suitable For | < 50MB files | > 100MB files |

## Reference

- **Streaming API Tutorial:** https://mkyong.com/java/gson-streaming-to-read-and-write-json/
- **JsonReader Javadoc:** https://javadoc.io/static/com.google.code.gson/gson/latest/com.google.gson/com/google/gson/stream/JsonReader.html
- **JsonWriter Javadoc:** https://javadoc.io/static/com.google.code.gson/gson/latest/com.google.gson/com/google/gson/stream/JsonWriter.html
