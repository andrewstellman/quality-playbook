# Retrieved Documentation Index — Gson

Retrieved: 2026-04-03
Purpose: Comprehensive documentation corpus for the Gson JSON serialization library, assembled to support requirement derivation in the Quality Playbook experiment. These files capture official documentation, API contracts, behavioral expectations from GitHub issues, and community-authored tutorials.

## How to use this folder

Point the quality playbook's Step 7 (requirement derivation) at this folder. The official documentation describes intended behavior, the GitHub issues describe edge cases and behavioral contracts users expect, and the community tutorials describe real-world usage patterns and pitfalls. Together they provide a much richer basis for requirement derivation than code alone.

---

## official/ — Documentation from the Gson repository and project

| File | Source | Description |
|------|--------|-------------|
| `user_guide.md` | [UserGuide.md](https://github.com/google/gson/blob/main/UserGuide.md) | Complete user guide: serialization, deserialization, generics, null handling, custom adapters, streaming, versioning, field exclusion, naming policies |
| `troubleshooting.md` | [Troubleshooting.md](https://github.com/google/gson/blob/main/Troubleshooting.md) | 24 common problems with solutions — ClassCastException, InaccessibleObjectException, R8/ProGuard, null handling, custom adapter registration, duplicate fields, java.lang.Class security |
| `design_document.md` | [GsonDesignDocument.md](https://github.com/google/gson/blob/main/GsonDesignDocument.md) | Design rationale: type tree navigation vs JSON tree, fields vs getters, final classes, unchecked exceptions, asymmetric serialization/deserialization, instance creation |
| `changelog.md` | [CHANGELOG.md](https://github.com/google/gson/blob/main/CHANGELOG.md) | Version history from 1.0.1 through 2.10 with behavioral changes, breaking changes, and API additions |
| `releases_changelog.md` | [GitHub Releases](https://github.com/google/gson/releases) | Release notes for versions 2.10 through 2.13.2 (supplements changelog.md which stops at 2.10) |
| `javadoc_gson_class.md` | [Gson.java](https://github.com/google/gson/blob/main/gson/src/main/java/com/google/gson/Gson.java) | Gson class Javadoc — thread safety guarantees, default configuration, JSON strictness handling, usage patterns |
| `javadoc_type_adapter.md` | [TypeAdapter.java](https://github.com/google/gson/blob/main/gson/src/main/java/com/google/gson/TypeAdapter.java) | TypeAdapter class Javadoc — read/write protocol contract, null handling contract, thread safety requirements |

## github_issues/ — Behavioral contracts from bug reports and feature discussions

Each issue captures what users expect Gson to do vs what it actually does — these are requirements stated in the most useful possible form.

| File | Issue | Status | Description |
|------|-------|--------|-------------|
| `issue_0530_circular_references.md` | [#530](https://github.com/google/gson/issues/530) | Open | Circular object references cause StackOverflowError; no built-in cycle detection |
| `issue_0613_thread_safety.md` | [#613](https://github.com/google/gson/issues/613) | Closed | Thread safety documentation — Gson instances are thread-safe, no state maintained during operations |
| `issue_0676_runtime_type_adapter_serialize_nulls.md` | [#676](https://github.com/google/gson/issues/676) | Open | RuntimeTypeAdapterFactory discards explicit serializeNulls settings from nested TypeAdapters |
| `issue_0913_selective_serialize_nulls.md` | [#913](https://github.com/google/gson/issues/913) | Open | serializeNulls() is global-only — no per-class null serialization control; TypeAdapterFactory workaround |
| `issue_0948_type_adapter_null_bypass.md` | [#948](https://github.com/google/gson/issues/948) | Closed | TypeAdapter.write/read not invoked for null values — by design, not a bug |
| `issue_1005_default_values_missing.md` | [#1005](https://github.com/google/gson/issues/1005) | Open | Missing JSON fields set to null instead of preserving field default values; Gson skips TypeAdapter for missing fields |
| `issue_1558_optional_vs_null.md` | [#1558](https://github.com/google/gson/issues/1558) | Open | Cannot distinguish required-nullable from optional fields in serialization; workaround with @JsonAdapter(nullSafe=false) |
| `issue_2032_deserializer_changes_serialization.md` | [#2032](https://github.com/google/gson/issues/2032) | Closed | Registering a custom JsonDeserializer unexpectedly changes serialization behavior, dropping subclass fields |
| `issue_2059_anonymous_class_null.md` | [#2059](https://github.com/google/gson/issues/2059) | Closed | Anonymous inner classes serialize as JSON "null" without explicit type parameter; intentional behavior |
| `issue_2295_strict_mode.md` | [#2295](https://github.com/google/gson/issues/2295) | Closed | Strictness enum (LENIENT/DEFAULT/STRICT) for RFC 8259 compliance; implemented in Gson 2.11.0 |
| `issue_2563_generic_type_boundary.md` | [#2563](https://github.com/google/gson/issues/2563) | Open | Bounded type variables (T extends Foo) ignored during deserialization — treated as Object |
| `issue_2739_class_loading_deadlock.md` | [#2739](https://github.com/google/gson/issues/2739) | Closed | Critical class loading deadlock between TypeAdapters and JsonElementTypeAdapter; fixed in PR #2740 |
| `issue_2787_backwards_compat_broken.md` | [#2787](https://github.com/google/gson/issues/2787) | Closed | Gson 2.11 broke backward compat by rejecting custom JsonElement adapters; reverted in 2.12.0 |

## community/ — Tutorials and guides from Gson users

| File | Source | Description |
|------|--------|-------------|
| `howtodoinjava_custom_serialization.md` | [HowToDoInJava](https://howtodoinjava.com/gson/custom-serialization-deserialization/) | Custom JsonSerializer and JsonDeserializer implementation patterns; null safety with has() checks |
| `futurestud_custom_serialization.md` | [Future Studio](https://futurestud.io/tutorials/gson-advanced-custom-serialization-part-1) | Four approaches to custom serialization for payload reduction; warnings about adapter overwriting and infinite recursion |
| `futurestud_custom_deserialization.md` | [Future Studio](https://futurestud.io/tutorials/gson-advanced-custom-deserialization-basics) | Custom deserialization for API data format mismatches; type-specific JSON accessor patterns |
| `futurestud_jsonadapter_annotation.md` | [Future Studio](https://futurestud.io/tutorials/gson-advanced-customizing-de-serialization-and-adding-instance-creators-via-jsonadapter) | @JsonAdapter annotation (Gson 2.7+) for simplified adapter registration; limitation of single adapter per type |

---

## Coverage summary

- **7 official documents** covering the user guide, troubleshooting, design rationale, changelog (all versions), API Javadoc for core classes, and JSON strictness
- **13 GitHub issues** capturing behavioral contracts around null handling (5 issues), type system edge cases (3), thread safety (1), serialization correctness (2), backward compatibility (1), and strictness (1)
- **4 community tutorials** covering custom serialization/deserialization patterns and the @JsonAdapter annotation

Total: **24 files** across 3 categories
