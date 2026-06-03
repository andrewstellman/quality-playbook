# Manifest

This directory contains general-purpose reference documentation for the `dasel` Go data-selection tool at a single pinned point in its history. The files are intended for a developer joining the project who wants a clear picture of how the library and CLI are organized.

## Files

- `overview.md` — high-level architecture, design philosophy, package layout, and the read → execute → write pipeline.
- `cli.md` — the `dasel` command-line interface: command tree, query flags, configuration file, and pipeline orchestration.
- `selector_language.md` — the selector language: lexer token set, AST node kinds, and the Pratt-style parser.
- `execution_engine.md` — the `execution` package: `Options`, the AST executor dispatch table, context threading, and built-in functions.
- `value_model.md` — the unified `model.Value` abstraction: type tags, constructors, comparison semantics, error vocabulary, and the ordered-map helper.
- `parsing_formats.md` — the pluggable `parsing` registry plus the supported encodings (JSON, YAML, TOML, XML, CSV, HCL, INI, and the inline-dasel reader).
- `library_api.md` — the Go library surface: `Query`, `Select`, `Modify`, options, idiomatic usage, and module layout.
- `_audit.md` — record of the sources consulted and the self-check verdict.
