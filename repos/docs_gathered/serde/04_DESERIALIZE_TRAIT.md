# Deserialize Trait Specification

**Source**: https://docs.rs/serde/latest/serde/trait.Deserialize.html
**Accessed**: 2026-04-04

## Trait Definition

```rust
pub trait Deserialize<'de>: Sized {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>;
}
```

## Core Contract

**The Deserialize trait is a data structure that can be deserialized from any data format supported by Serde.**

The trait maps external data into the Serde data model by providing the Deserializer with a Visitor that receives the various types. It is generic over the deserialization format (represented by the `Deserializer` trait), enabling a single implementation to work across JSON, MessagePack, Postcard, and other formats.

## Lifetime Parameter: 'de

The `'de` lifetime is critical to understanding Serde deserialization.

### Definition

The `'de` lifetime represents the lifetime of data that **may be borrowed** by the deserialized type.

### Borrowing Contract

**Every lifetime of data borrowed by a type must be constrained by the `'de` lifetime.**

Example:

```rust
// Struct with borrowed data
struct Config<'a> {
    name: &'a str,
    values: Vec<i32>,
}

impl<'de> Deserialize<'de> for Config<'de> {
    fn deserialize<D>(d: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>
    {
        // name: &str is borrowed from input with lifetime 'de
        // The 'de lifetime in Config<'de> ensures this safety
    }
}
```

### Implicit Borrowing

**Fields of type `&str` and `&[u8]` implicitly borrow from the input:**

```rust
#[derive(Deserialize)]
struct Message {
    text: String,           // Owned: no borrow
    label: &'de str,        // Borrowed from input
    data: &'de [u8],        // Borrowed from input
}
```

### Explicit Borrowing

Other types can opt into borrowing via `#[serde(borrow)]`:

```rust
#[derive(Deserialize)]
struct Message<'a> {
    content: Cow<'a, str>,  // Can borrow if input allows

    #[serde(borrow)]
    values: &'a [u8],       // Explicitly borrow
}
```

### Lifetime Constraints

When a type borrows with lifetime `'a`, the impl must be:

```rust
impl<'de, 'a> Deserialize<'de> for MyType<'a>
where
    'de: 'a,  // Input lifetime outlives borrowed lifetime
```

The `'de: 'a` bound ensures input data outlives the borrowed references.

---

## Method Signature

```rust
fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
where
    D: Deserializer<'de>
```

- **`deserializer: D`**: Generic deserializer for the format (unknown at trait definition time)
- **Result**: `Self::Ok` (the deserialized type) or `D::Error` (format-specific error)
- **No self**: Takes only the deserializer; doesn't receive any instance data

---

## Responsibilities

### 1. Provide a Visitor

The primary responsibility is to create and provide a Visitor to the Deserializer:

```rust
impl<'de> Deserialize<'de> for i32 {
    fn deserialize<D>(deserializer: D) -> Result<i32, D::Error>
    where
        D: Deserializer<'de>
    {
        struct I32Visitor;

        impl<'de> Visitor<'de> for I32Visitor {
            type Value = i32;

            fn expecting(&self, fmt: &mut fmt::Formatter) -> fmt::Result {
                fmt.write_str("an integer between -2^31 and 2^31")
            }

            fn visit_i32<E>(self, value: i32) -> Result<i32, E> {
                Ok(value)
            }

            fn visit_i64<E>(self, value: i64) -> Result<i32, E>
            where
                E: Error
            {
                i32::try_from(value)
                    .map_err(|_| E::custom("i32 out of range"))
            }
        }

        deserializer.deserialize_i32(I32Visitor)
    }
}
```

### 2. Handle Type Hints

Pass appropriate type hints to the deserializer:

```rust
impl<'de> Deserialize<'de> for String {
    fn deserialize<D>(deserializer: D) -> Result<String, D::Error>
    where
        D: Deserializer<'de>
    {
        deserializer.deserialize_string(StringVisitor)
    }
}

impl<'de, T: Deserialize<'de>> Deserialize<'de> for Vec<T> {
    fn deserialize<D>(deserializer: D) -> Result<Vec<T>, D::Error>
    where
        D: Deserializer<'de>
    {
        deserializer.deserialize_seq(VecVisitor)
    }
}
```

### 3. Handle Multiple Input Types

Visitors often handle multiple input types via visitor methods:

```rust
impl<'de> Visitor<'de> for I32Visitor {
    type Value = i32;

    fn expecting(&self, fmt: &mut fmt::Formatter) -> fmt::Result {
        fmt.write_str("an integer")
    }

    fn visit_i32<E>(self, value: i32) -> Result<i32, E> {
        Ok(value)
    }

    fn visit_u32<E>(self, value: u32) -> Result<i32, E>
    where E: Error {
        i32::try_from(value)
            .map_err(|_| E::custom("overflow"))
    }

    fn visit_i64<E>(self, value: i64) -> Result<i32, E>
    where E: Error {
        i32::try_from(value)
            .map_err(|_| E::custom("overflow"))
    }

    fn visit_u64<E>(self, value: u64) -> Result<i32, E>
    where E: Error {
        i32::try_from(value)
            .map_err(|_| E::custom("overflow"))
    }
}
```

---

## Implementation Patterns

### Primitives

```rust
impl<'de> Deserialize<'de> for bool {
    fn deserialize<D>(deserializer: D) -> Result<bool, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_bool(BoolVisitor)
    }
}

impl<'de> Deserialize<'de> for f64 {
    fn deserialize<D>(deserializer: D) -> Result<f64, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_f64(F64Visitor)
    }
}
```

### String and Bytes

```rust
impl<'de> Deserialize<'de> for String {
    fn deserialize<D>(deserializer: D) -> Result<String, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_string(StringVisitor)
    }
}

impl<'de> Deserialize<'de> for Vec<u8> {
    fn deserialize<D>(deserializer: D) -> Result<Vec<u8>, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_byte_buf(ByteBufVisitor)
    }
}
```

### Collections

```rust
impl<'de, T: Deserialize<'de>> Deserialize<'de> for Vec<T> {
    fn deserialize<D>(deserializer: D) -> Result<Vec<T>, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_seq(SeqVisitor)
    }
}

impl<'de, K: Deserialize<'de>, V: Deserialize<'de>> Deserialize<'de> for HashMap<K, V> {
    fn deserialize<D>(deserializer: D) -> Result<HashMap<K, V>, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_map(MapVisitor)
    }
}
```

### Tuples

```rust
impl<'de, T0: Deserialize<'de>, T1: Deserialize<'de>> Deserialize<'de> for (T0, T1) {
    fn deserialize<D>(deserializer: D) -> Result<(T0, T1), D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_tuple(2, TupleVisitor)
    }
}
```

### Structs

```rust
impl<'de> Deserialize<'de> for Point {
    fn deserialize<D>(deserializer: D) -> Result<Point, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_struct("Point", &["x", "y"], PointVisitor)
    }
}
```

### Enums

```rust
impl<'de> Deserialize<'de> for Color {
    fn deserialize<D>(deserializer: D) -> Result<Color, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_enum("Color", &["Red", "Green", "Blue"], ColorVisitor)
    }
}
```

---

## Interaction with Deserializer

### Self-Describing Formats

For JSON and similar self-describing formats:

```rust
// Deserializer can ignore type hints and inspect content directly
impl<'de> Deserialize<'de> for Value {
    fn deserialize<D>(deserializer: D) -> Result<Value, D::Error>
    where D: Deserializer<'de> {
        // JSON deserializer ignores the hint and just calls
        // the visit method matching the actual input type
        deserializer.deserialize_any(ValueVisitor)
    }
}
```

### Non-Self-Describing Formats

For Postcard and binary formats:

```rust
// Deserializer respects type hints to interpret compact data
impl<'de> Deserialize<'de> for MyType {
    fn deserialize<D>(deserializer: D) -> Result<MyType, D::Error>
    where D: Deserializer<'de> {
        // Postcard relies on the hint to know how to parse next bytes
        deserializer.deserialize_struct("MyType", &["field"], MyVisitor)
    }
}
```

---

## Provided Implementations

Serde provides Deserialize implementations for:

- All primitive types
- String types (str, String, OsStr, OsString)
- Byte types (&[u8], Vec<u8>)
- Standard collections (Vec, HashMap, BTreeMap, HashSet, BTreeSet)
- Option, Result
- Common library types (Path, PathBuf, Instant, Duration)
- Tuples (0 to 16 elements)
- Unit type ()

---

## Lifetime Misconceptions

### ❌ WRONG: Deserialize<'static>

```rust
T: Deserialize<'static>  // WRONG!
```

This means the type cannot borrow at all, which defeats the purpose.

### ❌ WRONG: Deserialize<'de> + 'static

```rust
T: Deserialize<'de> + 'static  // WRONG!
```

Cannot be both: `'static` means no borrowed lifetime, `'de` implies possible borrowing.

### ✅ CORRECT: for<'de> Deserialize<'de>

```rust
T: for<'de> Deserialize<'de>
```

Equivalent to `DeserializeOwned`; means "for any borrowed lifetime that may be needed."

### ✅ CORRECT: Deserialize<'a> with 'de: 'a

```rust
impl<'de, 'a> Deserialize<'de> for Type<'a>
where
    'de: 'a,  // Input outlives borrowed data
{ ... }
```

---

## Error Handling

Errors propagate immediately:

```rust
impl<'de, T: Deserialize<'de>> Deserialize<'de> for Vec<T> {
    fn deserialize<D>(deserializer: D) -> Result<Vec<T>, D::Error>
    where D: Deserializer<'de> {
        struct VecVisitor<T>(PhantomData<T>);

        impl<'de, T: Deserialize<'de>> Visitor<'de> for VecVisitor<T> {
            type Value = Vec<T>;

            fn visit_seq<A>(self, mut seq: A) -> Result<Vec<T>, A::Error>
            where A: SeqAccess<'de> {
                let mut vec = Vec::new();
                while let Some(elem) = seq.next_element()? {  // Error propagates
                    vec.push(elem);
                }
                Ok(vec)
            }
        }

        deserializer.deserialize_seq(VecVisitor(PhantomData))
    }
}
```

---

## References

- https://docs.rs/serde/latest/serde/trait.Deserialize.html
- https://serde.rs/impl-deserialize.html
- https://serde.rs/lifetimes.html
