# EdgeQuake Tenant Isolation Model

## Overview

EdgeQuake implements multi-tenant isolation via `TenantContext`, which is extracted from request headers/auth and propagated through the handler chain.

## Where TenantContext IS enforced

- `list_documents` — strict tenant/workspace filtering on document metadata queries
- `text_insert.rs` — associates ingested documents with tenant context
- Query operations — propagate tenant/workspace through `edgequake-query` crate

## Where TenantContext is NOT enforced (known gaps)

### track_status handler
- **Endpoint:** `GET /api/v1/documents/track/{track_id}`
- **Handler:** `get_track_status()` in `crates/edgequake-api/src/handlers/documents/query/track_status.rs`
- **Issue:** Handler signature takes only `State(state)` and `Path(track_id)` — no `TenantContext` parameter
- **Result:** Iterates ALL metadata values across all tenants, matching only on `track_id`
- **Severity:** Cross-tenant metadata disclosure

### Lineage handlers (EQ-29)
- All 8 lineage handlers lack `TenantContext` checks
- Same vulnerability class as track_status
- Enables cross-workspace data disclosure

## Key Files for Tenant Isolation Review

- `crates/edgequake-api/src/handlers/documents/query/track_status.rs` — the cross-tenant leak
- `crates/edgequake-api/src/handlers/documents/query/` — all query handlers (check each for TenantContext)
- `crates/edgequake-api/src/routes.rs` — route definitions showing which handlers are exposed
- `crates/edgequake-api/src/state/mod.rs` — AppState definition
- Any handler in `src/handlers/` that accesses metadata without tenant filtering

## Testing Approach

The regression test `regression_track_status_is_scoped_to_tenant_and_workspace` in `tests/e2e_tenant_isolation.rs` demonstrates the leak:
1. Insert a document under tenant A with a known track_id
2. Query `/api/v1/documents/track/{track_id}` as tenant B
3. Assert that tenant B receives NO results (currently fails — receives tenant A's metadata)
