# Known Issues and Documented Limitations

**Compiled from**: GitHub issues and Serde documentation
**Accessed**: 2026-04-04

## Critical Incompatibilities

### 1. flatten + deny_unknown_fields (Multiple Issues)

**Status**: Not officially supported

**GitHub Issues**:
- #1358: Combination of flattened internally-tagged enum and deny_unknown_fields results in unsatisfiable requirements
- #1547: Structs with nested flattens cannot be deserialized if deny_unknown_fields is set
- #1600: deny_unknown_fields incorrectly fails with flattened untagged enum
- #2283: flatten bypasses the deny_unknown_fields check
- #2384: Document that flatten + deny_unknown_fields works at least in simple cases
- #2634: deny_unknown_fields docs misleading

**Specification**:

The `#[serde(flatten)]` attribute and `#[serde(deny_unknown_fields)]` container attribute are fundamentally incompatible in most scenarios.

#### The Problem

When a struct field is flattened:
1. The flattened field's fields become part of the parent struct's field namespace
2. `deny_unknown_fields` checks for unknown fields by comparing against known field names
3. For flattened fields with optional fields, the deserializer cannot distinguish between:
   - A field not present in input (missing optional field)
   - A field unknown to this struct (should error with deny_unknown_fields)

#### Known Failure Cases

**Case 1: Flattened untagged enum with deny_unknown_fields**

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    name: String,
    #[serde(flatten)]
    variant: MyEnum,  // ← FAILS
}

#[derive(Deserialize)]
#[serde(untagged)]
enum MyEnum {
    A { a: String },
    B { b: String },
}
```

**Result**: Deserialization fails even with valid input that doesn't contain unknown fields.

**Case 2: Flattened internally-tagged enum with deny_unknown_fields**

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Wrapper {
    #[serde(flatten)]
    inner: TaggedEnum,  // ← FAILS
}

#[derive(Deserialize)]
#[serde(tag = "type")]
enum TaggedEnum {
    A { a: String },
    B { b: String },
}
```

**Result**: Panic or compilation error about unsatisfiable trait bounds.

**Case 3: Nested flattens with deny_unknown_fields**

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct A {
    #[serde(flatten)]
    b: B,
}

#[derive(Deserialize)]
struct B {
    #[serde(flatten)]
    c: C,
}

struct C { ... }
```

**Result**: Cannot deserialize even with correct input.

#### Workarounds

1. **Remove deny_unknown_fields** if flatten is required
2. **Use custom deserializer** that manually handles field rejection
3. **Restructure without flatten** if deny_unknown_fields is critical
4. **Use serde-ignored crate** for field tracking workarounds (limited effectiveness)

#### Official Documentation Status

Issue #2384 suggests Serde documentation should clarify that flatten + deny_unknown_fields "works at least in simple cases" — but what constitutes "simple" is undefined.

---

### 2. deny_unknown_fields + skip (Issue #2121)

**Status**: Not supported

**GitHub Issues**:
- #2121: 'deny_unknown_fields' and 'skip' not compatible
- #1164: Skipped fields still error as unknown

**Specification**:

The `#[serde(skip)]` attribute and `#[serde(deny_unknown_fields)]` container attribute are incompatible.

#### The Problem

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MyStruct {
    known_field: String,
    #[serde(skip)]
    skipped_field: String,
}
```

**Behavior**: When `skipped_field` appears in input, `deny_unknown_fields` treats it as an unknown field and raises an error.

**Root Cause**: The field is marked `skip` in the Serde impl, so it's not registered as a legitimate field for deny_unknown_fields checking.

#### Workarounds

**Option 1: Use custom deserialize_with**

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MyStruct {
    known_field: String,
    #[serde(deserialize_with = "ignore_field")]
    skipped_field: String,
}

fn ignore_field<'de, D>(_d: D) -> Result<(), D::Error>
where
    D: Deserializer<'de>,
{
    Ok(())
}
```

**Option 2: Use alias instead of skip**

```rust
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct MyStruct {
    known_field: String,
    #[serde(alias = "old_field_name", skip_serializing)]
    new_field: String,
}
```

---

### 3. Untagged Enum Edge Cases (Multiple Issues)

**Status**: Many documented edge cases with no clean fixes

#### Issue #1560: Empty Variants

**Problem**: Untagged enums with empty variants deserialize in "unintuitive ways"

```rust
#[serde(untagged)]
enum E {
    A {},
    B(String),
}
```

May serialize to `null` instead of expected representation.

#### Issue #2447: Optional Fields Failure

**Problem**: Deserialization fails on what looks like correct input

```rust
#[serde(untagged)]
enum E {
    A { required: String, optional: Option<String> },
    B { other: i32 },
}
```

When deserializing valid input, may fail because optional field matching is ambiguous.

**Workaround**: Rewrite optional fields as struct variants instead.

#### Issue #2607: Custom Deserializer Ignored

**Problem**: `#[serde(untagged)]` ignores custom `deserialize_struct` implementations

The untagged enum implementation:
1. Buffers input to `Content` structure (intermediate representation)
2. Attempts each variant's deserialization against the Content
3. Custom deserializers never see the original Deserializer (receives Content deserializer instead)

**Impact**: Custom format-specific logic is bypassed.

#### Issue #2724: Numeric Map Keys

**Problem**: Untagged enum fails with numeric map keys

```rust
#[serde(untagged)]
enum E {
    A(BTreeMap<u32, String>),
    B { field: String },
}
```

Numeric keys may be misinterpreted when matching against struct variant.

#### Issue #2066: Scalar in Vector

**Problem**: Vector of untagged enums fails if one variant is scalar

```rust
#[serde(untagged)]
enum E {
    Struct { x: i32 },
    Scalar(i32),
}

let v: Vec<E> = serde_json::from_str("[{"x": 1}, 42]")?;
// ← Fails: ambiguity between struct and scalar
```

#### Issue #1437: Enum Index in Non-Self-Describing Formats

**Problem**: Nested enums fail in formats that use variant index instead of name

In Postcard and similar binary formats:
- Outer enum uses variant index
- If inner enum variant is untagged, deserialization fails
- Format doesn't provide variant name information needed for untagged matching

#### Issue #2172: Human-Readable Expectation

**Problem**: Untagged enums expect human-readable representation even with binary formats

The implementation always assumes `is_human_readable()` behavior, which causes failures with compact binary formats.

---

### 4. JSON Map Keys Must Be Strings

**Status**: By design; documented constraint

**GitHub Issues**:
- #45: Consider serializing map integer keys as strings
- #122: Serializing a map with non-string keys will silently generate invalid JSON

**Specification**:

JSON specification requires all object keys to be strings. Serde enforces this.

#### The Problem

```rust
let mut map: HashMap<u32, String> = HashMap::new();
map.insert(1, "one".to_string());

let json = serde_json::to_string(&map)?;
// ← Would generate invalid JSON: {1: "one"}
// ← Valid JSON requires: {"1": "one"}
```

#### Behavior

- **serde_json rejects non-string keys** during serialization
- **Deserializers coerce string keys** for format compatibility
- **Other formats** (MessagePack, Postcard) may support non-string keys

#### Workarounds

1. **Convert keys to strings manually**

```rust
#[derive(Serialize)]
struct StringKeyMap {
    #[serde(serialize_with = "serialize_map")]
    map: HashMap<u32, String>,
}
```

2. **Use serde_json_any_key crate**

3. **Use serde_with crate** with appropriate attributes

4. **Represent as array of pairs** instead of map

---

### 5. Integer Overflow Behavior

**Status**: Checked conversion; documented as correct behavior

**GitHub Issues**:
- #75: Integer overflow when parsing JSON
- #77: Integer overflow when parsing JSON scientific notation

**Specification**:

Serde performs checked conversion for integer deserialization. If a value exceeds the target type's range, deserialization fails with an error rather than silently truncating.

#### Examples

```rust
// Attempt to deserialize 99999999999999999 as u32
// ← Error: number too large

// Attempt to deserialize -1 as u8
// ← Error: invalid value

// In JSON: "1e999" parsed as i64
// ← Error: number too large
```

#### serde_json Number Handling

- `Number::is_u64()` checks if fits in u64
- `Number::is_i64()` checks if fits in i64
- `Number::as_u128()` for larger values (requires "arbitrary_precision")
- No silent overflow; all overflow cases produce errors

---

### 6. No-std Limitations

**Status**: Documented; by design

**Specification**:

In bare no-std (without alloc):
- ✅ Externally tagged enums: Fully supported
- ❌ Internally tagged enums: Require alloc
- ❌ Adjacently tagged enums: Require alloc
- ❌ Untagged enums: Cannot be deserialized (require buffering)

#### Root Cause

Internally/adjacently/untagged enum deserialization require buffering input to attempt multiple Deserialize implementations. This needs heap allocation.

#### Error Message

Attempting to deserialize untagged enum without alloc:
```
error: untagged enums are not supported without the "alloc" feature
```

---

### 7. Lifetime Constraints (Incorrect Patterns)

**Status**: Documented as incorrect

**Specification**:

Common incorrect lifetime patterns:

#### ❌ WRONG: Deserialize<'static>

```rust
fn deserialize_from_reader<T: for<'de> Deserialize<'de>>()
    where T: Deserialize<'static>  // ← WRONG
{ ... }
```

**Problem**: `'static` means the type cannot borrow from input at all; this defeats the purpose of lifetimes.

#### ❌ WRONG: DeserializeOwned vs. Deserialize<'de>

```rust
// WRONG: Mixing bounds
where T: DeserializeOwned + Deserialize<'de>
```

**Problem**: DeserializeOwned implies "no borrowed lifetime" but Deserialize<'de> allows borrowing.

#### ✅ CORRECT: for<'de> Deserialize<'de>

```rust
fn deserialize_from_reader<T: for<'de> serde::Deserialize<'de>>() { ... }
```

This is equivalent to DeserializeOwned and correctly expresses "any borrowed lifetime works".

---

### 8. Remote Type Derive Constraints

**Status**: Documented pattern with limitations

**Specification**:

Using `#[serde(remote = "ExternalType")]` has constraints:

1. **Field visibility**: Must provide getters for private fields
2. **Construction**: Must implement `From<LocalDefinition>` or similar to construct remote type
3. **Orphan rule**: Respects Rust's orphan rule; doesn't violate it
4. **Compile-time checking**: Serde checks field count and types at compile time

#### Known Issue

Cannot derive for remote types without providing a complete field definition. If external type has private fields, compilation fails unless getters are provided.

---

## Summary of Incompatible Combinations

| Feature A | Feature B | Status | Notes |
|---|---|---|---|
| flatten | deny_unknown_fields | ❌ Incompatible | Multiple failure modes |
| skip | deny_unknown_fields | ❌ Incompatible | Field treated as unknown |
| untagged | nested untagged | ⚠️ Problematic | Ambiguity issues |
| untagged | custom deserializer | ❌ Incompatible | Custom logic bypassed |
| untagged | binary format | ⚠️ Problematic | Enum index not supported |
| HashMap<K != String> | JSON | ❌ Incompatible | JSON keys must be strings |
| untagged | no-std/no-alloc | ❌ Incompatible | Cannot buffer |
| internally-tagged | tuple variant | ❌ Incompatible | Cannot flatten tuple |
| adjacently-tagged | untagged nested | ⚠️ Problematic | Complex interaction |

## Recommendations for Spec Auditors

When auditing Serde implementations, pay special attention to:

1. **Attribute interaction** — Check that unsupported combinations are rejected at compile time
2. **Error messages** — Verify that failed deserialization provides useful context
3. **Overflow handling** — Confirm integer overflow produces errors, not silent truncation
4. **Empty variant handling** — Untagged enums with empty variants need special attention
5. **Format contract enforcement** — JSON should reject non-string map keys
6. **Lifetime correctness** — Borrowed data should constraint `'de` appropriately
7. **Custom deserializer bypass** — Untagged enums should not bypass custom deserializers

---

## References

- https://github.com/serde-rs/serde/issues (all issues listed above)
- https://serde.rs/data-model.html
- https://serde.rs/container-attrs.html
