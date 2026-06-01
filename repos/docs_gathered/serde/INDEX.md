# Serde Documentation Index

**Last compiled:** 2026-04-04

This directory contains comprehensive documentation gathered from official Serde sources, GitHub issues, and community discussions. The goal is to provide a complete behavioral specification of the Serde serialization framework for auditing implementation correctness.

## Documentation Files

### Core Architecture & Concepts

- **01_OVERVIEW.md** — Serde framework overview, core design principles, architectural patterns
- **02_DATA_MODEL.md** — Complete Serde data model specification (29 types), serialization contracts
- **03_SERIALIZE_TRAIT.md** — Serialize trait specification, method contracts, implementation patterns
- **04_DESERIALIZE_TRAIT.md** — Deserialize trait specification, visitor pattern, implementation patterns

### Serialization & Deserialization

- **05_SERIALIZER_TRAIT.md** — Serializer trait specification, all methods, associated types
- **06_DESERIALIZER_TRAIT.md** — Deserializer trait specification, all methods, visitor pattern
- **07_VISITOR_PATTERN.md** — Visitor trait implementation, required/optional methods, contracts
- **08_CUSTOM_SERIALIZATION.md** — Custom trait implementations, serialize_with/deserialize_with patterns
- **09_DERIVE_MACROS.md** — Derive macro system, code generation, attribute handling

### Attributes & Configuration

- **10_ATTRIBUTES_OVERVIEW.md** — Complete attributes guide, three categories (container, field, variant)
- **11_CONTAINER_ATTRIBUTES.md** — Container-level attributes with full specifications
- **12_FIELD_ATTRIBUTES.md** — Field-level attributes, flatten, skip, default, borrow, custom functions
- **13_VARIANT_ATTRIBUTES.md** — Variant-level attributes, enum-specific options

### Enum Representations

- **14_ENUM_REPRESENTATIONS.md** — Four enum representation types (externally tagged, internally tagged, adjacently tagged, untagged)
- **15_UNTAGGED_ENUM_ISSUES.md** — Known issues, edge cases, limitations with untagged enums

### Advanced Features

- **16_LIFETIMES.md** — Deserializer lifetimes, borrowing constraints, zero-copy deserialization, 'de lifetime
- **17_REMOTE_DERIVE.md** — Remote type derive patterns, orphan rule workarounds
- **18_FLATTEN_ATTRIBUTE.md** — Flatten behavior, interactions with deny_unknown_fields, known issues

### Known Limitations & Issues

- **19_KNOWN_ISSUES.md** — Comprehensive list of documented limitations and incompatibilities
- **20_FLATTEN_DENY_UNKNOWN_FIELDS.md** — Detailed flatten + deny_unknown_fields interaction problems
- **21_DENY_UNKNOWN_FIELDS_SKIP.md** — Incompatibility between deny_unknown_fields and skip attribute
- **22_INTEGER_HANDLING.md** — Integer size handling, overflow behavior, cross-platform compatibility
- **23_MAP_KEYS.md** — Map key serialization, JSON string key requirements, non-string key workarounds

### Format-Specific

- **24_SELF_DESCRIBING_FORMATS.md** — JSON, YAML, and other self-describing format behavior
- **25_NON_SELF_DESCRIBING_FORMATS.md** — Postcard, binary formats, format hints, schema evolution

### Platform & Environment

- **26_NO_STD_SUPPORT.md** — No-std environments, alloc feature, limitations (untagged enums)
- **27_FEATURE_FLAGS.md** — Serde feature system, derive feature, alloc feature

### Special Patterns

- **28_DOUBLE_OPTION_PATTERN.md** — Option<Option<T>> changesets pattern for nullable updates
- **29_TRANSPARENT_NEWTYPE.md** — Transparent wrapper serialization, newtype contracts

### Implementation Guides

- **30_IMPL_SERIALIZER.md** — Complete serializer implementation guide with examples
- **31_IMPL_DESERIALIZER.md** — Complete deserializer implementation guide with examples
- **32_IMPL_SERIALIZE.md** — Implementing Serialize trait, patterns for all types
- **33_IMPL_DESERIALIZE.md** — Implementing Deserialize trait, visitor patterns, lifetime handling

### Design & Rationale

- **34_DESIGN_RATIONALE.md** — Design decisions, dtolnay's miniserde comparison, alternative approaches
- **35_COMMUNITY_DISCUSSIONS.md** — Reddit, Stack Overflow, Rust forum discussions on edge cases

## Key Files for Spec Auditing

For quickly identifying spec violations, start with these files in order:

1. **02_DATA_MODEL.md** — All 29 types must follow their contracts
2. **11_CONTAINER_ATTRIBUTES.md** & **12_FIELD_ATTRIBUTES.md** — Attributes must behave as specified
3. **14_ENUM_REPRESENTATIONS.md** — Enum encoding must match contracts
4. **19_KNOWN_ISSUES.md** — Known incompatibilities must be understood
5. **30_IMPL_SERIALIZER.md** & **31_IMPL_DESERIALIZER.md** — Trait method contracts
6. **26_NO_STD_SUPPORT.md** — Platform-specific limitations

## Critical Behavioral Specifications

### Documented Incompatibilities

- **flatten + deny_unknown_fields** — Not officially supported; multiple unsupported combinations documented
- **deny_unknown_fields + skip** — Incompatible; results in "unknown field" errors
- **untagged enums** — Many edge cases: empty variants, ambiguous variants, custom deserializers, numeric keys
- **untagged enums in no-std** — Cannot be deserialized without heap allocation

### Important Design Constraints

- **JSON map keys** — Must be strings; non-string keys will produce invalid JSON
- **Integer overflow** — Checked conversion; deserialization fails on overflow (not silent truncation)
- **Self-describing formats** — Can ignore type hints; non-self-describing formats must respect them
- **Lifetimes** — Borrowed data must constrain 'de lifetime; avoid 'static incorrect patterns
- **Visitor methods** — Only implementing required `expecting()` is not sufficient; must implement type-specific visit_* methods

## Source Attribution

All content extracted from:
- Official Serde documentation (https://serde.rs/)
- API documentation (https://docs.rs/serde/)
- GitHub issues and discussions (https://github.com/serde-rs/serde)
- Community discussions (r/rust, Rust forum, Stack Overflow)

Each file includes source URLs for verification and cross-reference.

## Usage Recommendations

1. **For bug investigation**: Start with the relevant topic file, then check KNOWN_ISSUES.md
2. **For implementation**: Use the IMPL_* files as contracts for expected behavior
3. **For edge cases**: Cross-reference 14_ENUM_REPRESENTATIONS.md with 15_UNTAGGED_ENUM_ISSUES.md
4. **For attributes**: Use the ATTRIBUTES files with cross-references to field/container/variant specific docs

---

**Note**: This documentation is current as of 2026-04-04. Serde is actively maintained; check official sources for updates.
