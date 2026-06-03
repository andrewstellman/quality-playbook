# Serde Data Model Specification

**Source**: https://serde.rs/data-model.html
**Accessed**: 2026-04-04

## Overview

The Serde data model comprises **29 types** that serve as the intermediary between Rust data structures and serialization formats. Every Rust data structure must map to exactly one of these types.

**Critical Contract**: The Serialize trait maps your type into the Serde data model by invoking exactly one method on the Serializer. The Deserialize implementation receives the data mapped into the data model via Visitor methods.

## The 29 Types

### Primitive Types (14)

#### Boolean
- **Type**: `bool`
- **Contract**: Serializes to a boolean value (true/false)
- **Deserialization**: Visitor receives `visit_bool(bool)`
- **Format Support**: All formats

#### Signed Integers (5)
- **Types**: `i8`, `i16`, `i32`, `i64`, `i128`
- **Contract**: Serialize integral values within range; overflow behavior is format-dependent
- **Deserialization**: Visitor receives one of `visit_i8`, `visit_i16`, `visit_i32`, `visit_i64`, `visit_i128`
- **Cross-platform**: Smaller types may be promoted to larger types by deserializer
- **Overflow**: Checked conversion; deserialization fails on overflow (not truncated)
- **Note**: Postcard may store integers with variable-length encoding; JSON uses decimal notation

#### Unsigned Integers (5)
- **Types**: `u8`, `u16`, `u32`, `u64`, `u128`
- **Contract**: Serialize non-negative integral values
- **Deserialization**: Visitor receives one of `visit_u8`, `visit_u16`, `visit_u32`, `visit_u64`, `visit_u128`
- **Overflow**: Checked conversion; deserialization fails if value exceeds type range
- **Note**: JSON represents all unsigned integers as decimal numbers

#### Floating Point (2)
- **Types**: `f32`, `f64`
- **Contract**: Serialize floating-point values; NaN, Infinity may or may not be supported
- **Deserialization**: Visitor receives `visit_f32(f32)` or `visit_f64(f64)`
- **Precision**: Subject to format's floating-point representation
- **Note**: JSON may not support NaN or Infinity; binary formats vary

#### Character (1)
- **Type**: `char`
- **Contract**: Represents a Unicode scalar value
- **Deserialization**: Visitor receives `visit_char(char)`
- **Serialization**: Typically serialized as a single-character string or an integer (format-dependent)
- **Format Variation**: JSON serializes char as string; Postcard may use 4-byte encoding

### Composite Types (15)

#### String
- **Type**: `&str` (borrowed) or `String` (owned)
- **Contract**: UTF-8 bytes with a length and no null terminator. May contain 0-bytes internally.
- **Three Flavors**:
  - **Borrowed** (`visit_borrowed_str`): Data guaranteed to live as long as `'de` lifetime
  - **Owned** (`visit_string`): Allocated during deserialization
  - **Transient** (`visit_str`): Data valid only during the method call
- **Escape Handling**: Must handle escape sequences properly (JSON requires escaping)
- **Borrowing**: Field types `&str` implicitly borrow from input; other Cow<'a, str> requires `#[serde(borrow)]`

#### Byte Array
- **Type**: `&[u8]` (borrowed) or `Vec<u8>` (owned)
- **Contract**: Mirrors string with transient/owned/borrowed variants
- **Three Flavors**:
  - **Borrowed** (`visit_borrowed_bytes`): Raw byte data borrowing from input
  - **Owned** (`visit_byte_buf`): Allocated byte vector
  - **Transient** (`visit_bytes`): Bytes valid only during method call
- **Format Variation**: JSON typically base64-encodes; Postcard stores raw bytes
- **Zero-copy**: String and byte array deserialization are primary zero-copy opportunities

#### Option
- **Type**: `Option<T>`
- **Contract**: Represents either `None` or a contained value
- **Serialization**:
  - `None` → visitor receives `visit_none()`
  - `Some(value)` → visitor receives `visit_some(deserializer)` and deserializes T
- **JSON Behavior**: `Option::None` serializes as `null`; `Option::Some` serializes as just the value
- **Format Variation**: MessagePack uses type nil; binary formats may use tag byte

#### Unit
- **Type**: `()`
- **Contract**: The type of `()` in Rust. Represents an anonymous value containing no data.
- **Serialization**: Serializes to no data or a minimal representation (format-dependent)
- **Deserialization**: Visitor receives `visit_unit()`
- **Size**: Always zero-sized in output

#### Unit Struct
- **Type**: `struct Unit;` (zero fields)
- **Contract**: Named types without data; distinct from Unit type
- **Serialization**: Uses `serialize_unit_struct(name, len)` with len=0
- **Deserialization**: Visitor receives `visit_unit_struct(name)`
- **Distinction**: Named unit structs are distinct from the bare unit type ()

#### Unit Variant
- **Type**: `enum Color { Red }` (no data)
- **Contract**: Enum variants without associated data
- **Serialization**: Representation depends on enum tagging strategy:
  - **Externally tagged** (default): `{"Red": {}}`
  - **Internally tagged**: `{"type": "Red", ...}`
  - **Adjacently tagged**: `{"t": "Red", "c": null}`
  - **Untagged**: Depends on format
- **Deserialization**: Visitor receives variant name and `visit_unit()`

#### Newtype Struct
- **Type**: `struct Millimeters(u32)` (single field)
- **Contract**: Single-field wrapper types; transparent in serialization
- **Serialization**: Uses `serialize_newtype_struct(name, value)`
- **Deserialization**: Visitor receives `visit_newtype_struct(deserializer)` and deserializes inner type
- **Transparency**: With `#[serde(transparent)]`, serializes identically to inner value
- **Default Behavior**: Serializers are encouraged to treat as insignificant wrappers

#### Newtype Variant
- **Type**: `enum Result { Ok(T) }` (single field)
- **Contract**: Enum variants wrapping a single value
- **Serialization**: Uses `serialize_newtype_variant(name, index, variant, value)`
- **Representation**: Depends on enum tagging (externally/internally/adjacently tagged)
- **Deserialization**: Variant access followed by `visit_newtype_struct(deserializer)`

#### Sequence
- **Type**: `Vec<T>`, `&[T]`, `HashSet<T>`, etc.
- **Contract**: Variable-length heterogeneous collections
- **Serialization**:
  - Uses `serialize_seq(len)` to begin
  - `serialize_element(elem)` for each element
  - `end()` to finalize
- **Length**: May or may not be known upfront; serializer accepts `Option<usize>` for length hint
- **Format Variation**: JSON uses `[...]` array syntax; binary formats may store length prefix
- **Deserialization**: Visitor receives `visit_seq(seq_access)` for iteration

#### Tuple
- **Type**: `(T, U, V)` — fixed-size, known-length sequences
- **Contract**: Unlike sequences, tuple length is compile-time constant and known at deserialization time
- **Serialization**: Uses `serialize_tuple(len)` instead of `serialize_seq()`
- **Length**: Always known; deserializer does not need length hint
- **Element Heterogeneity**: Elements can be different types
- **Distinction from Sequence**: Tuple length is compile-time known; sequence length is runtime
- **Deserialization**: Visitor receives `visit_tuple(tuple_access)`

#### Tuple Struct
- **Type**: `struct Rgb(u8, u8, u8)` — named tuples
- **Contract**: Named tuple variants; semantically identical to tuples but with a name
- **Serialization**: Uses `serialize_tuple_struct(name, len)`
- **Deserialization**: Visitor receives `visit_tuple_struct(name, tuple_access)`
- **Fields**: Fixed number of fields known at compile time

#### Tuple Variant
- **Type**: `enum Event { Click(u32, u32) }` — enum variants containing tuple data
- **Contract**: Enum variants with multiple ordered fields
- **Serialization**: Uses `serialize_tuple_variant(name, index, variant_name, len)`
- **Length**: Always known
- **Format Representation**: Depends on enum tagging strategy

#### Map
- **Type**: `BTreeMap<K, V>`, `HashMap<K, V>`, etc.
- **Contract**: Variable-length key-value pairs
- **Key Restriction**: Keys must be non-compound types or strings
- **Serialization**:
  - Uses `serialize_map(len)` to begin
  - `serialize_entry(key, value)` for each pair
  - `end()` to finalize
- **JSON Constraint**: JSON requires string keys; non-string keys produce invalid JSON
- **Format Variation**: Postcard stores pairs in sequence; JSON uses object syntax
- **Deserialization**: Visitor receives `visit_map(map_access)` for iteration

#### Struct
- **Type**: `struct Point { x: i32, y: i32 }`
- **Contract**: Fixed-size key-value pairings with compile-time constant string keys
- **Field Names**: Names are compile-time constants; cannot be dynamically determined
- **Serialization**: Uses `serialize_struct(name, len)` with exactly known fields
- **Field Order**: May or may not be preserved depending on format
- **Distinction from Map**: Struct has known fields; map is dynamic
- **Deserialization**: Visitor receives `visit_struct(struct_access)` with field information
- **Field Availability**: All fields or subset thereof may be present in input

#### Struct Variant
- **Type**: `enum Shape { Rectangle { width: u32, height: u32 } }`
- **Contract**: Enum variants containing struct-like fields
- **Serialization**: Uses `serialize_struct_variant(name, index, variant_name, len)`
- **Fields**: Fixed number and names, compile-time known
- **Representation**: Depends on enum tagging strategy

## Type Mapping Examples

### Rust Type → Data Model

```rust
// Primitives
true                     → bool
42_i32                   → i32
3.14_f64                 → f64
'A'                      → char

// Collections
vec![1, 2, 3]           → seq of i32
(1, "hello")            → tuple
struct Point { x: 1 }   → struct "Point"
HashMap::new()          → map

// Enums (depends on tagging)
Some(42)                → option (newtype)
Ok(value)               → newtype variant or struct variant
Color::Red              → unit variant
```

### Data Model → Format (JSON Example)

```rust
// Primitive
i32(42)                 → 42
bool(true)              → true
char('A')               → "A"

// String/bytes
str("hello")            → "hello" (with escaping)
bytes([1,2,3])          → "AQID" (base64)

// Collections
seq([1,2,3])            → [1, 2, 3]
tuple((1, "hi"))        → [1, "hi"]
struct(Point{x:1})      → {"x": 1}
map({a:1})              → {"a": 1}

// Enums
newtype variant         → {"Ok": value}
unit variant            → "Red" or {"Red": {}}
struct variant          → {"Rect": {"w": 1, "h": 2}}
```

## Critical Behavioral Contracts

### 1. Exact Type Matching

**Contract**: Deserialize implementations must invoke exactly one of the 29 types. You cannot invoke multiple.

Example violation:
```rust
// WRONG - invokes two types
fn serialize<S>(&self, s: S) -> Result<S::Ok, S::Error> {
    s.serialize_unit()?;
    s.serialize_bool(true)?;  // ← VIOLATES CONTRACT
}
```

### 2. Visitor Method Dispatch

**Contract**: When deserializing, the Visitor receives method calls matching the incoming data type. Not all methods need be implemented; unimplemented methods return type errors.

### 3. Size Contracts

- **Tuples**: Length must be exact; deserializer knows exactly how many elements
- **Sequences**: Length may be unknown; deserializer learns size during iteration
- **Maps**: Length may be unknown; deserializer learns size during iteration
- **Structs**: Field count is known; field names are known

### 4. Type Hints vs. Format Content

- **Self-describing formats** (JSON): Ignore type hints; inspect actual content
- **Binary formats** (Postcard): Require type hints to interpret compact representation

### 5. Overflow Behavior

**Contract**: Integer overflow during deserialization produces an error, not silent truncation.

- `u32::MAX + 1` as u32 → Error
- JSON number "99999999999999999" as u32 → Error

### 6. String Escape Handling

**Contract**: Serializers must properly escape strings for the format. JSON requires escaping special characters; binary formats may not.

---

## References

- https://serde.rs/data-model.html
- https://docs.rs/serde/latest/serde/trait.Serializer.html
- https://docs.rs/serde/latest/serde/trait.Deserializer.html
