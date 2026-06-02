# Overview

Dasel (Data-Select) is both a command-line tool and a Go library for querying, modifying, and transforming structured data. It accepts data in several common encodings — JSON, YAML, TOML, XML, CSV, HCL, and INI — and exposes a single selector language that works uniformly across them. The same expression can pluck a field from JSON, navigate a YAML document, or update a TOML key, because every input is first normalized into an in-memory model and every output is rendered from that same model.

## Design philosophy

The project is organized around a clean pipeline: read bytes, decode into a unified value tree, execute a selector expression against that tree, and write the result back out in some chosen encoding. The pipeline stages are independent — each format has its own reader and writer plug-in, the selector language has its own lexer / parser / AST, and the execution engine operates entirely on the unified value model. This separation keeps the conversion of `JSON → YAML`, `TOML → JSON`, and so on essentially free: it is just a matter of pairing a reader for one format with a writer for another.

## Package layout

At the pinned revision the repository is laid out roughly as follows:

- `cmd/dasel/` — the `main` package for the CLI binary; it imports each format package for its registration side effects.
- `internal/cli/` — the Kong-based command definitions, flag handling, config loading, and the interactive mode.
- `internal/` — small internal helpers (a `ptr` package, the build-version constant).
- `selector/` — the selector language: `lexer/`, `ast/`, `parser/`, and a top-level `selector.Parse` convenience.
- `execution/` — the AST evaluator: one `execute_*.go` per expression kind, one `func_*.go` per built-in function, plus `Options` and execution context.
- `model/` — the `Value` abstraction (a reflect-backed type) plus comparison, arithmetic, map/slice operations, metadata, and Go-value conversion.
- `parsing/` — the pluggable format registry (`Format`, `Reader`, `Writer`) and one subpackage per encoding: `json`, `yaml`, `toml`, `xml`, `csv`, `hcl`, `ini`, and `d` (the inline-dasel reader used for variable parsing).
- `api.go` — the small top-level Go API: `Query`, `Select`, `Modify`.

## Data flow

A typical query — whether from the CLI or the library — runs the same path: bytes are handed to a `parsing.Reader` that produces a `*model.Value`; the selector string is tokenized, parsed into an `ast.Expr`, and evaluated by `execution.ExecuteAST` against that value with an `*execution.Options` carrying variables and functions; the resulting `*model.Value` is handed to a `parsing.Writer` that serializes it back into bytes in the requested output format. Format conversion and in-place modification are two specializations of this same pipeline.
