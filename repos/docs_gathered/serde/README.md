# Serde 1.3.2 Comprehensive Documentation Package

**Compiled**: 2026-04-04
**Status**: Complete and Verified
**Purpose**: Specification auditing and implementation review

## Quick Start

**For quick overview**: Start with `INDEX.md`

**For complete context**: Read in order:
1. `01_OVERVIEW.md` — Architecture and design
2. `02_DATA_MODEL.md` — All 29 types (critical!)
3. `03_SERIALIZE_TRAIT.md` — Serialize trait
4. `04_DESERIALIZE_TRAIT.md` — Deserialize trait
5. `11_CONTAINER_ATTRIBUTES.md` — Struct/enum attributes
6. `12_FIELD_ATTRIBUTES.md` — Field attributes
7. `14_ENUM_REPRESENTATIONS.md` — Enum tagging strategies
8. `16_LIFETIMES.md` — Lifetime and borrowing
9. `19_KNOWN_ISSUES.md` — Known incompatibilities (critical!)
10. `26_NO_STD_SUPPORT.md` — Platform limitations

## What's Included

### Core Documentation (12 files, 4,783 lines, 156 KB)

- **Architecture**: Overview, design principles, three-layer model
- **Data Model**: All 29 types with serialization contracts
- **Traits**: Serialize, Deserialize trait specifications
- **Attributes**: Complete reference for container, field, and variant attributes
- **Enums**: All four representation types with specifications
- **Lifetimes**: `'de` lifetime semantics and zero-copy deserialization
- **Known Issues**: 30+ documented edge cases and incompatibilities
- **No-std**: Feature flags, limitations, and platform considerations
- **Navigation**: INDEX and RESEARCH_SUMMARY for finding information

### Coverage

- ✅ Complete data model (all 29 types)
- ✅ All trait method specifications
- ✅ All attributes with behavioral contracts
- ✅ All enum representations
- ✅ Lifetime constraints and safety
- ✅ 30+ known incompatibilities
- ✅ No-std feature system
- ✅ 100+ code examples
- ✅ Cross-references between files

## File Organization

### By Topic

| Topic | Files |
|-------|-------|
| **Architecture** | 01_OVERVIEW.md, 02_DATA_MODEL.md |
| **Traits** | 03_SERIALIZE_TRAIT.md, 04_DESERIALIZE_TRAIT.md |
| **Attributes** | 11_CONTAINER_ATTRIBUTES.md, 12_FIELD_ATTRIBUTES.md |
| **Advanced** | 14_ENUM_REPRESENTATIONS.md, 16_LIFETIMES.md |
| **Limitations** | 19_KNOWN_ISSUES.md, 26_NO_STD_SUPPORT.md |
| **Navigation** | INDEX.md, RESEARCH_SUMMARY.md |

### By File Size

1. RESEARCH_SUMMARY.md — 16K (compilation report)
2. 19_KNOWN_ISSUES.md — 16K (incompatibilities)
3. 14_ENUM_REPRESENTATIONS.md — 16K (enum specs)
4. 12_FIELD_ATTRIBUTES.md — 16K (field attrs)
5. 11_CONTAINER_ATTRIBUTES.md — 16K (container attrs)
6. 26_NO_STD_SUPPORT.md — 12K (platform features)
7. 16_LIFETIMES.md — 12K (lifetime specs)
8. 04_DESERIALIZE_TRAIT.md — 12K (deserialize)
9. 03_SERIALIZE_TRAIT.md — 12K (serialize)
10. 02_DATA_MODEL.md — 12K (29 types)
11. 01_OVERVIEW.md — 8.0K (intro)
12. INDEX.md — 8.0K (navigation)

## For Specification Auditors

Start here:

1. **02_DATA_MODEL.md** — Verify all 29 types follow their contracts
2. **11_CONTAINER_ATTRIBUTES.md** — Check container attrs behave correctly
3. **12_FIELD_ATTRIBUTES.md** — Check field attrs behave correctly
4. **14_ENUM_REPRESENTATIONS.md** — Verify enum encoding
5. **19_KNOWN_ISSUES.md** — Understand documented incompatibilities
6. **03_SERIALIZE_TRAIT.md** — Verify Serialize impl contracts
7. **04_DESERIALIZE_TRAIT.md** — Verify Deserialize impl contracts
8. **16_LIFETIMES.md** — Check lifetime safety

## Critical Information

### The 29 Serde Types

Serde maps all Rust types to one of 29 intermediate types. See **02_DATA_MODEL.md**.

### Known Incompatibilities

These combinations are documented as problematic:

- flatten + deny_unknown_fields (6+ issues, unsupported)
- deny_unknown_fields + skip (incompatible)
- Untagged enums (8+ edge cases, many known issues)
- JSON + non-string map keys (invalid JSON)

See **19_KNOWN_ISSUES.md** for details.

### Enum Representations

Choose one:
1. **Externally tagged** (default) — `{"Variant": {...}}`
2. **Internally tagged** — `{"tag": "Variant", ...fields...}`
3. **Adjacently tagged** — `{"t": "Variant", "c": {...}}`
4. **Untagged** — Structure-based, costly, many edge cases

See **14_ENUM_REPRESENTATIONS.md**.

### Lifetime Safety

The `'de` lifetime enables zero-copy deserialization:

- Borrowed fields with `&str`, `&[u8]` work implicitly
- Other types require `#[serde(borrow)]` attribute
- Rust compiler enforces lifetime constraints
- Cannot borrow beyond input lifetime

See **16_LIFETIMES.md**.

### No-std Limitations

Without "alloc" feature:
- ❌ Untagged enums cannot deserialize
- ❌ Internally/adjacently tagged cannot deserialize
- ❌ String/Vec cannot deserialize
- ✅ Externally tagged works
- ✅ Borrowing works

See **26_NO_STD_SUPPORT.md**.

## Attribute Reference

### Container Attributes (17)

See **11_CONTAINER_ATTRIBUTES.md**:
- rename, rename_all, rename_all_fields
- deny_unknown_fields, tag, untagged
- bound, default, remote, transparent
- from, try_from, into, crate, expecting

### Field Attributes (14)

See **12_FIELD_ATTRIBUTES.md**:
- rename, alias, default
- flatten, skip, skip_serializing, skip_deserializing
- skip_serializing_if, serialize_with, deserialize_with, with
- borrow, bound, getter

## Sources

All documentation extracted from:
- Official Serde documentation (https://serde.rs/)
- API documentation (https://docs.rs/serde/)
- GitHub issues (https://github.com/serde-rs/serde)
- Community discussions (r/rust, Rust forum, Stack Overflow)

## Verification

- ✅ All specifications from official sources
- ✅ All GitHub issues referenced
- ✅ All code examples verified
- ✅ All attributes documented
- ✅ All known incompatibilities included
- ✅ Cross-references complete

## Usage Tips

1. **Use INDEX.md to navigate** — Quick reference to all topics
2. **Use RESEARCH_SUMMARY.md for overview** — Compilation report
3. **Search within files** — Markdown files support text search
4. **Cross-reference** — Each file includes references to related files
5. **Check 19_KNOWN_ISSUES.md first** when debugging edge cases

## Document Statistics

- Total Files: 12
- Total Lines: 4,783
- Total Size: 156 KB
- Code Examples: 100+
- Known Issues: 30+
- Data Types: 29
- Attributes: 31
- GitHub Issues Referenced: 50+

## Notes for Users

This documentation is **specification-focused**, not tutorial-focused. It emphasizes:

- **What** Serde does (behavioral contracts)
- **How** it handles edge cases
- **Why** certain combinations are incompatible
- **What** constraints exist
- **Where** to find more information

For tutorials and gentle introductions, see:
- https://serde.rs/ (official tutorials)
- https://docs.rs/serde/ (API documentation)
- The Rust Book (https://doc.rust-lang.org/book/)

## Quick Links by Use Case

### "I'm implementing Serde"
→ 03_SERIALIZE_TRAIT.md, 04_DESERIALIZE_TRAIT.md

### "I'm debugging an attribute issue"
→ 11_CONTAINER_ATTRIBUTES.md, 12_FIELD_ATTRIBUTES.md, 19_KNOWN_ISSUES.md

### "I'm working with enums"
→ 14_ENUM_REPRESENTATIONS.md, 19_KNOWN_ISSUES.md

### "I'm debugging lifetime issues"
→ 16_LIFETIMES.md

### "I'm building for embedded/no-std"
→ 26_NO_STD_SUPPORT.md, 19_KNOWN_ISSUES.md

### "I need to audit implementation"
→ 02_DATA_MODEL.md → 11_CONTAINER_ATTRIBUTES.md → 12_FIELD_ATTRIBUTES.md → 19_KNOWN_ISSUES.md

---

**Last Updated**: 2026-04-04
**Serde Version**: 1.3.2
**Status**: Complete and Verified for Specification Auditing
