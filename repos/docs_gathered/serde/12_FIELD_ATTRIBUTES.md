# Field Attributes (Complete Specification)

**Source**: https://serde.rs/field-attrs.html
**Accessed**: 2026-04-04

## Overview

Field attributes modify how individual fields in structs and enum variants are serialized and deserialized. They apply at the field level, not the type level.

**Scope**: Struct fields and enum variant fields

---

## Attribute Reference

### #[serde(rename = "name")]

**Purpose**: Serialize/deserialize using an alternate field name.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
struct Person {
    #[serde(rename = "full_name")]
    name: String,
}
```

**Contract**: Field serialized as "full_name" instead of "name".

**JSON Example**:
```json
{ "full_name": "John Doe" }
```

**Separate Serialize/Deserialize Names**:

```rust
#[serde(rename(serialize = "sendName", deserialize = "receiveName"))]
field: String,
```

---

### #[serde(alias = "name")]

**Purpose**: Accept alternate name(s) during deserialization only (not serialization).

**Specification**:

```rust
#[derive(Deserialize)]
struct Config {
    #[serde(alias = "legacy_name")]
    current_name: String,
}
```

**Deserialization Contract**: Field accepts either "current_name" or "legacy_name" as input.

**Serialization Contract**: Always serializes as "current_name" (default name).

**Multiple Aliases**:

```rust
#[serde(alias = "name1", alias = "name2", alias = "name3")]
field: String,
```

**Use Case**: API versioning and backward compatibility.

---

### #[serde(default)]

**Purpose**: Use `Default::default()` for missing field during deserialization.

**Specification**:

```rust
#[derive(Deserialize)]
struct Config {
    required_field: String,
    #[serde(default)]
    timeout: u32,  // Uses Default::default() if missing
}
```

**Contract**: If field is absent from input, use `Default::default()`.

**Example**:
```rust
let json = r#"{"required_field": "test"}"#;
// timeout: 0 (default for u32)
```

---

### #[serde(default = "path")]

**Purpose**: Use custom function to provide default value.

**Specification**:

```rust
fn default_timeout() -> u32 { 30 }

#[derive(Deserialize)]
struct Config {
    name: String,
    #[serde(default = "default_timeout")]
    timeout_secs: u32,
}
```

**Function Contract**:
- Takes no arguments
- Returns field type `T`
- Can be function or const function

**Use Case**: Non-trivial defaults that aren't `Default::default()`.

---

### #[serde(flatten)]

**Purpose**: Flatten the contents of this field into the container.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
struct Config {
    name: String,
    #[serde(flatten)]
    database: DbConfig,
}

struct DbConfig {
    host: String,
    port: u16,
}
```

**Serialization Contract**: Fields of flattened struct appear alongside parent fields.

**JSON Example**:
```json
{
  "name": "myapp",
  "host": "localhost",
  "port": 5432
}
```

**Not**:
```json
{
  "name": "myapp",
  "database": { "host": "localhost", "port": 5432 }
}
```

**Deserialization Contract**: Same; flattened fields are part of parent field namespace.

**Incompatibilities**:
- ❌ Incompatible with `#[serde(deny_unknown_fields)]` — Multiple known issues
- ⚠️ Complex interactions with untagged enums

**Known Issues**: See 19_KNOWN_ISSUES.md for details.

---

### #[serde(skip)]

**Purpose**: Omit field from both serialization and deserialization.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
struct User {
    name: String,
    #[serde(skip)]
    internal_id: String,
}
```

**Serialization Contract**: Field is never serialized.

**Deserialization Contract**: Field is not expected in input; uses `Default::default()` if missing.

**Requirement**: Field type must implement `Default`.

**Incompatibility**: ❌ Incompatible with `#[serde(deny_unknown_fields)]`.

---

### #[serde(skip_serializing)]

**Purpose**: Exclude field from serialization only.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
struct User {
    name: String,
    #[serde(skip_serializing)]
    internal_state: InternalState,
}
```

**Serialization Contract**: Field is never included in output.

**Deserialization Contract**: Field is expected in input and deserialized normally.

**Attempting to Serialize**: If field is serialized anyway (e.g., via custom logic), it's treated as an error.

---

### #[serde(skip_deserializing)]

**Purpose**: Exclude field from deserialization only.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
struct Metadata {
    data: String,
    #[serde(skip_deserializing)]
    computed_hash: u64,
}
```

**Serialization Contract**: Field is serialized normally.

**Deserialization Contract**: Field is not expected in input; uses `Default::default()` if missing.

**Use Case**: Computed or derived fields that shouldn't be trusted from input.

---

### #[serde(skip_serializing_if = "condition")]

**Purpose**: Skip serialization of field if condition returns true.

**Specification**:

```rust
fn is_empty<T: AsRef<str>>(s: &T) -> bool {
    s.as_ref().is_empty()
}

#[derive(Serialize)]
struct Request {
    name: String,
    #[serde(skip_serializing_if = "is_empty")]
    description: String,
}
```

**Function Contract**:
- Takes `&T` where T is the field type
- Returns `bool`
- Signature: `fn(&T) -> bool`

**Serialization Contract**: Field is serialized if condition returns `false`; skipped if `true`.

**Example**:
```rust
let req = Request {
    name: "test".to_string(),
    description: String::new(),
};
// description is not serialized (is_empty returns true)
```

**Common Patterns**:

```rust
#[serde(skip_serializing_if = "Option::is_none")]
optional_field: Option<T>,

#[serde(skip_serializing_if = "Vec::is_empty")]
items: Vec<T>,

#[serde(skip_serializing_if = "String::is_empty")]
text: String,
```

---

### #[serde(serialize_with = "path")]

**Purpose**: Use custom serialization function for this field.

**Specification**:

```rust
fn serialize_custom<S>(value: &MyType, s: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    // Custom serialization logic
}

#[derive(Serialize)]
struct MyStruct {
    #[serde(serialize_with = "serialize_custom")]
    field: MyType,
}
```

**Function Contract**:
- Signature: `fn(&T, S) -> Result<S::Ok, S::Error> where S: Serializer`
- First parameter: field value reference
- Second parameter: serializer

**Use Case**: Format-specific or custom logic for individual fields.

---

### #[serde(deserialize_with = "path")]

**Purpose**: Use custom deserialization function for this field.

**Specification**:

```rust
fn deserialize_custom<'de, D>(d: D) -> Result<MyType, D::Error>
where
    D: Deserializer<'de>,
{
    // Custom deserialization logic
}

#[derive(Deserialize)]
struct MyStruct {
    #[serde(deserialize_with = "deserialize_custom")]
    field: MyType,
}
```

**Function Contract**:
- Signature: `fn(D) -> Result<T, D::Error> where D: Deserializer<'de>`
- Parameter: deserializer
- Returns: deserialized value

**Use Case**: Custom validation, type coercion, or format conversion.

---

### #[serde(with = "module")]

**Purpose**: Combine serialize_with and deserialize_with from a module.

**Specification**:

```rust
mod my_format {
    use serde::{Deserialize, Deserializer, Serialize, Serializer};

    pub fn serialize<S>(value: &MyType, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        // ...
    }

    pub fn deserialize<'de, D>(d: D) -> Result<MyType, D::Error>
    where
        D: Deserializer<'de>,
    {
        // ...
    }
}

#[derive(Serialize, Deserialize)]
struct MyStruct {
    #[serde(with = "my_format")]
    field: MyType,
}
```

**Contract**: Module must have `serialize` and `deserialize` functions.

**Equivalent To**:

```rust
#[serde(serialize_with = "my_format::serialize", deserialize_with = "my_format::deserialize")]
```

---

### #[serde(borrow)]

**Purpose**: Enable zero-copy deserialization for fields that can borrow from input.

**Specification**:

```rust
#[derive(Deserialize)]
struct Message<'a> {
    name: String,  // Owned

    #[serde(borrow)]
    text: &'a str,  // Borrowed

    #[serde(borrow)]
    data: Cow<'a, [u8]>,  // Can borrow or own
}
```

**Lifetime Contract**:
- Field with `'a` lifetime borrows from input with `'de` lifetime
- Rust ensures: `'de: 'a` (input outlives borrowed data)

**Implicit Borrowing**: Fields `&str` and `&[u8]` borrow implicitly without attribute.

**Explicit Borrowing**: Other types (Cow, custom types) require `#[serde(borrow)]`.

**Behavior with Cow**:
- Attempts zero-copy deserialization first
- Falls back to cloning if necessary
- No additional logic needed

---

### #[serde(bound = "T: Trait")]

**Purpose**: Specify custom trait bounds for Serialize/Deserialize implementations.

**Specification**:

```rust
#[serde(bound(serialize = "T: Serialize + MyTrait"))]
struct Wrapper<T> {
    value: T,
}
```

**Contract**: Override default trait bound inference with custom bounds.

**Use Case**: When Serde's inference is too restrictive or incorrect.

**Separate Bounds**:

```rust
#[serde(bound(
    serialize = "T: Serialize",
    deserialize = "T: Deserialize<'de>"
))]
```

---

### #[serde(getter = "path")]

**Purpose**: Provide getter function for private fields in remote types.

**Specification**:

```rust
#[derive(Serialize)]
#[serde(remote = "ExternalType")]
struct Remote {
    #[serde(getter = "ExternalType::get_private_field")]
    private_field: Type,
}
```

**Use Case**: When deriving for external types with private fields.

**Function Contract**: Must be accessible method on remote type.

---

## Attribute Combination Rules

### Compatible Combinations

- ✅ `rename` + `alias`
- ✅ `default` + `skip_deserializing`
- ✅ `serialize_with` + `deserialize_with`
- ✅ `skip_serializing_if` with other attrs
- ✅ `borrow` + `alias`

### Incompatible Combinations

- ❌ `skip` + `deny_unknown_fields` (parent attr; will error)
- ❌ `flatten` + `deny_unknown_fields` (parent attr; known issues)
- ❌ `serialize_with` + `skip_serializing` (conflicting intents)
- ❌ `deserialize_with` + `skip_deserializing` (conflicting intents)

---

## Default Behavior (No Attributes)

- **Field name**: Uses Rust identifier as-is
- **Serialization**: All fields serialized
- **Deserialization**: Field expected in input; uses default if missing (if type implements Default)
- **Borrowing**: `&str` and `&[u8]` borrow implicitly; others require `#[serde(borrow)]`

---

## Practical Examples

### Example 1: API Field Versioning

```rust
#[derive(Deserialize)]
struct ApiRequest {
    id: u32,
    #[serde(alias = "oldName", alias = "legacy_name")]
    name: String,
}

// Accepts any of: {"id": 1, "name": "..."}
//                  {"id": 1, "oldName": "..."}
//                  {"id": 1, "legacy_name": "..."}
```

### Example 2: Optional Configuration

```rust
#[derive(Deserialize)]
struct Config {
    required: String,
    #[serde(default = "default_timeout")]
    timeout: u32,
    #[serde(default)]
    debug: bool,
}

fn default_timeout() -> u32 { 30 }
```

### Example 3: Custom Serialization

```rust
fn serialize_timestamp<S>(ts: &SystemTime, s: S) -> Result<S::Ok, S::Error>
where S: Serializer {
    ts.duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
        .serialize(s)
}

#[derive(Serialize)]
struct Event {
    name: String,
    #[serde(serialize_with = "serialize_timestamp")]
    timestamp: SystemTime,
}
```

### Example 4: Flattened Configuration

```rust
#[derive(Serialize, Deserialize)]
struct AppConfig {
    app_name: String,
    #[serde(flatten)]
    database: DatabaseConfig,
    #[serde(flatten)]
    server: ServerConfig,
}

struct DatabaseConfig {
    db_host: String,
    db_port: u16,
}

struct ServerConfig {
    port: u16,
    workers: usize,
}

// Serialized as flat JSON:
// {"app_name": "...", "db_host": "...", "db_port": 5432, "port": 8080, "workers": 4}
```

### Example 5: Zero-Copy Deserialization

```rust
#[derive(Deserialize)]
struct Message<'a> {
    id: u32,
    #[serde(borrow)]
    text: &'a str,  // Borrowed from JSON
    #[serde(borrow)]
    payload: Cow<'a, [u8]>,  // Can borrow or clone
}

// Deserializing from `{"id": 1, "text": "hello", "payload": "base64..."}`
// avoids allocating text; just uses pointer into JSON string
```

---

## References

- https://serde.rs/field-attrs.html
- https://serde.rs/container-attrs.html
- https://serde.rs/lifetimes.html
