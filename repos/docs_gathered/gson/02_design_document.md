# Gson Design Document

## Navigation Strategy

Gson navigates the **target type tree** rather than the JSON input tree during deserialization. This approach validates data against expected schemas and ignores unexpected fields. This design choice keeps developers in tight control of instantiating only the type of objects that they are expecting.

## Serialization vs. Deserialization Asymmetry

**Key Design Decision:** "Gson supports serialization of arbitrary collections, but can only deserialize genericized collections."

**Rationale:** This limitation stems from Java's type system. When you encounter a JSON array of arbitrary types, there is no way to detect the types of individual elements at runtime due to Java's type erasure. However, the team prioritized flexibility for users who focus primarily on one operation.

**Consequence:** In some cases, Gson can fail to deserialize JSON that it wrote itself (when arbitrary collections are involved).

## Third-Party Library Support

Rather than requiring annotations on fields to indicate JSON mapping, Gson uses **custom serializers and deserializers**. This design enables integration with unmodifiable external classes without modification, supporting the goal of working with classes where you don't have source code access.

## Exception Handling

The library employs **unchecked exceptions** for parsing failures. The reasoning: clients typically cannot recover from invalid input, so forcing checked exception handling would be unnecessarily burdensome.

## Instance Creation

Gson instantiates classes via **parameterless constructors**. For types lacking default constructors, developers can provide custom `InstanceCreator` implementations. This approach avoids forcing dependency injection frameworks or complex initialization logic.

## Field-Based Mapping

The design uses **non-transient, non-static fields** rather than relying on getter/setter methods. Rationale: "Not all classes are written with suitably named getters."

## Architecture Philosophy

- **Final classes:** Classes are marked `final` to prevent unintended extensions and limit extensibility use-cases. This also provides additional optimization opportunities to the Java compiler and virtual machine.
- **Inner classes:** The design uses inner classes substantially, with many public interfaces being inner interfaces as well, for organizing related functionality by style preference.

## Construction Patterns

Two construction methods exist:

1. **Simple no-args constructor:** `new Gson()` for basic use with default settings
2. **GsonBuilder:** For complex configurations and customizations

## Performance Considerations

The design emphasizes:
- Streaming support through `JsonReader` and `JsonWriter` for memory-efficient processing
- Token-based processing with minimal memory overhead
- Iterative deserialization (as of v2.9.1) rather than recursive to handle deeply nested structures

## Documentation Reference

**Official Design Document:** https://github.com/google/gson/blob/main/GsonDesignDocument.md
