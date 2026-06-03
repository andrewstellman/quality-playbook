# EdgeQuake Architecture Overview

EdgeQuake is a high-performance GraphRAG engine inspired by LightRAG, written in Rust.

## Crate Structure (Workspace)

The project is a Rust workspace with four main crates:

### edgequake-core
Core orchestration: ingestion, query operations, error types.
- `src/orchestrator/ingestion.rs` — document ingestion pipeline (graph merge, vector storage, chunk processing)
- `src/orchestrator/query_ops.rs` — query orchestration

### edgequake-pipeline
Pipeline processing: validation, chunking, extraction.
- `src/validation.rs` — heavily spec-annotated, boundary validation (blocked extensions, duplicates, whitespace-only docs, chunk-size guards)
- Some tests gated by `#![cfg(feature = "pipeline")]`

### edgequake-query
Query engine: modes, engine logic, provider/model override parsing, tenant/workspace propagation.
- `src/modes.rs` — query mode definitions
- `src/engine.rs` — query engine logic

### edgequake-api
Axum-based HTTP API: routes, handlers, processors, state management.
- `src/routes.rs` — route definitions
- `src/state/mod.rs` — application state management
- `src/processor/text_insert.rs` — text insertion pipeline with cancellation support
- `src/processor/status_updates.rs` — document status persistence
- Handler subdirectories:
  - `src/handlers/documents/query/` — document query handlers (including track_status)
  - `src/handlers/documents/upload/` — file upload handlers
  - `src/handlers/documents/delete/` — document deletion
  - `src/handlers/documents_types/` — document type definitions and listing DTOs

## Multi-Tenant Isolation Model

EdgeQuake uses `TenantContext` for multi-tenant isolation:
- `list_documents` enforces strict `TenantContext` filtering
- Document ingestion associates documents with tenant/workspace context
- Query operations propagate tenant/workspace through the call chain
- **Known gap:** Not all handlers enforce `TenantContext` consistently (see KNOWN_BUGS.md)

## Key Patterns

- **Status state machine:** Documents transition through states: processing -> completed | partial_failure | cancelled
- **Cancellation tokens:** `text_insert.rs` uses cancellation gates at multiple pipeline stages
- **Error detail propagation:** Storage errors are collected during ingestion and should surface via API
- **Graph-then-vector ordering:** Graph merge happens before vector storage in `ingestion.rs`
- **Spec annotations:** `validation.rs` uses business rule references (e.g., `BR0001`)

## Build and Test

```bash
# Full test suite
cargo test --manifest-path edgequake/Cargo.toml

# Pipeline-gated tests
cargo test --manifest-path edgequake/Cargo.toml --features pipeline

# API tests
cargo test --manifest-path edgequake/Cargo.toml -p edgequake-api

# Core tests with pipeline feature
cargo test --manifest-path edgequake/Cargo.toml -p edgequake-core --features pipeline
```
