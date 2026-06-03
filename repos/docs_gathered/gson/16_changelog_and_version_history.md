# Gson Changelog and Version History

## Version 2.13.2 (Latest)

**Release Date:** Recent

**Key Changes:**
- Improved packaging of JPMS module declaration in Gson jar
- Fixed issue where Eclipse and VS Code users could not refer to the Gson module name `com.google.gson`

## Version 2.10+

### Major Breaking Changes

**Java 7 Support Dropped:**
- Minimum Java version is now 8+
- Users still on Java 7 must use Gson 2.9 or earlier

### Version 2.10 Highlights

**New Features:**
- Support for Java records (Java 16+)
- Convenient view methods:
  - `JsonArray.asList()` - Get JsonArray as List
  - `JsonObject.asMap()` - Get JsonObject as Map
- Improved type adapter detection
- Fixed several edge cases in serialization

**Date/Time Improvements:**
- Enhanced deserialization support
- Better flexibility in date format handling

## Version 2.9.1

**Deserialization Improvements:**
- Made deserialization iterative rather than recursive
- Enables handling of deeply nested JSON structures
- Fixes potential StackOverflowError on very deep nesting

**Enum Handling:**
- Added parsing support for enums with overridden `toString()` methods

## Version 2.9.0

**Java Version Requirement:**
- Minimum Java version raised to 7

**New Features:**
- `GsonBuilder.disableJdkUnsafe()` - Greater control over reflection-based instantiation
- Prevents use of `Unsafe` for object creation
- More predictable behavior for classes with custom constructors

## Version 2.8

**TypeToken Improvements:**
- `TypeToken.getParameterized()` - Easier type adapter registration
- Simplified creating parameterized types at runtime

```java
Type mapType = TypeToken.getParameterized(
    Map.class, String.class, Person.class
).getType();
```

## Version 2.5 (2015)

**Atomic Types Support:**
- Added support for:
  - `AtomicLong`
  - `AtomicInteger`
  - `AtomicBoolean`
  - `AtomicLongArray`
  - `AtomicIntegerArray`

**Date Handling:**
- Improved date deserialization flexibility
- Better format detection

## Version 2.0 (2011) - Major Architectural Shift

### Fundamental Change

**Previous Approach (v1.x):**
- Parsed complete document into DOM-style tree model (JsonObject/JsonArray)
- Then bound data against that tree

**New Approach (v2.0):**
- Data binding directly from stream parser
- Significantly faster processing
- Reduced memory overhead

### Impact

This architectural change provided:
- **Performance improvements** - Direct binding without intermediate tree
- **Memory efficiency** - No need to construct complete DOM
- **Streaming support** - Foundation for JsonReader/JsonWriter

## Version 1.0 (2008)

**Initial Release:**
- May 22, 2008
- Apache License 2.0
- Basic serialization/deserialization support

## Known Issues and Backward Compatibility

### Incompatible Behavior Changes

#### JsonParser Empty Stream Handling

**Before:** Returned `JsonNull` for prematurely terminated streams
**After:** Throws `JsonSyntaxException` for invalid JSON

```java
String json = "{\"incomplete\":";
try {
    JsonParser.parseString(json);
} catch (JsonSyntaxException e) {
    // Now throws exception instead of returning JsonNull
}
```

#### IOException Removal

**Before:** `TypeAdapter.toJson()` declared `throws IOException`
**After:** IOException removed (but still caught internally)

**Impact:** Code catching IOException will compile error

```java
// This no longer works
try {
    gson.toJson(obj);
} catch (IOException e) {  // Error - IOException not thrown
}
```

#### Collection<Object> Serialization

**Before:** Serialized arbitrary object collections
**After:** Now backward-incompatible

```java
// Gson can serialize Collection<Object>
// But cannot deserialize reliably due to type erasure
```

**Solution:** Use custom wrappers with type information

#### Atomic Types Default Serialization Change

**Before:** Used default serialization (not intuitive)
**After:** Uses custom serialization

```java
// v2.5+: AtomicLong serializes its value directly
AtomicLong value = new AtomicLong(123);
String json = gson.toJson(value);
// Output: 123 (not {"value":123})
```

This is backward-incompatible but more intuitive.

### Deprecated Features

#### Instance Method JsonParser.parse()

**Deprecated in:** Recent versions
**Status:** Instance method deprecated

```java
// Old style - instance method
JsonParser parser = new JsonParser();
JsonElement element = parser.parse(jsonString);  // Deprecated

// New style - static methods
JsonElement element = JsonParser.parseString(jsonString);
JsonElement element = JsonParser.parseReader(reader);
```

### Type Variable Capture

**Behavior:** TypeToken with type variables has changed

**Backward Compatibility Option:**
```
-Dgson.allowCapturingTypeVariables=true
```

Set this system property to restore old behavior (not recommended).

## Migration Path

### From Gson 2.9 to 2.10+

No breaking changes for most users. Main improvements:
- Records support (if using Java 16+)
- View methods (asList, asMap) are optional conveniences

### From Gson 2.5 to 2.8+

**Potential issues:**
- Code catching IOException on toJson()
- Enum toString() overrides now supported (might behave differently)

### From Gson 1.x to 2.0+

**Complete rewrite likely needed:**
- API changes in streaming
- Performance characteristics different
- Memory usage patterns changed

## Release Schedule

- **Maintenance mode:** Current status
- **Bug fixes:** Applied promptly
- **New features:** Unlikely to be added
- **Support:** Community-driven

## Dependency Information

### Maven Central

```
Group: com.google.code.gson
Artifact: gson
Version: 2.13.2 (latest)
```

### Historical Versions

All versions available on Maven Central at:
https://mvnrepository.com/artifact/com.google.code.gson/gson

## Source Code Timeline

**Initial commit:** 2008
**Language support:** Java
**Current status:** Stable, maintenance mode
**Repository:** https://github.com/google/gson

## Performance Evolution

| Version | Key Change |
|---------|-----------|
| 1.x | Initial implementation |
| 2.0 | Stream-based parsing (major performance gain) |
| 2.5 | Atomic type support |
| 2.8 | TypeToken.getParameterized() |
| 2.9 | Iterative deserialization (deep nesting fix) |
| 2.10 | Records support, view methods |

## Reference

- **Official Changelog:** https://github.com/google/gson/blob/main/CHANGELOG.md
- **GitHub Releases:** https://github.com/google/gson/releases
- **Maven Repository:** https://mvnrepository.com/artifact/com.google.code.gson/gson
