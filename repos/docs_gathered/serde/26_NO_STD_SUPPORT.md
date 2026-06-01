# No-std Support and Feature Flags

**Source**: https://serde.rs/no-std.html
**Accessed**: 2026-04-04

## Overview

Serde provides support for embedded and bare-metal Rust environments through feature flags. However, not all Serde features work in no-std contexts.

**Critical Contract**: Some deserialization features that require heap-allocated temporary buffers are unavailable in bare no-std without the "alloc" feature.

---

## Disabling Standard Library

### Configuration

```toml
[dependencies]
serde = { version = "1.0", default-features = false }
```

**Contract**: This disables the default `"std"` feature.

### What Gets Disabled

When `"std"` is disabled:

- **Removed**: All standard library data structures that involve heap memory allocation
- **Removed**: `String` and `String::` methods
- **Removed**: `Vec<T>` and vector methods
- **Removed**: Traits requiring std (e.g., `io::Error` handling)
- **Removed**: System-dependent types (`OsString`, `OsStr`, `Path`, `PathBuf`)

### Remaining Functionality

- Primitive types (bool, integers, floats, char)
- Manual implementations via `serde::ser` and `serde::de`
- `&str` and `&[u8]` (borrowed data)
- Stack-allocated types
- User-defined types with custom Serialize/Deserialize impls

---

## Using Derive Macros in No-std

The derive macros work in no-std but require enabling the `"derive"` feature:

```toml
[dependencies]
serde = { version = "1.0", default-features = false, features = ["derive"] }
serde_derive = { version = "1.0", default-features = false }
```

### What Works

```rust
#![no_std]

use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
struct Point {
    x: i32,
    y: i32,
}
```

### What Doesn't Work Without Alloc

The derive macro can generate code, but certain types require heap allocation:

- **Untagged enums**: Cannot be deserialized in bare no-std (requires buffering)
- **String fields**: Cannot be deserialized without allocator
- **Vec fields**: Cannot be deserialized without allocator
- **Internally-tagged enums**: Require buffering (need alloc)
- **Adjacently-tagged enums**: Require buffering (need alloc)

---

## Adding Heap Allocation Support

### The "alloc" Feature

```toml
[dependencies]
serde = { version = "1.0", default-features = false, features = ["alloc"] }
```

**Contract**: Provides impls for heap-allocated types from the allocation library.

### What Gets Enabled

- `String` and `String` deserialization
- `Vec<T>` and vector deserialization
- `Box<T>`
- `BTreeMap<K, V>`
- `BTreeSet<T>`
- `CowStr` and `Cow<T>`
- `LinkedList<T>`
- `VecDeque<T>`
- `BinaryHeap<T>`

### Internally Supported

These types work with "alloc" feature:
- Internally-tagged enums (require buffering)
- Adjacently-tagged enums (require buffering)
- Untagged enums (require buffering)

### Still Works

- All primitives
- All formats (JSON, MessagePack, Postcard, etc.)
- Custom deserializers
- Generic types

---

## Combining No-std + Alloc

Typical embedded configuration:

```toml
[dependencies]
serde = { version = "1.0", default-features = false, features = ["alloc", "derive"] }
```

**Behavior**:
- No dependency on `std` library
- Heap allocation available via global allocator
- Derive macros work for all types except those specifically requiring std

### Example

```rust
#![no_std]
extern crate alloc;

use alloc::string::String;
use alloc::vec::Vec;
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
struct Message {
    content: String,
    tags: Vec<String>,
}
```

---

## Format-Specific Limitations

### serde_json

Default features include `"std"`. For no-std:

```toml
[dependencies]
serde_json = { version = "1.0", default-features = false, features = ["alloc"] }
```

**Issue #463**: Supporting no-std usage requires careful dependency management.

**Issue #1040**: Supporting no-std and no-alloc is limited.

### Postcard

Works well with no-std + alloc:

```toml
[dependencies]
postcard = { version = "1.0", default-features = false, features = ["alloc"] }
```

### MessagePack

Varies by implementation; check documentation.

---

## Cargo Features Union Behavior

**Critical Issue**: Cargo features are unioned together across your entire dependency graph.

**Impact**: If any transitive dependency enables `"std"`, it will be enabled for all dependencies.

**Example Problem**:

```toml
[dependencies]
my_serializer = "1.0"  # Doesn't opt out of std

[target.'cfg(embedded)'.dependencies]
serde = { version = "1.0", default-features = false }
```

**Result**: If `my_serializer` depends on `serde` with `std`, the whole build gets `std` enabled.

**Solution**: All dependencies must explicitly disable std:

```toml
serde = { version = "1.0", default-features = false, features = ["alloc"] }
my_serializer = { version = "1.0", default-features = false }
```

---

## Deserialization Limitations in Bare No-std

### What Works

- ✅ Externally tagged enums (no buffering needed)
- ✅ Primitive types
- ✅ Borrowed strings and bytes (`&str`, `&[u8]`)
- ✅ Structs with known fields
- ✅ Custom Deserialize impls

### What Fails

- ❌ Untagged enums (requires buffering)
- ❌ Internally-tagged enums (requires buffering)
- ❌ Adjacently-tagged enums (requires buffering)
- ❌ String and Vec deserialization (requires allocation)
- ❌ Dynamic field collections

### Error Message

Attempting untagged enum without alloc:

```
error: untagged enums are not supported without the "alloc" feature
```

### Root Cause

Enum deserialization requires:
1. Buffering input (to attempt multiple variants)
2. Trying each variant's Deserialize impl
3. Keeping the first successful match

Steps 1 and 3 require heap allocation.

---

## Using Serde in No-std Embedded Projects

### Pattern: Manual Deserializer

For tight embedded constraints:

```rust
#![no_std]

use serde::de::{Deserializer, Deserialize};

// Manually implement Deserialize without allocating
impl<'de> Deserialize<'de> for MyType {
    fn deserialize<D>(_: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        // Custom logic that respects embedded constraints
        todo!()
    }
}
```

### Pattern: Borrowed References

Maximize zero-copy deserialization:

```rust
#[derive(Deserialize)]
struct Config<'a> {
    name: &'a str,
    #[serde(borrow)]
    description: Cow<'a, str>,
}
```

No allocations when data is borrowed.

### Pattern: Fixed-Size Arrays

Instead of `Vec<T>`:

```rust
#[derive(Serialize, Deserialize)]
struct Data {
    items: [Item; 10],  // Fixed size, no allocation
}
```

---

## Integration with Global Allocator

With `"alloc"` feature, Serde uses the global allocator:

```rust
#![no_std]

use core::alloc::GlobalAlloc;

struct CustomAllocator;

// Must be provided in no-std
#[global_allocator]
static ALLOCATOR: CustomAllocator = CustomAllocator;

unsafe impl GlobalAlloc for CustomAllocator {
    // Implementation for custom memory management
}
```

Serde respects the global allocator for all allocation requests.

---

## vec! Macro in No-std

When using "alloc" feature, `vec!` requires import:

```rust
#![no_std]
extern crate alloc;

use alloc::vec;

fn main() {
    let v = vec![1, 2, 3];  // Works with alloc import
}
```

**Common Error**:
```
error: macro `vec` not found in this scope
```

**Solution**: Always `use alloc::vec;` when using `vec!` macro in no-std.

---

## Feature Combination Reference

| Configuration | std | alloc | derive | Capabilities |
|---|---|---|---|---|
| `default` | ✅ | ✅ | ✅ | Everything |
| `no-std` | ❌ | ❌ | ✅ | Primitives, borrowed only |
| `no-std + alloc` | ❌ | ✅ | ✅ | Most features, no system types |
| `alloc-only` | ❌ | ✅ | ❌ | Manual impl only |
| `no-features` | ❌ | ❌ | ❌ | Manual impl with primitives |

---

## Testing No-std Code

Serde provides no-std builds in CI. To test locally:

```bash
# Test no-std
cargo test --no-default-features

# Test no-std + alloc
cargo test --no-default-features --features alloc

# Test with derive in no-std
cargo test --no-default-features --features derive

# Full embedded config
cargo test --no-default-features --features "alloc,derive"
```

---

## Platform-Specific Considerations

### Embedded (ARM Cortex-M)

Typical configuration:

```toml
[dependencies]
serde = { version = "1.0", default-features = false, features = ["alloc", "derive"] }
```

### WASM (WebAssembly)

WASM has access to linear memory but may have std available:

```toml
# WASM with std
serde = "1.0"  # Default

# WASM without std
serde = { version = "1.0", default-features = false, features = ["alloc"] }
```

### Bare Metal

Most restrictive; typically no-std + minimal alloc:

```toml
serde = { version = "1.0", default-features = false, features = ["derive"] }
# Possibly add "alloc" if custom allocator available
```

---

## Known Issues and Workarounds

### Issue: Untagged Enum in No-std

**Problem**: Untagged enums cannot be deserialized without alloc.

**Workaround 1**: Use externally-tagged enums instead.

```rust
// Instead of untagged:
#[serde(untagged)]
enum E { A, B }

// Use externally-tagged:
enum E { A, B }
```

**Workaround 2**: Implement custom Deserialize.

```rust
impl<'de> Deserialize<'de> for MyEnum {
    fn deserialize<D>(d: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        // Custom matching logic
    }
}
```

### Issue: String Fields in No-std

**Problem**: String deserialization requires allocation.

**Workaround**: Use borrowed `&str` or `Cow<'a, str>` with borrow attribute.

```rust
#[derive(Deserialize)]
struct Config<'a> {
    name: &'a str,  // Borrowed, no allocation
}
```

---

## References

- https://serde.rs/no-std.html
- https://github.com/serde-rs/json/issues/1040
- https://github.com/serde-rs/serde/issues/1339
