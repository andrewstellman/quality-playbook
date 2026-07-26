# Documentation Manifest

| File | Contents |
|---|---|
| `architecture.md` | High-level architecture, design philosophy, module layout, subsystem interactions, build/packaging overview, error-handling conventions |
| `uri_parsing.md` | `Addressable::URI` factory methods, component accessors, validation rules, joining, merging, relative URI computation, serialization, comparison |
| `normalization.md` | Per-component normalization pipeline, lazy memoization with NONE sentinel, `normalize`/`normalize!`, display URI, class-level encoding helpers (`encode_component`, `unencode`, `normalize_component`, `encode`, `normalized_encode`, `form_encode`, `form_unencode`) |
| `template.md` | `Addressable::Template` pattern syntax, full and partial expansion, extraction, `MatchData`, `to_regexp`, equality, processor protocol |
| `idna.md` | `Addressable::IDNA` dual-backend architecture, native backend (idn gem), pure-Ruby backend (Punycode codec, Unicode codepoint table, `to_ascii`, `to_unicode`) |
| `character_classes.md` | `CharacterClasses`, `CharacterClassesRegexps`, `NormalizeCharacterClasses` constants, encoding lookup tables, relationship to RFC 3986 |
| `query_handling.md` | Raw `query` attribute, structured `query_values` (Hash/Array), `query_values=`, class-level `form_encode`/`form_unencode`, normalized query with `:compacted`/`:sorted` flags, template query expansion |
| `testing.md` | RSpec suite layout, coverage configuration, platform helpers, compatibility gemfiles, CI matrix, patterns in uri_spec/template_spec/idna_spec |
| `packaging.md` | Gem metadata, runtime and optional dependencies, `VERSION` module, semantic versioning, Rakefile/build tasks, YARD, CI workflows, benchmarks |
