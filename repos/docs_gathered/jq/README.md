# jq Documentation — Reference for Code Quality Analysis

This directory contains comprehensive reference documentation for the jq JSON processor, extracted from the official jq manual (v1.8), GitHub repository, and implementation sources. These docs are designed for AI-driven code quality analysis of the jq codebase.

## Purpose

Unlike tutorial-style documentation, these files focus on **behavioral contracts and edge cases**—the exact rules jq implements for type coercion, error handling, null propagation, number precision, and operator precedence. This level of specificity helps auditors and AI tools identify deviations from specification and catch subtle bugs in the implementation.

## Documentation Structure

- **README.md** — This file
- **INDEX.md** — Master index of all documentation files
- **architecture.md** — Lexer, parser, compiler, bytecode VM, and value representation
- **type-system.md** — Type system, internal representation, comparison semantics, precision
- **operators-and-filters.md** — Pipe, comma, conditionals, alternatives, arithmetic, logical operations
- **builtin-functions.md** — map, select, reduce, foreach, path expressions, type introspection
- **string-interpolation.md** — String interpolation syntax, format strings (@base64, @csv, @html, etc.)
- **advanced-features.md** — def, recursion, variable binding, $ENV, input/inputs, modules
- **filter-language.md** — Parser grammar, update expressions, reduce syntax, recursion mechanics
- **behavioral-contracts.md** — Null propagation, error handling, try-catch semantics, edge cases

## Key Files

Start with **behavioral-contracts.md** for a comprehensive list of "MUST/SHOULD" behaviors and known edge cases. Then consult **type-system.md** for precise rules on number representation, comparison, and type coercion.

## Sources

- Official jq Manual: https://jqlang.org/manual/
- GitHub Repository: https://github.com/jqlang/jq
- Internals Wiki: https://github.com/jqlang/jq/wiki/Internals:-the-compiler

## Version Coverage

These docs cover jq 1.8 and implementation details from the jqlang/jq repository (main branch). Some behaviors documented here evolved across versions (1.5, 1.6, 1.7, 1.8)—version-specific notes appear where relevant.
