# EdgeQuake — Known Bugs from Previous Quality Audit

These bugs were confirmed with regression tests in a previous code review session. Each has a specific file location, code-level root cause, and failing regression test.

---

## Bug 1: Cross-Tenant Data Leakage in track_status [HIGH — Security]

**File:** `crates/edgequake-api/src/handlers/documents/query/track_status.rs` (lines 25-28, 55-60)

**Root cause:** The `get_track_status` handler does not accept or check `TenantContext`. It accepts only `State(state)` and `Path(track_id)`:

```rust
pub async fn get_track_status(
    State(state): State<AppState>,
    axum::extract::Path(track_id): axum::extract::Path<String>,
) -> ApiResult<Json<TrackStatusResponse>> {
```

It then iterates ALL metadata without tenant filtering:

```rust
for value in metadata_values {
    if let Some(obj) = value.as_object() {
        let doc_track_id = obj.get("track_id").and_then(|v| v.as_str()).unwrap_or("");
        if doc_track_id == track_id {
```

**Impact:** The `/api/v1/documents/track/{track_id}` endpoint is a cross-tenant metadata disclosure path. Any caller with a known `track_id` can read another tenant's document metadata. This directly contradicts `list_documents` which enforces strict `TenantContext` filtering on the same data.

**Regression test:** `regression_track_status_is_scoped_to_tenant_and_workspace` in `crates/edgequake-api/tests/e2e_tenant_isolation.rs`

```
test regression_track_status_is_scoped_to_tenant_and_workspace ... FAILED
assertion `left == right` failed: cross-tenant track lookups must not leak document metadata
  left: Some(1)
 right: Some(0)
```

**Related:** EQ-29 found that ALL 8 lineage handlers also lack TenantContext checks — same vulnerability class.

---

## Bug 2: False `completed` Status on File Upload with Partial Failures [HIGH — Contract/UX]

**File:** `crates/edgequake-api/src/handlers/documents/upload/file_upload.rs` (lines 232-239, 293-295, 437-440, 458-459, 524-528)

**Root cause:** The multipart file-upload path logs partial failures and ignores several storage errors, but still persists `"status": "completed"` and returns `"processed"` to the caller.

Logs partial failures but continues:
```rust
if result.stats.failed_chunks > 0 {
    tracing::warn!(
        document_id = %document_id,
        failed_chunks = result.stats.failed_chunks,
        chunk_count = result.stats.chunk_count,
        "File upload pipeline completed with partial failures"
    );
}
```

Silently ignores vector storage failures:
```rust
Err(e) => {
    tracing::error!(chunk_id = %chunk.id, error = %e, "VECTOR STORAGE: Failed to store chunk embedding");
}
```

Ignores graph storage errors:
```rust
let _ = state
    .graph_storage
    .upsert_edge(&relationship.source, &relationship.target, properties)
    .await;
```

Still marks as completed and returns "processed":
```rust
"status": "completed",
// ...
status: "processed".to_string(),
```

**Impact:** Undermines the "degraded ingestion must not masquerade as success" contract that `text_insert.rs` and `text_upload.rs` already implement correctly.

**Regression test:** `regression_file_upload_with_zero_entities_is_not_marked_completed` in `crates/edgequake-api/tests/e2e_file_upload.rs`

```
test regression_file_upload_with_zero_entities_is_not_marked_completed ... FAILED
assertion `left == right` failed: zero-entity file ingests should surface degraded status instead of completed
  left: Some("completed")
 right: Some("partial_failure")
```

---

## Bug 3: Late Cancellation Overwrites Terminal `completed` Status [HIGH — State Machine]

**File:** `crates/edgequake-api/src/processor/text_insert.rs` (lines 15-24, 942-944, 997-999)

**Root cause:** After `final_status` is persisted (completed or partial_failure), there is still a cancellation gate before lineage/checkpoint cleanup. If cancellation arrives in that window, the document has already been stored and marked `completed`/`partial_failure`, but `check_cancelled()` overwrites it to `cancelled` and returns an error.

Cancellation handler overwrites status:
```rust
if cancel_token.is_cancelled() {
    let msg = format!(
        "Task cancelled during '{}' stage for document {}",
        stage, document_id
    );
    warn!("{}", msg);
    self.update_document_status(document_id, "cancelled", Some(&msg))
        .await
        .ok();
    return Err(TaskError::Cancelled(msg));
}
```

Final status already persisted at line 942-944, but cancellation gate still runs AFTER at line 997-999:
```rust
self.check_cancelled(&cancel_token, "pre-lineage", &document_id)
    .await?;
```

**Impact:** Creates inconsistent state: stored document, failed task, wrong terminal status.

**Regression test:** `regression_late_cancellation_does_not_overwrite_completed_status` in `crates/edgequake-api/src/processor/mod.rs`

```
test processor::tests::regression_late_cancellation_does_not_overwrite_completed_status ... FAILED
assertion `left == right` failed: late cancellation must not rewrite a terminal completed status
  left: String("cancelled")
 right: "completed"
```

---

## Bug 4: `partial_failure` Drops User-Visible Error Detail [MEDIUM — Observability]

**Files:**
- `crates/edgequake-api/src/processor/text_insert.rs` (lines 926-937)
- `crates/edgequake-api/src/processor/status_updates.rs` (lines 353-358)
- `crates/edgequake-api/src/handlers/documents_types/listing.rs` (lines 127-129)

**Root cause:** `text_insert.rs` deliberately records storage-failure detail in `error_details`:

```rust
} else if has_storage_errors {
    let combined = storage_errors.join("; ");
    warn!(
        document_id = %document_id,
        storage_error_count = storage_errors.len(),
        "Storage errors during indexing -- marking as partial_failure: {}",
        combined
    );
    stats_with_lineage.error_details = Some(combined);
    "partial_failure"
```

But `update_document_status_with_stats()` in `status_updates.rs` never persists `error_details` and explicitly removes `error_message`:

```rust
updated.remove("error_message");

self.kv_storage
    .upsert(&[(metadata_key, json!(updated))])
    .await
    .map_err(|e| edgequake_tasks::TaskError::Storage(e.to_string()))?;
```

The listing DTO only exposes `error_message` (which was removed):
```rust
pub error_message: Option<String>,
```

**Impact:** `partial_failure` becomes countable but not diagnosable from the API.

**Regression test:** `regression_partial_failure_persists_user_visible_error_detail` in `crates/edgequake-api/src/processor/mod.rs`

```
test processor::tests::regression_partial_failure_persists_user_visible_error_detail ... FAILED
assertion `left == right` failed: partial_failure metadata should preserve a user-visible error message
  left: None
 right: Some("vector storage failed for 1 embedding")
```

---

## Bug 5: Partial Graph Writes Survive Failed Insert — Atomicity Gap [HIGH — Data Integrity]

**File:** `crates/edgequake-core/src/orchestrator/ingestion.rs` (lines 279-307)

**Root cause:** The graph merge happens before chunk-vector storage. If any later `vector_storage.upsert()` fails, `insert()` returns an error after graph/entity state has already been committed, with no cleanup or rollback.

```rust
let merge_stats = merger
    .merge(processing_result.extractions.clone())
    .await
    .map_err(|e| Error::internal(format!("Merge error: {}", e)))?;

// Stage 3: Store chunk embeddings with type metadata
for chunk in &processing_result.chunks {
    if let Some(embedding) = &chunk.embedding {
        let mut metadata = serde_json::json!({
            "type": "chunk",
            "document_id": doc_id,
            "index": chunk.index,
            "content": chunk.content
        });

        vector_storage
            .upsert(&[(chunk.id.clone(), embedding.clone(), metadata)])
            .await
            .map_err(|e| Error::internal(format!("Vector storage error: {}", e)))?;
    }
}
```

**Impact:** A retry will re-run against partially persisted state rather than a clean failure boundary. Orphaned graph nodes/edges accumulate.

**Note:** This test is gated by `#![cfg(feature = "pipeline")]`.

**Also noted:** `ingestion.rs` documents `BR0001` ("Document ID must be unique") but no explicit duplicate-ID check was found — possible doc/code divergence.

**Regression test:** `regression_insert_does_not_leave_graph_data_after_late_vector_failure` in `crates/edgequake-core/tests/regression_ingestion_atomicity.rs`

Test showed 5 graph nodes left behind after a failed insert.

---

## Combined Regression Test Command

```bash
( cargo test --manifest-path edgequake/Cargo.toml -q -p edgequake-api regression_ --lib; \
  cargo test --manifest-path edgequake/Cargo.toml -q -p edgequake-api --test e2e_tenant_isolation regression_; \
  cargo test --manifest-path edgequake/Cargo.toml -q -p edgequake-api --test e2e_file_upload regression_; \
  cargo test --manifest-path edgequake/Cargo.toml -q -p edgequake-core --features pipeline --test regression_ingestion_atomicity ) > test-output.txt 2>&1
```

## Additional Known Issues (from defect mining, less detail available)

- **EQ-29:** All 8 lineage handlers missing TenantContext checks — cross-workspace data disclosure (Critical)
- **EQ-30:** JWT type confusion vulnerability (details incomplete)
- Total defect library: 35 items (EQ-1 through EQ-35) from 164 commits
