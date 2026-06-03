# Serialize Trait Specification

**Source**: https://docs.rs/serde/latest/serde/trait.Serialize.html
**Accessed**: 2026-04-04

## Trait Definition

```rust
pub trait Serialize {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer;
}
```

## Core Contract

**The Serialize trait's job is to take your type and map it into the Serde data model by invoking exactly one of the methods on the given Serializer.**

This single method is the entire interface. It is generic over the serialization format (represented by the `Serializer` trait), enabling a single implementation to work across JSON, MessagePack, Postcard, and any other Serde-compatible format without modification.

## Method Signature

```rust
fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer
```

- **`&self`**: Immutable reference to the value being serialized
- **`serializer: S`**: Generic serializer implementing the Serializer trait
- **Result**: Returns either `S::Ok` (typically `()`) or `S::Error` (format-specific error type)
- **Generic Over Format**: The `S` type parameter is determined by the caller and unknown at trait definition time

## Responsibilities

### 1. Type Mapping

Map your Rust type into exactly one of the 29 Serde data model types:

```rust
// Example: i32 struct field
impl Serialize for i32 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_i32(*self)  // Map to i32 type
    }
}
```

### 2. Compound Type Handling

For collections, sequences, and structures, follow the three-phase pattern:

```rust
// Example: Vec<T>
impl<T: Serialize> Serialize for Vec<T> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(self.len()))?;
        for element in self {
            seq.serialize_element(element)?;
        }
        seq.end()
    }
}
```

**Three phases**:
1. **Initiate**: Call `serialize_seq()`, `serialize_map()`, `serialize_struct()`, etc.
2. **Serialize elements**: Call `serialize_element()`, `serialize_entry()`, etc.
3. **Finalize**: Call `end()`

### 3. Enum Handling

For enums, invoke the appropriate variant serialization method:

```rust
// Externally tagged (default)
impl Serialize for Color {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match self {
            Color::Red => serializer.serialize_unit_variant("Color", 0, "Red"),
            Color::Green => serializer.serialize_unit_variant("Color", 1, "Green"),
        }
    }
}
```

## Implementation Patterns by Type

### Primitives

```rust
impl Serialize for bool {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_bool(*self)
    }
}

impl Serialize for i32 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_i32(*self)
    }
}

impl Serialize for f64 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_f64(*self)
    }
}

impl Serialize for char {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_char(*self)
    }
}
```

### String and Bytes

```rust
impl Serialize for str {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_str(self)
    }
}

impl Serialize for [u8] {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_bytes(self)
    }
}
```

### Option

```rust
impl<T: Serialize> Serialize for Option<T> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        match self {
            None => serializer.serialize_none(),
            Some(value) => serializer.serialize_some(value),
        }
    }
}
```

### Sequences

```rust
impl<T: Serialize> Serialize for Vec<T> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        let mut seq = serializer.serialize_seq(Some(self.len()))?;
        for element in self {
            seq.serialize_element(element)?;
        }
        seq.end()
    }
}
```

### Tuples

```rust
// Tuple length is known at compile time
impl<T0: Serialize, T1: Serialize> Serialize for (T0, T1) {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        let mut tuple = serializer.serialize_tuple(2)?;
        tuple.serialize_element(&self.0)?;
        tuple.serialize_element(&self.1)?;
        tuple.end()
    }
}
```

### Tuple Structs

```rust
struct Point(i32, i32);

impl Serialize for Point {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        let mut tuple = serializer.serialize_tuple_struct("Point", 2)?;
        tuple.serialize_element(&self.0)?;
        tuple.serialize_element(&self.1)?;
        tuple.end()
    }
}
```

### Newtype Structs

```rust
struct Millimeters(u32);

impl Serialize for Millimeters {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_newtype_struct("Millimeters", &self.0)
    }
}
```

### Structs

```rust
struct Point { x: i32, y: i32 }

impl Serialize for Point {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        let mut state = serializer.serialize_struct("Point", 2)?;
        state.serialize_field("x", &self.x)?;
        state.serialize_field("y", &self.y)?;
        state.end()
    }
}
```

### Maps

```rust
impl<K: Serialize, V: Serialize> Serialize for HashMap<K, V> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        let mut map = serializer.serialize_map(Some(self.len()))?;
        for (k, v) in self {
            map.serialize_entry(k, v)?;
        }
        map.end()
    }
}
```

### Unit Types

```rust
impl Serialize for () {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_unit()
    }
}

struct Unit;

impl Serialize for Unit {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        serializer.serialize_unit_struct("Unit")
    }
}
```

### Unit Variants

```rust
impl Serialize for Color {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: Serializer {
        match self {
            Color::Red => serializer.serialize_unit_variant("Color", 0, "Red"),
        }
    }
}
```

## Provided Implementations

Serde provides Serialize implementations for:

- All primitive types (bool, i8-i128, u8-u128, f32, f64, char)
- String types (str, String, OsStr, OsString)
- Byte types (&[u8], Vec<u8>, etc.)
- Standard collections (Vec, HashMap, BTreeMap, HashSet, BTreeSet)
- Option, Result (when variants implement Serialize)
- Common library types (Path, PathBuf, Instant, Duration, etc.)
- Tuples of all sizes (0 to 16 elements)

## Special Behaviors

### Option Serialization

**JSON Example**:
- `Option::None` serializes as `null`
- `Option::Some(value)` serializes as just the value (no wrapper)

```rust
let opt = Some(42);
// JSON: 42 (not {"Some": 42})
```

### Bytes Serialization

Some formats optimize byte array handling:
- JSON: Base64 encoding with padding
- Postcard: Raw bytes in sequence
- MessagePack: Binary format

### Newtype Struct Transparency

Serializers are encouraged to treat newtype structs as insignificant wrappers:

```rust
struct Millimeters(u32);

let mm = Millimeters(5);
// Serializer should treat as transparent to u32
// JSON: 5 (not {"Millimeters": 5})
```

## Error Handling

All serialization methods return `Result<_, S::Error>`:

```rust
let mut seq = serializer.serialize_seq(Some(self.len()))?;  // Can fail
for element in self {
    seq.serialize_element(element)?;  // Can fail
}
seq.end()  // Can fail
```

**Error propagation**: Errors bubble up immediately; no partial serialization is recovered.

## Lifetime and Borrowing

- **No lifetime parameters**: Serialize trait takes no lifetime parameters
- **Borrowed access**: Implementation receives `&self` (borrowed reference)
- **Format-specific lifetime**: Serializer may require lifetime constraints (unusual)

## Interaction with Derive Macro

The `#[derive(Serialize)]` macro automatically generates implementations following these patterns:

- **Default tagging** for enums: Externally tagged
- **Default field ordering**: Source order
- **Customization**: Via `#[serde(...)]` attributes
- **Optimization**: Generated code optimized for specific struct/enum shape

## Key Guarantees

1. **Format-agnostic**: A single impl works for all formats
2. **Type safety**: No unsafe code required; type system ensures correctness
3. **No allocation required**: Serialization can be zero-allocation (format-dependent)
4. **Deterministic**: Same input produces same output for same format
5. **Composable**: Serialize implementations can be nested arbitrarily

## Common Pitfalls

### 1. Violating "Exactly One" Contract

```rust
// WRONG: Invokes multiple types
fn serialize<S>(&self, s: S) -> Result<S::Ok, S::Error> {
    s.serialize_i32(self.x)?;
    s.serialize_i32(self.y)?;  // ← Only second one is valid
}
```

**Correct**: Use `serialize_struct()` instead.

### 2. Forgetting Serialization in Compounds

```rust
// WRONG: Missing phase (doesn't call end())
fn serialize<S>(&self, s: S) -> Result<S::Ok, S::Error> {
    let mut seq = s.serialize_seq(Some(self.len()))?;
    for elem in self {
        seq.serialize_element(elem)?;
    }
    // Missing: seq.end()?
    Ok(())  // ← Wrong return type
}
```

**Correct**: Call `seq.end()` and return its result.

### 3. Wrong Type Encoding

```rust
// WRONG: Field is a tuple but serialized as sequence
struct Pair { x: i32, y: i32 }

fn serialize<S>(&self, s: S) -> Result<S::Ok, S::Error> {
    let mut seq = s.serialize_seq(Some(2))?;  // ← Wrong! Should be struct
    // ...
}
```

**Correct**: Use `serialize_struct()` for struct types.

---

## References

- https://docs.rs/serde/latest/serde/trait.Serialize.html
- https://serde.rs/impl-serialize.html
- https://serde.rs/custom-serialization.html
