# Enum Representation Types (Complete Specification)

**Source**: https://serde.rs/enum-representations.html
**Accessed**: 2026-04-04

## Overview

Serde provides **four ways of representing enums** in serialized form. The choice affects how variant data is encoded and how deserializers identify which variant is present.

**Critical Distinction**: Enum representation is independent of whether the enum's variants are unit, newtype, struct, or tuple variants. The representation only specifies where the discriminator/tag appears.

## The Four Representation Types

### 1. Externally Tagged (Default)

**Attribute**: None (default behavior)

**Characteristic**: Tag appears outside the content, identifiable before parsing variant data.

#### JSON Example

```json
{
  "Request": {
    "id": "...",
    "method": "...",
    "params": {}
  }
}
```

```json
{
  "Response": {
    "result": {...}
  }
}
```

```json
"Null"
```

#### Rust Code

```rust
#[derive(Serialize, Deserialize)]
enum Message {
    Request {
        id: String,
        method: String,
        params: serde_json::Value,
    },
    Response {
        result: serde_json::Value,
    },
    Null,
}
```

#### Serialization Contract

For each variant type:
- **Unit variant**: `{"Red": {}}`
- **Newtype variant**: `{"Point": [1, 2]}`
- **Tuple variant**: `{"Click": [100, 200]}`
- **Struct variant**: `{"Rectangle": {"width": 10, "height": 20}}`

#### Deserialization Contract

1. **Map structure required**: Input is a map with exactly one key
2. **Key is variant name**: The key identifies which variant this is
3. **Value type matches variant**: Content type depends on the variant being deserialized
4. **No type hint needed**: Deserializer can identify variant before parsing content

#### Method Calls (Internal)

- **Serialization**: Calls `Serializer::serialize_*_variant()` methods with variant name and index
- **Deserialization**: Calls `Deserializer::deserialize_enum()` which uses enum access to read variant name

#### Format Support

- **All formats supported**: Works with JSON, YAML, MessagePack, Postcard, etc.
- **Binary format support**: Can be represented efficiently in any format
- **No-std support**: Works in no-std environments (only externally tagged works without alloc)

#### Advantages

- Works across all text and binary formats
- Unambiguous: can identify variant before deserializing content
- Works with all variant types (unit, newtype, tuple, struct)
- Schema evolution: can add new variants without breaking old deserializers
- Required for no-std environments without heap allocation

#### Disadvantages

- Larger serialized size due to explicit tag
- Extra nesting level for content

#### Edge Cases

1. **Variant name collisions**: If variant name matches reserved words, use `#[serde(rename)]`
2. **Format-specific encoding**: Some formats may encode variant index instead of name (Postcard)
3. **Empty struct variants**: `{"Empty": {}}` or `{"Empty": null}` depending on format

---

### 2. Internally Tagged

**Attribute**: `#[serde(tag = "type")]`

**Characteristic**: Tag field embedded alongside variant content within the same object.

#### JSON Example

```json
{
  "type": "Request",
  "id": "...",
  "method": "...",
  "params": {}
}
```

```json
{
  "type": "Response",
  "result": {...}
}
```

#### Rust Code

```rust
#[derive(Serialize, Deserialize)]
#[serde(tag = "type")]
enum Message {
    Request {
        id: String,
        method: String,
        params: serde_json::Value,
    },
    Response {
        result: serde_json::Value,
    },
    Null,
}
```

#### Serialization Contract

For each variant type:
- **Unit variant**: `{"type": "Null"}`
- **Newtype variant (struct)**: `{"type": "Point", "x": 1, "y": 2}`
- **Newtype variant (map)**: `{"type": "Config", ...map contents...}`
- **Struct variant**: `{"type": "Request", "id": "...", ...fields...}`

#### Supported Variant Types

- **Struct variants**: ✅ Full support
- **Newtype variants (containing structs/maps)**: ✅ Full support
- **Newtype variants (containing primitives/sequences)**: ❌ Compile-time error
- **Tuple variants**: ❌ Compile-time error (cannot flatten)
- **Unit variants**: ✅ Full support

#### Deserialization Contract

1. **Map structure required**: Input must be a map
2. **Tag field identifies variant**: Field specified in `tag = "..."` contains the discriminator
3. **Content fields follow**: Other fields in the same map are variant data
4. **Type hint not used**: Deserializer ignores type hints; reads from actual input

#### Method Calls (Internal)

- **Serialization**: Calls `Serializer::serialize_struct_variant()` with variant name
- **Deserialization**: Reads tag field first, then deserializes based on variant type

#### Alloc Requirements

**Requires "alloc" Cargo feature**: Cannot be deserialized in bare no-std without heap allocation.

#### Advantages

- More compact than externally tagged (no extra nesting)
- Common pattern in Java ecosystem
- Field order is preserved

#### Disadvantages

- Cannot handle tuple or newtype variants containing non-struct types
- Requires tag field in serialized representation (potential field name collision)
- Requires heap allocation for deserialization

#### Known Issues

**GitHub Issue #2755**: Internally tagged newtype variant containing unit struct fails to deserialize when extra keys exist

```rust
#[serde(tag = "type")]
enum E {
    #[serde(newtype)]
    Unit(()),  // ← Can fail with extra fields
}
```

---

### 3. Adjacently Tagged

**Attribute**: `#[serde(tag = "t", content = "c")]`

**Characteristic**: Two separate fields: one for tag, one for content.

#### JSON Example

```json
{
  "t": "Para",
  "c": [
    {"text": "Hello"},
    {"text": "World"}
  ]
}
```

```json
{
  "t": "Str",
  "c": "the string"
}
```

```json
{
  "t": "Unit"
}
```

#### Rust Code

```rust
#[derive(Serialize, Deserialize)]
#[serde(tag = "t", content = "c")]
enum Content {
    Para(Vec<Inline>),
    Str(String),
    Unit,
}
```

#### Serialization Contract

For each variant type:
- **Unit variant**: `{"t": "Unit"}` (no "c" field)
- **Newtype variant**: `{"t": "Str", "c": "value"}`
- **Tuple variant**: `{"t": "Click", "c": [100, 200]}`
- **Struct variant**: `{"t": "Click", "c": {"x": 100, "y": 200}}`

#### Deserialization Contract

1. **Map structure required**: Input must be a map
2. **Tag field identifies variant**: Field specified in `tag = "..."` contains discriminator
3. **Content field (if present)**: Field specified in `content = "..."` contains variant data
4. **Unit variants have no content**: Omit content field for unit variants

#### Alloc Requirements

**Requires "alloc" Cargo feature**: Deserialization needs heap buffering.

#### Advantages

- Supports all variant types (unit, newtype, tuple, struct)
- Clear separation between discriminator and content
- Common pattern in Haskell ecosystem
- Relatively compact

#### Disadvantages

- Requires two fields in serialized form (potential collisions)
- Requires heap allocation for deserialization

#### Format Representation Issues

**GitHub Issue #2496**: Variant ID representation for adjacently tagged enums could be more efficient

---

### 4. Untagged

**Attribute**: `#[serde(untagged)]`

**Characteristic**: No explicit identifying tag. Variants are distinguished solely by their data structure.

#### JSON Example

```json
{
  "id": "...",
  "method": "...",
  "params": {}
}
```

```json
42
```

```json
"string value"
```

#### Rust Code

```rust
#[derive(Serialize, Deserialize)]
#[serde(untagged)]
enum Message {
    Request {
        id: String,
        method: String,
        params: serde_json::Value,
    },
    Number(i32),
    String(String),
}
```

#### Serialization Contract

- No tag/discriminator in serialized form
- Each variant's content is serialized directly
- Deserializer must distinguish variants by structure alone

#### Deserialization Contract

1. **Variant matching**: Tries each variant's Deserialize implementation in order
2. **First match wins**: Returns the first variant that successfully deserializes the input
3. **Sequential evaluation**: Does not return the "best" match, only the first match
4. **Error on complete failure**: If no variant matches, returns error with limited context

#### Supported Variant Types

- ✅ All variant types: unit, newtype, tuple, struct

#### Performance Characteristics

**Important Contract Violation Potential**: The untagged implementation approach can be costly in performance-critical scenarios.

**Behavior**: Implementation buffers input to attempt multiple deserialize implementations. This requires:
- Buffering all input data
- Multiple deserialization attempts
- Stack space for error tracking

#### Alloc Requirements

**Requires "alloc" Cargo feature**: Cannot be deserialized in bare no-std.

#### Known Issues and Edge Cases

1. **Empty variant matching** (Issue #1560)
   - Variants with no content deserialize in "unintuitive ways"
   - May deserialize to `null` instead of expected representation

2. **Custom deserializer ignored** (Issue #2607)
   - `#[serde(untagged)]` ignores custom `deserialize_struct` implementations
   - Content is buffered before reaching custom deserializer

3. **Numeric key issues** (Issue #2724)
   - Unexpected behavior with untagged enums and numeric map keys

4. **Scalar in vector** (Issue #2066)
   - Vector of enum values fails if one enum option is scalar
   - Conflicts with struct/map variants in same enum

5. **Optional fields conflict** (Issue #2447)
   - Deserialization fails on correct input when variants have optional fields
   - Workaround: Rewrite variant as struct instead

6. **Custom deserializer + HashMap** (Issue #2457)
   - Custom deserializer doesn't work with untagged enum + HashMap

7. **Enum index vs. name** (Issue #1437)
   - In formats using variant index (not name), nested enums fail
   - Affects non-self-describing binary formats

8. **Non-human-readable formats** (Issue #2172)
   - Untagged enum expects human-readable representation even with binary formats

#### Advantages

- No discriminator in output (most compact)
- Supports all variant types
- Clean data structure representation

#### Disadvantages

- **Very costly performance** (buffering + multiple attempts)
- **Ambiguity resolution**: First match wins, not best match
- **Poor error messages**: Generic "did not match any variant" error
- **Many edge cases and known bugs**
- **Requires alloc feature**
- **Difficult to implement correctly**: Multiple reported issues with custom deserializers
- **Schema evolution issues**: Adding new variants can break existing data

#### Design Recommendations

Avoid untagged enums when:
- Performance is critical
- Error messages matter
- Variants have overlapping structure
- Custom deserializers are involved
- Data may come from non-self-describing formats

## Choosing the Right Representation

| Requirement | Externally Tagged | Internally Tagged | Adjacently Tagged | Untagged |
|---|---|---|---|---|
| All variant types | ✅ | ❌ (no tuple/plain newtype) | ✅ | ✅ |
| No-std (no alloc) | ✅ | ❌ | ❌ | ❌ |
| Compact | ⚠️ | ✅ | ⚠️ | ✅ |
| Performance | ✅ | ✅ | ✅ | ❌ |
| Error messages | ✅ | ✅ | ✅ | ❌ |
| Schema evolution | ✅ | ⚠️ | ✅ | ❌ |
| Custom deserializer support | ✅ | ✅ | ✅ | ❌ |

## Format-Specific Considerations

### JSON

All four representations produce valid JSON:
- Externally tagged: Works naturally
- Internally tagged: Embedding works naturally
- Adjacently tagged: Two fields naturally
- Untagged: Structure depends on variant

### MessagePack

- Externally tagged: Map with one key
- Internally tagged: Map with embedded tag
- Adjacently tagged: Map with two keys
- Untagged: Direct variant representation

### Postcard (Binary)

- Externally tagged: Variant index + content
- Internally tagged: Works but not optimal
- Adjacently tagged: Works but not optimal
- Untagged: Ambiguous without format enhancement

---

## References

- https://serde.rs/enum-representations.html
- https://github.com/serde-rs/serde/issues/1560 (empty variants)
- https://github.com/serde-rs/serde/issues/2447 (optional fields)
- https://github.com/serde-rs/serde/issues/2607 (custom deserializer)
- https://github.com/serde-rs/serde/issues/2724 (numeric keys)
