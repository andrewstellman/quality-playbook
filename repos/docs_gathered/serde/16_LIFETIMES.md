# Deserializer Lifetimes and Borrowing Specification

**Source**: https://serde.rs/lifetimes.html
**Accessed**: 2026-04-04

## Core Concept

The `'de` lifetime parameter in Deserialize and Deserializer traits enables safe, efficient zero-copy deserialization.

**Critical Contract**: This lifetime is what enables Serde to safely perform efficient zero-copy deserialization across a variety of data formats.

---

## The 'de Lifetime

### Definition

```rust
pub trait Deserialize<'de>: Sized { ... }
pub trait Deserializer<'de> { ... }
```

The `'de` lifetime represents the **lifetime of data that may be borrowed** by the deserialized type.

### Meaning in Context

- `'de` = Input data lifetime
- Data with lifetime `'de` is guaranteed to remain valid during deserialization
- Borrowed references in deserialized types must not outlive the input

### Safety Guarantee

Rust's lifetime system ensures:
1. Input data outlives any references to it
2. Borrowed references in deserialized types are valid
3. No dangling pointers result from losing the input data

---

## Two Trait Bound Patterns

### Pattern 1: Caller Provides Lifetime

**When the caller has data with a known lifetime:**

```rust
pub fn deserialize_from_str<'de, T>(s: &'de str) -> Result<T, Error>
where
    T: Deserialize<'de>,
{
    let mut deserializer = JsonDeserializer::from_str(s);
    T::deserialize(&mut deserializer)
}
```

**Contract**:
- Caller provides `&'de str` with lifetime `'de`
- Type `T` can borrow from input with lifetime `'de`
- Lifetime `'de` is determined by the caller

**Common Pattern**: `from_str`, `from_slice`, `from_bytes`

### Pattern 2: Callee Decides Lifetime

**When the input data will be discarded before returning:**

```rust
pub fn deserialize_from_reader<T>(reader: impl Read) -> Result<T, Error>
where
    T: DeserializeOwned,
{
    // Data is read, deserialized, then thrown away
    let json = read_all(reader)?;
    serde_json::from_str(&json)
}
```

**Contract**:
- Input data is used only for deserialization, then discarded
- Type `T` cannot borrow from input (would be invalid after reader closes)
- `DeserializeOwned` = `for<'de> Deserialize<'de>` (any lifetime works)

**Common Pattern**: `from_reader`, `from_slice` where data is internal

### Equivalence

```rust
// These are equivalent:
T: DeserializeOwned
T: for<'de> Deserialize<'de>
```

Both mean: "T can be deserialized regardless of input data lifetime"

---

## Three Data Flavors in Visitor

When deserializing, the Visitor trait provides three ways to receive data:

### 1. Borrowed Data (visit_borrowed_*)

**Signature**:
```rust
fn visit_borrowed_str<E>(self, v: &'de str) -> Result<Self::Value, E>
```

**Contract**: Data is guaranteed to live as long as `'de` lifetime.

**Use Case**: Deserialize `&str` fields that borrow from input.

**Characteristic**: No allocation; direct pointer to input string.

### 2. Owned Data (visit_string, visit_byte_buf)

**Signature**:
```rust
fn visit_string<E>(self, v: String) -> Result<Self::Value, E>
fn visit_byte_buf<E>(self, v: Vec<u8>) -> Result<Self::Value, E>
```

**Contract**: Data is allocated; no borrowing constraint.

**Use Case**: When borrowing from input is impossible or undesired.

**Characteristic**: Always allocates; independent of input lifetime.

### 3. Transient Data (visit_str, visit_bytes)

**Signature**:
```rust
fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
fn visit_bytes<E>(self, v: &[u8]) -> Result<Self::Value, E>
```

**Contract**: Data is valid **only during the method call**.

**Use Case**: Data that may not outlive the call (e.g., from temporary buffer).

**Characteristic**: Cannot be stored in deserialized type; must be processed immediately.

### Visitor Hierarchy

```
Input Data Lifetime 'de
    ├── Borrowed (visit_borrowed_*) — &'de T
    │   └── Lifetime: 'de
    ├── Owned (visit_string, visit_byte_buf) — Owned T
    │   └── Lifetime: Arbitrary
    └── Transient (visit_str, visit_bytes) — &'_ T
        └── Lifetime: Limited to method call
```

---

## Borrowing Rules

### Implicit Borrowing

**String and byte fields borrow implicitly:**

```rust
#[derive(Deserialize)]
struct Message {
    text: &'de str,      // Implicitly borrows from 'de
    data: &'de [u8],     // Implicitly borrows from 'de
}
```

**No attribute needed**; the `&str` and `&[u8]` types signal borrowing intent.

### Explicit Borrowing with #[serde(borrow)]

**Other types require explicit annotation:**

```rust
#[derive(Deserialize)]
struct Message<'a> {
    content: Cow<'a, str>,           // WRONG without borrow attr

    #[serde(borrow)]
    content: Cow<'a, str>,           // CORRECT: explicit borrowing
}
```

**Contract**: The `#[serde(borrow)]` attribute tells Serde that this field can borrow from input.

**Result**: Serde generates code that attempts zero-copy deserialization for `Cow`.

### Cow Fallback Behavior

```rust
#[serde(borrow)]
value: Cow<'a, str>
```

**Behavior**:
- First attempt: Zero-copy deserialization (borrows from input)
- Fallback: Cloning (if input requires modification)
- Result: Works in all scenarios; always valid

---

## Lifetime Constraints

### When Type Borrows with Multiple Lifetimes

```rust
struct Message<'a, 'b> {
    from: &'a str,
    to: &'b str,
}

impl<'de, 'a, 'b> Deserialize<'de> for Message<'a, 'b>
where
    'de: 'a,     // Input outlives 'a
    'de: 'b,     // Input outlives 'b
{
    fn deserialize<D>(d: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        // ...
    }
}
```

**Contract**: Every borrowed lifetime must be constrained by `'de`.

**Reasoning**: If type borrows with lifetime `'a`, then input data (lifetime `'de`) must outlive `'a`.

### Simplified Rule

**Every borrowed lifetime in a type must satisfy `'de: lifetime`.**

### Generic Types with Bounds

```rust
struct Wrapper<'a, T: ?Sized> {
    data: &'a T,
}

impl<'de, 'a, T> Deserialize<'de> for Wrapper<'a, T>
where
    T: Deserialize<'de> + ?Sized,
    'de: 'a,
{
    fn deserialize<D>(d: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        // ...
    }
}
```

---

## Common Lifetime Mistakes

### ❌ WRONG: Deserialize<'static>

```rust
T: Deserialize<'static>
```

**Problem**: Means the type cannot borrow from input; defeats borrowing purpose.

**When it happens**: Misunderstanding that types must be 'static-owned.

**Why wrong**: Borrowing requires lifetime constraints; 'static forbids borrowing.

### ❌ WRONG: Deserialize<'de> + 'static

```rust
T: Deserialize<'de> + 'static
```

**Problem**: Contradictory bounds:
- `Deserialize<'de>` allows borrowing with lifetime 'de
- `'static` means no borrowed references

**Why wrong**: Can't both borrow from input and be 'static.

### ❌ WRONG: Explicit Lifetime Longer Than Input

```rust
fn deserialize_owned<'a, T>(s: &'static str) -> Result<T<'a>, Error>
where
    T: Deserialize<'a>,  // WRONG: 'a might exceed 'static
{
    // ...
}
```

**Problem**: Type might borrow with lifetime `'a`, but input is `'static`.

If `'a > 'static`, the type could outlive the input.

### ✅ CORRECT: for<'de> Deserialize<'de>

```rust
T: for<'de> Deserialize<'de>
```

**Meaning**: "For any lifetime 'de, T can be deserialized from input with that lifetime"

**Equivalent**: `T: DeserializeOwned`

**Use**: When you don't know the input lifetime and don't care if T borrows.

### ✅ CORRECT: Constrained Bounds

```rust
impl<'de, 'a> Deserialize<'de> for MyType<'a>
where
    'de: 'a,
{
    fn deserialize<D>(d: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        // ...
    }
}
```

**Meaning**: "Type borrows with lifetime 'a, which must not outlive input lifetime 'de"

**Correctness**: 'de: 'a ensures input outlives any borrowed references.

---

## Practical Scenarios

### Scenario 1: Zero-Copy from String Slice

```rust
#[derive(Deserialize)]
struct Config<'a> {
    name: &'a str,
    #[serde(borrow)]
    description: Cow<'a, str>,
}

let json = r#"{"name": "App", "description": "Desc"}"#;
let config: Config = serde_json::from_str(json)?;

// config.name borrows from json (lifetime = &json)
// No allocations occur unless description needs modification
```

### Scenario 2: Owned Data (no borrowing)

```rust
#[derive(Deserialize)]
struct Message {
    text: String,
    data: Vec<u8>,
}

let json = r#"{"text": "Hello", "data": "...base64..."}"#;
let msg: Message = serde_json::from_str(json)?;

// text and data own their data
// Can use msg after json is dropped
```

### Scenario 3: Generic Wrapper

```rust
#[derive(Deserialize)]
struct Wrapper<'a, T: Deserialize<'a>> {
    #[serde(borrow)]
    value: T,
}

// T can borrow with lifetime 'a, constrained by input 'de
```

### Scenario 4: Custom Deserializer

```rust
fn from_reader<R, T>(reader: R) -> Result<T, Error>
where
    R: Read,
    T: DeserializeOwned,  // No lifetime constraints
{
    let data = read_all(reader)?;
    serde_json::from_slice(&data)  // data is temporary; dropped after
}

// T must not borrow from data (data is temporary)
// T: DeserializeOwned ensures this is safe
```

---

## Why Lifetimes Matter

### Performance Benefit

Zero-copy deserialization avoids allocations:

```
Input JSON:  {"name": "John", "email": "john@example.com"}
             └──┬──────────────────────────────────────────┘
                 Bytes in memory; owned by caller

Without borrowing:
    → Allocate String for "John"
    → Copy bytes
    → Allocate String for email
    → Copy bytes

With borrowing (lifetimes):
    → Name points to original "John" (no copy)
    → Email points to original email address (no copy)
    → Zero allocations
```

### Safety Benefit

Rust's lifetime system guarantees:

```
struct Message<'a> {
    text: &'a str,  // Borrows from input
}

// ✅ SAFE: Input outlives message
let json = "...".to_string();
let msg: Message = serde_json::from_str(&json)?;
// json still valid; msg is valid

// ❌ COMPILE ERROR: Would be unsafe
fn get_msg<'a>() -> Message<'a> {
    let json = "...".to_string();
    serde_json::from_str(&json)  // ← Compile error: lifetime mismatch
}  // json dropped; Message<'a> would have dangling pointer
```

The compiler prevents these errors at compile time.

---

## Reference Hierarchy

```
DeserializeOwned (top)
    ↑
    │ (equivalent to)
    │
for<'de> Deserialize<'de>
    ↑
    │ (implies)
    │
Deserialize<'de> where type may borrow
    ↑
    │ (for specific lifetimes)
    │
Message<'a> where 'de: 'a
```

**Key insight**: As you go down the hierarchy, you lose flexibility but gain performance.

---

## References

- https://serde.rs/lifetimes.html
- https://docs.rs/serde/latest/serde/trait.Deserialize.html
- https://docs.rs/serde/latest/serde/trait.DeserializeOwned.html
