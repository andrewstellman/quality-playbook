# Container Attributes (Complete Specification)

**Source**: https://serde.rs/container-attrs.html
**Accessed**: 2026-04-04

## Overview

Container attributes modify the behavior of `#[derive(Serialize, Deserialize)]` on structs and enums. They affect how the entire type is serialized and deserialized.

**Contract**: Container attributes override default derive macro behavior for top-level type representation.

---

## Attribute Reference

### #[serde(rename = "name")]

**Scope**: Structs and enums

**Purpose**: Serialize/deserialize using an alternate name instead of the Rust identifier.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(rename = "MyAlias")]
struct MyStruct { ... }
```

**Serialization Contract**: The struct is serialized with name "MyAlias" instead of "MyStruct".

**Deserialization Contract**: Input expecting "MyAlias" deserializes to this struct.

**Separate Serialize/Deserialize Names**:

```rust
#[serde(rename(serialize = "SendName", deserialize = "ReceiveName"))]
```

---

### #[serde(rename_all = "...")]

**Scope**: Structs (applies to all fields), Enums (applies to all variants)

**Purpose**: Apply case conversion to all fields or variants automatically.

**Supported Cases**:
- `"lowercase"` — lowercase
- `"UPPERCASE"` — UPPERCASE
- `"PascalCase"` — PascalCase
- `"camelCase"` — camelCase
- `"snake_case"` — snake_case
- `"SCREAMING_SNAKE_CASE"` — SCREAMING_SNAKE_CASE
- `"kebab-case"` — kebab-case
- `"SCREAMING-KEBAB-CASE"` — SCREAMING-KEBAB-CASE

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Point {
    x_coordinate: i32,  // Serialized as "xCoordinate"
    y_coordinate: i32,  // Serialized as "yCoordinate"
}
```

**Enum Example**:

```rust
#[serde(rename_all = "PascalCase")]
enum Color {
    dark_red,      // Serialized as "DarkRed"
    light_green,   // Serialized as "LightGreen"
}
```

**Separate Serialize/Deserialize Cases**:

```rust
#[serde(rename_all(serialize = "camelCase", deserialize = "snake_case"))]
```

---

### #[serde(rename_all_fields = "...")]

**Scope**: Enums only

**Purpose**: Apply `rename_all` to struct variant fields within an enum.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
enum E {
    #[serde(rename_all_fields = "camelCase")]
    A { x_coordinate: i32, y_coordinate: i32 },

    #[serde(rename_all_fields = "SCREAMING_SNAKE_CASE")]
    B { user_name: String, user_age: u32 },
}
```

**Contract**: Each variant can have its own field naming convention.

**Separate Rules**:

```rust
#[serde(rename_all_fields(serialize = "camelCase", deserialize = "snake_case"))]
```

---

### #[serde(deny_unknown_fields)]

**Scope**: Structs and enums

**Purpose**: Trigger an error during deserialization if unknown fields are encountered.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    name: String,
    value: i32,
}
```

**Deserialization Contract**:
- If input contains only known fields: ✅ Success
- If input contains unknown fields: ❌ Error with "unknown field" message

**JSON Example**:

```json
// Valid
{"name": "test", "value": 42}

// Invalid - triggers error
{"name": "test", "value": 42, "unknown_field": "oops"}
```

**Default Behavior**: By default, unknown fields are silently ignored for self-describing formats like JSON.

**Incompatibilities**:
- ❌ Incompatible with `#[serde(flatten)]` — Known bugs in multiple scenarios
- ❌ Incompatible with `#[serde(skip)]` — Skipped fields treated as unknown

---

### #[serde(tag = "type")]

**Scope**: Enums only

**Purpose**: Use internally tagged enum representation (tag field embedded in content).

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(tag = "type")]
enum Message {
    Request { id: String, method: String },
    Response { result: serde_json::Value },
}
```

**Serialization Contract**:
- Struct variant: `{"type": "Request", "id": "...", "method": "..."}`
- Newtype variant (struct): `{"type": "Var", ...fields...}`
- Unit variant: `{"type": "Null"}`

**Deserialization Contract**: Deserializer reads the "type" field first to identify variant.

**Supported Variant Types**:
- ✅ Struct variants
- ✅ Newtype variants containing structs/maps
- ✅ Unit variants
- ❌ Tuple variants (compile-time error)
- ❌ Newtype variants containing primitives/sequences (compile-time error)

**Alloc Requirement**: Requires "alloc" feature for deserialization.

---

### #[serde(tag = "t", content = "c")]

**Scope**: Enums only

**Purpose**: Use adjacently tagged enum representation (separate tag and content fields).

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(tag = "t", content = "c")]
enum Result {
    Ok(i32),
    Err(String),
}
```

**Serialization Contract**:
- `Ok(42)` → `{"t": "Ok", "c": 42}`
- `Err("error")` → `{"t": "Err", "c": "error"}`

**Deserialization Contract**: Two fields identify and contain the variant.

**Supported Variant Types**: All variant types (unit, newtype, tuple, struct).

**Alloc Requirement**: Requires "alloc" feature for deserialization.

---

### #[serde(untagged)]

**Scope**: Enums only

**Purpose**: Use untagged enum representation (no explicit discriminator).

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(untagged)]
enum Message {
    Request { id: String, method: String },
    Number(i32),
}
```

**Serialization Contract**: No tag in output; each variant serialized directly.

**Deserialization Contract**: Tries each variant in order; first match wins.

**Supported Variant Types**: All variant types.

**Performance Note**: "The implementation approach used by `untagged` can be costly" in performance scenarios.

**Alloc Requirement**: Requires "alloc" feature for deserialization.

**Many Known Issues**: See 14_ENUM_REPRESENTATIONS.md and 19_KNOWN_ISSUES.md.

---

### #[serde(bound = "T: MyTrait")]

**Scope**: Structs and enums

**Purpose**: Specify custom trait bounds for generated Serialize/Deserialize impls.

**Specification**:

```rust
#[derive(Serialize)]
#[serde(bound = "T: Serialize")]
struct Wrapper<T> { value: T }
```

**Contract**: Overrides Serde's default trait bound inference.

**Use Case**: When Serde's automatic bound inference is too restrictive or incorrect.

**Separate Bounds**:

```rust
#[serde(bound(serialize = "T: Serialize", deserialize = "T: Deserialize<'de>"))]
```

**Default Inference**: Without explicit bounds, Serde infers bounds based on which trait bounds are needed for the derived methods.

---

### #[serde(default)]

**Scope**: Structs only

**Purpose**: Use type's `Default::default()` implementation for missing fields during deserialization.

**Specification**:

```rust
#[derive(Deserialize)]
struct Config {
    required_field: String,
    #[serde(default)]
    optional_field: i32,  // Uses Default::default() if missing
}
```

**Deserialization Contract**:
- If field present in input: deserialize normally
- If field missing in input: use `Default::default()`

**Container-Level Usage**: Can apply to entire struct:

```rust
#[derive(Deserialize)]
#[serde(default)]
struct Config { ... }
// All fields use default if missing
```

---

### #[serde(default = "path")]

**Scope**: Structs only

**Purpose**: Specify custom function to provide default values.

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

**Function Signature**: Must return the field type and take no arguments.

```rust
fn default_fn() -> T { ... }
```

---

### #[serde(remote = "...")]

**Scope**: Structs only

**Purpose**: Derive Serialize/Deserialize for external (foreign) types.

**Specification**:

```rust
#[derive(Serialize)]
#[serde(remote = "external_crate::ExternalType")]
struct Remote {
    field1: Type,
    field2: Type,
}
```

**Contract**: Must be paired with `#[serde(with = "Remote")]` on fields using this type.

**Orphan Rule Compliance**: Works around Rust's orphan rule without violating it.

**Requires**:
- Exact field match with remote type
- For private fields: provide getters via `#[serde(getter = "...")]`
- For reconstruction: implement `From<Remote> for ExternalType`

---

### #[serde(transparent)]

**Scope**: Structs with exactly one field

**Purpose**: Serialize newtype struct identically to its inner field.

**Specification**:

```rust
#[derive(Serialize, Deserialize)]
#[serde(transparent)]
struct Millimeters(u32);

let mm = Millimeters(5);
// Serializes as: 5 (not {"Millimeters": 5})
```

**Serialization Contract**: Wrapper is completely transparent; inner value serialized as-is.

**Deserialization Contract**: Input expected to be the inner type; wraps it automatically.

**Applicability**: Works analogously to `#[repr(transparent)]` in C layout.

---

### #[serde(from = "FromType")]

**Scope**: Structs and enums

**Purpose**: Deserialize via intermediate type using `From` trait.

**Specification**:

```rust
#[derive(Deserialize)]
#[serde(from = "String")]
struct MyType { ... }

impl From<String> for MyType {
    fn from(s: String) -> Self { ... }
}
```

**Contract**:
1. Deserialize to `FromType` first
2. Convert using `From<FromType> for Self`
3. Return constructed value

**Use Case**: When deserialization requires preprocessing or validation.

---

### #[serde(try_from = "TryFromType")]

**Scope**: Structs and enums

**Purpose**: Deserialize via intermediate type using `TryFrom` trait.

**Specification**:

```rust
#[derive(Deserialize)]
#[serde(try_from = "String")]
struct ValidString { ... }

impl TryFrom<String> for ValidString {
    type Error = /* error type */;
    fn try_from(s: String) -> Result<Self, Self::Error> { ... }
}
```

**Contract**:
1. Deserialize to `TryFromType` first
2. Convert using `TryFrom<TryFromType> for Self`
3. Propagate conversion errors as deserialization errors

**Error Handling**: Conversion errors become deserialization errors with custom messages.

---

### #[serde(into = "IntoType")]

**Scope**: Structs and enums

**Purpose**: Serialize by converting via `Into` trait.

**Specification**:

```rust
#[derive(Serialize)]
#[serde(into = "String")]
struct MyType { ... }

impl From<MyType> for String {
    fn from(m: MyType) -> Self { ... }
}
```

**Contract**: Convert to `IntoType` and serialize that instead.

**Equivalent to**: `impl Into<String> for MyType` (which is auto-implemented from `From`).

---

### #[serde(crate = "...")]

**Scope**: Structs and enums

**Purpose**: Specify custom serde crate path for generated code references.

**Specification**:

```rust
#[derive(Serialize)]
#[serde(crate = "my_serde")]
struct MyStruct { ... }
```

**Contract**: Generated code references serde traits from the specified path.

**Use Case**: When serde is renamed or re-exported:

```rust
use serde as my_serde;

#[derive(Serialize)]
#[serde(crate = "my_serde")]
struct MyStruct { ... }
```

---

### #[serde(expecting = "...")]

**Scope**: Structs and enums

**Purpose**: Customize error messages for deserialization failures and untagged enum fallback messaging.

**Specification**:

```rust
#[derive(Deserialize)]
#[serde(expecting = "a greeting message")]
struct Greeting { ... }
```

**Deserialization Error**: "expected a greeting message" instead of generic message.

**Untagged Enum Use**: Provides better error context when untagged matching fails.

---

### #[serde(variant_identifier)] and #[serde(field_identifier)]

**Scope**: Specialized (Visitor implementations)

**Purpose**: Deserialize variant/field names as either strings or integers depending on format.

**Variant Identifier Specification**:

```rust
#[derive(Deserialize)]
#[serde(variant_identifier)]
enum E {
    A,
    B,
}
```

**Contract**:
- If format provides variant index: accepts integer
- If format provides variant name: accepts string

**Field Identifier Specification**:

```rust
#[derive(Deserialize)]
#[serde(field_identifier)]
enum Fields {
    Name,
    Value,
}
```

**Contract**: Similar to variant identifier; accepts format's field representation.

---

## Attribute Combination Rules

### Compatible Combinations

- ✅ `rename` + `rename_all` (rename_all applies after rename)
- ✅ `tag = "..."` + `deny_unknown_fields`
- ✅ `deny_unknown_fields` + (most attributes except flatten/skip)
- ✅ `from = "..."` + other attributes

### Incompatible Combinations

- ❌ `flatten` + `deny_unknown_fields` (documented bugs)
- ❌ `skip` + `deny_unknown_fields` (documented incompatibility)
- ❌ `tag = "..."` + `untagged` (conflicting tagging strategies)
- ❌ Multiple tagging strategies on same enum (e.g., internally + adjacently tagged)

---

## Default Behavior (No Attributes)

- **Struct name**: Uses Rust identifier as-is
- **Field names**: Uses Rust identifiers as-is
- **Enum representation**: Externally tagged (default)
- **Unknown fields**: Silently ignored (default)
- **Enum variants**: Named by Rust identifier

---

## References

- https://serde.rs/container-attrs.html
- https://serde.rs/data-model.html
- https://serde.rs/enum-representations.html
