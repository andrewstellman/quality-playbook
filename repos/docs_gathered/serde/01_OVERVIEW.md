# Serde Framework Overview

**Source**: https://serde.rs/
**Accessed**: 2026-04-04

## Core Definition

Serde is a Rust framework for **serializing and deserializing data structures** efficiently and generically. It operates through trait implementations rather than runtime reflection.

## Key Architectural Principle

A data structure that knows how to serialize and deserialize itself is one that implements Serde's `Serialize` and `Deserialize` traits. The framework leverages Rust's trait system to enable compile-time code generation, avoiding reflection overhead. The compiler can optimize interactions between data structures and formats completely in many cases.

## Supported Data Formats

The Serde ecosystem includes implementations for:

- **Text formats**: JSON, YAML, TOML, S-expressions
- **Binary formats**: MessagePack, CBOR, Postcard, BSON, Avro, Bencode, FlexBuffers
- **Domain-specific**: RON (Rust Object Notation), D-Bus
- **Specialized**: CSV, URL query strings, environment variables (deserialization-only)

## Core Design Pattern: Trait-Based Architecture

Unlike languages that rely on runtime reflection, Serde is built on Rust's powerful trait system. This design enables:

1. **Compile-time code generation** via derive macros
2. **Format-agnostic implementations** — a single Serialize impl works across all formats
3. **Type safety** — no runtime type coercion or unsafe reflection
4. **Optimization opportunities** — compiler can inline and optimize trait calls

### The Three-Layer Architecture

```
┌─────────────────┐
│  Data Formats   │   (JSON, Postcard, MessagePack, etc.)
├─────────────────┤
│  Serde Data     │   (29 types: primitives, composites, enums)
│  Model          │
├─────────────────┤
│  Rust Types     │   (structs, enums, generics, lifetime constraints)
└─────────────────┘
```

**Contract**: Any supported data structure can serialize/deserialize using any supported format by mapping to the intermediate Serde data model.

## Usage Pattern: The Derive Macro

```rust
#[derive(Serialize, Deserialize, Debug)]
struct Person {
    name: String,
    age: u32,
}
```

The procedural macro `#[derive(Serialize, Deserialize)]` automatically generates implementations of both traits at compile time.

## Two Core Traits

### Serialize

```rust
pub trait Serialize {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer;
}
```

**Contract**: Map your type into the Serde data model by invoking exactly one method on the provided Serializer.

### Deserialize

```rust
pub trait Deserialize<'de>: Sized {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>;
}
```

**Contract**: Map data from a Deserializer into your type by providing a Visitor that receives the Serde data model types.

## The Visitor Pattern

Deserialization uses the visitor pattern:

1. **Visitor** declares what types it can accept and handles construction
2. **Deserializer** inspects input data and calls appropriate visitor methods
3. **Visitor methods** construct the desired type from the incoming data

This pattern enables efficient zero-copy deserialization and supports both self-describing formats (JSON) and binary formats (Postcard).

## Key Design Decisions

### 1. Compile-Time vs. Runtime

- **No runtime reflection**: All trait dispatch resolved at compile time
- **Zero-cost abstractions**: Optimized away by compiler when possible
- **Generic code generation**: Derive macro generates specialized code per type

### 2. Format Independence

- **Single impl per type**: `Serialize` impl works for JSON, MessagePack, Postcard, etc.
- **Format-specific hints**: Deserializer may ignore hints (JSON) or require them (Postcard)
- **Trait objects optional**: Can use `erased-serde` for dynamic trait objects

### 3. Lifetime Management

- **Borrowing efficiency**: Zero-copy deserialization via `'de` lifetime constraints
- **Borrow safety**: Rust enforces that borrowed data outlives deserialized structs
- **Implicit borrowing**: String and byte fields automatically borrow from input

## Documentation Structure

The Serde ecosystem provides guidance on:

- Data model specifications and type mapping
- Derive macro usage and attributes (container, field, variant)
- Custom trait implementations for unusual requirements
- Data format development (implementing Serializer/Deserializer)
- Platform support (no-std environments, embedded)
- Error handling and custom error types

## Performance Characteristics

The framework is designed for efficiency:

- **Compile-time specialization**: Generic code specialized per combination of type + format
- **Zero allocation in happy path**: Many serialization scenarios allocate nothing
- **Zero-copy deserialization**: Borrowed string/byte references avoid data copying
- **Stream processing capable**: Supports streaming deserializers for large data
- **Format flexibility**: Binary formats can be significantly more compact than text

## Important Limitations

1. **Orphan rule**: Cannot implement Serialize/Deserialize for foreign types directly; use remote derive
2. **Untagged enums**: Performance cost; many edge cases; require careful design
3. **Untagged enums in no-std**: Cannot be deserialized without heap allocation
4. **flatten + deny_unknown_fields**: Not officially supported; multiple edge case failures
5. **JSON map keys**: Must be strings; non-string keys produce invalid JSON

## Related Ecosystem

Key companion crates:

- **serde_json**: JSON format implementation
- **serde_derive**: Procedural macro for derive attributes
- **serde_with**: Attribute decorators for advanced serialization
- **erased-serde**: Type-erased serialization for dynamic dispatch
- **serde-ignored**: Track which fields were ignored during deserialization
- **miniserde**: Alternative serialization design by dtolnay (opposite design goals)

## Module Organization

Serde is organized into:

- `serde::ser` — Serialization traits and implementations
- `serde::de` — Deserialization traits and visitors
- `serde_derive` — Procedural macro implementations
- `serde::__private` — Private implementation details (not public API)

---

## References

- https://serde.rs/ — Official documentation
- https://docs.rs/serde/latest/serde/ — API documentation
- https://github.com/serde-rs/serde — Source repository
